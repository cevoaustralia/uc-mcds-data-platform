"""
Compile the MCDS schema package into a single, self-contained "intermediate" schema bundle that holds
only the definitions this pipeline uses (and everything they reference), with all cross-file $refs
rewritten to local refs. The pipeline validates against the bundle instead of the full package.

Why: the full v2.1.1 package is 20 domain files / 581 definitions; the pipeline needs a fraction of
them. A compiled bundle is one small file, needs no $ref resolution across files at run time, is
reproducible (provenance + source checksums are stamped into it) and changes only when entities or the
MCDS version change. Re-run after adding an entity with a new MCDS definition.

    python scripts/compile_mcds_bundle.py --package <path to MCDS v2.1.1 package> \
        --out mcds/compiled/mcds-v2.1.1-uc-bundle.json

Roots = every mcds.{schema, definition} in pipeline/silver/*.yaml (+ embedded entities) and the two
reporting schemas when any pipeline/gold/*.yaml has an mcds_report block.
"""

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import posixpath
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "etl", "common"))
from mcds_config import PipelineConfig  # noqa: E402

REPORT_DEF = "reporting/schemas/reporting-reportdefinition.schema.json"
REPORT_FACT = "reporting/schemas/reporting-factdata.schema.json"
ALIASES = {"reporting/schemas/reporting.reportdefinition.schema.json": REPORT_DEF}   # package defect


def bundle_key(file_rel, pointer):
    """Bundle $defs name for <file>#<pointer>, e.g. 'curriculum/unitOfLearning'."""
    base = posixpath.basename(file_rel).replace(".schema.json", "")
    ptr = pointer.replace("/$defs/", "/").strip("/")
    return f"{base}/{ptr}" if ptr else base


def encode(name):          # JSON-pointer escaping for use inside "#/$defs/<name>"
    return name.replace("~", "~0").replace("/", "~1")


class Compiler:
    def __init__(self, package):
        self.package = package
        self.docs = {}
        self.defs = {}
        self.files_used = set()

    def load(self, rel):
        rel = ALIASES.get(rel, rel)
        if rel not in self.docs:
            with open(os.path.join(self.package, rel), encoding="utf-8") as fh:
                self.docs[rel] = json.load(fh)
            self.files_used.add(rel)
        return rel, self.docs[rel]

    @staticmethod
    def resolve_pointer(doc, pointer):
        cur = doc
        for part in [p for p in pointer.split("/") if p]:
            cur = cur[part.replace("~1", "/").replace("~0", "~")]
        return cur

    def add(self, file_rel, pointer):
        file_rel, doc = self.load(file_rel)
        key = bundle_key(file_rel, pointer)
        if key in self.defs:
            return key
        self.defs[key] = None                       # reserve (handles recursion)
        node = copy.deepcopy(self.resolve_pointer(doc, pointer))
        if isinstance(node, dict):
            for k in ("$id", "$schema"):
                node.pop(k, None)
            if not pointer:                         # whole-file root: its $defs are reached via refs
                node.pop("$defs", None)
        self.defs[key] = self.rewrite(node, file_rel)
        return key

    def rewrite(self, node, file_rel):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    target, _, pointer = v.partition("#")
                    if target:
                        target_rel = posixpath.normpath(posixpath.join(posixpath.dirname(file_rel), target))
                    else:
                        target_rel = file_rel
                    out[k] = "#/$defs/" + encode(self.add(target_rel, pointer))
                else:
                    out[k] = self.rewrite(v, file_rel)
            return out
        if isinstance(node, list):
            return [self.rewrite(x, file_rel) for x in node]
        return node


def sha256(path):
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True, help="MCDS v2.1.1 package folder (schemas/, reporting/, manifest)")
    ap.add_argument("--config", default=os.path.join(ROOT, "pipeline"))
    ap.add_argument("--out", default=os.path.join(ROOT, "mcds", "compiled", "mcds-v2.1.1-uc-bundle.json"))
    a = ap.parse_args(argv)

    cfg = PipelineConfig(a.config)
    roots = {}
    for name, e in cfg.entities.items():
        m = e.get("mcds") or {}
        if m.get("definition"):
            roots[f"{m['schema']}#/$defs/{m['definition']}"] = (f"schemas/{m['schema']}", f"/$defs/{m['definition']}")
    if any(r.get("mcds_report") for r in cfg.reports.values()):
        roots[REPORT_DEF] = (REPORT_DEF, "")
        roots[REPORT_FACT] = (REPORT_FACT, "")

    c = Compiler(a.package)
    index = {ref: c.add(f, p) for ref, (f, p) in roots.items()}
    manifest_path = os.path.join(a.package, "MCDS-v2.1.1-package-manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"schemas": []}
    expected = {s["path"]: s["checksum"] for s in manifest["schemas"]}
    sources = {}
    for rel in sorted(c.files_used):
        actual = sha256(os.path.join(a.package, rel))
        if rel in expected and expected[rel] != actual:
            sys.exit(f"checksum mismatch for {rel}: package is not the published v2.1.1 release")
        sources[rel] = actual
    bundle = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:uc-mcds:mcds-v2.1.1-uc-bundle",
        "title": "MCDS v2.1.1 - compiled subset used by the UC MCDS pipeline",
        "x-provenance": {
            "mcdsPackageVersion": manifest.get("header", {}).get("packageVersion", "V2.1.1"),
            "copyright": manifest.get("header", {}).get("copyright", "MCDS Limited"),
            "compiledAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "compiledBy": "scripts/compile_mcds_bundle.py",
            "sourceFiles": sources,
            "definitions": len(c.defs),
        },
        "x-index": {ref: "#/$defs/" + encode(k) for ref, k in index.items()},
        "$defs": c.defs,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=1, ensure_ascii=False, sort_keys=False)
    print(f"bundle: {len(c.defs)} definitions from {len(sources)} schema files -> {a.out} "
          f"({os.path.getsize(a.out) // 1024} KB); roots: {len(index)}")


if __name__ == "__main__":
    main()
