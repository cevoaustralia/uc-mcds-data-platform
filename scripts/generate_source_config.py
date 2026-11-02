"""
Generate (or extend) a source-system config from the Callista schema metadata export.

The metadata export (Sisprod_schema_metadata.csv: OWNER, TABLE_NAME, COLUMN_ID, COLUMN_NAME,
DATA_TYPE, DATA_PRECISION, DATA_SCALE, NULLABLE) is the authoritative column list. This script
turns selected tables into pipeline/sources/<system>.yaml so the bronze job can type every column
without shipping the 3,914-table metadata file to Glue.

Adding a new Callista table to the pipeline:
    python scripts/generate_source_config.py --metadata <Sisprod_schema_metadata.csv> \
        --table COURSE_VERSION --key COURSE_CD,VERSION_NUMBER --date-format dd/MMM/yy
Existing tables in the YAML are kept unless --replace is given.
"""

import argparse
import csv
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "pipeline", "sources", "callista.yaml")


def spark_type(data_type, precision, scale):
    t = data_type.upper()
    if t in ("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR", "CLOB", "LONG"):
        return "string"
    if t == "DATE" or t.startswith("TIMESTAMP"):
        return "date" if t == "DATE" else "timestamp"
    if t in ("NUMBER", "FLOAT", "INTEGER"):
        p = int(precision) if precision not in ("", None) else None
        s = int(scale) if scale not in ("", None) else 0
        if p is None:
            return "double"
        if s == 0:
            return "int" if p <= 9 else ("bigint" if p <= 18 else f"decimal({p},0)")
        return f"decimal({p},{s})"
    return "string"


def read_metadata(path):
    tables = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            tables.setdefault(r["TABLE_NAME"], []).append(r)
    for cols in tables.values():
        cols.sort(key=lambda r: int(r["COLUMN_ID"]))
    return tables


def table_config(meta_cols, key, date_format, file_name, description):
    return {
        "file": file_name,
        "description": description,
        "primary_key": key,
        "date_format": date_format,
        "columns": {c["COLUMN_NAME"]: {"type": spark_type(c["DATA_TYPE"], c["DATA_PRECISION"], c["DATA_SCALE"]),
                                        "nullable": c["NULLABLE"] != "N"} for c in meta_cols},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--table", required=True, help="Callista table name, e.g. STUDENT_UNIT_ATTEMPT")
    ap.add_argument("--key", required=True, help="comma-separated natural key columns")
    ap.add_argument("--date-format", default="dd/MMM/yy")
    ap.add_argument("--file", help="file name in the landing folder (default: <table lower>.csv)")
    ap.add_argument("--description", default="")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--replace", action="store_true")
    a = ap.parse_args(argv)

    meta = read_metadata(a.metadata)
    if a.table not in meta:
        sys.exit(f"{a.table} not found in {a.metadata}")
    cfg = yaml.safe_load(open(a.out)) if os.path.exists(a.out) else {"system": "callista", "tables": {}}
    name = a.table.lower()
    if name in cfg["tables"] and not a.replace:
        sys.exit(f"{name} already configured (use --replace)")
    key = [k.strip().upper() for k in a.key.split(",")]
    missing = [k for k in key if k not in {c["COLUMN_NAME"] for c in meta[a.table]}]
    if missing:
        sys.exit(f"key columns not in {a.table}: {missing}")
    cfg["tables"][name] = table_config(meta[a.table], key, a.date_format, a.file or f"{name}.csv",
                                       a.description or f"Callista SIS_OWNER.{a.table}")
    with open(a.out, "w") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, width=120)
    print(f"{a.table}: {len(meta[a.table])} columns written to {a.out}")


if __name__ == "__main__":
    main()
