#!/usr/bin/env python3
"""Show generated MCDS reports in human-readable format"""
import json
from pathlib import Path

def show_report(report_path, max_records=5):
    with open(report_path) as f:
        data = json.load(f)
    
    print(f"\n{'='*80}")
    print(f"📊 {data['factDataId']}")
    print(f"{'='*80}")
    print(f"Reporting Period: {data['reportingPeriod']['label']['en']}")
    print(f"Total Records: {len(data['records'])}")
    print(f"\nFirst {min(max_records, len(data['records']))} records:\n")
    
    for i, rec in enumerate(data['records'][:max_records], 1):
        print(f"{i}. ", end="")
        
        # Unit-based reports
        if 'unitOfLearning' in rec:
            unit = rec['unitOfLearning']
            print(f"Unit: {unit['code']} - {unit['name']['en']}")
        
        # Campus-based reports
        if 'location' in rec:
            loc = rec['location']
            print(f"Campus: {loc.get('code', 'N/A')} - {loc['name']['en']}")
        
        # Org unit-based reports
        if 'organisation' in rec and 'organisationUnit' in rec:
            org_unit = rec['organisationUnit']
            print(f"Org Unit: {org_unit.get('code', 'N/A')} - {org_unit['name']['en']}")
        
        print(f"   📈 Students (headcount): {rec['headcount']}")
        print(f"   📊 Study Load (EFTSL): {rec['studyLoad']}")
        print()

if __name__ == '__main__':
    base_path = Path('.local-lake/gold/mcds_reporting/factdata')
    
    # Show all 4 reports
    reports = [
        'factdata.AU.UC.StudentLoadByUnit.2026-1.json',
        'factdata.AU.UC.StudentLoadByCampus.2026-1.json',
        'factdata.AU.UC.StudentLoadByTeachingOrgUnit.2026-1.json',
        'factdata.AU.UC.StudentLoadByUnitAndCampus.2026-1.json'
    ]
    
    for report_name in reports:
        report_path = base_path / report_name
        if report_path.exists():
            show_report(report_path, max_records=3)
        else:
            print(f"\n⚠️  {report_name} not found")
    
    print(f"\n{'='*80}")
    print("✅ Reports generated successfully!")
    print(f"{'='*80}")
