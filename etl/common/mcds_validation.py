"""
MCDS v2.1.1 conformance validation (SOW D2 "MCDS conformance validated against representative data").

Two artefact types are validated:
  1. Student-domain payloads (students, unitsOfLearning, locations, learningPeriods, ...)
     against schemas/studentlifecycle.schema.json, with every cross-file $ref resolved and
     `format` (date, date-time, email) enforced.
     NOTE: validating against parties.schema.json (as earlier docs proposed) is meaningless:
     that file has only $defs and no root constraints, so ANY JSON passes.
  2. Reporting Framework artefacts (Report Definition + Fact Data) against
     reporting/schemas/*.schema.json, plus the framework's cross-file semantic checks
     (file integrity, dimension integrity, cell rules, measure-defining dimension).

Before validating, schema files are verified against the SHA-256 checksums in
MCDS-v2.1.1-package-manifest.json.

Known MCDS v2.1.1 package defect handled here: reporting-factdata.schema.json references
"reporting.reportdefinition.schema.json" but the file is named
"reporting-reportdefinition.schema.json", so the package's own validate_mega.py fails on
the package's own sample. We register the schema under both names.
"""

import glob
import hashlib
import json
import os

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def verify_checksums(mcds_root):
    """Return list of problems (empty = all schema files match the package manifest)."""
    manifest = os.path.join(mcds_root, "MCDS-v2.1.1-package-manifest.json")
    if not os.path.exists(manifest):
        return [f"package manifest not found: {manifest}"]
    problems = []
    for entry in _load(manifest)["schemas"]:
        path = os.path.join(mcds_root, entry["path"])
        if not os.path.exists(path):
            problems.append(f"missing schema file: {entry['path']}")
            continue
        digest = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
        if digest != entry["checksum"]:
            problems.append(f"checksum mismatch: {entry['path']}")
    return problems


def build_registry(mcds_root):
    reg = Registry()
    files = glob.glob(os.path.join(mcds_root, "schemas", "*.schema.json")) + \
        glob.glob(os.path.join(mcds_root, "reporting", "schemas", "*.schema.json"))
    for path in files:
        contents = _load(path)
        res = Resource.from_contents(contents)
        name = os.path.basename(path)
        aliases = {name, f"../../schemas/{name}", f"schemas/{name}"}
        if contents.get("$id"):
            aliases.add(contents["$id"])
        if name == "reporting-reportdefinition.schema.json":
            aliases.add("reporting.reportdefinition.schema.json")   # package defect workaround
        for a in aliases:
            reg = reg.with_resource(a, res)
    return reg


def _validator(registry, ref):
    return Draft202012Validator({"$ref": ref}, registry=registry, format_checker=FormatChecker())


def _errors(validator, instance, limit=50):
    out = []
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))[:limit]:
        out.append({"path": "/".join(str(p) for p in e.absolute_path) or "<root>", "message": e.message[:300]})
    return out


def validate_student_documents(mcds_root, documents):
    """documents: list of (name, dict). Returns list of {name, valid, errors}."""
    v = _validator(build_registry(mcds_root), "studentlifecycle.schema.json")
    results = []
    for name, doc in documents:
        errs = _errors(v, doc)
        results.append({"name": name, "valid": not errs, "errors": errs})
    return results


def _semantic_checks(definition, factdata):
    errs = []
    for key in ("reportDefinitionId", "region"):
        if definition.get(key) != factdata.get(key):
            errs.append(f"{key} mismatch: definition={definition.get(key)!r} factdata={factdata.get(key)!r}")
    if definition.get("version") != factdata.get("reportDefinitionVersion"):
        errs.append("reportDefinitionVersion does not match definition version")
    dims = {d["dimensionID"]: {m["dimensionMemberID"]: m for m in d["members"]} for d in definition["dimensions"]}
    required = definition.get("requiredDimensions") or list(dims)
    measure_defining = [d["dimensionID"] for d in definition["dimensions"] if d.get("isMeasureDefining")]
    if len(measure_defining) > 1:
        errs.append(f"more than one isMeasureDefining dimension: {measure_defining}")
    disabled = [r["selector"] for r in definition.get("cellRules", []) if r.get("status") == "disabled"]
    seen = set()
    for i, fact in enumerate(factdata.get("facts", [])):
        fd = fact.get("dimensions", {})
        for rd in required:
            if rd not in fd:
                errs.append(f"fact {i}: missing required dimension {rd}")
        for d_id, m_id in fd.items():
            if d_id not in dims:
                errs.append(f"fact {i}: unknown dimension {d_id}")
            elif m_id not in dims[d_id]:
                errs.append(f"fact {i}: unknown member {m_id} in {d_id}")
            elif dims[d_id][m_id].get("nature") in ("derived", "check"):
                errs.append(f"fact {i}: derived/check member {m_id} must not be reported as a fact")
        for sel in disabled:
            if all(fd.get(k) == v for k, v in sel.items()):
                errs.append(f"fact {i}: reported in a disabled cell {sel}")
        key = tuple(sorted(fd.items()))
        if key in seen:
            errs.append(f"fact {i}: duplicate fact for the same cell {dict(key)}")
        seen.add(key)
        if len(errs) > 50:
            break
    return errs


def validate_reporting(mcds_root, definitions, factdata):
    """definitions/factdata: lists of (name, dict). Returns list of {name, valid, errors}."""
    reg = build_registry(mcds_root)
    v_def = _validator(reg, "reporting-reportdefinition.schema.json")
    v_fact = _validator(reg, "reporting-factdata.schema.json")
    by_id = {}
    results = []
    for name, d in definitions:
        errs = _errors(v_def, d)
        by_id[d.get("reportDefinitionId")] = d
        results.append({"name": name, "valid": not errs, "errors": errs})
    for name, f in factdata:
        errs = _errors(v_fact, f)
        definition = by_id.get(f.get("reportDefinitionId"))
        if definition is None:
            errs.append({"path": "reportDefinitionId", "message": "no matching Report Definition"})
        else:
            errs += [{"path": "(semantic)", "message": m} for m in _semantic_checks(definition, f)]
        results.append({"name": name, "valid": not errs, "errors": errs})
    return results
