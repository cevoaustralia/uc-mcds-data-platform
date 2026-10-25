"""
Spark Schema Definitions for Callista Tables
Explicit schemas for all 5 Callista tables based on Oracle source
"""

from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    LongType, DateType, DecimalType, TimestampType
)


# PERSON table schema
PERSON_SCHEMA = StructType([
    StructField("PERSON_ID", LongType(), nullable=False),
    StructField("SURNAME", StringType(), nullable=True),
    StructField("GIVEN_NAMES", StringType(), nullable=True),
    StructField("BIRTH_DT", DateType(), nullable=True),
    StructField("EMAIL_ADDR", StringType(), nullable=True)
])

# UNIT_VERSION table schema
UNIT_VERSION_SCHEMA = StructType([
    StructField("UNIT_CD", StringType(), nullable=False),
    StructField("UNIT_NAME", StringType(), nullable=True),
    StructField("CREDIT_POINTS", DecimalType(5, 1), nullable=True)
])

# ORG_UNIT table schema
ORG_UNIT_SCHEMA = StructType([
    StructField("ORG_UNIT_CD", StringType(), nullable=False),
    StructField("ORG_UNIT_START_DT", DateType(), nullable=True)
    # NOTE: Real description column TBD from UC
])

# LOCATION table schema
LOCATION_SCHEMA = StructType([
    StructField("GOVT_LOCATION_CD", StringType(), nullable=False)
    # NOTE: Real location name column TBD from UC
])

# GOVT_STUDENT_LOAD table schema
GOVT_STUDENT_LOAD_SCHEMA = StructType([
    StructField("PERSON_ID", LongType(), nullable=False),
    StructField("UNIT_CD", StringType(), nullable=False),
    StructField("EFTSU", DecimalType(5, 3), nullable=True),
    StructField("TR_ORG_UNIT_CD", StringType(), nullable=True),
    StructField("GOVT_LOCATION_CD", StringType(), nullable=True),
    StructField("GOVT_SEMESTER", StringType(), nullable=True),
    StructField("UNIT_COMPLETION_STATUS", IntegerType(), nullable=True)
])

# Schema registry - maps table names to schemas
SCHEMA_REGISTRY = {
    "PERSON": PERSON_SCHEMA,
    "UNIT_VERSION": UNIT_VERSION_SCHEMA,
    "ORG_UNIT": ORG_UNIT_SCHEMA,
    "LOCATION": LOCATION_SCHEMA,
    "GOVT_STUDENT_LOAD": GOVT_STUDENT_LOAD_SCHEMA
}


def get_schema(table_name):
    """Get schema for a table by name"""
    schema = SCHEMA_REGISTRY.get(table_name)
    if schema is None:
        raise ValueError(f"Unknown table: {table_name}. Available tables: {list(SCHEMA_REGISTRY.keys())}")
    return schema
