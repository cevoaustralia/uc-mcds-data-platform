"""
Callista (Oracle SIS_OWNER) landing-table definitions.

Callista data arrives as CSV extracts (one file per table per extract date). Column names,
types and nullability below are taken from the real Callista schema export
(analysis/Sisprod_schema_metadata.csv). Only the columns needed for the EBA scope are
extracted (data minimisation): no birth dates, emails, addresses or other personal data.

`key=True` marks the natural key used for joins and uniqueness. The schema export has no
constraint metadata, so keys are inferred from Callista's design and must be confirmed by the
UC Callista DBA (see Docs/published-docs/05-UC-Requirements-and-Open-Decisions.md).

The specs are plain Python so the mock generator and unit tests can use them without Spark.
"""

# (column, type, nullable_in_source, key)
# types: string | int | long | decimal | date
TABLE_SPECS = {
    # Government student load (census-date load file). Fact table for D5.
    # Grain: student x course x unit attempt x teaching-responsibility org unit x submission.
    "GOVT_STUDENT_LOAD": [
        ("SUBMISSION_YR", "int", False, True),
        ("SUBMISSION_NUMBER", "int", False, True),
        ("PERSON_ID", "long", False, True),
        ("COURSE_CD", "string", False, True),
        ("CRV_VERSION_NUMBER", "int", False, True),
        ("GOVT_SEMESTER", "int", False, True),            # NUMBER(1): 1 or 2 (not "2024-1")
        ("UNIT_CD", "string", False, True),
        ("UV_VERSION_NUMBER", "int", False, True),        # required to join UNIT_VERSION
        ("SUA_CAL_TYPE", "string", False, True),          # teaching calendar of the unit attempt
        ("SUA_CI_SEQUENCE_NUMBER", "int", False, True),
        ("TR_ORG_UNIT_CD", "string", False, True),        # teaching-responsibility org unit
        ("TR_OU_START_DT", "date", False, True),          # required to join ORG_UNIT
        ("DISCIPLINE_GROUP_CD", "string", False, False),
        ("EFTSU", "decimal", False, False),               # load share for this split row
        ("UNIT_COMPLETION_STATUS", "int", False, False),  # TCSI E355: 1 withdrew, 2 failed, 3 completed, 4 in progress, 5 RPL (VET)
        ("GOVT_LOCATION_CD", "string", True, False),      # nullable government code, not the Callista campus code
        ("UPDATE_ON", "date", False, False),
    ],
    # Unit attempts: the real delivery campus (LOCATION_CD) and offering (UOO_ID).
    "STUDENT_UNIT_ATTEMPT": [
        ("PERSON_ID", "long", False, True),
        ("COURSE_CD", "string", False, True),
        ("UNIT_CD", "string", False, True),
        ("VERSION_NUMBER", "int", False, True),
        ("CAL_TYPE", "string", False, True),
        ("CI_SEQUENCE_NUMBER", "int", False, True),
        ("LOCATION_CD", "string", False, False),
        ("UNIT_CLASS", "string", False, False),
        ("UOO_ID", "long", False, False),
        ("UNIT_ATTEMPT_STATUS", "string", False, False),
    ],
    # People. Real PERSON also holds staff/applicants, so Silver keeps only people with load.
    # Names must arrive masked (SOW: no PII). MCDS requires studentName.lastName.
    "PERSON": [
        ("PERSON_ID", "long", False, True),
        ("SURNAME", "string", False, False),
        ("GIVEN_NAMES", "string", True, False),
        ("UPDATE_ON", "date", False, False),
    ],
    # Unit definitions. Key is (UNIT_CD, VERSION_NUMBER), not UNIT_CD alone.
    "UNIT_VERSION": [
        ("UNIT_CD", "string", False, True),
        ("VERSION_NUMBER", "int", False, True),
        ("TITLE", "string", False, False),
        ("SHORT_TITLE", "string", False, False),
        ("UNIT_LEVEL", "string", False, False),
        ("ENROLLED_CREDIT_POINTS", "decimal", True, False),
        ("OWNER_ORG_UNIT_CD", "string", False, False),
        ("OWNER_OU_START_DT", "date", False, False),
        ("UNIT_STATUS", "string", False, False),
        ("START_DT", "date", False, False),
    ],
    # Organisational units (faculties/schools). Key is (ORG_UNIT_CD, START_DT).
    "ORG_UNIT": [
        ("ORG_UNIT_CD", "string", False, True),
        ("START_DT", "date", False, True),
        ("END_DT", "date", True, False),
        ("DESCRIPTION", "string", False, False),
        ("ORG_TYPE", "string", False, False),
        ("ORG_STATUS", "string", False, False),
    ],
    # Delivery locations (campuses, online).
    "LOCATION": [
        ("LOCATION_CD", "string", False, True),
        ("DESCRIPTION", "string", False, False),
        ("LOCATION_TYPE", "string", False, False),
        ("GOVT_LOCATION_CD", "string", True, False),
        ("CLOSED_IND", "string", False, False),
    ],
    # Calendar instances: teaching periods -> MCDS learningPeriod (required by MCDS).
    "CAL_INSTANCE": [
        ("CAL_TYPE", "string", False, True),
        ("SEQUENCE_NUMBER", "int", False, True),
        ("START_DT", "date", False, False),
        ("END_DT", "date", False, False),
        ("ALTERNATE_CODE", "string", True, False),
        ("CAL_STATUS", "string", False, False),
    ],
}

TABLES = list(TABLE_SPECS.keys())

# Columns added by landing-to-bronze
BRONZE_METADATA_COLUMNS = ["_extract_date", "_source_file", "_ingested_at"]


def columns(table):
    return [c[0] for c in TABLE_SPECS[table]]


def key_columns(table):
    return [c[0] for c in TABLE_SPECS[table] if c[3]]


def required_columns(table):
    return [c[0] for c in TABLE_SPECS[table] if not c[2]]


def spark_schema(table):
    """Explicit Spark schema for a landing CSV (no inference). All fields nullable on read;
    required-ness is enforced by data-quality rules so bad rows are reported, not dropped."""
    from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                                   LongType, DecimalType, DateType)
    if table not in TABLE_SPECS:
        raise ValueError(f"Unknown table: {table}. Available: {TABLES}")
    type_map = {"string": StringType(), "int": IntegerType(), "long": LongType(),
                "decimal": DecimalType(12, 6), "date": DateType()}
    return StructType([StructField(n, type_map[t], True) for n, t, _, _ in TABLE_SPECS[table]])
