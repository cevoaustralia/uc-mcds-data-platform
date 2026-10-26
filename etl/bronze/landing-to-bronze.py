"""
Glue job: landing-to-bronze (SOW D3)

Reads one Callista CSV extract (s3://<landing>/callista/<EXTRACT_DATE>/<TABLE>.csv) with an
explicit schema, adds audit columns and appends it to Bronze as Parquet partitioned by
_extract_date. Registers bronze tables in the Glue Data Catalog and runs Bronze DQ rules.

Arguments: --LANDING_BUCKET --BRONZE_BUCKET --BRONZE_DATABASE [--EXTRACT_DATE YYYY-MM-DD]
           [--CONFIG_PREFIX s3://...]
Common modules (schemas, pipeline, data_quality, glue_io) arrive via --extra-py-files.
"""

import sys

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext

import data_quality as DQ
import glue_io as G
import pipeline as P
from schemas import TABLES, key_columns

args = G.job_args(["LANDING_BUCKET", "BRONZE_BUCKET", "BRONZE_DATABASE"],
                  {"EXTRACT_DATE": "", "CONFIG_PREFIX": ""})
sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
job = Job(glue)
job.init(args["JOB_NAME"], args)

cfg = G.load_configs(args, {"rules": "business-rules.yaml", "dq": "data-quality-rules.yaml"})
rules = cfg["rules"]


def latest_extract_date(bucket):
    """Most recent callista/YYYY-MM-DD/ prefix in the landing bucket."""
    s3 = boto3.client("s3")
    prefixes = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="callista/", Delimiter="/"):
        prefixes += [p["Prefix"].split("/")[1] for p in page.get("CommonPrefixes", [])]
    if not prefixes:
        raise RuntimeError(f"No extracts under s3://{bucket}/callista/")
    return sorted(prefixes)[-1]


extract_date = args["EXTRACT_DATE"] or latest_extract_date(args["LANDING_BUCKET"])
print(f"Extract date: {extract_date}")

bronze = {}
for table in TABLES:
    rel = rules["source"]["extract_path_pattern"].format(extract_date=extract_date, table=table)
    src = f"s3://{args['LANDING_BUCKET']}/{rel}"
    df = P.read_landing_table(spark, src, table, rules["source"]["csv_options"], extract_date)
    n_in = df.count()
    n_out = G.write_catalog_table(
        spark, df, args["BRONZE_DATABASE"], table.lower(),
        f"s3://{args['BRONZE_BUCKET']}/callista/{table.lower()}/",
        description=f"Bronze: Callista SIS_OWNER.{table} as extracted (CSV -> Parquet), append-only by _extract_date",
        properties={"source_system": "callista", "source_table": f"SIS_OWNER.{table}", "layer": "bronze",
                    "natural_key": ",".join(key_columns(table)), "load_frequency": "per extract",
                    "classification": "confidential" if table == "PERSON" else "internal",
                    "contains_pii": "true" if table == "PERSON" else "false"},
        partition_by=["_extract_date"], mode="overwrite")
    print(f"{table}: landing {n_in} rows -> bronze table now {n_out} rows (all extracts)")
    bronze[table] = P.latest_extract(spark.table(f"{args['BRONZE_DATABASE']}.{table.lower()}"))
    if bronze[table].count() != n_in:
        raise RuntimeError(f"{table}: bronze latest extract row count != landing row count")

P.register_bronze_views(bronze)
results = DQ.run_rules(spark, cfg["dq"], rules, {"bronze"})
summary = DQ.print_results(results, "BRONZE DATA QUALITY")
job.commit()
if not summary["ok"]:
    sys.exit(1)
