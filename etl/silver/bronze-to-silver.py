"""
Bronze to Silver ETL Job
Transform Bronze Callista data to Silver MCDS v2.1.1 format

Input: Parquet tables in mcds_bronze database
Output: MCDS-compliant Parquet in mcds_silver database
"""

import sys
import yaml
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import (
    col, concat, lit, cast, current_timestamp, coalesce,
    md5, concat_ws, when
)

# Job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'INPUT_DATABASE',
    'OUTPUT_BUCKET',
    'OUTPUT_DATABASE'
])

# Initialize contexts
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configuration
INPUT_DATABASE = args['INPUT_DATABASE']
OUTPUT_BUCKET = args['OUTPUT_BUCKET']
OUTPUT_DATABASE = args['OUTPUT_DATABASE']


def transform_student(person_df):
    """Transform PERSON to MCDS student entity"""
    print("Transforming student entity...")
    
    student_df = person_df.select(
        # studentId
        cast(col("PERSON_ID"), "string").alias("studentId"),
        
        # studentNumber - PLACEHOLDER formula from business-rules.yaml
        concat(lit("STU"), cast(col("PERSON_ID"), "string")).alias("studentNumber"),
        
        # Names
        col("GIVEN_NAMES").alias("givenName"),
        col("SURNAME").alias("familyName"),
        
        # Contact
        col("EMAIL_ADDR").alias("email"),
        
        # Demographics
        col("BIRTH_DT").alias("birthDate"),
        
        # Metadata
        current_timestamp().alias("createdAt")
    )
    
    return student_df


def transform_unit_of_learning(unit_version_df):
    """Transform UNIT_VERSION to MCDS unit entity"""
    print("Transforming unit_of_learning entity...")
    
    unit_df = unit_version_df.select(
        col("UNIT_CD").alias("unitCode"),
        col("UNIT_NAME").alias("unitName"),
        col("CREDIT_POINTS").alias("creditPoints"),
        current_timestamp().alias("createdAt")
    )
    
    return unit_df


def transform_location(org_unit_df, location_df):
    """Transform ORG_UNIT/LOCATION to MCDS location entity - PLACEHOLDER"""
    print("Transforming location entity (PLACEHOLDER logic)...")
    
    # PLACEHOLDER: Using ORG_UNIT only (facility field TBD from business-rules.yaml)
    location_mcds_df = org_unit_df.select(
        col("ORG_UNIT_CD").alias("locationCode"),
        cast(col("ORG_UNIT_START_DT"), "string").alias("locationName"),  # PLACEHOLDER
        lit("organizational").alias("locationType"),
        current_timestamp().alias("createdAt")
    )
    
    return location_mcds_df


def transform_student_unit_load(govt_student_load_df):
    """Transform GOVT_STUDENT_LOAD to MCDS student_unit_load fact"""
    print("Transforming student_unit_load fact table...")
    
    load_df = govt_student_load_df.select(
        # Surrogate key
        md5(concat_ws("|", 
            cast(col("PERSON_ID"), "string"),
            col("UNIT_CD"),
            col("GOVT_SEMESTER")
        )).alias("loadId"),
        
        # Foreign keys
        cast(col("PERSON_ID"), "string").alias("studentId"),
        col("UNIT_CD").alias("unitCode"),
        
        # PLACEHOLDER: facility field from business-rules.yaml
        coalesce(col("TR_ORG_UNIT_CD"), col("GOVT_LOCATION_CD")).alias("locationCode"),
        
        # Measures
        col("EFTSU").alias("eftsu"),
        
        # Dimensions
        col("GOVT_SEMESTER").alias("semester"),
        col("UNIT_COMPLETION_STATUS").alias("status"),
        
        # Metadata
        current_timestamp().alias("createdAt")
    ).filter(
        # Filter out records with null keys
        (col("PERSON_ID").isNotNull()) & (col("UNIT_CD").isNotNull())
    )
    
    return load_df


def write_silver_table(df, entity_name, output_path):
    """Write DataFrame to Silver layer as Parquet"""
    print(f"Writing {entity_name} to Silver: {output_path}")
    
    df.write \
        .mode("overwrite") \
        .format("parquet") \
        .option("compression", "snappy") \
        .save(output_path)
    
    row_count = df.count()
    print(f"  ✓ Wrote {row_count} rows")
    
    return row_count


def register_silver_table(spark, entity_name, output_path):
    """Register Parquet table in Glue Catalog"""
    print(f"Registering table: {OUTPUT_DATABASE}.{entity_name}")
    
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_DATABASE}.{entity_name}
        USING parquet
        LOCATION '{output_path}'
    """)
    
    print(f"  ✓ Table registered")


def main():
    """Main ETL execution"""
    print("="*60)
    print("BRONZE TO SILVER ETL JOB")
    print("="*60)
    print(f"Input Database: {INPUT_DATABASE}")
    print(f"Output Bucket: {OUTPUT_BUCKET}")
    print(f"Output Database: {OUTPUT_DATABASE}")
    print("="*60)
    
    # Read Bronze tables
    print("\nReading Bronze tables...")
    person_df = spark.table(f"{INPUT_DATABASE}.person")
    unit_version_df = spark.table(f"{INPUT_DATABASE}.unit_version")
    org_unit_df = spark.table(f"{INPUT_DATABASE}.org_unit")
    location_df = spark.table(f"{INPUT_DATABASE}.location")
    govt_student_load_df = spark.table(f"{INPUT_DATABASE}.govt_student_load")
    
    print(f"  ✓ PERSON: {person_df.count()} rows")
    print(f"  ✓ UNIT_VERSION: {unit_version_df.count()} rows")
    print(f"  ✓ ORG_UNIT: {org_unit_df.count()} rows")
    print(f"  ✓ LOCATION: {location_df.count()} rows")
    print(f"  ✓ GOVT_STUDENT_LOAD: {govt_student_load_df.count()} rows")
    
    # Transform to MCDS entities
    print("\nTransforming to MCDS entities...")
    
    student_df = transform_student(person_df)
    unit_df = transform_unit_of_learning(unit_version_df)
    location_mcds_df = transform_location(org_unit_df, location_df)
    load_df = transform_student_unit_load(govt_student_load_df)
    
    # Write to Silver
    print("\nWriting to Silver layer...")
    
    write_silver_table(student_df, "student", f"s3://{OUTPUT_BUCKET}/mcds/student/")
    register_silver_table(spark, "student", f"s3://{OUTPUT_BUCKET}/mcds/student/")
    
    write_silver_table(unit_df, "unit_of_learning", f"s3://{OUTPUT_BUCKET}/mcds/unit_of_learning/")
    register_silver_table(spark, "unit_of_learning", f"s3://{OUTPUT_BUCKET}/mcds/unit_of_learning/")
    
    write_silver_table(location_mcds_df, "location", f"s3://{OUTPUT_BUCKET}/mcds/location/")
    register_silver_table(spark, "location", f"s3://{OUTPUT_BUCKET}/mcds/location/")
    
    write_silver_table(load_df, "student_unit_load", f"s3://{OUTPUT_BUCKET}/mcds/student_unit_load/")
    register_silver_table(spark, "student_unit_load", f"s3://{OUTPUT_BUCKET}/mcds/student_unit_load/")
    
    print("\n✓ SUCCESS - Bronze to Silver transformation complete")
    print("="*60)
    
    job.commit()


if __name__ == "__main__":
    main()
