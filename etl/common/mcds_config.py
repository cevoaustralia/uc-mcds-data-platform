"""
Config loading for the config-driven MCDS pipeline.

All behaviour comes from YAML under pipeline/ (see pipeline/pipeline.yaml). The same loader reads a
local directory (tests, local runs) or an s3:// prefix (Glue jobs; CI syncs pipeline/ to S3), so a new
entity or report is deployed by pushing a YAML file - no code or infrastructure change.
"""

import os
import re
from collections import OrderedDict

import yaml

TOKEN = re.compile(r"\$\{([A-Za-z0-9_.\-]+)\}")
LAYER_REF = re.compile(r"\b(bronze|silver|gold)\.([A-Za-z_][A-Za-z0-9_]*)\b")


# ------------------------------------------------------------------------------------------------
# reading files from a local folder or S3
# ------------------------------------------------------------------------------------------------
def _split_s3(uri):
    bucket, _, key = uri[5:].partition("/")
    return bucket, key


def list_files(root, subdir, suffix=".yaml"):
    """Sorted list of file paths/URIs under root/subdir ending with suffix."""
    if root.startswith("s3://"):
        import boto3
        bucket, prefix = _split_s3(root.rstrip("/") + "/" + subdir.strip("/") + "/")
        s3 = boto3.client("s3")
        keys = []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(suffix)]
        return [f"s3://{bucket}/{k}" for k in sorted(keys)]
    folder = os.path.join(root, subdir)
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.endswith(suffix)]


def read_text(path):
    if path.startswith("s3://"):
        import boto3
        bucket, key = _split_s3(path)
        return boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_yaml(path):
    return yaml.safe_load(read_text(path)) or {}


def join_path(root, *parts):
    if root.startswith("s3://"):
        return "/".join([root.rstrip("/")] + [p.strip("/") for p in parts])
    return os.path.join(root, *parts)


# ------------------------------------------------------------------------------------------------
# the config bundle
# ------------------------------------------------------------------------------------------------
class PipelineConfig:
    """Everything under pipeline/, validated and ready for the engine."""

    def __init__(self, root):
        self.root = root
        self.settings = read_yaml(join_path(root, "pipeline.yaml"))
        self.sources = {}
        for f in list_files(root, "sources"):
            doc = read_yaml(f)
            for name, t in doc["tables"].items():
                t["system"] = doc.get("system", "source")
                self.sources[name] = t
        self.rules = {os.path.basename(f)[:-5]: read_yaml(f) for f in list_files(root, "rules")}
        self.crosswalks = {}
        for f in list_files(root, "crosswalks"):
            doc = read_yaml(f)
            self.crosswalks[doc["name"]] = doc
        self.entities = OrderedDict()
        for f in list_files(root, "silver"):
            doc = read_yaml(f)
            self.entities[doc["entity"]] = doc
        self.reports = OrderedDict()
        for f in list_files(root, "gold"):
            doc = read_yaml(f)
            self.reports[doc["report"]] = doc
        self.dq = {}
        for f in list_files(root, "dq"):
            self.dq[os.path.basename(f)[:-5]] = read_yaml(f).get("rules", [])
        self.validate()

    # tokens --------------------------------------------------------------------------------------
    def namespace(self):
        return {"rules": self.rules, "identity": self.settings.get("identity", {}),
                "settings": self.settings}

    def resolve(self, text, extra=None):
        """Replace ${a.b.c} tokens from rules/identity/settings (and `extra`, e.g. derived exprs)."""
        ns = dict(self.namespace())
        ns.update(extra or {})

        def lookup(m):
            cur = ns
            for part in m.group(1).split("."):
                if not isinstance(cur, dict) or part not in cur:
                    raise KeyError(f"unknown config token ${{{m.group(1)}}}")
                cur = cur[part]
            return str(cur)

        for _ in range(5):          # tokens may expand to text containing tokens
            new = TOKEN.sub(lookup, str(text))
            if new == text:
                break
            text = new
        return text

    # ordering ------------------------------------------------------------------------------------
    @staticmethod
    def _refs(cfg, layer):
        text = yaml.safe_dump(cfg)
        return {name for lay, name in LAYER_REF.findall(text) if lay == layer}

    def _ordered(self, items, layer):
        order, seen = [], set()

        def visit(name, stack=()):
            if name in seen:
                return
            if name in stack:
                raise ValueError(f"circular {layer} dependency: {' -> '.join(stack + (name,))}")
            for dep in sorted(self._refs(items[name], layer) - {name}):
                if dep not in items:
                    raise ValueError(f"{layer}.{dep} referenced by {name} is not configured")
                visit(dep, stack + (name,))
            seen.add(name)
            order.append(name)

        for n in items:
            visit(n)
        return order

    def entity_order(self):
        return self._ordered(self.entities, "silver")

    def report_order(self):
        return self._ordered(self.reports, "gold")

    # validation ----------------------------------------------------------------------------------
    def validate(self):
        problems = []
        for k in ("landing", "layers", "identity", "mcds"):
            if k not in self.settings:
                problems.append(f"pipeline.yaml: missing '{k}'")
        for name, t in self.sources.items():
            for k in ("file", "primary_key", "columns"):
                if k not in t:
                    problems.append(f"sources.{name}: missing '{k}'")
            for col in t.get("primary_key", []):
                if col not in t.get("columns", {}):
                    problems.append(f"sources.{name}: key column {col} not in columns")
        for name, e in self.entities.items():
            for k in ("from", "columns", "primary_key"):
                if k not in e:
                    problems.append(f"silver.{name}: missing '{k}'")
            for col in e.get("primary_key", []):
                if col not in e.get("columns", {}):
                    problems.append(f"silver.{name}: key column {col} not in columns")
            for col, ref in (e.get("foreign_keys") or {}).items():
                ent, _, refcol = ref.partition(".")
                if ent not in self.entities or refcol not in self.entities[ent]["columns"]:
                    problems.append(f"silver.{name}: foreign key {col} -> {ref} does not exist")
            for col, spec in e.get("columns", {}).items():
                if not isinstance(spec, dict) or "expr" not in spec:
                    problems.append(f"silver.{name}.{col}: column needs an 'expr'")
            for fld, emb in ((e.get("mcds") or {}).get("embed") or {}).items():
                if emb["entity"] not in self.entities:
                    problems.append(f"silver.{name}: embed {fld} -> unknown entity {emb['entity']}")
        for name, r in self.reports.items():
            if r.get("type") == "detail":
                if "columns" not in r:
                    problems.append(f"gold.{name}: detail report needs 'columns'")
            elif "measures" not in r or "dimensions" not in r:
                problems.append(f"gold.{name}: aggregate report needs 'dimensions' and 'measures'")
        if problems:
            raise ValueError("Invalid pipeline config:\n  " + "\n  ".join(problems))
        # dependency checks (raise on unknown refs / cycles)
        self.entity_order()
        self.report_order()


def layer_sql(sql):
    """Rewrite bronze.x / silver.x / gold.x references to the engine's temp view names."""
    return LAYER_REF.sub(lambda m: f"{m.group(1)}__{m.group(2)}", sql)
