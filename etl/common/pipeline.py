"""
UC MCDS pipeline: Callista CSV -> Bronze -> Silver (MCDS-aligned) -> Gold (student load)
plus MCDS JSON export and MCDS Reporting Framework export.

Pure PySpark + Python. The AWS Glue job scripts (etl/bronze|silver|gold/*.py) and the local
runner (scripts/run-local-pipeline.py) both call these functions, so what is tested locally
is exactly what runs in Glue.

Behaviour is driven by:
  config/business-rules.yaml      rules and EBA defaults awaiting UC confirmation
  config/silver-mappings.yaml     Callista -> MCDS column mappings (Spark SQL expressions)
  config/gold-aggregations.yaml   Gold report definitions (dimensions, measures, filters)
  config/data-quality-rules.yaml  data quality rules (SQL returning violation counts)
"""

import datetime as _dt
import json
import re
from collections import OrderedDict, defaultdict
from decimal import Decimal

try:  # pyspark is not needed for the pure-Python helpers (tests, mock generator)
    from pyspark.sql import functions as F
    from pyspark.sql import Window
except ImportError:  # pragma: no cover
    F = None
    Window = None

from schemas import TABLES, spark_schema, key_columns

FACT = "student_unit_load"
DIMENSIONS = ["student", "unit_of_learning", "organisation", "location", "learning_period"]
SILVER_ENTITIES = DIMENSIONS + [FACT]


# --------------------------------------------------------------------------- config helpers

def load_yaml_text(text):
    import yaml
    return yaml.safe_load(text)


def load_yaml(path):
    """Load YAML from a local path or s3://bucket/key."""
    if str(path).startswith("s3://"):
        import boto3
        bucket, key = str(path)[5:].split("/", 1)
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        return load_yaml_text(body)
    with open(path, "r", encoding="utf-8") as fh:
        return load_yaml_text(fh.read())


def _lookup(rules, dotted):
    node = rules
    for part in dotted.split("."):
        node = node[part]
    return node


def format_to_sql(fmt):
    """'STU-{PERSON_ID}' -> concat('STU-', CAST(PERSON_ID AS STRING))"""
    parts = []
    for literal, col in re.findall(r"([^{]*)(?:\{([A-Z][A-Z0-9_]*)\})?", fmt):
        if literal:
            parts.append("'" + literal.replace("'", "''") + "'")
        if col:
            parts.append(f"CAST({col} AS STRING)")
    parts = [p for p in parts if p != "''"]
    if not parts:
        return "''"
    return parts[0] if len(parts) == 1 else "concat(" + ", ".join(parts) + ")"


def resolve_tokens(text, rules):
    """Replace {a.b.c} tokens (lower-case dotted paths) with values from business-rules.
    Lists become comma-separated SQL lists; '{COL}' format strings become SQL expressions."""
    def repl(m):
        value = _lookup(rules, m.group(1))
        if isinstance(value, dict) and "format" in value:
            value = value["format"]
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        if isinstance(value, str) and re.search(r"\{[A-Z][A-Z0-9_]*\}", value):
            return format_to_sql(value)
        return str(value)
    return re.sub(r"\{([a-z_]+(?:\.[a-z_]+)+)\}", repl, text)


# --------------------------------------------------------------------------- landing -> bronze

def read_landing_table(spark, path, table, csv_options, extract_date):
    """Read one Callista CSV extract with the explicit schema and add audit columns."""
    opts = csv_options or {}
    df = (spark.read.format("csv")
          .option("header", str(opts.get("header", True)).lower())
          .option("sep", opts.get("delimiter", ","))
          .option("dateFormat", opts.get("date_format", "yyyy-MM-dd"))
          .option("nullValue", opts.get("null_value", ""))
          .option("mode", "FAILFAST")
          .schema(spark_schema(table))
          .load(path))
    return (df.withColumn("_extract_date", F.lit(extract_date))
              .withColumn("_source_file", F.lit(str(path)))
              .withColumn("_ingested_at", F.current_timestamp()))


def latest_extract(df):
    """Bronze is append-only by extract date; Silver uses the latest complete extract."""
    if "_extract_date" not in df.columns:
        return df
    latest = df.agg(F.max("_extract_date")).collect()[0][0]
    return df.filter(F.col("_extract_date") == latest)


# --------------------------------------------------------------------------- bronze -> silver

def select_government_load(gsl, rules):
    """Apply submission selection so a unit attempt re-reported in a later submission is
    counted once. Keeps every teaching-responsibility split row of the chosen submission."""
    mode = rules["government_load"]["submission_selection"]
    if mode == "all":
        return gsl
    if mode != "latest_per_unit_attempt":
        raise ValueError(f"Unknown submission_selection: {mode}")
    attempt = ["SUBMISSION_YR", "GOVT_SEMESTER", "PERSON_ID", "COURSE_CD", "UNIT_CD",
               "UV_VERSION_NUMBER", "SUA_CAL_TYPE", "SUA_CI_SEQUENCE_NUMBER"]
    w = Window.partitionBy(*attempt)
    return (gsl.withColumn("_max_sub", F.max("SUBMISSION_NUMBER").over(w))
               .filter(F.col("SUBMISSION_NUMBER") == F.col("_max_sub"))
               .drop("_max_sub"))


def _select_mapped(df, entity_cfg, rules):
    exprs = []
    for col, spec in entity_cfg["columns"].items():
        exprs.append(f"{resolve_tokens(spec['expr'], rules)} AS {col}")
    return df.selectExpr(*exprs)


def _case_map(column, mapping, default=None, quote_keys=True):
    whens = []
    for k, v in mapping.items():
        if k == "_default":
            continue
        key = f"'{k}'" if quote_keys else str(k)
        whens.append(f"WHEN {column} = {key} THEN '{v}'")
    tail = f" ELSE '{default}'" if default is not None else " ELSE NULL"
    return "CASE " + " ".join(whens) + tail + " END"


def build_silver(bronze, rules, mappings):
    """bronze: dict TABLE -> DataFrame (latest extract). Returns dict entity -> DataFrame,
    plus '_gsl_selected' (GOVT_STUDENT_LOAD after submission selection, for reconciliation)."""
    ents = mappings["entities"]
    gsl_sel = select_government_load(bronze["GOVT_STUDENT_LOAD"], rules)
    out = {"_gsl_selected": gsl_sel}

    # student: only people with government load (PERSON also holds staff/applicants)
    people = bronze["PERSON"].join(gsl_sel.select("PERSON_ID").distinct(), "PERSON_ID", "left_semi")
    out["student"] = _select_mapped(people, ents["student"], rules)

    out["unit_of_learning"] = _select_mapped(bronze["UNIT_VERSION"], ents["unit_of_learning"], rules)
    out["organisation"] = _select_mapped(bronze["ORG_UNIT"], ents["organisation"], rules)

    loc = _select_mapped(bronze["LOCATION"], ents["location"], rules)
    ltm = rules.get("location_type_map", {})
    out["location"] = loc.withColumn(
        "location_type", F.expr(_case_map("callista_location_type", ltm, ltm.get("_default", "Campus"))))

    out["learning_period"] = _select_mapped(bronze["CAL_INSTANCE"], ents["learning_period"], rules)

    # fact: GOVT_STUDENT_LOAD + STUDENT_UNIT_ATTEMPT (campus + offering). Other dimensions are
    # referenced by key and checked by referential-integrity DQ rules.
    att = bronze["STUDENT_UNIT_ATTEMPT"].select(
        F.col("PERSON_ID").alias("att_PERSON_ID"), F.col("COURSE_CD").alias("att_COURSE_CD"),
        F.col("UNIT_CD").alias("att_UNIT_CD"), F.col("VERSION_NUMBER").alias("att_VERSION_NUMBER"),
        F.col("CAL_TYPE").alias("att_CAL_TYPE"), F.col("CI_SEQUENCE_NUMBER").alias("att_CI_SEQUENCE_NUMBER"),
        F.col("LOCATION_CD").alias("att_LOCATION_CD"), F.col("UOO_ID").alias("att_UOO_ID"))
    cond = [gsl_sel.PERSON_ID == att.att_PERSON_ID, gsl_sel.COURSE_CD == att.att_COURSE_CD,
            gsl_sel.UNIT_CD == att.att_UNIT_CD, gsl_sel.UV_VERSION_NUMBER == att.att_VERSION_NUMBER,
            gsl_sel.SUA_CAL_TYPE == att.att_CAL_TYPE,
            gsl_sel.SUA_CI_SEQUENCE_NUMBER == att.att_CI_SEQUENCE_NUMBER]
    joined = gsl_sel.join(att, cond, "left")
    fact = _select_mapped(joined, ents[FACT], rules)
    cs = {k: v["mcds_status"] for k, v in rules["completion_status"].items()}
    out[FACT] = fact.withColumn(
        "completion_status_label", F.expr(_case_map("completion_status", cs, quote_keys=False)))
    return out


# --------------------------------------------------------------------------- silver -> gold

def _report_sql(report, gold_cfg, rules):
    views = {alias: f"silver_{table}" for alias, table in gold_cfg["silver_tables"].items()}
    joins = []
    for j in report.get("joins", []):
        joins.append(re.sub(r"JOIN\s+(\w+)\s+ON",
                            lambda m: f"JOIN {views[m.group(1)]} {m.group(1)} ON", j))
    dims = report["dimensions"]
    select = [f"{expr} AS {name}" for name, expr in dims.items()]
    select += [f"{expr} AS {name}" for name, expr in report.get("attributes", {}).items()]
    select += [f"{expr} AS {name}" for name, expr in report["measures"].items()]
    where = resolve_tokens(gold_cfg["common_filter"], rules)
    inner = (f"SELECT {', '.join(select)} FROM {views['f']} f {' '.join(joins)} "
             f"WHERE {where} GROUP BY {', '.join(dims.values())}")
    derived = report.get("derived") or {}
    extra = "".join(f", {expr} AS {name}" for name, expr in derived.items())
    order = ", ".join(dims.keys())
    return f"SELECT *{extra}, current_timestamp() AS report_generated_at FROM ({inner}) t ORDER BY {order}"


def report_sql(name, gold_cfg, rules):
    return _report_sql(gold_cfg["reports"][name], gold_cfg, rules)


def build_gold(spark, silver, gold_cfg, rules):
    register_views(silver, "silver")
    return {name: spark.sql(_report_sql(rep, gold_cfg, rules))
            for name, rep in gold_cfg["reports"].items()}


def register_views(frames, prefix):
    for name, df in frames.items():
        view = f"{prefix}_{name.lstrip('_').lower()}"
        df.createOrReplaceTempView(view)


def register_bronze_views(bronze, silver=None):
    register_views({t.lower(): df for t, df in bronze.items()}, "bronze")
    if silver is not None and "_gsl_selected" in silver:
        silver["_gsl_selected"].createOrReplaceTempView("bronze_gsl_selected")


# --------------------------------------------------------------------------- MCDS JSON export

def _num(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def _iso(v):
    return v.isoformat() if isinstance(v, (_dt.date, _dt.datetime)) else v


def _clean(obj):
    """Drop None values recursively (MCDS uses additionalProperties:false and typed fields)."""
    if isinstance(obj, dict):
        return OrderedDict((k, _clean(v)) for k, v in obj.items() if v is not None and v != [] and v != {})
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def mcds_documents(silver_rows, rules, students_per_file=None):
    """Build MCDS studentlifecycle documents from collected Silver rows.

    silver_rows: dict entity -> list of Row/dict. Returns list of documents, each
    {"students": [...], "unitsOfLearning": [...], "organisations": [...],
     "locations": [...], "learningPeriods": [...], "programmeOfLearningEnrolments": [...]}
    """
    exp = rules["mcds_export"]
    per_file = students_per_file or exp.get("students_per_file", 500)
    as_dict = {k: [r.asDict() if hasattr(r, "asDict") else dict(r) for r in v] for k, v in silver_rows.items()}
    units = {u["unit_of_learning_id"]: u for u in as_dict["unit_of_learning"]}
    orgs = {o["organisation_id"]: o for o in as_dict["organisation"]}
    locs = {l["location_id"]: l for l in as_dict["location"]}
    lps = {p["learning_period_id"]: p for p in as_dict["learning_period"]}
    include = set(rules["government_load"]["include_completion_status"])

    def unit_obj(u):
        level = u.get("unit_level")
        return {"unitOfLearningID": u["unit_of_learning_id"], "unitOfLearningCode": u["unit_code"],
                "unitOfLearningName": u["unit_name"], "shortName": u.get("short_name"),
                "version": str(u["unit_version"]),
                "level": int(level) if isinstance(level, str) and level.isdigit() else None,
                "responsibleOrganisations": [{"organisationID": u["owner_organisation_id"], "role": exp["owner_role"]}]
                if u.get("owner_organisation_id") else None,
                "x-additional": {"enrolledCreditPoints": _num(u.get("credit_points"))}
                if u.get("credit_points") is not None else None}

    def loc_obj(l):
        return {"locationID": l["location_id"], "locationName": l["location_name"],
                "code": l["location_code"], "locationType": l["location_type"],
                "x-additional": {"govtLocationCode": l.get("govt_location_cd")} if l.get("govt_location_cd") else None}

    def lp_obj(p):
        return {"learningPeriodID": p["learning_period_id"], "code": p["code"],
                "startDate": _iso(p["start_date"]), "endDate": _iso(p["end_date"]), "year": p["year"],
                "x-additional": {"callistaCalType": p["cal_type"]}}

    def org_obj(o):
        return {"organisationID": o["organisation_id"], "organisationName": o["organisation_name"],
                "organisationCode": o["organisation_code"], "status": o.get("status"),
                "x-additional": {"callistaOrgType": o.get("organisation_type"),
                                 "effectiveFromDate": _iso(o.get("start_date")),
                                 "effectiveToDate": _iso(o.get("end_date"))}}

    # group load rows (teaching splits) into one MCDS unitOfLearningEnrolment
    enrol = OrderedDict()
    for r in sorted(as_dict[FACT], key=lambda x: (x["student_id"], x["unit_enrolment_id"], x["teaching_organisation_id"])):
        if r["completion_status"] not in include:
            continue
        e = enrol.setdefault(r["unit_enrolment_id"], {"row": r, "splits": []})
        e["splits"].append(r)

    by_student = defaultdict(list)
    for eid, e in enrol.items():
        r = e["row"]
        unit = units.get(r["unit_of_learning_id"])
        avail = {
            "unitOfLearningAvailabilityID": r.get("unit_offering_id"),
            "unitOfLearning": {"unitOfLearningID": r["unit_of_learning_id"], "unitOfLearningCode": r["unit_code"],
                               "unitOfLearningName": unit["unit_name"] if unit else None,
                               "version": str(r["unit_version"])},
            "learningPeriod": lp_obj(lps[r["learning_period_id"]]) if r["learning_period_id"] in lps
            else {"learningPeriodID": r["learning_period_id"]},
            "location": loc_obj(locs[r["location_id"]]) if r["location_id"] in locs
            else {"locationName": r["location_id"] or "UNKNOWN"},
            "responsibleOrganisations": [{"organisationID": s["teaching_organisation_id"], "role": exp["teaching_role"]}
                                         for s in e["splits"]],
        }
        total = sum(Decimal(str(s["eftsu"])) for s in e["splits"])
        by_student[r["student_id"]].append({
            "unitOfLearningEnrolmentID": eid,
            "studentID": r["student_id"],
            "programmeOfLearningEnrolmentID": r["programme_enrolment_id"],
            "unitOfLearningAvailability": avail,
            "status": r.get("completion_status_label"),
            "x-additional": {"governmentLoad": {
                "submissionYear": r["reporting_year"], "governmentSemester": r["govt_semester"],
                "submissionNumber": r["submission_number"], "reportingPeriod": r["reporting_period"],
                "completionStatusCode": r["completion_status"], "eftsl": float(total),
                "disciplineGroupCode": r.get("discipline_group_code"),
                "teachingSplits": [{"organisationID": s["teaching_organisation_id"], "eftsl": _num(s["eftsu"])}
                                   for s in e["splits"]]}},
        })

    students = sorted(as_dict["student"], key=lambda s: s["student_id"])
    docs = []
    for i in range(0, len(students), per_file):
        chunk = students[i:i + per_file]
        s_objs, unit_ids, org_ids, loc_ids, lp_ids, poe = [], set(), set(), set(), set(), OrderedDict()
        for s in chunk:
            ens = by_student.get(s["student_id"], [])
            for en in ens:
                a = en["unitOfLearningAvailability"]
                unit_ids.add(a["unitOfLearning"]["unitOfLearningID"])
                loc_ids.add(a["location"].get("locationID"))
                lp_ids.add(a["learningPeriod"].get("learningPeriodID"))
                org_ids.update(o["organisationID"] for o in a["responsibleOrganisations"])
                poe.setdefault(en["programmeOfLearningEnrolmentID"], {
                    "programmeOfLearningEnrolmentID": en["programmeOfLearningEnrolmentID"],
                    "studentID": s["student_id"], "studentNumber": s["student_number"],
                    "x-additional": {"courseCode": en["programmeOfLearningEnrolmentID"].split("|", 1)[1]}})
            s_objs.append({"studentID": s["student_id"], "personID": s["person_id"],
                           "studentNumber": s["student_number"],
                           "studentName": {"lastName": s["last_name"], "firstName": s.get("first_name")},
                           "unitOfLearningEnrolments": ens})
        for uid in list(unit_ids):
            u = units.get(uid)
            if u and u.get("owner_organisation_id"):
                org_ids.add(u["owner_organisation_id"])
        doc = {"students": s_objs,
               "programmeOfLearningEnrolments": list(poe.values()),
               "unitsOfLearning": [unit_obj(units[u]) for u in sorted(unit_ids) if u in units],
               "organisations": [org_obj(orgs[o]) for o in sorted(org_ids) if o in orgs],
               "locations": [loc_obj(locs[l]) for l in sorted(x for x in loc_ids if x) if l in locs],
               "learningPeriods": [lp_obj(lps[p]) for p in sorted(x for x in lp_ids if x) if p in lps]}
        docs.append(_clean(doc))
    return docs


# --------------------------------------------------------------------------- MCDS Reporting Framework export

def _lm(text):
    return {"en": str(text)}


def mcds_reporting_artefacts(gold_rows, gold_cfg, rules, as_of_date, created_at=None):
    """Build MCDS Reporting Framework artefacts from collected Gold rows.

    Returns (definitions, factdata): lists of (filename, json-dict).
    One Report Definition per report; one Fact Data file per report per reporting period.
    Derived values (e.g. EFTSL per student) are NOT facts: they are declared as a derived
    member with a formula, as the framework requires.
    """
    rep_cfg = gold_cfg["mcds_reporting"]
    inst = rules["mcds_export"]["institution"]
    org = {"organisationId": inst["organisationId"], "legalName": _lm(inst["legalName"])}
    resp = [{"name": r["name"], "role": _lm(r["role"])} for r in rep_cfg["responsibilities"]]
    version = rep_cfg["definition_version"]
    created_at = created_at or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metric = rep_cfg["metric_dimension"]
    periods = {r["reporting_period"]: r for r in (x.asDict() if hasattr(x, "asDict") else x
                                                   for x in gold_rows.get("reporting_period", []))}

    metric_dim = {
        "dimensionID": metric["dimensionID"], "dimensionType": "Metric", "labels": _lm("Metric"),
        "isMeasureDefining": True,
        "members": [{"dimensionMemberID": mid, "labels": _lm(m["label"]), "nature": "measure",
                     "measure": {"measureType": m["measureType"]}, "unitOfMeasure": {"code": m["unit"]},
                     "precision": {"decimalPlaces": m["decimals"]}}
                    for mid, m in metric["members"].items()]
        + [{"dimensionMemberID": "EFTSL_PER_STUDENT", "labels": _lm("EFTSL per student"), "nature": "derived",
            "formula": {"language": "mcds-simple", "expr": "EFTSL / HEADCOUNT", "refs": ["EFTSL", "HEADCOUNT"]},
            "precision": {"decimalPlaces": 3}}],
    }

    definitions, factdata = [], []
    for name, rep in gold_cfg["reports"].items():
        mr = rep.get("mcds_report")
        if not mr:
            continue
        rows = [x.asDict() if hasattr(x, "asDict") else dict(x) for x in gold_rows[name]]
        dims = []
        for dim_id, d in mr["dimensions"].items():
            members = OrderedDict()
            for r in rows:
                key = r[d["member"]]
                if key is not None:
                    members[str(key)] = r.get(d["label"]) or str(key)
            dims.append({"dimensionID": dim_id, "dimensionType": d["type"], "labels": _lm(d["type"]),
                         "members": [{"dimensionMemberID": k, "labels": _lm(v), "nature": "presentation"}
                                     for k, v in sorted(members.items())]})
        definition = {
            "reportDefinitionId": mr["reportDefinitionId"],
            "reportDefinitionName": _lm(mr["label"]),
            "description": _lm(rep["description"]),
            "version": version, "organisation": org, "responsibilities": resp,
            "region": rep_cfg["region"], "reportLabel": _lm(mr["label"]),
            "reportKind": {"type": "Public Sector", "label": _lm("Student Enrolment & Load Reporting")},
            "languages": ["en"],
            "defaultMeasure": {"measureType": "students"},
            "requiredDimensions": list(mr["dimensions"].keys()) + [metric["dimensionID"]],
            "dimensions": dims + [metric_dim],
        }
        definitions.append((f"reportdefinition.{mr['reportDefinitionId']}.json", definition))

        by_period = defaultdict(list)
        for r in rows:
            by_period[r["reporting_period"]].append(r)
        for period, prow in sorted(by_period.items()):
            facts = []
            for r in prow:
                base = {dim_id: str(r[d["member"]]) for dim_id, d in mr["dimensions"].items()}
                for mid, m in metric["members"].items():
                    facts.append({"amount": round(float(r[m["measure"]]), m["decimals"]) if m["decimals"] else int(r[m["measure"]]),
                                  "dimensions": dict(base, **{metric["dimensionID"]: mid})})
            p = periods.get(period, {})
            fd = {
                "factDataId": f"{mr['reportDefinitionId']}.{period}",
                "version": "1.0",
                "reportDefinitionId": mr["reportDefinitionId"],
                "reportDefinitionVersion": version,
                "region": rep_cfg["region"],
                "organisation": org, "responsibilities": resp,
                "reportCreationDate": created_at,
                "reportingAsOfDate": as_of_date,
                "reportingPeriod": {"startDate": _iso(p.get("start_date")) or f"{period[:4]}-01-01",
                                    "endDate": _iso(p.get("end_date")) or f"{period[:4]}-12-31",
                                    "code": period, "label": _lm(f"Government semester {period[-1]} {period[:4]}")},
                "languages": ["en"],
                "facts": facts,
                "notes": _lm("Generated from Callista GOVT_STUDENT_LOAD via the UC MCDS pipeline. "
                             "Headcount is distinct students and is not additive across members."),
            }
            factdata.append((f"factdata.{mr['reportDefinitionId']}.{period}.json", fd))
    return definitions, factdata


def to_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, default=lambda v: _num(_iso(v)))
