"""
Silver to Gold ETL Job
Generate analytics reports from Silver MCDS data

Input: mcds_silver database tables
Output: Gold aggregation reports (SOW D5 deliverables)
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import (
    col, count, countDistinct, sum as _sum, avg, current_timestamp
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

# PLACEHOLDER values from business-rules.yaml
ACTIVE_STATUS_CODES = [1, 2]  # Mock: 1=ENROLLED, 2=CONTINUING (real codes TBD)
CURRENT_SEMESTER = '2024-S1'  # Mock semester (real current semester TBD)


def generate_student_load_by_unit(load_df, unit_df):
    """
    Report 1: Student load by unit (SOW D5.1)
    
    PLACEHOLDER: Uses COUNT(DISTINCT studentId) - confirm with UC (headcount vs EFTSU sum)
    PLACEHOLDER: Filters by active status codes and current semester from business-rules.yaml
    """
    print("\nGenerating Report 1: Student load by unit")
    
    # Filter active enrolments in current semester
    filtered_df = load_df.filter(
        (col("status").isin(ACTIVE_STATUS_CODES)) &
        (col("semester") == CURRENT_SEMESTER)
    )
    
    # Join with unit dimension
    joined_df = filtered_df.join(unit_df, "unitCode", "left")
    
    # Aggregate
    report_df = joined_df.groupBy("unitCode", "unitName", "semester").agg(
        countDistinct("studentId").alias("student_count"),
        _sum("eftsu").alias("total_eftsu"),
        avg("eftsu").alias("avg_eftsu_per_student")
    ).withColumn(
        "report_generated_at", current_timestamp()
    ).orderBy(
        col("student_count").desc()
    )
    
    return report_df


def generate_student_load_by_facility(load_df, location_df):
    """
    Report 2: Student load by facility (SOW D5.2)
    
    PLACEHOLDER: Uses COUNT(DISTINCT studentId) - confirm with UC
    PLACEHOLDER: Filters by active status codes and current semester
    PLACEHOLDER: facility field (locationCode) from business-rules.yaml
    """
    print("\nGenerating Report 2: Student load by facility")
    
    # Filter active enrolments in current semester
    filtered_df = load_df.filter(
        (col("status").isin(ACTIVE_STATUS_CODES)) &
        (col("semester") == CURRENT_SEMESTER)
    )
    
    # Join with location dimension
    joined_df = filtered_df.join(location_df, "locationCode", "left")
    
    # Aggregate
    report_df = joined_df.groupBy("locationCode", "locationName", "semester").agg(
        countDistinct("studentId").alias("student_count"),
        _sum("eftsu").alias("total_eftsu"),
        countDistinct("unitCode").alias("unit_count")
    ).withColumn(
        "report_generated_at", current_timestamp()
    ).orderBy(
        col("student_count").desc()
    )
    
    return report_df


def write_gold_table(df, report_name, output_path):
    """Write DataFrame to Gold layer as Parquet"""
    print(f"Writing {report_name} to Gold: {output_path}")
    
    df.write \
        .mode("overwrite") \
        .format("parquet") \
        .option("compression", "snappy") \
        .save(output_path)
    
    row_count = df.count()
    print(f"  ✓ Wrote {row_count} rows")
    
    # Show sample
    print(f"  Sample data:")
    df.show(5, truncate=False)
    
    return row_count


def register_gold_table(spark, report_name, output_path):
    """Register Parquet table in Glue Catalog"""
    print(f"Registering table: {OUTPUT_DATABASE}.{report_name}")
    
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_DATABASE}.{report_name}
        USING parquet
        LOCATION '{output_path}'
    """)
    
    print(f"  ✓ Table registered")


def main():
    """Main ETL execution"""
    print("="*60)
    print("SILVER TO GOLD ETL JOB")
    print("="*60)
    print(f"Input Database: {INPUT_DATABASE}")
    print(f"Output Bucket: {OUTPUT_BUCKET}")
    print(f"Output Database: {OUTPUT_DATABASE}")
    print(f"Active Status Codes (PLACEHOLDER): {ACTIVE_STATUS_CODES}")
    print(f"Current Semester (PLACEHOLDER): {CURRENT_SEMESTER}")
    print("="*60)
    
    # Read Silver tables
    print("\nReading Silver tables...")
    student_df = spark.table(f"{INPUT_DATABASE}.student")
    unit_df = spark.table(f"{INPUT_DATABASE}.unit_of_learning")
    location_df = spark.table(f"{INPUT_DATABASE}.location")
    load_df = spark.table(f"{INPUT_DATABASE}.student_unit_load")
    
    print(f"  ✓ student: {student_df.count()} rows")
    print(f"  ✓ unit_of_learning: {unit_df.count()} rows")
    print(f"  ✓ location: {location_df.count()} rows")
    print(f"  ✓ student_unit_load: {load_df.count()} rows")
    
    # Generate reports
    print("\nGenerating Gold reports...")
    
    report1_df = generate_student_load_by_unit(load_df, unit_df)
    report2_df = generate_student_load_by_facility(load_df, location_df)
    
    # Write to Gold
    print("\nWriting to Gold layer...")
    
    write_gold_table(report1_df, "student_load_by_unit", 
                    f"s3://{OUTPUT_BUCKET}/analytics/student_load_by_unit/")
    register_gold_table(spark, "student_load_by_unit", 
                       f"s3://{OUTPUT_BUCKET}/analytics/student_load_by_unit/")
    
    write_gold_table(report2_df, "student_load_by_facility", 
                    f"s3://{OUTPUT_BUCKET}/analytics/student_load_by_facility/")
    register_gold_table(spark, "student_load_by_facility", 
                       f"s3://{OUTPUT_BUCKET}/analytics/student_load_by_facility/")
    
    print("\n✓ SUCCESS - Silver to Gold transformation complete")
    print("="*60)
    print("\nSOW D5 Deliverables:")
    print("  ✓ D5.1: Student load by unit report generated")
    print("  ✓ D5.2: Student load by facility report generated")
    print("="*60)
    
    job.commit()


if __name__ == "__main__":
    main()
