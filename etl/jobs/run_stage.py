"""
Glue job entry point (one script, three MDAA jobs: --STAGE bronze | silver | gold).

All behaviour comes from the pipeline config synced to S3 (--CONFIG_URI) and the compiled MCDS schema
bundle (--MCDS_SCHEMA_URI). Buckets come from MDAA SSM parameters via job default arguments, so the
same script runs unchanged in any account.

Arguments
  --STAGE             bronze | silver | gold
  --EXTRACT_DATE      YYYY-MM-DD (optional; default = latest extract_date= folder in the landing bucket)
  --ARTIFACTS_BUCKET  holds pipeline/ (config) and mcds/<bundle>.json (synced by GitHub Actions)
  --CONFIG_URI        optional override, default s3://<artifacts>/pipeline/
  --MCDS_SCHEMA_URI   optional override, default s3://<artifacts>/mcds/mcds-v2.1.1-uc-bundle.json
  --LANDING_BUCKET --BRONZE_BUCKET --SILVER_BUCKET --GOLD_BUCKET
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

from mcds_config import PipelineConfig
from mcds_store import GlueStore
import mcds_json as MJ
import mcds_run as RUN

REQUIRED = ["JOB_NAME", "STAGE", "ARTIFACTS_BUCKET", "LANDING_BUCKET", "BRONZE_BUCKET", "SILVER_BUCKET", "GOLD_BUCKET"]
OPTIONAL = [o for o in ("EXTRACT_DATE", "CONFIG_URI", "MCDS_SCHEMA_URI") if f"--{o}" in sys.argv]
args = getResolvedOptions(sys.argv, REQUIRED + OPTIONAL)
args.setdefault("CONFIG_URI", f"s3://{args['ARTIFACTS_BUCKET']}/pipeline/")
args.setdefault("MCDS_SCHEMA_URI", f"s3://{args['ARTIFACTS_BUCKET']}/mcds/mcds-v2.1.1-uc-bundle.json")

sc = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
spark.conf.set("spark.sql.session.timeZone", "UTC")
job = Job(glue)
job.init(args["JOB_NAME"], args)

cfg = PipelineConfig(args["CONFIG_URI"])
layers = cfg.settings["layers"]
bucket = {"bronze": args["BRONZE_BUCKET"], "silver": args["SILVER_BUCKET"],
          "gold": args["GOLD_BUCKET"], "ops": args["GOLD_BUCKET"]}
store = GlueStore(spark, {k: {"database": v["database"], "prefix": v["prefix"], "bucket": bucket[k]}
                          for k, v in layers.items()})


def latest_extract_date():
    import boto3
    prefix = cfg.settings["landing"]["path_pattern"].split("{extract_date}")[0]   # e.g. callista/extract_date=
    s3 = boto3.client("s3")
    dates = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=args["LANDING_BUCKET"], Prefix=prefix, Delimiter="/"):
        dates += [p["Prefix"][len(prefix):].strip("/") for p in page.get("CommonPrefixes", [])]
    if not dates:
        raise RuntimeError(f"no extracts under s3://{args['LANDING_BUCKET']}/{prefix}")
    return sorted(dates)[-1]


extract_date = (args.get("EXTRACT_DATE") or "").strip() or latest_extract_date()
stage = args["STAGE"]
print(f"stage={stage} extract_date={extract_date} config={args['CONFIG_URI']}")

if stage == "bronze":
    ok = RUN.run_bronze(spark, cfg, store, f"s3://{args['LANDING_BUCKET']}", extract_date)
elif stage == "silver":
    ok = RUN.run_silver(spark, cfg, store, extract_date, MJ.fetch_schema_root(args["MCDS_SCHEMA_URI"]))
elif stage == "gold":
    ok = RUN.run_gold(spark, cfg, store, extract_date, MJ.fetch_schema_root(args["MCDS_SCHEMA_URI"]),
                      f"s3://{args['GOLD_BUCKET']}/mcds-reporting/extract_date={extract_date}")
else:
    raise ValueError(f"unknown STAGE {stage}")

job.commit()
if not ok:
    raise RuntimeError(f"{stage}: data quality rules with severity 'fail' failed - see table mcds_ops.dq_results")
