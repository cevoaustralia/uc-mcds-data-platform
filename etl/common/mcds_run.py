"""
Stage runners shared by the Glue jobs and the local runner. Each runner executes one stage,
records DQ results and row counts in the ops layer (for QuickSight pipeline monitoring and the
Bedrock DQ advisor) and returns False when a 'fail' rule failed.
"""

import datetime as dt
import json
import os

from pyspark.sql import Row

import mcds_dq as DQ
import mcds_engine as E


def _ops_write(spark, store, table, rows, extract_date, stage):
    if not rows:
        return
    recs = []
    for r in rows:
        rec = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in r.items()}
        rec.update({"extract_date": extract_date, "stage": stage})
        recs.append(Row(**rec))
    df = spark.createDataFrame(recs)
    store.write(df, "ops", table, description=f"Ops: {table}", properties={"layer": "ops"},
                partition_by=["extract_date", "stage"])


def _record(spark, store, extract_date, stage, counts, results, started, extra=None):
    s = DQ.summarise(results)
    run = {"run_id": f"{extract_date}:{stage}:{started.isoformat()}",
           "started_at": started.isoformat(),
           "finished_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "status": "SUCCEEDED" if s["ok"] else "FAILED_DQ",
           "rules_total": s["total"], "rules_passed": s["passed"], "rules_failed": s["failed"],
           "rules_warned": s["warnings"], "details": json.dumps(extra or {})}
    _ops_write(spark, store, "dq_results", results, extract_date, stage)
    _ops_write(spark, store, "table_counts",
               [{"table_name": t, "row_count": int(n)} for t, n in counts.items()], extract_date, stage)
    _ops_write(spark, store, "pipeline_runs", [run], extract_date, stage)
    DQ.print_results(results, f"{stage.upper()} DATA QUALITY ({extract_date})")
    return s["ok"]


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def run_bronze(spark, cfg, store, landing_root, extract_date):
    started = _now()
    counts, results = E.bronze_stage(spark, cfg, store, landing_root, extract_date)
    return _record(spark, store, extract_date, "bronze", counts, results, started)


def run_silver(spark, cfg, store, extract_date, mcds_root):
    import mcds_json as MJ
    started = _now()
    E.register_bronze_views(spark, cfg, store, extract_date)
    counts, results = E.silver_stage(spark, cfg, store, extract_date)
    if not os.path.exists(mcds_root):
        # e.g. CI without the licensed schemas: report, do not silently pass
        results.append(DQ._result("silver_mcds_schemas_available", "silver", "warn",
                                  f"MCDS schemas not found at {mcds_root}: conformance NOT validated", 1))
        return _record(spark, store, extract_date, "silver", counts, results, started)
    problems = MJ.SchemaSet(mcds_root).checksum_problems()
    results.append(DQ._result("silver_mcds_schema_checksums", "silver", "warn",
                              "MCDS schemas match the published package (manifest checksums / bundle provenance)"
                              + (f": {'; '.join(problems)}" if problems else ""), len(problems)))
    summary, mres = MJ.validate_entities(spark, cfg, mcds_root, cfg.settings["mcds"].get("validation_sample", 0))
    results += mres
    _ops_write(spark, store, "mcds_validation", summary, extract_date, "silver")
    return _record(spark, store, extract_date, "silver", counts, results, started)


def run_gold(spark, cfg, store, extract_date, mcds_root, reporting_out):
    """reporting_out: local folder or s3:// prefix for MCDS Reporting Framework JSON files."""
    import mcds_reporting as MR
    started = _now()
    E.register_silver_views(spark, cfg, store)
    counts, results = E.gold_stage(spark, cfg, store, extract_date)
    gold_rows = {n: [r.asDict() for r in spark.table(f"gold__{n}").collect()]
                 for n, r in cfg.reports.items() if r.get("mcds_report")}
    periods = {(r["academic_year"], r["calendar_type"]): (r["start_date"], r["end_date"])
               for r in spark.sql("SELECT academic_year, calendar_type, min(start_date) start_date, max(end_date) end_date "
                                  "FROM silver__learning_period GROUP BY academic_year, calendar_type").collect()}
    defs, facts = MR.build_artefacts(cfg, gold_rows, periods, extract_date)
    if os.path.exists(mcds_root):
        checks = MR.validate_artefacts(mcds_root, defs, facts)
        bad = [c for c in checks if c["errors"]]
        results.append(DQ._result("gold_mcds_reporting_conformance", "gold", "fail",
                                  f"MCDS Reporting Framework files valid ({len(defs)} definitions, {len(facts)} factData)"
                                  + (f"; first: {bad[0]['name']} {bad[0]['errors'][0]}" if bad else ""), len(bad)))
    else:
        # e.g. CI without the licensed schemas: same treatment as Silver - reported as NOT validated, not passed
        results.append(DQ._result("gold_mcds_schemas_available", "gold", "warn",
                                  f"MCDS schemas not found at {mcds_root}: Reporting Framework files NOT validated", 1))
    _write_json_files(reporting_out, defs + facts)
    return _record(spark, store, extract_date, "gold", counts, results, started,
                   {"mcds_reporting_files": len(defs) + len(facts)})


def _write_json_files(out, files):
    body = {name: json.dumps(doc, indent=2, ensure_ascii=False, default=str) for name, doc in files}
    if out.startswith("s3://"):
        import boto3
        bucket, _, prefix = out[5:].partition("/")
        s3 = boto3.client("s3")
        for name, text in body.items():
            s3.put_object(Bucket=bucket, Key=f"{prefix.rstrip('/')}/{name}", Body=text.encode("utf-8"),
                          ContentType="application/json")
    else:
        os.makedirs(out, exist_ok=True)
        for name, text in body.items():
            with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
                fh.write(text)
