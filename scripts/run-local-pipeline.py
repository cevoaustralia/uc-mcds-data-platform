#!/usr/bin/env python3
"""
Run the full UC MCDS pipeline locally on Spark (no AWS needed):

  Callista CSV (landing) -> Bronze Parquet -> Silver MCDS Parquet -> Gold reports
  + data quality rules at every layer
  + MCDS JSON export validated against studentlifecycle.schema.json
  + MCDS Reporting Framework Report Definitions / Fact Data validated (structure + semantics)
  + CSV exports of every Gold report

Uses the same etl/common/pipeline.py functions as the AWS Glue jobs.

Usage:
  python scripts/generate-mock-data.py
  python scripts/run-local-pipeline.py [--landing data/mock/landing] [--extract-date 2026-10-25]
         [--work .local-lake] [--mcds "MCDS - v2.1.1/v2.1.1"]

Requires: pyspark (Java 17+), pyyaml, jsonschema, referencing.
Exit code 0 only if every fail-severity DQ rule and every MCDS validation passes.
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl" / "common"))

import pipeline as P              # noqa: E402
import data_quality as DQ         # noqa: E402
from schemas import TABLES        # noqa: E402


def spark_session():
    from pyspark.sql import SparkSession
    return (SparkSession.builder.master("local[2]").appName("uc-mcds-local")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.sql.session.timeZone", "UTC")
            .getOrCreate())


def write_csv(rows, path):
    rows = [r.asDict() for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if not rows:
            return
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--landing", default=str(ROOT / "data" / "mock" / "landing"))
    ap.add_argument("--extract-date", default=None, help="default: latest folder in landing/callista")
    ap.add_argument("--work", default=str(ROOT / ".local-lake"))
    ap.add_argument("--config", default=str(ROOT / "config"))
    ap.add_argument("--mcds", default=str(ROOT / "MCDS - v2.1.1" / "v2.1.1"))
    a = ap.parse_args()

    cfg = Path(a.config)
    rules = P.load_yaml(cfg / "business-rules.yaml")
    mappings = P.load_yaml(cfg / "silver-mappings.yaml")
    gold_cfg = P.load_yaml(cfg / "gold-aggregations.yaml")
    dq_cfg = P.load_yaml(cfg / "data-quality-rules.yaml")

    landing = Path(a.landing)
    dates = sorted(p.name for p in (landing / "callista").iterdir() if p.is_dir())
    extract_date = a.extract_date or dates[-1]
    work = Path(a.work)
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    report = {"extract_date": extract_date, "stages": {}, "dq": [], "mcds_validation": {}}

    spark = spark_session()
    spark.sparkContext.setLogLevel("ERROR")

    # ---------------- landing -> bronze
    print(f"\n== Landing -> Bronze (extract {extract_date})")
    bronze = {}
    for table in TABLES:
        src = landing / rules["source"]["extract_path_pattern"].format(extract_date=extract_date, table=table)
        df = P.read_landing_table(spark, str(src), table, rules["source"]["csv_options"], extract_date)
        n_in = df.count()
        out = work / "bronze" / "callista" / table.lower()
        df.write.mode("overwrite").partitionBy("_extract_date").parquet(str(out))
        bronze[table] = P.latest_extract(spark.read.parquet(str(out)))
        n_out = bronze[table].count()
        report["stages"].setdefault("bronze", {})[table] = {"landing_rows": n_in, "bronze_rows": n_out}
        print(f"  {table:22s} landing {n_in:6d} -> bronze {n_out:6d}")

    # ---------------- bronze -> silver
    print("\n== Bronze -> Silver (MCDS)")
    silver = P.build_silver(bronze, rules, mappings)
    silver_tables = {}
    for name in P.SILVER_ENTITIES:
        out = work / "silver" / "mcds" / name
        silver[name].write.mode("overwrite").parquet(str(out))
        silver_tables[name] = spark.read.parquet(str(out))
        n = silver_tables[name].count()
        report["stages"].setdefault("silver", {})[name] = n
        print(f"  {name:22s} {n:6d} rows")
    sel = silver["_gsl_selected"].count()
    report["stages"]["silver"]["_gsl_after_submission_selection"] = sel
    print(f"  (GOVT_STUDENT_LOAD rows after submission selection: {sel})")
    silver_tables["_gsl_selected"] = silver["_gsl_selected"]

    P.register_bronze_views(bronze, silver_tables)
    P.register_views({k: v for k, v in silver_tables.items() if not k.startswith("_")}, "silver")
    dq = DQ.run_rules(spark, dq_cfg, rules, {"bronze", "silver"})

    # ---------------- silver -> gold
    print("\n== Silver -> Gold (student load)")
    gold = P.build_gold(spark, {k: v for k, v in silver_tables.items() if not k.startswith("_")}, gold_cfg, rules)
    gold_rows = {}
    for name, df in gold.items():
        out = work / "gold" / "analytics" / name
        df.write.mode("overwrite").parquet(str(out))
        g = spark.read.parquet(str(out))
        g.createOrReplaceTempView(f"gold_{name}")
        gold_rows[name] = g.orderBy(*gold_cfg["reports"][name]["dimensions"].keys()).collect()
        write_csv(gold_rows[name], work / "exports" / f"{name}.csv")
        report["stages"].setdefault("gold", {})[name] = len(gold_rows[name])
        print(f"  {name:36s} {len(gold_rows[name]):5d} rows")
    dq += DQ.run_rules(spark, dq_cfg, rules, {"gold"})
    dq_summary = DQ.print_results(dq)
    report["dq"] = dq

    # ---------------- MCDS exports
    print("\n== MCDS exports")
    silver_rows = {k: silver_tables[k].collect() for k in P.SILVER_ENTITIES}
    docs = P.mcds_documents(silver_rows, rules)
    json_dir = work / "silver" / "mcds_json"
    json_dir.mkdir(parents=True, exist_ok=True)
    doc_files = []
    for i, d in enumerate(docs, 1):
        name = f"students-{extract_date}-{i:04d}.json"
        (json_dir / name).write_text(P.to_json(d), encoding="utf-8")
        doc_files.append((name, json.loads(P.to_json(d))))
    print(f"  MCDS student payloads: {len(doc_files)} file(s), "
          f"{sum(len(d['students']) for _, d in doc_files)} students")

    defs, facts = P.mcds_reporting_artefacts(gold_rows, gold_cfg, rules, as_of_date=extract_date)
    rep_dir = work / "gold" / "mcds_reporting"
    for sub, items in (("reportdefinitions", defs), ("factdata", facts)):
        (rep_dir / sub).mkdir(parents=True, exist_ok=True)
        for name, obj in items:
            (rep_dir / sub / name).write_text(P.to_json(obj), encoding="utf-8")
    print(f"  MCDS reporting: {len(defs)} report definitions, {len(facts)} fact data files")

    # ---------------- MCDS validation
    ok_mcds = True
    mcds_root = Path(a.mcds)
    if (mcds_root / "schemas").exists():
        import mcds_validation as V
        problems = V.verify_checksums(str(mcds_root))
        report["mcds_validation"]["checksums"] = problems or "all schema files match package manifest"
        res_students = V.validate_student_documents(str(mcds_root), doc_files)
        res_reporting = V.validate_reporting(
            str(mcds_root), [(n, json.loads(P.to_json(o))) for n, o in defs],
            [(n, json.loads(P.to_json(o))) for n, o in facts])
        report["mcds_validation"]["student_payloads"] = res_students
        report["mcds_validation"]["reporting"] = res_reporting
        ok_mcds = not problems and all(r["valid"] for r in res_students + res_reporting)
        print(f"  schema checksums: {'OK' if not problems else problems}")
        for r in res_students + res_reporting:
            print(f"  [{'PASS' if r['valid'] else 'FAIL'}] {r['name']}")
            for e in r["errors"][:5]:
                print(f"      {e['path']}: {e['message']}")
    else:
        report["mcds_validation"] = f"skipped: MCDS package not found at {mcds_root}"
        print(f"  MCDS validation skipped (package not found at {mcds_root})")
        ok_mcds = False

    report["ok"] = dq_summary["ok"] and ok_mcds
    (work / "run-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nRun report: {work / 'run-report.json'}")
    print("RESULT:", "PASS" if report["ok"] else "FAIL")
    spark.stop()
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
