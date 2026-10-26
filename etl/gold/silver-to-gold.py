"""
Glue job: silver-to-gold (SOW D5)

Builds the Gold student-load reports defined in config/gold-aggregations.yaml from the Silver
MCDS tables, registers them in the Glue Data Catalog, runs Gold reconciliation DQ rules and
publishes the MCDS Reporting Framework artefacts (Report Definitions + Fact Data per period).

Arguments: --SILVER_DATABASE --GOLD_BUCKET --GOLD_DATABASE [--CONFIG_PREFIX s3://...]
"""

import sys

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext

import data_quality as DQ
import glue_io as G
import pipeline as P

args = G.job_args(["SILVER_DATABASE", "GOLD_BUCKET", "GOLD_DATABASE"], {"CONFIG_PREFIX": ""})
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job = Job(glue)
job.init(args["JOB_NAME"], args)

cfg = G.load_configs(args, {"rules": "business-rules.yaml", "gold": "gold-aggregations.yaml",
                            "dq": "data-quality-rules.yaml"})
rules, gold_cfg = cfg["rules"], cfg["gold"]

silver = {name: spark.table(f"{args['SILVER_DATABASE']}.{name}") for name in P.SILVER_ENTITIES}
extract_date = spark.sql(f"SHOW TBLPROPERTIES {args['SILVER_DATABASE']}.student_unit_load('extract_date')").first()[1]
gold = P.build_gold(spark, silver, gold_cfg, rules)

gold_rows = {}
for name, df in gold.items():
    rep = gold_cfg["reports"][name]
    comments = {c: f"Dimension: {e}" for c, e in rep["dimensions"].items()}
    comments.update({c: f"Attribute: {e}" for c, e in rep.get("attributes", {}).items()})
    comments.update({c: f"Measure: {e} FROM silver_mcds.student_unit_load" for c, e in rep["measures"].items()})
    comments.update({c: f"Derived: {e}" for c, e in (rep.get("derived") or {}).items()})
    n = G.write_catalog_table(
        spark, df, args["GOLD_DATABASE"], name, f"s3://{args['GOLD_BUCKET']}/analytics/{name}/",
        description=f"Gold (SOW D5): {rep['description']}",
        properties={"layer": "gold", "source": "silver student_unit_load + dimensions",
                    "filter": P.resolve_tokens(gold_cfg["common_filter"], rules),
                    "extract_date": extract_date, "contains_pii": "false", "classification": "internal"},
        column_comments=comments)
    tbl = spark.table(f"{args['GOLD_DATABASE']}.{name}")
    tbl.createOrReplaceTempView(f"gold_{name}")
    gold_rows[name] = tbl.collect()
    print(f"gold.{name}: {n} rows")

P.register_views(silver, "silver")
results = DQ.run_rules(spark, cfg["dq"], rules, {"gold"})
summary = DQ.print_results(results, "GOLD DATA QUALITY")

definitions, factdata = P.mcds_reporting_artefacts(gold_rows, gold_cfg, rules, as_of_date=extract_date)
s3 = boto3.client("s3")
for folder, items in (("reportdefinitions", definitions), ("factdata", factdata)):
    for fname, obj in items:
        s3.put_object(Bucket=args["GOLD_BUCKET"], Key=f"mcds_reporting/{extract_date}/{folder}/{fname}",
                      Body=P.to_json(obj).encode("utf-8"), ContentType="application/json")

job.commit()
if not summary["ok"]:
    sys.exit(1)
