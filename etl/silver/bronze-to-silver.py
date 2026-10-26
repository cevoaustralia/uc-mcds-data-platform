"""
Glue job: bronze-to-silver (SOW D2 / D3 / D4)

Transforms the latest Bronze Callista extract into MCDS-aligned Silver tables
(student, unit_of_learning, organisation, location, learning_period, student_unit_load),
registers them in the Glue Data Catalog with MCDS lineage column comments, runs Silver DQ
rules, writes the DQ results, and exports MCDS JSON payloads (students-*.json) for
conformance validation.

Arguments: --BRONZE_DATABASE --SILVER_BUCKET --SILVER_DATABASE [--CONFIG_PREFIX s3://...]
"""

import datetime as dt
import sys

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext

import data_quality as DQ
import glue_io as G
import pipeline as P
from schemas import TABLES

args = G.job_args(["BRONZE_DATABASE", "SILVER_BUCKET", "SILVER_DATABASE"], {"CONFIG_PREFIX": ""})
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job = Job(glue)
job.init(args["JOB_NAME"], args)

cfg = G.load_configs(args, {"rules": "business-rules.yaml", "map": "silver-mappings.yaml",
                            "dq": "data-quality-rules.yaml"})
rules, mappings = cfg["rules"], cfg["map"]

bronze = {t: P.latest_extract(spark.table(f"{args['BRONZE_DATABASE']}.{t.lower()}")) for t in TABLES}
extract_date = bronze["GOVT_STUDENT_LOAD"].select("_extract_date").first()[0]
silver = P.build_silver(bronze, rules, mappings)

written = {}
for name in P.SILVER_ENTITIES:
    ent = mappings["entities"][name]
    n = G.write_catalog_table(
        spark, silver[name], args["SILVER_DATABASE"], name, f"s3://{args['SILVER_BUCKET']}/mcds/{name}/",
        description=f"Silver (MCDS v{mappings['mcds_version']}): {ent['description']}",
        properties={"layer": "silver", "source_system": "callista", "source_table": ent["source"],
                    "mcds_entity": name, "mcds_version": mappings["mcds_version"],
                    "primary_key": ",".join(ent["primary_key"]), "extract_date": extract_date,
                    "contains_pii": str(bool(ent.get("pii"))).lower(),
                    "classification": "confidential" if ent.get("pii") else "internal"},
        column_comments=G.lineage_comments(ent, rules))
    written[name] = spark.table(f"{args['SILVER_DATABASE']}.{name}")
    print(f"silver.{name}: {n} rows")

written["_gsl_selected"] = silver["_gsl_selected"]
P.register_bronze_views(bronze, written)
P.register_views({k: v for k, v in written.items() if not k.startswith("_")}, "silver")
results = DQ.run_rules(spark, cfg["dq"], rules, {"bronze", "silver"})
summary = DQ.print_results(results, "SILVER DATA QUALITY")
DQ.results_dataframe(spark, results).write.mode("append").json(
    f"s3://{args['SILVER_BUCKET']}/_dq_results/run_date={dt.date.today().isoformat()}/")

# MCDS JSON export (validated by the mcds-validate job / scripts/validate-mcds-json.py)
rows = {k: written[k].collect() for k in P.SILVER_ENTITIES}
s3 = boto3.client("s3")
for i, doc in enumerate(P.mcds_documents(rows, rules), 1):
    s3.put_object(Bucket=args["SILVER_BUCKET"], Key=f"mcds_json/{extract_date}/students-{i:04d}.json",
                  Body=P.to_json(doc).encode("utf-8"), ContentType="application/json")

job.commit()
if not summary["ok"]:
    sys.exit(1)
