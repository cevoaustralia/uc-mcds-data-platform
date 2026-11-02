"""
Deploy QuickSight datasets and dashboards from quicksight/dashboards.yaml (config-driven).

MDAA (infra/consumption/quicksight-project.yaml) creates the Athena data source and shared folder;
MDAA does not manage datasets/dashboards, so this script creates or updates them with the QuickSight API.
Account ID comes from the caller's credentials (STS) - nothing account-specific is stored in the repo.

    python scripts/deploy_quicksight.py --env cevo-aws-mcds --dry-run      # offline: print definitions, no AWS calls
    python scripts/deploy_quicksight.py --env cevo-aws-mcds                # create/update in the target account

Column types for each dataset are read from the Glue Data Catalog (tables exist after the first
pipeline run), so dashboards stay in sync with pipeline/gold/*.yaml.
"""

import argparse
import json
import os
import re
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NUMERIC = re.compile(r"^(int|bigint|smallint|tinyint|double|float|decimal.*)$")
GLUE_TO_QS = {"string": "STRING", "boolean": "STRING", "date": "DATETIME", "timestamp": "DATETIME"}


def qs_type(glue_type):
    if NUMERIC.match(glue_type):
        return "INTEGER" if glue_type in ("int", "bigint", "smallint", "tinyint") else "DECIMAL"
    return GLUE_TO_QS.get(glue_type, "STRING")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ------------------------------------------------------------------------------------------------
# definition builders (pure functions - unit tested offline)
# ------------------------------------------------------------------------------------------------
def _col(ds, column):
    return {"DataSetIdentifier": ds, "ColumnName": column}


def _dim(ds, column, numeric, fid):
    key = "NumericalDimensionField" if numeric else "CategoricalDimensionField"
    return {key: {"FieldId": fid, "Column": _col(ds, column)}}


def _measure(ds, m, fid):
    agg = m.get("agg", "SUM").upper()
    if agg in ("COUNT", "DISTINCT_COUNT"):
        return {"CategoricalMeasureField": {"FieldId": fid, "Column": _col(ds, m["column"]), "AggregationFunction": agg}}
    return {"NumericalMeasureField": {"FieldId": fid, "Column": _col(ds, m["column"]),
                                      "AggregationFunction": {"SimpleNumericalAggregation": agg}}}


def _title(text):
    return {"Visibility": "VISIBLE", "FormatText": {"PlainText": text}}


def visual(v, vid, columns):
    """columns: {dataset: {column: qs_type}} - used to pick numeric vs categorical dimensions."""
    ds = v["dataset"]
    cols = columns[ds]
    for c in [v.get("category"), v.get("color")] + list(v.get("group_by", [])) + [m["column"] for m in v.get("measures", [])]:
        if c and c not in cols:
            raise ValueError(f"visual '{v['title']}': column {c} not in dataset {ds}")
    num = lambda c: cols[c] in ("INTEGER", "DECIMAL")   # noqa: E731
    measures = [_measure(ds, m, f"{vid}-m{i}") for i, m in enumerate(v.get("measures", []))]
    if v["type"] == "kpi":
        return {"KPIVisual": {"VisualId": vid, "Title": _title(v["title"]),
                              "ChartConfiguration": {"FieldWells": {"Values": measures}}}}
    if v["type"] == "bar":
        wells = {"Category": [_dim(ds, v["category"], num(v["category"]), f"{vid}-c")], "Values": measures}
        if v.get("color"):
            wells["Colors"] = [_dim(ds, v["color"], num(v["color"]), f"{vid}-col")]
        first = next(iter(measures[0].values()))["FieldId"]
        return {"BarChartVisual": {"VisualId": vid, "Title": _title(v["title"]),
                                   "ChartConfiguration": {
                                       "FieldWells": {"BarChartAggregatedFieldWells": wells},
                                       "Orientation": "HORIZONTAL", "BarsArrangement": "STACKED",
                                       "SortConfiguration": {"CategorySort": [{"FieldSort": {"FieldId": first, "Direction": "DESC"}}],
                                                             "CategoryItemsLimit": {"ItemsLimit": 25, "OtherCategories": "INCLUDE"}}}}}
    if v["type"] == "table":
        group = [_dim(ds, c, num(c), f"{vid}-g{i}") for i, c in enumerate(v["group_by"])]
        return {"TableVisual": {"VisualId": vid, "Title": _title(v["title"]),
                                "ChartConfiguration": {"FieldWells": {"TableAggregatedFieldWells": {"GroupBy": group, "Values": measures}}}}}
    raise ValueError(f"unknown visual type {v['type']}")


def dashboard_definition(dash_id, dash, dataset_arns, columns):
    used = sorted({v["dataset"] for s in dash["sheets"] for v in s["visuals"]})
    sheets = []
    for si, sheet in enumerate(dash["sheets"]):
        sheets.append({"SheetId": f"{dash_id}-s{si}", "Name": sheet["name"],
                       "Visuals": [visual(v, f"{dash_id}-s{si}-v{vi}", columns) for vi, v in enumerate(sheet["visuals"])]})
    return {"DataSetIdentifierDeclarations": [{"Identifier": d, "DataSetArn": dataset_arns[d]} for d in used],
            "Sheets": sheets}


def dataset_physical_table(ds_cfg, data_source_arn, glue_columns):
    return {"t": {"RelationalTable": {"DataSourceArn": data_source_arn, "Catalog": "AwsDataCatalog",
                                      "Schema": ds_cfg["database"], "Name": ds_cfg["table"],
                                      "InputColumns": [{"Name": c, "Type": t} for c, t in glue_columns.items()]}}}


# ------------------------------------------------------------------------------------------------
def load(env_name):
    cfg = yaml.safe_load(open(os.path.join(ROOT, "quicksight", "dashboards.yaml")))
    env = yaml.safe_load(open(os.path.join(ROOT, "config", "environments", f"{env_name}.yaml")))
    return cfg, env


def offline_columns(cfg):
    """Column types from the local pipeline run (.local-lake) - used by --dry-run and tests."""
    import pyarrow.parquet as pq
    out = {}
    for name, d in cfg["datasets"].items():
        layer = {"mcds_gold": "gold", "mcds_ops": "ops"}[d["database"]]
        path = os.path.join(ROOT, ".local-lake", layer, d["table"])
        schema = pq.ParquetDataset(path).schema
        out[name] = {}
        for f in schema:
            t = str(f.type)
            out[name][f.name] = ("INTEGER" if t.startswith("int") else "DECIMAL" if t.startswith(("decimal", "double", "float"))
                                 else "DATETIME" if t.startswith(("date", "timestamp")) else "STRING")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--dry-run", action="store_true", help="no AWS calls; types from .local-lake")
    a = ap.parse_args(argv)
    cfg, env = load(a.env)
    prefix = cfg["id_prefix"]

    if a.dry_run:
        columns = offline_columns(cfg)
        arns = {d: f"arn:aws:quicksight:<REGION>:<ACCOUNT>:dataset/{prefix}-{d}" for d in cfg["datasets"]}
        for dash_id, dash in cfg["dashboards"].items():
            d = dashboard_definition(f"{prefix}-{dash_id}", dash, arns, columns)
            print(f"{dash['name']}: {len(d['Sheets'])} sheets, {sum(len(s['Visuals']) for s in d['Sheets'])} visuals, "
                  f"datasets {', '.join(x['Identifier'] for x in d['DataSetIdentifierDeclarations'])}")
        return 0

    import boto3
    region = env["aws"]["region"]
    if region.startswith("<"):
        sys.exit("aws.region is still a placeholder in config/environments - set it first")
    account = boto3.client("sts").get_caller_identity()["Account"]
    qs = boto3.client("quicksight", region_name=region)
    glue = boto3.client("glue", region_name=region)
    qs_region = env["quicksight"]["identity_region"]
    principals = {g: f"arn:aws:quicksight:{qs_region}:{account}:group/default/{env['quicksight'][g]}"
                  for g in ("readers_group", "authors_group")}
    sources = [s for p in qs.get_paginator("list_data_sources").paginate(AwsAccountId=account) for s in p["DataSources"]]
    match = [s for s in sources if s["Name"] == cfg["data_source_name"]]
    if not match:
        sys.exit(f"QuickSight data source '{cfg['data_source_name']}' not found - deploy the consumption/quicksight-project module first")
    ds_arn = match[0]["Arn"]

    ds_perm = [{"Principal": principals["authors_group"], "Actions": [
        "quicksight:DescribeDataSet", "quicksight:DescribeDataSetPermissions", "quicksight:PassDataSet",
        "quicksight:DescribeIngestion", "quicksight:ListIngestions", "quicksight:UpdateDataSet",
        "quicksight:DeleteDataSet", "quicksight:CreateIngestion", "quicksight:CancelIngestion",
        "quicksight:UpdateDataSetPermissions"]},
        {"Principal": principals["readers_group"], "Actions": [
            "quicksight:DescribeDataSet", "quicksight:DescribeDataSetPermissions", "quicksight:PassDataSet",
            "quicksight:DescribeIngestion", "quicksight:ListIngestions"]}]
    columns, arns = {}, {}
    for name, d in cfg["datasets"].items():
        cols = glue.get_table(DatabaseName=d["database"], Name=d["table"])["Table"]["StorageDescriptor"]["Columns"]
        parts = glue.get_table(DatabaseName=d["database"], Name=d["table"])["Table"].get("PartitionKeys", [])
        glue_cols = {c["Name"]: qs_type(c["Type"]) for c in cols + parts}
        columns[name] = glue_cols
        ds_id = f"{prefix}-{name}"
        body = dict(AwsAccountId=account, DataSetId=ds_id, Name=f"MCDS {name}", ImportMode="DIRECT_QUERY",
                    PhysicalTableMap=dataset_physical_table(d, ds_arn, glue_cols))
        try:
            arns[name] = qs.create_data_set(**body, Permissions=ds_perm)["Arn"]
            print(f"dataset created: {ds_id}")
        except qs.exceptions.ResourceExistsException:
            arns[name] = qs.update_data_set(**body)["Arn"]
            print(f"dataset updated: {ds_id}")

    dash_perm = [{"Principal": principals["authors_group"], "Actions": [
        "quicksight:DescribeDashboard", "quicksight:ListDashboardVersions", "quicksight:QueryDashboard",
        "quicksight:UpdateDashboard", "quicksight:UpdateDashboardPermissions", "quicksight:DescribeDashboardPermissions",
        "quicksight:UpdateDashboardPublishedVersion", "quicksight:DeleteDashboard"]},
        {"Principal": principals["readers_group"], "Actions": [
            "quicksight:DescribeDashboard", "quicksight:ListDashboardVersions", "quicksight:QueryDashboard"]}]
    for dash_id, dash in cfg["dashboards"].items():
        did = f"{prefix}-{dash_id}"
        body = dict(AwsAccountId=account, DashboardId=did, Name=dash["name"],
                    Definition=dashboard_definition(did, dash, arns, columns))
        try:
            qs.create_dashboard(**body, Permissions=dash_perm)
            print(f"dashboard created: {did}")
        except qs.exceptions.ResourceExistsException:
            ver = qs.update_dashboard(**body)["VersionArn"].rsplit("/", 1)[-1]
            qs.update_dashboard_published_version(AwsAccountId=account, DashboardId=did, VersionNumber=int(ver))
            print(f"dashboard updated: {did} (version {ver})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
