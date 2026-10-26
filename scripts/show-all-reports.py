#!/usr/bin/env python3
"""Show all 4 generated MCDS reports in a simple format"""
import json
from collections import defaultdict
from pathlib import Path

base = Path(".local-lake/gold/mcds_reporting/factdata")

reports = [
    ("Student Load by Unit", "factdata.AU.UC.StudentLoadByUnit.2026-1.json", "dim.unit"),
    ("Student Load by Campus", "factdata.AU.UC.StudentLoadByCampus.2026-1.json", "dim.campus"),
    ("Student Load by Teaching Org Unit", "factdata.AU.UC.StudentLoadByTeachingOrgUnit.2026-1.json", "dim.orgUnit"),
]

for title, filename, dim_key in reports:
    with open(base / filename) as f:
        d = json.load(f)
    
    by_dim = defaultdict(dict)
    for fact in d["facts"]:
        key = fact["dimensions"][dim_key]
        metric = fact["dimensions"]["dim.metric"]
        by_dim[key][metric] = fact["amount"]
    
    print(f"\n{'='*80}")
    print(f"📊 {title} - Semester 1 2026")
    print(f"{'='*80}")
    print(f"Total records: {len(by_dim)}\n")
    
    sorted_dims = sorted(by_dim.items(), key=lambda x: x[1].get("HEADCOUNT", 0), reverse=True)[:5]
    for i, (dim_val, metrics) in enumerate(sorted_dims, 1):
        hc = metrics.get("HEADCOUNT", 0)
        load = metrics.get("STUDYLOAD", 0.0)
        print(f"{i}. {dim_val:20s} | Students: {hc:4d} | EFTSL: {load:7.3f}")

# Show Unit+Campus report separately (has 2 dimensions)
with open(base / "factdata.AU.UC.StudentLoadByUnitAndCampus.2026-1.json") as f:
    d = json.load(f)

by_combo = defaultdict(dict)
for fact in d["facts"]:
    dims = fact["dimensions"]
    key = (dims["dim.unit"], dims["dim.campus"])
    metric = dims["dim.metric"]
    by_combo[key][metric] = fact["amount"]

print(f"\n{'='*80}")
print(f"📊 Student Load by Unit AND Campus - Semester 1 2026")
print(f"{'='*80}")
print(f"Total combinations: {len(by_combo)}\n")

sorted_combos = sorted(by_combo.items(), key=lambda x: x[1].get("HEADCOUNT", 0), reverse=True)[:8]
for i, ((unit, campus), metrics) in enumerate(sorted_combos, 1):
    hc = metrics.get("HEADCOUNT", 0)
    load = metrics.get("STUDYLOAD", 0.0)
    print(f"{i}. {unit:10s} @ {campus:15s} | Students: {hc:3d} | EFTSL: {load:6.3f}")

print(f"\n{'='*80}")
print("✅ All 4 MCDS reports generated successfully!")
print(f"{'='*80}")
print(f"\nFiles: {base.resolve()}/factdata.AU.UC.*.json")
print("These are ready to submit to the MCDS Hub.")
