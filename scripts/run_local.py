"""
Run the full pipeline locally (PySpark) on an extract under data/landing/ - same engine and configs as
the Glue jobs, with Parquet output in .local-lake/<layer>/<table>/.

    python scripts/run_local.py --extract-date 2026-10-26
    python scripts/run_local.py --extract-date 2026-10-26 --stages silver,gold   # reuse bronze

Requires: pyspark (Java 11/17), pyyaml, jsonschema, referencing; MCDS schemas in mcds/v2.1.1/.
"""

import argparse
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "etl", "common"))

from mcds_config import PipelineConfig  # noqa: E402
from mcds_store import LocalStore  # noqa: E402
import mcds_run as RUN  # noqa: E402


def spark_session():
    from pyspark.sql import SparkSession
    return (SparkSession.builder.master("local[2]").appName("mcds-local")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.ui.enabled", "false")
            .config("spark.driver.memory", "3g")
            .getOrCreate())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract-date", required=True)
    ap.add_argument("--stages", default="bronze,silver,gold")
    ap.add_argument("--config", default=os.path.join(ROOT, "pipeline"))
    ap.add_argument("--landing", default=os.path.join(ROOT, "data", "landing"))
    ap.add_argument("--lake", default=os.path.join(ROOT, ".local-lake"))
    ap.add_argument("--mcds", default=None, help="MCDS schema root (default: pipeline.yaml mcds.schema_root)")
    a = ap.parse_args(argv)

    cfg = PipelineConfig(a.config)
    mcds_root = a.mcds or os.path.join(ROOT, cfg.settings["mcds"]["schema_root"])
    spark = spark_session()
    spark.sparkContext.setLogLevel("ERROR")
    store = LocalStore(spark, a.lake)
    ok = True
    for stage in a.stages.split(","):
        t0 = time.time()
        if stage == "bronze":
            ok = RUN.run_bronze(spark, cfg, store, a.landing, a.extract_date)
        elif stage == "silver":
            ok = RUN.run_silver(spark, cfg, store, a.extract_date, mcds_root)
        elif stage == "gold":
            ok = RUN.run_gold(spark, cfg, store, a.extract_date, mcds_root,
                              os.path.join(a.lake, "gold", "_mcds_reporting"))
        print(f"{stage}: {'OK' if ok else 'FAILED'} in {time.time() - t0:.0f}s")
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
