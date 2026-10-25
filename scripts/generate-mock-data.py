#!/usr/bin/env python3
"""
UC MCDS Data Platform - Mock Data Generator
Generates realistic Callista mock data for testing

Tables Generated:
  1. PERSON (50 records) - Student demographics
  2. UNIT_VERSION (10 records) - Unit/course definitions
  3. ORG_UNIT (5 records) - Organizational units/facilities
  4. LOCATION (3 records) - Physical locations
  5. GOVT_STUDENT_LOAD (500 records) - Student enrolment fact table

Output: CSV files in data/mock/landing/callista/YYYY-MM-DD/
"""

import csv
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# Faker for Australian-specific data
try:
    from faker import Faker
    fake = Faker('en_AU')
except ImportError:
    print("ERROR: Faker library not installed. Run: pip install faker")
    exit(1)


# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / 'data' / 'mock' / 'landing' / 'callista' / datetime.now().strftime('%Y-%m-%d')
NUM_PERSONS = 50
NUM_UNITS = 10
NUM_ORG_UNITS = 5
NUM_LOCATIONS = 3
NUM_LOAD_RECORDS = 500

# Random seed for reproducibility
random.seed(42)
Faker.seed(42)


def ensure_output_dir():
    """Create output directory if it doesn't exist"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")


def generate_person_table():
    """Generate PERSON table with Australian demographics"""
    print(f"Generating PERSON table ({NUM_PERSONS} records)...")
    
    persons = []
    for i in range(1, NUM_PERSONS + 1):
        # Australian-specific data
        surname = fake.last_name()
        given_names = f"{fake.first_name()} {fake.first_name()}" if random.random() > 0.7 else fake.first_name()
        
        # Birth date: students aged 18-55
        birth_dt = fake.date_of_birth(minimum_age=18, maximum_age=55).strftime('%Y-%m-%d')
        
        # Email using UC domain
        email_addr = f"{given_names.split()[0].lower()}.{surname.lower()}{random.randint(1,99)}@uni.canberra.edu.au"
        
        persons.append({
            'PERSON_ID': i,
            'SURNAME': surname,
            'GIVEN_NAMES': given_names,
            'BIRTH_DT': birth_dt,
            'EMAIL_ADDR': email_addr
        })
    
    # Write CSV
    filepath = OUTPUT_DIR / 'PERSON.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['PERSON_ID', 'SURNAME', 'GIVEN_NAMES', 'BIRTH_DT', 'EMAIL_ADDR'])
        writer.writeheader()
        writer.writerows(persons)
    
    print(f"  ✓ Created {filepath} ({len(persons)} rows)")
    return persons


def generate_unit_version_table():
    """Generate UNIT_VERSION table with realistic Australian university units"""
    print(f"Generating UNIT_VERSION table ({NUM_UNITS} records)...")
    
    # Realistic UC unit codes and names
    units_data = [
        ('MATH1001', 'Mathematics 1A', 6.0),
        ('PHYS1101', 'Physics 1 - Fundamentals', 6.0),
        ('CHEM1101', 'Chemistry 1A', 6.0),
        ('BIOL1001', 'Biology 1', 6.0),
        ('COMP1100', 'Introduction to Programming', 6.0),
        ('ECON1001', 'Principles of Economics', 6.0),
        ('ENGL1001', 'Academic Writing', 3.0),
        ('PSYC1001', 'Introduction to Psychology', 6.0),
        ('STAT2001', 'Statistics for Data Science', 6.0),
        ('COMM2001', 'Communication and Media', 6.0),
    ]
    
    units = []
    for i, (code, name, credit_points) in enumerate(units_data[:NUM_UNITS], 1):
        units.append({
            'UNIT_CD': code,
            'UNIT_NAME': name,
            'CREDIT_POINTS': credit_points
        })
    
    # Write CSV
    filepath = OUTPUT_DIR / 'UNIT_VERSION.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['UNIT_CD', 'UNIT_NAME', 'CREDIT_POINTS'])
        writer.writeheader()
        writer.writerows(units)
    
    print(f"  ✓ Created {filepath} ({len(units)} rows)")
    return units


def generate_org_unit_table():
    """Generate ORG_UNIT table with UC faculties/schools"""
    print(f"Generating ORG_UNIT table ({NUM_ORG_UNITS} records)...")
    
    org_units_data = [
        ('FAC_SCI', '2020-01-01'),  # Faculty of Science
        ('FAC_ENG', '2020-01-01'),  # Faculty of Engineering
        ('FAC_ART', '2020-01-01'),  # Faculty of Arts
        ('FAC_BUS', '2020-01-01'),  # Faculty of Business
        ('FAC_EDU', '2020-01-01'),  # Faculty of Education
    ]
    
    org_units = []
    for i, (code, start_date) in enumerate(org_units_data[:NUM_ORG_UNITS], 1):
        org_units.append({
            'ORG_UNIT_CD': code,
            'ORG_UNIT_START_DT': start_date
            # NOTE: Real description column TBD from UC - using start date as placeholder
        })
    
    # Write CSV
    filepath = OUTPUT_DIR / 'ORG_UNIT.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ORG_UNIT_CD', 'ORG_UNIT_START_DT'])
        writer.writeheader()
        writer.writerows(org_units)
    
    print(f"  ✓ Created {filepath} ({len(org_units)} rows)")
    return org_units


def generate_location_table():
    """Generate LOCATION table with UC campuses"""
    print(f"Generating LOCATION table ({NUM_LOCATIONS} records)...")
    
    locations_data = [
        ('BRUCE', 'Bruce Campus'),  # Main campus
        ('REID', 'Reid Campus'),
        ('ONLINE', 'Online'),
    ]
    
    locations = []
    for i, (code, name) in enumerate(locations_data[:NUM_LOCATIONS], 1):
        locations.append({
            'GOVT_LOCATION_CD': code
            # NOTE: Real location name column TBD from UC - placeholder only
        })
    
    # Write CSV
    filepath = OUTPUT_DIR / 'LOCATION.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['GOVT_LOCATION_CD'])
        writer.writeheader()
        writer.writerows(locations)
    
    print(f"  ✓ Created {filepath} ({len(locations)} rows)")
    return locations


def generate_govt_student_load_table(persons, units, org_units, locations):
    """Generate GOVT_STUDENT_LOAD fact table with realistic enrolment patterns"""
    print(f"Generating GOVT_STUDENT_LOAD table ({NUM_LOAD_RECORDS} records)...")
    
    load_records = []
    
    # Semesters
    semesters = ['2024-S1', '2024-S2']
    
    # Unit completion statuses (1=ENROLLED, 2=CONTINUING, 3=COMPLETED, 4=WITHDRAWN - mock values)
    active_statuses = [1, 2]  # Active enrolments only
    all_statuses = [1, 2, 3, 4]
    
    for i in range(NUM_LOAD_RECORDS):
        # Random student
        person = random.choice(persons)
        
        # Random unit
        unit = random.choice(units)
        
        # Random org unit (teaching responsibility)
        org_unit = random.choice(org_units)
        
        # Random location (physical campus)
        location = random.choice(locations)
        
        # Random semester
        semester = random.choice(semesters)
        
        # EFTSU: Realistic Australian values (0.125 to 1.0 in increments of 0.125)
        # Most units are 0.125 (equivalent to 6 credit points / 48 credit points per year)
        eftsu_values = [0.125, 0.25, 0.5, 0.75, 1.0]
        eftsu_weights = [70, 15, 10, 3, 2]  # 70% are 0.125
        eftsu = random.choices(eftsu_values, weights=eftsu_weights)[0]
        
        # Status: 80% active, 20% completed/withdrawn
        status = random.choices(all_statuses, weights=[50, 30, 15, 5])[0]
        
        load_records.append({
            'PERSON_ID': person['PERSON_ID'],
            'UNIT_CD': unit['UNIT_CD'],
            'EFTSU': f"{eftsu:.3f}",
            'TR_ORG_UNIT_CD': org_unit['ORG_UNIT_CD'],
            'GOVT_LOCATION_CD': location['GOVT_LOCATION_CD'],
            'GOVT_SEMESTER': semester,
            'UNIT_COMPLETION_STATUS': status
        })
    
    # Write CSV
    filepath = OUTPUT_DIR / 'GOVT_STUDENT_LOAD.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['PERSON_ID', 'UNIT_CD', 'EFTSU', 'TR_ORG_UNIT_CD', 
                      'GOVT_LOCATION_CD', 'GOVT_SEMESTER', 'UNIT_COMPLETION_STATUS']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(load_records)
    
    print(f"  ✓ Created {filepath} ({len(load_records)} rows)")
    return load_records


def validate_referential_integrity(persons, units, org_units, locations, load_records):
    """Validate that all foreign keys in GOVT_STUDENT_LOAD exist in parent tables"""
    print("\nValidating referential integrity...")
    
    person_ids = {p['PERSON_ID'] for p in persons}
    unit_cds = {u['UNIT_CD'] for u in units}
    org_unit_cds = {o['ORG_UNIT_CD'] for o in org_units}
    location_cds = {l['GOVT_LOCATION_CD'] for l in locations}
    
    errors = []
    
    for i, record in enumerate(load_records, 1):
        if record['PERSON_ID'] not in person_ids:
            errors.append(f"Row {i}: PERSON_ID {record['PERSON_ID']} not in PERSON table")
        if record['UNIT_CD'] not in unit_cds:
            errors.append(f"Row {i}: UNIT_CD {record['UNIT_CD']} not in UNIT_VERSION table")
        if record['TR_ORG_UNIT_CD'] not in org_unit_cds:
            errors.append(f"Row {i}: TR_ORG_UNIT_CD {record['TR_ORG_UNIT_CD']} not in ORG_UNIT table")
        if record['GOVT_LOCATION_CD'] not in location_cds:
            errors.append(f"Row {i}: GOVT_LOCATION_CD {record['GOVT_LOCATION_CD']} not in LOCATION table")
    
    if errors:
        print(f"  ✗ FAILED - {len(errors)} referential integrity errors:")
        for error in errors[:10]:  # Show first 10
            print(f"    {error}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more errors")
        return False
    else:
        print("  ✓ PASSED - All foreign keys valid")
        return True


def print_summary(persons, units, org_units, locations, load_records):
    """Print generation summary"""
    print("\n" + "="*60)
    print("MOCK DATA GENERATION COMPLETE")
    print("="*60)
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"\nRow Counts:")
    print(f"  PERSON:              {len(persons):4d} rows")
    print(f"  UNIT_VERSION:        {len(units):4d} rows")
    print(f"  ORG_UNIT:            {len(org_units):4d} rows")
    print(f"  LOCATION:            {len(locations):4d} rows")
    print(f"  GOVT_STUDENT_LOAD:   {len(load_records):4d} rows")
    print(f"\nTotal Records:         {len(persons) + len(units) + len(org_units) + len(locations) + len(load_records):4d}")
    print(f"\nAll files written to: {OUTPUT_DIR}")
    print("="*60)


def main():
    """Main execution"""
    print("="*60)
    print("UC MCDS MOCK DATA GENERATOR")
    print("="*60)
    print(f"Generating Callista mock data for {NUM_PERSONS} students")
    print(f"Random seed: 42 (for reproducibility)\n")
    
    ensure_output_dir()
    
    # Generate tables
    persons = generate_person_table()
    units = generate_unit_version_table()
    org_units = generate_org_unit_table()
    locations = generate_location_table()
    load_records = generate_govt_student_load_table(persons, units, org_units, locations)
    
    # Validate
    if not validate_referential_integrity(persons, units, org_units, locations, load_records):
        print("\n✗ VALIDATION FAILED - Referential integrity errors found")
        exit(1)
    
    # Summary
    print_summary(persons, units, org_units, locations, load_records)
    
    print("\n✓ SUCCESS - Mock data generated with referential integrity")


if __name__ == '__main__':
    main()
