#!/usr/bin/env python3
"""
Validate MCDS v2.1.1 artefacts produced by the pipeline (SOW D2 conformance evidence).

  python scripts/validate-mcds-json.py --mcds "MCDS - v2.1.1/v2.1.1" \
      --students .local-lake/silver/mcds_json/*.json \
      --definitions .local-lake/gold/mcds_reporting/reportdefinitions/*.json \
      --factdata .local-lake/gold/mcds_reporting/factdata/*.json \
      [--report validation-report.json]

Student payloads are validated against studentlifecycle.schema.json (all $refs resolved,
formats enforced). Reporting artefacts are validated against the MCDS reporting schemas plus
the Reporting Framework's cross-file semantic rules. Schema checksums are verified first.
Exit code 0 only if everything passes.
"""

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl" / "common"))
import mcds_validation as V  # noqa: E402


def expand(patterns):
    files = []
    for p in patterns or []:
        files += sorted(glob.glob(p)) or [p]
    return [(f, json.load(open(f, encoding="utf-8"))) for f in files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcds", default=str(ROOT / "MCDS - v2.1.1" / "v2.1.1"))
    ap.add_argument("--students", nargs="*")
    ap.add_argument("--definitions", nargs="*")
    ap.add_argument("--factdata", nargs="*")
    ap.add_argument("--report")
    a = ap.parse_args()

    out = {"checksums": V.verify_checksums(a.mcds)}
    results = []
    if a.students:
        results += V.validate_student_documents(a.mcds, expand(a.students))
    if a.definitions or a.factdata:
        results += V.validate_reporting(a.mcds, expand(a.definitions), expand(a.factdata))
    out["results"] = results
    print("schema checksums:", "OK" if not out["checksums"] else out["checksums"])
    for r in results:
        print(f"[{'PASS' if r['valid'] else 'FAIL'}] {r['name']}")
        for e in r["errors"][:10]:
            print(f"    {e['path']}: {e['message']}")
    ok = not out["checksums"] and results and all(r["valid"] for r in results)
    print(f"{sum(r['valid'] for r in results)}/{len(results)} artefacts valid")
    if a.report:
        Path(a.report).write_text(json.dumps(out, indent=2), encoding="utf-8")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
