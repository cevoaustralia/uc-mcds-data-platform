"""
AWS Glue helpers shared by the job scripts: arguments, config loading, writing tables to the
Glue Data Catalog with descriptions, properties and column comments (SOW D4: catalogue +
column-level lineage visible in the Glue Data Catalog).

Config YAMLs are shipped with each job by MDAA (`additionalFiles` -> --extra-files), so they
sit in the job's working directory. Pass --CONFIG_PREFIX s3://bucket/prefix/ to override.
"""

import sys

from pipeline import load_yaml, resolve_tokens


def job_args(required, optional=None):
    from awsglue.utils import getResolvedOptions
    optional = optional or {}
    present = [o for o in optional if f"--{o}" in sys.argv]
    args = getResolvedOptions(sys.argv, ["JOB_NAME"] + required + present)
    for k, default in optional.items():
        args.setdefault(k, default)
    return args


def load_configs(args, names):
    prefix = args.get("CONFIG_PREFIX") or ""
    out = {}
    for key, filename in names.items():
        path = f"{prefix.rstrip('/')}/{filename}" if prefix else filename
        out[key] = load_yaml(path)
    return out


def _sql_str(text):
    return str(text).replace("\\", "\\\\").replace("'", "\\'")


def write_catalog_table(spark, df, database, table, path, description, properties,
                        column_comments=None, partition_by=None, mode="overwrite"):
    """Write Parquet to `path`, register/replace `database.table` in the Glue Data Catalog,
    and set the table description, table properties and column comments."""
    full = f"{database}.{table}"
    if partition_by and spark.catalog.tableExists(full):
        # append-only by partition: replace only this extract's partition (dynamic overwrite)
        df.select(*spark.table(full).columns).write.mode("overwrite").insertInto(full)
    else:
        writer = df.write.mode(mode).format("parquet").option("path", path)
        if partition_by:
            writer = writer.partitionBy(*partition_by)
        writer.saveAsTable(full)
    props = dict(properties or {})
    props["comment"] = description
    prop_sql = ", ".join(f"'{_sql_str(k)}' = '{_sql_str(v)}'" for k, v in props.items())
    spark.sql(f"ALTER TABLE {database}.{table} SET TBLPROPERTIES ({prop_sql})")
    for col, comment in (column_comments or {}).items():
        if col in df.columns:
            spark.sql(f"ALTER TABLE {database}.{table} ALTER COLUMN {col} COMMENT '{_sql_str(comment)}'")
    return spark.table(f"{database}.{table}").count()


def lineage_comments(entity_cfg, rules):
    """Column comments from silver-mappings.yaml: '<MCDS path> <- <source expression>'."""
    out = {}
    for col, spec in entity_cfg["columns"].items():
        pii = " [PII]" if spec.get("pii") else ""
        out[col] = f"MCDS {spec['mcds']} <- Callista {resolve_tokens(spec['expr'], rules)}{pii}"[:255]
    return out
