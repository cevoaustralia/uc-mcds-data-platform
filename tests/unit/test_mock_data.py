"""
Unit Tests for Mock Data Generator
Tests for referential integrity, row counts, and data quality
"""

import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime

# Mock data directory (adjust path based on test execution location)
DATA_DIR = Path(__file__).parent.parent.parent / 'data' / 'mock' / 'landing' / 'callista'
LATEST_DATE = datetime.now().strftime('%Y-%m-%d')
DATA_PATH = DATA_DIR / LATEST_DATE


def test_all_csv_files_exist():
    """Test that all 5 CSV files were generated"""
    expected_files = [
        'PERSON.csv',
        'UNIT_VERSION.csv',
        'ORG_UNIT.csv',
        'LOCATION.csv',
        'GOVT_STUDENT_LOAD.csv'
    ]
    
    for filename in expected_files:
        filepath = DATA_PATH / filename
        assert filepath.exists(), f"Missing file: {filename}"


def test_person_row_count():
    """Test PERSON table has expected row count (50)"""
    df = pd.read_csv(DATA_PATH / 'PERSON.csv')
    assert len(df) == 50, f"Expected 50 PERSON rows, got {len(df)}"


def test_unit_version_row_count():
    """Test UNIT_VERSION table has expected row count (10)"""
    df = pd.read_csv(DATA_PATH / 'UNIT_VERSION.csv')
    assert len(df) == 10, f"Expected 10 UNIT_VERSION rows, got {len(df)}"


def test_org_unit_row_count():
    """Test ORG_UNIT table has expected row count (5)"""
    df = pd.read_csv(DATA_PATH / 'ORG_UNIT.csv')
    assert len(df) == 5, f"Expected 5 ORG_UNIT rows, got {len(df)}"


def test_location_row_count():
    """Test LOCATION table has expected row count (3)"""
    df = pd.read_csv(DATA_PATH / 'LOCATION.csv')
    assert len(df) == 3, f"Expected 3 LOCATION rows, got {len(df)}"


def test_govt_student_load_row_count():
    """Test GOVT_STUDENT_LOAD table has expected row count (500)"""
    df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    assert len(df) == 500, f"Expected 500 GOVT_STUDENT_LOAD rows, got {len(df)}"


def test_referential_integrity_person():
    """Test all PERSON_IDs in GOVT_STUDENT_LOAD exist in PERSON table"""
    person_df = pd.read_csv(DATA_PATH / 'PERSON.csv')
    load_df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    
    person_ids = set(person_df['PERSON_ID'])
    load_person_ids = set(load_df['PERSON_ID'])
    
    orphaned = load_person_ids - person_ids
    assert len(orphaned) == 0, f"Found {len(orphaned)} orphaned PERSON_IDs in GOVT_STUDENT_LOAD"


def test_referential_integrity_unit():
    """Test all UNIT_CDs in GOVT_STUDENT_LOAD exist in UNIT_VERSION table"""
    unit_df = pd.read_csv(DATA_PATH / 'UNIT_VERSION.csv')
    load_df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    
    unit_cds = set(unit_df['UNIT_CD'])
    load_unit_cds = set(load_df['UNIT_CD'])
    
    orphaned = load_unit_cds - unit_cds
    assert len(orphaned) == 0, f"Found {len(orphaned)} orphaned UNIT_CDs in GOVT_STUDENT_LOAD"


def test_referential_integrity_org_unit():
    """Test all TR_ORG_UNIT_CDs in GOVT_STUDENT_LOAD exist in ORG_UNIT table"""
    org_unit_df = pd.read_csv(DATA_PATH / 'ORG_UNIT.csv')
    load_df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    
    org_unit_cds = set(org_unit_df['ORG_UNIT_CD'])
    load_org_unit_cds = set(load_df['TR_ORG_UNIT_CD'])
    
    orphaned = load_org_unit_cds - org_unit_cds
    assert len(orphaned) == 0, f"Found {len(orphaned)} orphaned TR_ORG_UNIT_CDs in GOVT_STUDENT_LOAD"


def test_referential_integrity_location():
    """Test all GOVT_LOCATION_CDs in GOVT_STUDENT_LOAD exist in LOCATION table"""
    location_df = pd.read_csv(DATA_PATH / 'LOCATION.csv')
    load_df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    
    location_cds = set(location_df['GOVT_LOCATION_CD'])
    load_location_cds = set(load_df['GOVT_LOCATION_CD'])
    
    orphaned = load_location_cds - location_cds
    assert len(orphaned) == 0, f"Found {len(orphaned)} orphaned GOVT_LOCATION_CDs in GOVT_STUDENT_LOAD"


def test_eftsu_range():
    """Test EFTSU values are within valid range (0.0 to 1.0)"""
    load_df = pd.read_csv(DATA_PATH / 'GOVT_STUDENT_LOAD.csv')
    
    min_eftsu = load_df['EFTSU'].min()
    max_eftsu = load_df['EFTSU'].max()
    
    assert min_eftsu >= 0.0, f"EFTSU min ({min_eftsu}) is below 0.0"
    assert max_eftsu <= 1.0, f"EFTSU max ({max_eftsu}) is above 1.0"


def test_person_no_nulls_in_pk():
    """Test PERSON_ID has no null values"""
    person_df = pd.read_csv(DATA_PATH / 'PERSON.csv')
    null_count = person_df['PERSON_ID'].isna().sum()
    assert null_count == 0, f"Found {null_count} null PERSON_IDs"


def test_unit_no_nulls_in_pk():
    """Test UNIT_CD has no null values"""
    unit_df = pd.read_csv(DATA_PATH / 'UNIT_VERSION.csv')
    null_count = unit_df['UNIT_CD'].isna().sum()
    assert null_count == 0, f"Found {null_count} null UNIT_CDs"


def test_email_format():
    """Test all emails contain @ symbol (basic validation)"""
    person_df = pd.read_csv(DATA_PATH / 'PERSON.csv')
    
    # Check non-null emails contain @
    emails = person_df['EMAIL_ADDR'].dropna()
    invalid = emails[~emails.str.contains('@')]
    
    assert len(invalid) == 0, f"Found {len(invalid)} emails without @ symbol"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
