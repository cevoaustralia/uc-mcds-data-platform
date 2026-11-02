import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "etl", "common"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
CONFIG = os.path.join(ROOT, "pipeline")


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[1]").appName("mcds-tests")
         .config("spark.sql.shuffle.partitions", "1").config("spark.ui.enabled", "false")
         .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()
