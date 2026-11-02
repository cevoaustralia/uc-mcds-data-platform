"""
MCDS v2.1.1 conformance (SOW D2): render Silver rows to MCDS JSON and validate each record against
its own MCDS definition (e.g. student-management.schema.json#/$defs/unitOfLearningEnrolment).

Rendering is driven by the entity YAML:
  columns.<col>.mcds        dotted MCDS path ("studentName.lastName", "x-additional.eftsl")
  columns.<col>.mcds_wrap   optional wrapper: languageMap -> {"en": value}
  columns.<col>.mcds_cast   optional: string (e.g. MCDS year is a string; Silver keeps it numeric)
  mcds.unique_ids_field     adds [{organisationUniqueID, systemID, entityID}] from pipeline.yaml identity
  mcds.unique_ids_type      'organisation' for organisationUniqueIDs ([{organisationUniqueIDType, organisationID}])
  mcds.embed                MCDS fields that hold a full nested object (e.g. unitOfLearningAvailability):
                            {field: {entity, key}} - the embedded entity is rendered the same way.
Silver stays relational; the nested JSON is assembled only for validation (Structures deck, slide 17).

Known MCDS v2.1.1 package defect handled here: reporting-factdata.schema.json references
"reporting.reportdefinition.schema.json" but the file is "reporting-reportdefinition.schema.json".
"""

import datetime as dt
import decimal
import glob
import hashlib
import json
import os

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


# ------------------------------------------------------------------------------------------------
# schema registry (local folder; Glue jobs download the S3 copy first)
# ------------------------------------------------------------------------------------------------
def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def verify_checksums(mcds_root):
    """Problems list (empty = schema files match the package manifest)."""
    manifest = os.path.join(mcds_root, "MCDS-v2.1.1-package-manifest.json")
    if not os.path.exists(manifest):
        return ["package manifest not found (checksums not verified)"]
    problems = []
    for entry in _load(manifest)["schemas"]:
        path = os.path.join(mcds_root, entry["path"])
        if not os.path.exists(path):
            continue                    # only the schemas the pipeline needs are shipped
        digest = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
        if digest != entry["checksum"]:
            problems.append(f"checksum mismatch: {entry['path']}")
    return problems


def fetch_schema_root(uri, tmp="/tmp/mcds"):
    """Glue jobs: copy an s3:// schema bundle (file) or package (prefix) to local disk."""
    if not uri.startswith("s3://"):
        return uri
    import boto3
    bucket, _, key = uri[5:].partition("/")
    s3 = boto3.client("s3")
    if key.endswith(".json"):
        dest = os.path.join(tmp, os.path.basename(key))
        os.makedirs(tmp, exist_ok=True)
        s3.download_file(bucket, key, dest)
        return dest
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=key.rstrip("/") + "/"):
        for o in page.get("Contents", []):
            dest = os.path.join(tmp, os.path.relpath(o["Key"], key.rstrip("/")))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            s3.download_file(bucket, o["Key"], dest)
    return tmp


class SchemaSet:
    """MCDS schemas from either the compiled bundle (one .json file, see scripts/compile_mcds_bundle.py)
    or the full package folder. validator(ref) takes 'curriculum.schema.json#/$defs/unitOfLearning' or
    'reporting/schemas/reporting-factdata.schema.json'."""

    def __init__(self, root):
        self.root = root
        self.bundle = root.endswith(".json")
        if self.bundle:
            doc = _load(root)
            self.index = doc["x-index"]
            self.provenance = doc.get("x-provenance", {})
            self.registry = Registry().with_resource(doc["$id"], Resource.from_contents(doc))
            self.base = doc["$id"]
        else:
            self.registry = build_registry(root)

    def validator(self, ref):
        if self.bundle:
            if ref not in self.index:
                raise KeyError(f"{ref} is not in the compiled MCDS bundle - re-run scripts/compile_mcds_bundle.py")
            target = self.base + self.index[ref]
        else:
            target = os.path.basename(ref.split("#")[0]) + (("#" + ref.split("#", 1)[1]) if "#" in ref else "")
        return Draft202012Validator({"$ref": target}, registry=self.registry, format_checker=FormatChecker())

    def checksum_problems(self):
        if self.bundle:
            return [] if self.provenance.get("sourceFiles") else ["bundle has no provenance"]
        return verify_checksums(self.root)


def build_registry(mcds_root):
    reg = Registry()
    files = glob.glob(os.path.join(mcds_root, "schemas", "**", "*.schema.json"), recursive=True) + \
        glob.glob(os.path.join(mcds_root, "reporting", "schemas", "*.schema.json"))
    for path in files:
        contents = _load(path)
        res = Resource.from_contents(contents)
        name = os.path.basename(path)
        rel = os.path.relpath(path, os.path.join(mcds_root, "schemas")).replace(os.sep, "/")
        aliases = {name, rel, f"../../schemas/{name}", f"schemas/{name}"}
        if contents.get("$id"):
            aliases.add(contents["$id"])
        if name == "reporting-reportdefinition.schema.json":
            aliases.add("reporting.reportdefinition.schema.json")   # package defect workaround
        for a in aliases:
            reg = reg.with_resource(a, res)
    return reg


def errors(v, instance, limit=20):
    out = []
    for e in sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))[:limit]:
        out.append({"path": "/".join(str(p) for p in e.absolute_path) or "<root>", "message": e.message[:300]})
    return out


# ------------------------------------------------------------------------------------------------
# rendering
# ------------------------------------------------------------------------------------------------
def _json_value(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def _set(doc, path, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


class Renderer:
    """Renders rows of configured entities to MCDS JSON documents."""

    def __init__(self, cfg, rows_by_entity):
        self.cfg = cfg
        self.rows = rows_by_entity          # {entity: [dict rows]}
        self._index = {}
        ident = cfg.settings["identity"]
        org = {k: v for k, v in ident["organisation_unique_id"].items() if k != "confirmed"}
        self._org = org
        self._system = ident["system_id"]

    def _lookup(self, entity, key_col):
        k = (entity, key_col)
        if k not in self._index:
            self._index[k] = {r[key_col]: r for r in self.rows[entity]}
        return self._index[k]

    def render(self, entity, row, depth=0):
        e = self.cfg.entities[entity]
        mcds = e.get("mcds") or {}
        doc = {}
        for col, spec in e["columns"].items():
            path = spec.get("mcds")
            val = _json_value(row.get(col))
            if not path or val is None:
                continue
            if spec.get("mcds_cast") == "string":
                val = str(val)
            if spec.get("mcds_wrap") == "languageMap":
                val = {"en": str(val)}
            _set(doc, path, val)
        if mcds.get("unique_ids_field"):
            pk = "|".join(str(row[c]) for c in e["primary_key"])
            if mcds.get("unique_ids_type") == "organisation":
                # organisationUniqueIDs hold organisationUniqueID items (issuer type + id), not entityUniqueID
                doc[mcds["unique_ids_field"]] = [{"organisationUniqueIDType": f"{self._system}:{entity}", "organisationID": pk}]
            else:
                doc[mcds["unique_ids_field"]] = [{"organisationUniqueID": dict(self._org), "systemID": self._system,
                                                  "entityID": pk}]
        for field, emb in (mcds.get("embed") or {}).items():
            if depth > 3:
                break
            child_entity = emb["entity"]
            child_key = self.cfg.entities[child_entity]["primary_key"][0]
            ref_val = row.get(emb.get("key", child_key))
            child = self._lookup(child_entity, child_key).get(ref_val)
            if child is not None:
                doc[field] = self.render(child_entity, child, depth + 1)
        return doc


def validate_entities(spark, cfg, mcds_root, sample=0):
    """Render and validate every entity with an mcds block. Returns (summary rows, DQ results)."""
    import mcds_dq as DQ
    entities = [n for n, e in cfg.entities.items() if (e.get("mcds") or {}).get("definition")]
    needed = set(entities)
    for n in entities:
        for emb in ((cfg.entities[n]["mcds"].get("embed")) or {}).values():
            needed.add(emb["entity"])
    # embedded entities are needed in full; validated entities may be sampled
    rows = {}
    for n in needed:
        df = spark.table(f"silver__{n}")
        if sample and n in entities and not any(
                n == emb["entity"] for m in entities for emb in ((cfg.entities[m]["mcds"].get("embed")) or {}).values()):
            df = df.orderBy(*cfg.entities[n]["primary_key"]).limit(sample)
        rows[n] = [r.asDict(recursive=True) for r in df.collect()]
    schemas = SchemaSet(mcds_root)
    renderer = Renderer(cfg, rows)
    summary, results = [], []
    for n in entities:
        m = cfg.entities[n]["mcds"]
        v = schemas.validator(f"{m['schema']}#/$defs/{m['definition']}")
        recs = rows[n][:sample] if sample else rows[n]
        bad, first = 0, None
        for r in recs:
            errs = errors(v, renderer.render(n, r), limit=3)
            if errs:
                bad += 1
                first = first or {"key": "|".join(str(r[c]) for c in cfg.entities[n]["primary_key"]), "errors": errs}
        summary.append({"entity": n, "mcds_definition": f"{m['schema']}#/$defs/{m['definition']}",
                        "records_validated": len(recs), "records_invalid": bad,
                        "first_error": json.dumps(first)[:1000] if first else ""})
        sev = "fail" if cfg.settings["mcds"].get("fail_on_invalid", True) else "warn"
        results.append(DQ._result(f"silver_{n}_mcds_conformance", "silver", sev,
                                  f"{n}: records valid against MCDS {m['definition']} ({len(recs)} validated)"
                                  + (f"; first error {first['errors'][0]['path']}: {first['errors'][0]['message']}" if first else ""),
                                  bad, table=n))
    return summary, results


def sample_documents(cfg, rows, entity, n=3):
    """A few rendered documents for an entity (for docs/demo)."""
    return [Renderer(cfg, rows).render(entity, r) for r in rows[entity][:n]]
