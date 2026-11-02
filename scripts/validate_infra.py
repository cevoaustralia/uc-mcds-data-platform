"""
Validate the rendered mdaa.yaml and every module config against the MDAA JSON schemas shipped with the
pinned MDAA version (npm package @aws-mdaa/cli -> node_modules/@aws-mdaa/schemas). No AWS access needed.

    npm ci && python scripts/render_mdaa.py --env cevo-aws-mcds --allow-placeholders && python scripts/validate_infra.py

Also checks: every module_configs file exists, Glue job/Lambda source paths exist, and the pipeline
config (pipeline/) is valid.
"""

import json
import os
import re
import sys

import yaml
from jsonschema import Draft7Validator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMAS = os.path.join(ROOT, "node_modules", "@aws-mdaa", "schemas", "@aws-mdaa")


def schema(name):
    path = os.path.join(SCHEMAS, f"{name}.json")
    if not os.path.exists(path):
        sys.exit(f"MDAA schema {name}.json not found - run `npm ci` first")
    return json.load(open(path))


def deep_merge(a, b):
    """Same semantics as MDAA (lodash mergeWith, arrays concatenated) for multiple module_configs."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = deep_merge(a[k], v) if k in a else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    return b


def check(doc, sch, label):
    errs = sorted(Draft7Validator(sch).iter_errors(doc), key=lambda e: list(e.absolute_path))
    for e in errs[:10]:
        print(f"  [FAIL] {label}: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}")
    return not errs


def main():
    ok = True
    mdaa_path = os.path.join(ROOT, "mdaa.yaml")
    if not os.path.exists(mdaa_path):
        sys.exit("mdaa.yaml not found - run scripts/render_mdaa.py first")
    mdaa = yaml.safe_load(open(mdaa_path))
    ok &= check(mdaa, schema("cli"), "mdaa.yaml")
    n = 0
    for dname, dom in mdaa["domains"].items():
        for ename, env in dom["environments"].items():
            for mname, mod in env["modules"].items():
                pkg = mod["module_path"].split("@aws-mdaa/")[1].split("@")[0]
                merged, files_ok = {}, True
                for rel in mod.get("module_configs", []):
                    path = os.path.join(ROOT, rel)
                    if not os.path.exists(path):
                        print(f"  [FAIL] {dname}/{mname}: missing config {rel}")
                        ok = files_ok = False
                        continue
                    merged = deep_merge(merged, yaml.safe_load(open(path)) or {})
                    base = os.path.dirname(path)
                    for ref in re.findall(r"(?:scriptLocation|srcDir|- )\s*:?\s*(\.\./[^\s\"']+)", open(path).read()):
                        if not os.path.exists(os.path.normpath(os.path.join(base, ref))):
                            print(f"  [FAIL] {dname}/{mname}: path not found {ref}")
                            ok = files_ok = False
                good = files_ok and check(merged, schema(pkg), f"{dname}/{mname}")
                ok &= good
                n += 1
                print(f"  [{'PASS' if good else 'FAIL'}] {dname}/{mname} -> @aws-mdaa/{pkg}"
                      f" ({len(mod.get('module_configs', []))} config file(s) merged)")
    sys.path.insert(0, os.path.join(ROOT, "etl", "common"))
    from mcds_config import PipelineConfig
    try:
        PipelineConfig(os.path.join(ROOT, "pipeline"))
        print("  [PASS] pipeline/ config")
    except Exception as exc:
        print(f"  [FAIL] pipeline/ config: {exc}")
        ok = False
    print(f"{'OK' if ok else 'FAILED'}: mdaa.yaml + {n} module configs validated against MDAA schemas")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
