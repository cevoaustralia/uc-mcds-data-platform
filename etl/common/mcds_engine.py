"""
Generic, config-driven engine: landing CSV -> Bronze -> Silver (MCDS) -> Gold.

Nothing here knows about Callista tables, MCDS entities or reports: every table, column, rule,
crosswalk, entity and report comes from PipelineConfig (pipeline/*.yaml). The Glue jobs and the
local runner call the three stage functions below with a store (LocalStore or GlueStore).
"""

import datetime as dt

from pyspark.sql import functions as F
from pyspark.sql import types as T

from mcds_config import layer_sql
import mcds_dq as DQ

AUDIT_COLUMNS = ["extract_date", "_source_file", "_ingestion_ts"]


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


# ================================================================================================
# Bronze
# ================================================================================================
def _typed_column(raw, name, spec, date_format, past_century, extract_date):
    """Cast one raw string column to its configured type. Returns (typed column, parse-failure flag)."""
    t = spec["type"]
    src = F.trim(F.col(f"`{raw}`"))
    src = F.when(src == "", None).otherwise(src)
    if t == "string":
        typed = src
    elif t == "date":
        typed = F.to_date(src, date_format)
        if past_century:
            limit = F.add_months(F.lit(extract_date).cast("date"), 12)
            typed = F.when(typed > limit, F.add_months(typed, -1200)).otherwise(typed)
    elif t == "timestamp":
        typed = F.to_timestamp(src)
    else:
        typed = src.cast(t)
    failed = src.isNotNull() & typed.isNull()
    return typed.alias(name), failed


def bronze_stage(spark, cfg, store, landing_root, extract_date):
    """Read every configured source file for `extract_date`, type it, add audit columns and write
    one Bronze partition per table. Returns (row counts, DQ results)."""
    from mcds_config import join_path
    csv_opts = {k: str(v).lower() if isinstance(v, bool) else str(v)
                for k, v in cfg.settings["landing"]["csv"].items()}
    pattern = cfg.settings["landing"]["path_pattern"]
    counts, results, absent = {}, [], {}
    ingestion_ts = _now()
    for table, src in cfg.sources.items():
        rel = pattern.format(extract_date=extract_date, file=src["file"])
        path = join_path(landing_root, rel)
        raw = spark.read.options(**csv_opts).csv(path)          # all columns as strings
        raw_cols = set(raw.columns)
        conf_cols = list(src["columns"])
        missing = [c for c in conf_cols if c not in raw_cols]
        unexpected = sorted(raw_cols - set(conf_cols))
        cols, fails = [], []
        for c in conf_cols:
            spec = src["columns"][c]
            if c in raw_cols:
                typed, failed = _typed_column(c, c, spec, src.get("date_format", "dd/MMM/yy"),
                                              c in (src.get("past_century_columns") or []), extract_date)
                cols.append(typed)
                fails.append(F.sum(F.when(failed, 1).otherwise(0)).alias(c))
            else:
                cols.append(F.lit(None).cast(spec["type"] if spec["type"] != "date" else "date").alias(c))
        df = raw.select(*cols,
                        F.lit(extract_date).alias("extract_date"),
                        F.lit(rel).alias("_source_file"),
                        F.lit(ingestion_ts.isoformat()).alias("_ingestion_ts"))
        n_raw = raw.count()
        parse_fail = raw.select(*fails).collect()[0].asDict() if fails else {}
        parse_fail = {k: int(v or 0) for k, v in parse_fail.items() if v}
        comments = {c: f"{src['system']}.{table.upper()}.{c} ({src['columns'][c]['type']})" for c in conf_cols}
        store.write(df, "bronze", table,
                    description=f"Bronze: {src['description']} - as extracted, typed, one partition per extract",
                    properties={"layer": "bronze", "source_system": src["system"],
                                "source_table": table.upper(), "primary_key": ",".join(src["primary_key"]),
                                "classification": src.get("classification", "internal")},
                    column_comments=comments, partition_by=["extract_date"])
        counts[table] = n_raw
        absent[table] = missing
        results += DQ.bronze_file_checks(table, n_raw, missing, unexpected, parse_fail)
    register_bronze_views(spark, cfg, store, extract_date)
    results += DQ.run_generated_bronze(spark, cfg, absent)
    results += DQ.run_custom(spark, cfg, "bronze")
    return counts, results


def register_bronze_views(spark, cfg, store, extract_date):
    for table in cfg.sources:
        df = store.read("bronze", table).where(F.col("extract_date") == extract_date)
        df.createOrReplaceTempView(f"bronze__{table}")


# ================================================================================================
# Crosswalks
# ================================================================================================
def register_crosswalks(spark, cfg):
    for name, xw in cfg.crosswalks.items():
        cols = list(xw.get("columns", []))
        schema = T.StructType([T.StructField("source_code", T.StringType())] +
                              [T.StructField(c, T.StringType()) for c in cols])
        rows = [[str(code)] + [None if (vals or {}).get(c) is None else str(vals[c]) for c in cols]
                for code, vals in (xw.get("rows") or {}).items()]
        spark.createDataFrame(rows, schema).createOrReplaceTempView(f"xw_{name}")


# ================================================================================================
# Silver
# ================================================================================================
def entity_sql(cfg, name):
    e = cfg.entities[name]
    derived = {k: f"({cfg.resolve(v)})" for k, v in (e.get("derived") or {}).items()}
    extra = {"d": derived}
    select = ",\n  ".join(f"{cfg.resolve(spec['expr'], extra)} AS `{col}`" for col, spec in e["columns"].items())
    sql = f"SELECT\n  {select}\nFROM {cfg.resolve(e['from'], extra)}"
    for j in e.get("joins") or []:
        sql += f"\n{cfg.resolve(j, extra)}"
    if e.get("where"):
        sql += f"\nWHERE {cfg.resolve(e['where'], extra)}"
    return layer_sql(sql)


def lineage_comments(e):
    out = {}
    for col, spec in e["columns"].items():
        target = f" -> MCDS {spec['mcds']}" if spec.get("mcds") else ""
        pii = " [PII]" if spec.get("pii") else ""
        out[col] = f"{spec.get('source', spec['expr'])}{target}{pii}"
    return out


def silver_stage(spark, cfg, store, extract_date):
    """Build every configured MCDS entity in dependency order. Returns (row counts, DQ results)."""
    register_crosswalks(spark, cfg)
    counts = {}
    for name in cfg.entity_order():
        e = cfg.entities[name]
        df = spark.sql(entity_sql(cfg, name)).withColumn("extract_date", F.lit(extract_date))
        mcds = e.get("mcds") or {}
        pii_cols = [c for c, s in e["columns"].items() if s.get("pii")]
        written = store.write(
            df, "silver", name, description=f"Silver (MCDS {cfg.settings['mcds']['version']}): {e['description']}",
            properties={"layer": "silver", "mcds_schema": mcds.get("schema", ""),
                        "mcds_definition": mcds.get("definition", ""),
                        "primary_key": ",".join(e["primary_key"]),
                        "classification": e.get("classification", "internal"),
                        "contains_pii": str(bool(pii_cols)).lower(), "pii_columns": ",".join(pii_cols),
                        "extract_date": extract_date},
            column_comments=lineage_comments(e))
        written.createOrReplaceTempView(f"silver__{name}")
        counts[name] = written.count()
    results = DQ.run_generated_silver(spark, cfg)
    results += DQ.run_custom(spark, cfg, "silver")
    return counts, results


def register_silver_views(spark, cfg, store):
    register_crosswalks(spark, cfg)
    for name in cfg.entities:
        store.read("silver", name).createOrReplaceTempView(f"silver__{name}")


# ================================================================================================
# Gold
# ================================================================================================
def report_sql(cfg, name):
    r = cfg.reports[name]
    if r.get("type") == "detail":
        select = ",\n  ".join(f"{cfg.resolve(x)} AS `{c}`" for c, x in r["columns"].items())
        group = ""
    else:
        dims = [(c, cfg.resolve(x)) for c, x in r["dimensions"].items()]
        aggs = list((r.get("attributes") or {}).items()) + list(r["measures"].items())
        select = ",\n  ".join([f"{x} AS `{c}`" for c, x in dims] + [f"{cfg.resolve(x)} AS `{c}`" for c, x in aggs])
        group = "\nGROUP BY " + ", ".join(x for _, x in dims)
    sql = f"SELECT\n  {select}\nFROM {cfg.resolve(r['from'])}"
    for j in r.get("joins") or []:
        sql += f"\n{cfg.resolve(j)}"
    if r.get("where"):
        sql += f"\nWHERE {cfg.resolve(r['where'])}"
    return layer_sql(sql + group)


def gold_stage(spark, cfg, store, extract_date):
    counts = {}
    for name in cfg.report_order():
        r = cfg.reports[name]
        df = spark.sql(report_sql(cfg, name)).withColumn("extract_date", F.lit(extract_date))
        comments = {c: f"{'dimension' if c in (r.get('dimensions') or {}) else 'measure' if c in (r.get('measures') or {}) else 'column'}: "
                       f"{(r.get('columns') or r.get('dimensions') or {}).get(c) or (r.get('measures') or {}).get(c) or (r.get('attributes') or {}).get(c, '')}"
                    for c in df.columns if c != "extract_date"}
        written = store.write(df, "gold", name, description=f"Gold (use case {r.get('use_case', '-')}): {r['description']}",
                              properties={"layer": "gold", "use_case": str(r.get("use_case", "")),
                                          "report_type": r.get("type", "aggregate"), "extract_date": extract_date,
                                          "classification": "internal"},
                              column_comments=comments)
        written.createOrReplaceTempView(f"gold__{name}")
        counts[name] = written.count()
    results = DQ.run_custom(spark, cfg, "gold")
    return counts, results
