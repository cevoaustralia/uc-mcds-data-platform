"""
Storage back-ends for the engine.

LocalStore  - Parquet folders under .local-lake/<layer>/<table>/ (local runs and tests)
GlueStore   - Parquet in the MDAA data lake buckets + Glue Data Catalog tables, with table
              properties and column comments carrying classification and column-level lineage
              (SOW D4: lineage visible in the Glue Data Catalog).

Both write one partition per extract (`extract_date`) for Bronze and overwrite Silver/Gold/ops
tables per run, so re-running an extract is idempotent.
"""

import os


def _sql_str(text):
    return str(text).replace("\\", "\\\\").replace("'", "\\'")


class LocalStore:
    def __init__(self, spark, root):
        self.spark = spark
        self.root = root

    def path(self, layer, table):
        return os.path.join(self.root, layer, table)

    def write(self, df, layer, table, description="", properties=None, column_comments=None,
              partition_by=None):
        writer = df.write.mode("overwrite").format("parquet")
        if partition_by:
            self.spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
            writer = writer.partitionBy(*partition_by)
        writer.save(self.path(layer, table))
        return self.read(layer, table)

    def read(self, layer, table):
        return self.spark.read.parquet(self.path(layer, table))

    def exists(self, layer, table):
        return os.path.isdir(self.path(layer, table))


class GlueStore:
    """layers: {layer: {"database": name, "bucket": bucket, "prefix": prefix}}"""

    def __init__(self, spark, layers):
        self.spark = spark
        self.layers = layers
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

    def path(self, layer, table):
        cfg = self.layers[layer]
        return f"s3://{cfg['bucket']}/{cfg['prefix']}/{table}/"

    def write(self, df, layer, table, description="", properties=None, column_comments=None,
              partition_by=None):
        db = self.layers[layer]["database"]
        full = f"`{db}`.`{table}`"
        if partition_by and self.spark.catalog.tableExists(f"{db}.{table}"):
            existing = self.spark.table(f"{db}.{table}").columns
            if set(existing) == set(df.columns):
                df.select(*existing).write.mode("overwrite").insertInto(f"{db}.{table}")
            else:   # schema changed (e.g. new source column): rewrite the table
                self._save(df, full, layer, table, partition_by)
        else:
            self._save(df, full, layer, table, partition_by)
        props = dict(properties or {})
        props["comment"] = description
        prop_sql = ", ".join(f"'{_sql_str(k)}' = '{_sql_str(v)}'" for k, v in props.items())
        self.spark.sql(f"ALTER TABLE {full} SET TBLPROPERTIES ({prop_sql})")
        for col, comment in (column_comments or {}).items():
            if col in df.columns:
                self.spark.sql(f"ALTER TABLE {full} ALTER COLUMN `{col}` COMMENT '{_sql_str(comment[:255])}'")
        return self.read(layer, table)

    def _save(self, df, full, layer, table, partition_by):
        if self.spark.catalog.tableExists(full.replace("`", "")):
            self.spark.sql(f"DROP TABLE {full}")      # external table: data replaced below
        writer = df.write.mode("overwrite").format("parquet").option("path", self.path(layer, table))
        if partition_by:
            writer = writer.partitionBy(*partition_by)
        writer.saveAsTable(full)

    def read(self, layer, table):
        return self.spark.table(f"{self.layers[layer]['database']}.{table}")

    def exists(self, layer, table):
        return self.spark.catalog.tableExists(f"{self.layers[layer]['database']}.{table}")
