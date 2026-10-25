"""
Landing to Bronze ETL Job
Ingest Callista CSV files from Landing S3 to Bronze Parquet

Input: CSV files in s3://uc-mcds-dev-landing/callista/YYYY-MM-DD/
Output: Parquet files in s3://uc-mcds-dev-bronze/callista/{table}/
"""

import sys
from datetime import datetime
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import lit, current_timestamp

# Add common modules to path
sys.path.append("s3://uc-mcds-dev-scripts/etl/common/")
from schemas import SCHEMA_REGISTRY, get_schema
from data_quality import DataQualityChecker


# Job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'INPUT_BUCKET',
    'OUTPUT_BUCKET',
    'DATABASE_NAME'
])

# Initialize Spark and Glue contexts
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configuration
INPUT_BUCKET = args['INPUT_BUCKET']
OUTPUT_BUCKET = args['OUTPUT_BUCKET']
DATABASE_NAME = args['DATABASE_NAME']

# For local testing, can override with local paths
INPUT_PATH_PREFIX = f"s3://{INPUT_BUCKET}/callista/"
OUTPUT_PATH_PREFIX = f"s3://{OUTPUT_BUCKET}/callista/"

# Tables to process
TABLES = ['PERSON', 'UNIT_VERSION', 'ORG_UNIT', 'LOCATION', 'GOVT_STUDENT_LOAD']

# Date suffix for input files (can be parameterized)
INPUT_DATE = datetime.now().strftime('%Y-%m-%d')


def read_csv_with_schema(spark, file_path, schema):
    """Read CSV file with explicit schema (no inference)"""
    print(f"Reading CSV from: {file_path}")
    
    df = spark.read.format("csv") \
        .option("header", "true") \
        .option("mode", "PERMISSIVE") \
        .option("dateFormat", "yyyy-MM-dd") \
        .schema(schema) \
        .load(file_path)
    
    return df


def write_parquet_to_bronze(df, table_name, output_path):
    """Write DataFrame to Bronze as Parquet"""
    print(f"Writing Parquet to: {output_path}")
    
    # Add metadata columns
    df_with_metadata = df \
        .withColumn("ingestion_timestamp", current_timestamp()) \
        .withColumn("source_file_date", lit(INPUT_DATE))
    
    # Write Parquet (snappy compression)
    df_with_metadata.write \
        .mode("overwrite") \
        .format("parquet") \
        .option("compression", "snappy") \
        .save(output_path)
    
    print(f"  ✓ Wrote {df_with_metadata.count()} rows")
    
    return df_with_metadata.count()


def register_table_in_catalog(spark, table_name, output_path):
    """Register Parquet table in Glue Data Catalog"""
    table_name_lower = table_name.lower()
    
    print(f"Registering table: {DATABASE_NAME}.{table_name_lower}")
    
    # Create external table
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {DATABASE_NAME}.{table_name_lower}
        USING parquet
        LOCATION '{output_path}'
    """)
    
    print(f"  ✓ Table registered")


def main():
    """Main ETL execution"""
    print("="*60)
    print("LANDING TO BRONZE ETL JOB")
    print("="*60)
    print(f"Input Bucket: {INPUT_BUCKET}")
    print(f"Output Bucket: {OUTPUT_BUCKET}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Input Date: {INPUT_DATE}")
    print(f"Tables to process: {', '.join(TABLES)}")
    print("="*60)
    
    # Data quality checker
    dq_checker = DataQualityChecker(spark)
    
    # Process each table
    for table_name in TABLES:
        print(f"\nProcessing table: {table_name}")
        print("-" * 40)
        
        try:
            # Get schema
            schema = get_schema(table_name)
            
            # Input/output paths
            input_path = f"{INPUT_PATH_PREFIX}{INPUT_DATE}/{table_name}.csv"
            output_path = f"{OUTPUT_PATH_PREFIX}{table_name}/"
            
            # Read CSV
            df = read_csv_with_schema(spark, input_path, schema)
            input_count = df.count()
            print(f"  Input rows: {input_count}")
            
            # Data quality checks
            # 1. Row count > 0
            if input_count == 0:
                print(f"  ✗ WARNING: No rows found in {input_path}")
                continue
            
            # 2. Check for nulls in primary keys
            if table_name == 'PERSON':
                dq_checker.check_nulls(df, table_name, ['PERSON_ID'], tolerance=0.0)
            elif table_name == 'UNIT_VERSION':
                dq_checker.check_nulls(df, table_name, ['UNIT_CD'], tolerance=0.0)
            elif table_name == 'ORG_UNIT':
                dq_checker.check_nulls(df, table_name, ['ORG_UNIT_CD'], tolerance=0.0)
            elif table_name == 'LOCATION':
                dq_checker.check_nulls(df, table_name, ['GOVT_LOCATION_CD'], tolerance=0.0)
            elif table_name == 'GOVT_STUDENT_LOAD':
                dq_checker.check_nulls(df, table_name, ['PERSON_ID', 'UNIT_CD'], tolerance=0.0)
            
            # Write Parquet to Bronze
            output_count = write_parquet_to_bronze(df, table_name, output_path)
            
            # Row count reconciliation
            dq_checker.check_row_count(df, table_name, expected_count=input_count, tolerance=0.0)
            
            # Register in Glue Catalog
            register_table_in_catalog(spark, table_name, output_path)
            
            print(f"  ✓ {table_name} processing complete ({output_count} rows)")
        
        except Exception as e:
            print(f"  ✗ ERROR processing {table_name}: {str(e)}")
            raise
    
    # Print data quality summary
    dq_checker.print_summary()
    
    # Check if any DQ checks failed
    summary = dq_checker.get_summary()
    if summary['failed'] > 0:
        print(f"\n✗ FAILED - {summary['failed']} data quality checks failed")
        job.commit()
        sys.exit(1)
    
    print("\n✓ SUCCESS - All tables processed successfully")
    print("="*60)
    
    job.commit()


if __name__ == "__main__":
    main()
