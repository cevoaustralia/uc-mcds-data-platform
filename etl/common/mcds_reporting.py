"""
MCDS Reporting Framework output (Structures deck slide 21): for every Gold report with an
`mcds_report` block, one reportDefinition plus one factData file per reporting period, validated
against reporting/schemas/*.schema.json and the framework's semantic rules.

Headcount is a fact per cell but is not additive across members; EFTSL is additive.
"""

import datetime as dt
from collections import OrderedDict, defaultdict

from mcds_json import SchemaSet, errors


def _lm(text):
    return {"en": str(text)}


def _num(v, decimals):
    v = float(v or 0)
    return int(round(v)) if decimals == 0 else round(v, decimals)


def build_artefacts(cfg, gold_rows, period_dates, as_of_date):
    """gold_rows: {report: [row dicts]}; period_dates: {(year, cal_type): (start, end)}.
    Returns (definitions, factdata) as lists of (file name, dict)."""
    rep = cfg.settings["reporting"]
    ident = cfg.settings["identity"]["organisation_unique_id"]
    org = {"organisationId": f"{ident['organisationUniqueIDType']}:{ident['organisationID']}",
           "legalName": _lm("University of Canberra")}
    resp = [{"name": r["name"], "role": _lm(r["role"])} for r in rep["responsibilities"]]
    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    definitions, factdata = [], []
    for name, r in cfg.reports.items():
        mr = r.get("mcds_report")
        if not mr:
            continue
        rows = gold_rows[name]
        dims = []
        for dim_id, d in mr["dimensions"].items():
            members = OrderedDict()
            for row in rows:
                if row.get(d["member"]) is not None:
                    members[str(row[d["member"]])] = row.get(d["label"]) or str(row[d["member"]])
            dims.append({"dimensionID": dim_id, "dimensionType": d["type"], "labels": _lm(d["type"]),
                         "members": [{"dimensionMemberID": k, "labels": _lm(v), "nature": "presentation"}
                                     for k, v in sorted(members.items())]})
        metric = {"dimensionID": "dim.metric", "dimensionType": "Metric", "labels": _lm("Metric"),
                  "isMeasureDefining": True,
                  "members": [{"dimensionMemberID": mid, "labels": _lm(m["label"]), "nature": "measure",
                               "measure": {"measureType": m["measureType"]}, "unitOfMeasure": {"code": m["unit"]},
                               "precision": {"decimalPlaces": m["decimals"]}} for mid, m in mr["measures"].items()]}
        definition = {
            "reportDefinitionId": mr["reportDefinitionId"], "reportDefinitionName": _lm(mr["label"]),
            "description": _lm(r["description"]), "version": rep["definition_version"],
            "organisation": org, "responsibilities": resp, "region": rep["region"],
            "reportLabel": _lm(mr["label"]),
            "reportKind": {"type": "Public Sector", "label": _lm("Student Enrolment & Load Reporting")},
            "languages": ["en"], "defaultMeasure": {"measureType": "students"},
            "requiredDimensions": list(mr["dimensions"]) + ["dim.metric"],
            "dimensions": dims + [metric],
        }
        definitions.append((f"reportdefinition.{mr['reportDefinitionId']}.json", definition))
        by_period = defaultdict(list)
        for row in rows:
            by_period[tuple(row[c] for c in mr["period_columns"])].append(row)
        for period, prow in sorted(by_period.items(), key=lambda kv: [str(x) for x in kv[0]]):
            code = "-".join(str(p) for p in period)
            start, end = period_dates.get(period, (None, None))
            facts = []
            for row in prow:
                base = {dim_id: str(row[d["member"]]) for dim_id, d in mr["dimensions"].items()}
                for mid, m in mr["measures"].items():
                    facts.append({"amount": _num(row[m["column"]], m["decimals"]),
                                  "dimensions": dict(base, **{"dim.metric": mid})})
            factdata.append((f"factdata.{mr['reportDefinitionId']}.{code}.json", {
                "factDataId": f"{mr['reportDefinitionId']}.{code}", "version": "1.0",
                "reportDefinitionId": mr["reportDefinitionId"], "reportDefinitionVersion": rep["definition_version"],
                "region": rep["region"], "organisation": org, "responsibilities": resp,
                "reportCreationDate": created, "reportingAsOfDate": as_of_date,
                "reportingPeriod": {"startDate": str(start or f"{period[0]}-01-01"), "endDate": str(end or f"{period[0]}-12-31"),
                                    "code": code, "label": _lm(code)},
                "languages": ["en"], "facts": facts,
                "notes": _lm(f"Generated from Callista via the UC MCDS pipeline (extract as at {as_of_date}). "
                             "Headcount is distinct students and is not additive across members."),
            }))
    return definitions, factdata


def _semantic(definition, fd):
    errs = []
    for key in ("reportDefinitionId", "region"):
        if definition.get(key) != fd.get(key):
            errs.append(f"{key} mismatch")
    if definition.get("version") != fd.get("reportDefinitionVersion"):
        errs.append("reportDefinitionVersion mismatch")
    dims = {d["dimensionID"]: {m["dimensionMemberID"] for m in d["members"]} for d in definition["dimensions"]}
    seen = set()
    for i, f in enumerate(fd["facts"]):
        for d_id in definition["requiredDimensions"]:
            if d_id not in f["dimensions"]:
                errs.append(f"fact {i}: missing dimension {d_id}")
        for d_id, m in f["dimensions"].items():
            if m not in dims.get(d_id, set()):
                errs.append(f"fact {i}: unknown member {d_id}={m}")
        k = tuple(sorted(f["dimensions"].items()))
        if k in seen:
            errs.append(f"fact {i}: duplicate cell")
        seen.add(k)
        if len(errs) > 20:
            break
    return errs


def validate_artefacts(mcds_root, definitions, factdata):
    schemas = SchemaSet(mcds_root)
    v_def = schemas.validator("reporting/schemas/reporting-reportdefinition.schema.json")
    v_fact = schemas.validator("reporting/schemas/reporting-factdata.schema.json")
    by_id, out = {}, []
    for name, d in definitions:
        by_id[d["reportDefinitionId"]] = d
        out.append({"name": name, "errors": errors(v_def, d)})
    for name, f in factdata:
        errs = errors(v_fact, f) + [{"path": "(semantic)", "message": m}
                                    for m in _semantic(by_id[f["reportDefinitionId"]], f)]
        out.append({"name": name, "errors": errs})
    return out
