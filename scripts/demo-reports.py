#!/usr/bin/env python3
"""Demo script: Show all 4 generated MCDS reports"""
import json
from collections import defaultdict
from pathlib import Path

def show_student_load_by_unit(base_path):
    path = base_path / "factdata.AU.UC.StudentLoadByUnit.2026-1.json"
    with open(path) as f:
        d = json.load(f)
    
    by_unit = defaultdict(dict)
    for fact in d["facts"]:
        unit = fact["dimensions"]["dim.unit"]
        metric = fact["dimensions"]["dim.metric"]
        by_unit[unit][metric] = fact["amount"]
    
    print("\n" + "="*80)
    print("📊 Report 1: Student Load by Unit - Semester 1 2026")
    print("="*80)
    print(f"Total units: {len(by_unit)}")
    print("\nTop 5 units by student count:\n")
    sorted_units = sorted(by_unit.items(), key=lambda x: x[1].get("HEADCOUNT", 0), reverse=True)[:5]
    for i, (unit, metrics) in enumerate(sorted_units, 1):
        print(f"{i}. Unit: {unit:10s} | Students: {metrics.get('HEADCOUNT', 0):3d} | EFTSL: {metrics.get('STUDYLOAD', 0):6.3f}")

def show_student_load_by_campus(base_path):
    path = base_path / "factdata.AU.UC.StudentLoadByCampus.2026-1.json"
    with open(path) as f:
        d = json.load(f)
    
    by_campus = defaultdict(dict)
    for fact in d["facts"]:
        campus = fact["dimensions"]["dim.location"]
        metric = fact["dimensions"]["dim.metric"]
        by_campus[campus][metric] = fact["amount"]
    
    print("\n" + "="*80)
    print("📊 Report 2: Student Load by Campus - Semester 1 2026")
    print("="*80)
    print(f"Total campuses: {len(by_campus)}\n")
    for i, (campus, metrics) in enumerate(by_campus.items(), 1):
        print(f"{i}. Campus: {campus:15s} | Students: {metrics.get('HEADCOUNT', 0):3d} | EFTSL: {metrics.get('STUDYLOAD', 0):6.3f}")

def show_student_load_by_org_unit(base_path):
    path = base_path / "factdata.AU.UC.StudentLoadByTeachingOrgUnit.2026-1.json"
    with open(path) as f:
        d = json.load(f)
    
    by_org = defaultdict(dict)
    for fact in d["facts"]:
        org = fact["dimensions"]["dim.organisationUnit"]
        metric = fact["dimensions"]["dim.metric"]
        by_org[org][metric] = fact["amount"]
    
    print("\n" + "="*80)
    print("📊 Report 3: Student Load by Teaching Org Unit - Semester 1 2026")
    print("="*80)
    print(f"Total org units: {len(by_org)}\n")
    for i, (org, metrics) in enumerate(by_org.items(), 1):
        print(f"{i}. Org: {org:15s} | Students: {metrics.get('HEADCOUNT', 0):3d} | EFTSL: {metrics.get('STUDYLOAD', 0):6.3f}")

def show_student_load_by_unit_campus(base_path):
    path = base_path / "factdata.AU.UC.StudentLoadByUnitAndCampus.2026-1.json"
    with open(path) as f:
        d = json.load(f)
    
    by_combo = defaultdict(dict)
    for fact in d["facts"]:
        dims = fact["dimensions"]
        key = (dims["dim.unit"], dims["dim.location"])
        metric = dims["dim.metric"]
        by_combo[key][metric] = fact["amount"]
    
    print("\n" + "="*80)
    print("📊 Report 4: Student Load by Unit AND Campus - Semester 1 2026")
    print("="*80)
    print(f"Total combinations: {len(by_combo)}")
    print("\nTop 5 unit-campus combinations by student count:\n")
    sorted_combos = sorted(by_combo.items(), key=lambda x: x[1].get("HEADCOUNT", 0), reverse=True)[:5]
    for i, ((unit, campus), metrics) in enumerate(sorted_combos, 1):
        print(f"{i}. {unit:10s} @ {campus:15s} | Students: {metrics.get('HEADCOUNT', 0):3d} | EFTSL: {metrics.get('STUDYLOAD', 0):6.3f}")

if __name__ == "__main__":
    base_path = Path(".local-lake/gold/mcds_reporting/factdata")
    
    show_student_load_by_unit(base_path)
    show_student_load_by_campus(base_path)
    show_student_load_by_org_unit(base_path)
    show_student_load_by_unit_campus(base_path)
    
    print("\n" + "="*80)
    print("✅ All 4 MCDS reports generated successfully!")
    print("="*80)
    print(f"\nReport files location:")
    print(f"  {base_path.resolve()}/")
    print("\nThese JSON files are ready to submit to the MCDS Hub.")
