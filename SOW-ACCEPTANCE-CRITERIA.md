# SOW Acceptance Criteria - Implementation Checklist

**Project:** UC MCDS Data Foundation EBA  
**Document:** Cevo SoW - MCDS - AWS Experienced Based Accelerator-v1.1  
**Implementation Status:** Ready to build

---

## D1: MDAA Platform Foundation

**Requirement:**
> "Working governed AWS data platform: S3 data lake, Glue Data Catalog, Lake Formation governance, Athena, CloudTrail audit, IAM/KMS controls."

**Acceptance Criteria:**
> "Platform deployed and operational demonstration completed with University stakeholders."

### Implementation Checklist

#### S3 Data Lake
- [ ] `uc-mcds-bronze` bucket created
  - [ ] KMS encryption enabled
  - [ ] Versioning enabled
  - [ ] Lifecycle policies configured
  - [ ] Folder structure: `landing/`, `callista/`
  - [ ] Tags: `project=uc-mcds`, `layer=bronze`, `managed-by=cdk`

- [ ] `uc-mcds-silver` bucket created
  - [ ] KMS encryption enabled
  - [ ] Versioning enabled
  - [ ] Folder structure: `mcds/`
  - [ ] Tags: `project=uc-mcds`, `layer=silver`, `managed-by=cdk`

- [ ] `uc-mcds-gold` bucket created
  - [ ] KMS encryption enabled
  - [ ] Folder structure: `analytics/`, `athena-results/`
  - [ ] Tags: `project=uc-mcds`, `layer=gold`, `managed-by=cdk`

#### AWS Glue Data Catalog
- [ ] Database: `bronze_callista` created
  - [ ] Tables: `person`, `unit_version`, `org_unit`, `location`, `govt_student_load`
  - [ ] All tables have descriptions
  - [ ] All columns have comments
  - [ ] Partitioning by date configured (where applicable)
  - [ ] Tags: `project=uc-mcds`, `layer=bronze`

- [ ] Database: `silver_mcds` created
  - [ ] Tables: `student`, `unit_of_learning`, `location`, `student_unit_load`
  - [ ] MCDS schema documented in table descriptions
  - [ ] Tags: `project=uc-mcds`, `layer=silver`

- [ ] Database: `gold_analytics` created
  - [ ] Tables: `student_load_by_unit`, `student_load_by_facility`
  - [ ] Business definitions in descriptions
  - [ ] Tags: `project=uc-mcds`, `layer=gold`

#### Lake Formation Governance
- [ ] Data catalog settings configured
  - [ ] Lake Formation enabled
  - [ ] IAM mode: Lake Formation permissions
  - [ ] Tags enabled for column-level security

- [ ] Permissions configured
  - [ ] Data engineer role: full access to bronze/silver
  - [ ] Analyst role: read-only access to gold
  - [ ] Admin role: full administrative access
  - [ ] Service roles for Glue jobs

#### Amazon Athena
- [ ] Workgroup `uc-mcds-analytics` created
  - [ ] Output location: `s3://uc-mcds-gold/athena-results/`
  - [ ] Encryption: SSE-KMS
  - [ ] Data scanned limit: 10 GB per query
  - [ ] Query timeout: 30 minutes

- [ ] Sample queries validated
  - [ ] Query: Student count per unit
  - [ ] Query: Student load by facility
  - [ ] Query: Semester comparison
  - [ ] Query: Facility comparison
  - [ ] All queries return results < 5 seconds

#### AWS CloudTrail
- [ ] Trail `uc-mcds-audit` created
  - [ ] S3 data events logged (bronze/silver/gold buckets)
  - [ ] Management events logged
  - [ ] Log file validation enabled
  - [ ] Log retention: 90 days

#### IAM Roles and Policies
- [ ] Role: `uc-mcds-glue-etl-role`
  - [ ] Trust: AWS Glue service
  - [ ] Policies: S3 access, Glue catalog access, KMS decrypt
  - [ ] Tags: `project=uc-mcds`, `purpose=etl`

- [ ] Role: `uc-mcds-data-engineer-role`
  - [ ] Policies: Full bronze/silver access, read-only gold
  - [ ] Lake Formation permissions granted

- [ ] Role: `uc-mcds-analyst-role`
  - [ ] Policies: Read-only gold access, Athena query access
  - [ ] Lake Formation permissions granted

#### KMS Encryption
- [ ] Key: `alias/uc-mcds-data`
  - [ ] Key policy: Glue, Athena, admin access
  - [ ] Automatic key rotation enabled
  - [ ] Tags: `project=uc-mcds`

**Demonstration Script:**
```bash
# Show S3 buckets
aws s3 ls | grep uc-mcds

# Show Glue databases
aws glue get-databases | jq '.DatabaseList[].Name'

# Show Glue tables
aws glue get-tables --database-name bronze_callista | jq '.TableList[].Name'

# Run Athena query
aws athena start-query-execution --query-string "SELECT COUNT(*) FROM gold_analytics.student_load_by_unit" --result-configuration OutputLocation=s3://uc-mcds-gold/athena-results/

# Show CloudTrail logs
aws cloudtrail lookup-events --max-results 5
```

---

## D2: MCDS Student Model

**Requirement:**
> "Selected MCDS-aligned student enrolment entities implemented, schema structures defined and data quality validation rules configured."

**Acceptance Criteria:**
> "University technical review completed; MCDS conformance validated against representative data."

### Implementation Checklist

#### MCDS Entities Implemented

**Student Entity:**
- [ ] Schema: `silver_mcds.student`
  - [ ] `student_id` STRING (PK) - from PERSON_ID
  - [ ] `student_number` STRING - from TBD (mock: "STU{PERSON_ID}")
  - [ ] `first_name` STRING - from GIVEN_NAMES
  - [ ] `last_name` STRING - from SURNAME
  - [ ] `birth_date` DATE - from BIRTH_DT (year only)
  - [ ] `email_address` STRING - from EMAIL_ADDR
  - [ ] `created_at` TIMESTAMP
  - [ ] `updated_at` TIMESTAMP
  - [ ] Tags: `mcds-entity=student`, `pii=true`

**Unit of Learning Entity:**
- [ ] Schema: `silver_mcds.unit_of_learning`
  - [ ] `unit_code` STRING (PK) - from UNIT_CD
  - [ ] `unit_name` STRING - from TITLE
  - [ ] `created_at` TIMESTAMP
  - [ ] Tags: `mcds-entity=unitOfLearning`

**Location Entity:**
- [ ] Schema: `silver_mcds.location`
  - [ ] `location_code` STRING (PK) - from TR_ORG_UNIT_CD or GOVT_LOCATION_CD
  - [ ] `location_name` STRING - from ORG_UNIT.DESCRIPTION or LOCATION.DESCRIPTION
  - [ ] `location_type` STRING - organizational or physical
  - [ ] `created_at` TIMESTAMP
  - [ ] Tags: `mcds-entity=location`

**Student Unit Load Fact:**
- [ ] Schema: `silver_mcds.student_unit_load`
  - [ ] `load_id` STRING (PK) - generated
  - [ ] `student_id` STRING (FK) - from PERSON_ID
  - [ ] `unit_code` STRING (FK) - from UNIT_CD
  - [ ] `location_code` STRING (FK) - from TR_ORG_UNIT_CD or GOVT_LOCATION_CD
  - [ ] `eftsu` DECIMAL(5,3) - from EFTSU
  - [ ] `semester` STRING - from GOVT_SEMESTER
  - [ ] `status` INT - from UNIT_COMPLETION_STATUS
  - [ ] `created_at` TIMESTAMP
  - [ ] Tags: `mcds-entity=studentEnrollment`

#### MCDS JSON Schema Validation

- [ ] Validator script: `scripts/validate-mcds-json.py`
  - [ ] Validates against `MCDS - v2.1.1/v2.1.1/schemas/parties.schema.json#/$defs/student`
  - [ ] Note: `student.schema.json` does NOT exist; student entity defined in `parties.schema.json`
  - [ ] Sample format: `student-sample.json` (simplified, no AU refdata required)
  - [ ] Checks all required fields present (studentID, studentNumber, studentName, unitOfLearningEnrolments)
  - [ ] Validates data types
  - [ ] Generates validation report

- [ ] Validation results:
  - [ ] 100% of records pass schema validation
  - [ ] All required MCDS fields populated
  - [ ] NO Australian reference data required (SOW only needs aggregates)
  - [ ] Validation report generated

#### Data Quality Rules

- [ ] DQ Rule 1: Completeness
  - [ ] No null `student_id`
  - [ ] No null `unit_code`
  - [ ] No null `location_code`
  - [ ] Threshold: 100%

- [ ] DQ Rule 2: Uniqueness
  - [ ] `student_id` unique in student table
  - [ ] `unit_code` unique in unit_of_learning table
  - [ ] `location_code` unique in location table
  - [ ] Threshold: 100%

- [ ] DQ Rule 3: Referential Integrity
  - [ ] All `student_unit_load.student_id` exists in `student.student_id`
  - [ ] All `student_unit_load.unit_code` exists in `unit_of_learning.unit_code`
  - [ ] All `student_unit_load.location_code` exists in `location.location_code`
  - [ ] Threshold: 100%

- [ ] DQ Rule 4: Value Ranges
  - [ ] EFTSU between 0.0 and 1.0
  - [ ] Status codes in valid set
  - [ ] Semester codes match pattern (YYYY-N)
  - [ ] Threshold: 100%

- [ ] DQ Rule 5: Row Count Reconciliation
  - [ ] Bronze row count = Source row count (±0%)
  - [ ] Silver row count ≥ Bronze row count × 0.95 (allow 5% filter)
  - [ ] Gold aggregations match Silver sums

#### Configuration Files

- [ ] `config/mcds-mappings.yaml`
  - [ ] Callista → MCDS field mappings
  - [ ] Data type conversions
  - [ ] Business rules (filters, transformations)
  - [ ] Reference data lookups

- [ ] `config/data-quality-rules.yaml`
  - [ ] All 5 DQ rules defined
  - [ ] Thresholds documented
  - [ ] Actions on failure (warn/fail)

**Demonstration:**
- [ ] Show MCDS JSON output file
- [ ] Run JSON schema validator (pass)
- [ ] Show DQ report (all rules pass)
- [ ] Query Silver tables in Athena

---

## D3: Callista Onboarding Pattern

**Requirement:**
> "Reusable ingestion and transformation pipeline from the Callista/Oracle enrolment model, with repeatable onboarding patterns documented."

**Acceptance Criteria:**
> "Representative enrolment data successfully onboarded and transformed end to end."

### Implementation Checklist

#### Ingestion Pipeline (Landing → Bronze)

- [ ] Glue ETL Job: `landing-to-bronze`
  - [ ] Script: `etl/landing-to-bronze.py`
  - [ ] Worker type: G.1X
  - [ ] Workers: 2
  - [ ] Timeout: 10 minutes
  - [ ] Retry: 2 attempts
  - [ ] Tags: `project=uc-mcds`, `pipeline=bronze`

- [ ] Input: CSV files in `s3://uc-mcds-bronze/landing/`
  - [ ] PERSON.csv
  - [ ] UNIT_VERSION.csv
  - [ ] ORG_UNIT.csv
  - [ ] LOCATION.csv
  - [ ] GOVT_STUDENT_LOAD.csv

- [ ] Processing:
  - [ ] Read CSV with schema inference disabled (explicit schema)
  - [ ] Data type casting (STRING→BIGINT, STRING→DATE)
  - [ ] Null handling
  - [ ] Deduplication
  - [ ] Write Parquet (snappy compression)

- [ ] Output: Parquet files in `s3://uc-mcds-bronze/callista/{table}/`
  - [ ] Partitioned by date (optional)
  - [ ] Registered in Glue Catalog
  - [ ] Row counts logged

- [ ] Validation:
  - [ ] Source row count = Target row count
  - [ ] No corrupt files
  - [ ] All tables present

#### Transformation Pipeline (Bronze → Silver)

- [ ] Glue ETL Job: `bronze-to-silver`
  - [ ] Script: `etl/bronze-to-silver.py`
  - [ ] Worker type: G.1X
  - [ ] Workers: 3
  - [ ] Timeout: 20 minutes
  - [ ] Retry: 2 attempts
  - [ ] Tags: `project=uc-mcds`, `pipeline=silver`

- [ ] Input: Bronze Parquet tables

- [ ] Processing:
  - [ ] Join GOVT_STUDENT_LOAD + PERSON + UNIT_VERSION + ORG_UNIT/LOCATION
  - [ ] Map to MCDS field names
  - [ ] Apply business rules (filters, derivations)
  - [ ] Generate MCDS JSON (optional, for validation)
  - [ ] Write MCDS Parquet

- [ ] Output: Parquet files in `s3://uc-mcds-silver/mcds/{entity}/`
  - [ ] `student/`
  - [ ] `unit_of_learning/`
  - [ ] `location/`
  - [ ] `student_unit_load/`
  - [ ] Registered in Glue Catalog

- [ ] Validation:
  - [ ] JSON schema validation (pass)
  - [ ] Data quality rules (pass)
  - [ ] Row count reconciliation (≥95%)

#### Analytics Pipeline (Silver → Gold)

- [ ] Glue ETL Job: `silver-to-gold`
  - [ ] Script: `etl/silver-to-gold.py`
  - [ ] Worker type: G.1X
  - [ ] Workers: 2
  - [ ] Timeout: 10 minutes
  - [ ] Retry: 2 attempts
  - [ ] Tags: `project=uc-mcds`, `pipeline=gold`

- [ ] Input: Silver MCDS tables

- [ ] Processing:
  - [ ] Aggregate: Student load by unit
  - [ ] Aggregate: Student load by facility
  - [ ] Apply filters (active status, current semester - configurable)
  - [ ] Write aggregated Parquet

- [ ] Output: Parquet files in `s3://uc-mcds-gold/analytics/{report}/`
  - [ ] `student_load_by_unit/`
  - [ ] `student_load_by_facility/`
  - [ ] Registered in Glue Catalog

- [ ] Validation:
  - [ ] Sum of aggregates = Silver totals
  - [ ] All units represented
  - [ ] All facilities represented

#### Configuration-Driven Pattern

- [ ] YAML configs in `config/`
  - [ ] `bronze-mappings.yaml` - CSV → Bronze schema
  - [ ] `silver-mappings.yaml` - Bronze → MCDS schema
  - [ ] `gold-aggregations.yaml` - Report definitions

- [ ] Pattern reusability:
  - [ ] Add new table: Edit YAML only
  - [ ] Change filter: Edit YAML only
  - [ ] Change calculation: Edit YAML only
  - [ ] No code changes needed

#### Documentation

- [ ] `docs/ONBOARDING-PATTERN.md`
  - [ ] Step-by-step guide
  - [ ] YAML config examples
  - [ ] Common scenarios (add table, change filter)
  - [ ] Troubleshooting guide

**Demonstration:**
- [ ] Run full pipeline: Landing → Bronze → Silver → Gold
- [ ] Show row counts at each stage
- [ ] Show sample data at each stage
- [ ] Show configuration files driving transformations

---

## D4: Governance Framework

**Requirement:**
> "Data catalogue, column level lineage, access controls and auditable data management workflows configured via Lake Formation."

**Acceptance Criteria:**
> "Governance controls demonstrated to University; lineage visible in AWS Glue Data Catalog."

### Implementation Checklist

#### Data Catalog Metadata

- [ ] All tables have descriptions
  - [ ] Bronze tables: Source system documented
  - [ ] Silver tables: MCDS entity documented
  - [ ] Gold tables: Business definition documented

- [ ] All columns have comments
  - [ ] Data types explained
  - [ ] Business meaning documented
  - [ ] PII/sensitive flags added

- [ ] Table properties
  - [ ] `source_system`: callista
  - [ ] `load_frequency`: daily/weekly
  - [ ] `owner`: data-engineering-team
  - [ ] `classification`: public/internal/confidential
  - [ ] `retention_period`: 7 years (or as per policy)

#### Column-Level Lineage

- [ ] Lineage documented in table descriptions
  - [ ] `silver_mcds.student.student_id` ← `bronze_callista.person.person_id`
  - [ ] `silver_mcds.student.first_name` ← `bronze_callista.person.given_names`
  - [ ] `silver_mcds.student.last_name` ← `bronze_callista.person.surname`
  - [ ] `gold_analytics.student_load_by_unit.student_count` ← `COUNT(DISTINCT silver_mcds.student_unit_load.student_id)`
  - [ ] All transformations documented

- [ ] Lineage visualization (optional)
  - [ ] Diagram: Bronze → Silver → Gold
  - [ ] Field-level lineage chart

#### Lake Formation Access Controls

- [ ] Data Lake Administrators
  - [ ] Admin user/role granted
  - [ ] Full catalog and data access

- [ ] Data Engineer Persona
  - [ ] Role: `uc-mcds-data-engineer-role`
  - [ ] Permissions:
    - [ ] SELECT, INSERT on bronze_callista.*
    - [ ] SELECT, INSERT, DELETE on silver_mcds.*
    - [ ] SELECT on gold_analytics.*
    - [ ] Glue job execution

- [ ] Analyst Persona
  - [ ] Role: `uc-mcds-analyst-role`
  - [ ] Permissions:
    - [ ] SELECT on gold_analytics.* (all columns)
    - [ ] Athena query execution
    - [ ] No access to bronze/silver

- [ ] Tag-Based Access Control (TBAC) - Optional
  - [ ] Tag: `pii=true` on student name/email columns
  - [ ] Restricted access to PII columns
  - [ ] Analysts see redacted PII

#### Auditable Data Management

- [ ] CloudTrail logging
  - [ ] All S3 data events logged
  - [ ] All Glue job executions logged
  - [ ] All Athena queries logged
  - [ ] All Lake Formation permission changes logged

- [ ] Glue job execution history
  - [ ] Job name, start time, end time, status
  - [ ] Input row counts, output row counts
  - [ ] Error messages (if failed)
  - [ ] Retention: 90 days

- [ ] Data quality audit trail
  - [ ] DQ checks executed, timestamp, results
  - [ ] Failed rules logged with details
  - [ ] Retention: 365 days

#### Workflow Orchestration (Optional for EBA)

- [ ] AWS Step Functions state machine: `uc-mcds-etl-pipeline`
  - [ ] Step 1: landing-to-bronze
  - [ ] Step 2: bronze-to-silver
  - [ ] Step 3: silver-to-gold
  - [ ] Step 4: data-quality-validation
  - [ ] Error handling: Retry + SNS notification

**Demonstration:**
- [ ] Show catalog metadata (table/column descriptions)
- [ ] Show lineage documentation
- [ ] Demonstrate access control:
  - [ ] Engineer can query bronze/silver/gold
  - [ ] Analyst can only query gold
  - [ ] Analyst denied access to bronze/silver
- [ ] Show CloudTrail audit log (sample events)
- [ ] Show Glue job execution history

---

## D5: Reporting Showcase

**Requirement:**
> "Curated reporting datasets in Amazon Athena demonstrating standardised student load and cross-mapping to units and facilities."

**Acceptance Criteria:**
> "Analytics outputs generated from onboarded data; results reviewed by University stakeholders."

### Implementation Checklist

#### Report 1: Student Load by Unit

- [ ] Gold table: `gold_analytics.student_load_by_unit`
  - [ ] Columns:
    - [ ] `unit_code` STRING
    - [ ] `unit_name` STRING
    - [ ] `semester` STRING
    - [ ] `student_count` BIGINT - COUNT(DISTINCT student_id)
    - [ ] `total_eftsu` DECIMAL(10,3) - SUM(eftsu)
    - [ ] `avg_eftsu_per_student` DECIMAL(5,3) - AVG(eftsu)
    - [ ] `report_generated_at` TIMESTAMP

- [ ] Sample query:
  ```sql
  SELECT * FROM gold_analytics.student_load_by_unit
  WHERE semester = '2024-1'
  ORDER BY student_count DESC
  LIMIT 10;
  ```

- [ ] Expected output (mock data):
  ```
  unit_code | unit_name  | semester | student_count | total_eftsu
  ----------|------------|----------|---------------|-------------
  MATH101   | Math 101   | 2024-1   | 25            | 18.75
  PHYS101   | Physics    | 2024-1   | 23            | 17.25
  CHEM101   | Chemistry  | 2024-1   | 22            | 16.50
  ...
  ```

- [ ] Query performance: < 5 seconds
- [ ] Data freshness: Updated daily (or as per schedule)

#### Report 2: Student Load by Facility

- [ ] Gold table: `gold_analytics.student_load_by_facility`
  - [ ] Columns:
    - [ ] `facility_code` STRING
    - [ ] `facility_name` STRING
    - [ ] `facility_type` STRING - organizational or physical
    - [ ] `semester` STRING
    - [ ] `student_count` BIGINT - COUNT(DISTINCT student_id)
    - [ ] `total_eftsu` DECIMAL(10,3) - SUM(eftsu)
    - [ ] `unit_count` BIGINT - COUNT(DISTINCT unit_code)
    - [ ] `report_generated_at` TIMESTAMP

- [ ] Sample query:
  ```sql
  SELECT * FROM gold_analytics.student_load_by_facility
  WHERE semester = '2024-1'
  ORDER BY student_count DESC;
  ```

- [ ] Expected output (mock data):
  ```
  facility_code | facility_name          | semester | student_count | total_eftsu | unit_count
  --------------|------------------------|----------|---------------|-------------|------------
  FAC_SCI       | Faculty of Science     | 2024-1   | 45            | 35.50       | 8
  FAC_ENG       | Faculty of Engineering | 2024-1   | 38            | 28.75       | 7
  FAC_ART       | Faculty of Arts        | 2024-1   | 32            | 24.00       | 6
  ...
  ```

- [ ] Query performance: < 5 seconds
- [ ] Data freshness: Updated daily

#### Cross-Mapping Demonstration

- [ ] Query: Student load by unit AND facility
  ```sql
  SELECT 
      u.unit_code,
      u.unit_name,
      f.facility_name,
      COUNT(DISTINCT sul.student_id) as student_count,
      SUM(sul.eftsu) as total_eftsu
  FROM silver_mcds.student_unit_load sul
  JOIN silver_mcds.unit_of_learning u ON sul.unit_code = u.unit_code
  JOIN silver_mcds.location f ON sul.location_code = f.location_code
  WHERE sul.semester = '2024-1'
    AND sul.status IN (1, 2)
  GROUP BY u.unit_code, u.unit_name, f.facility_name
  ORDER BY student_count DESC
  LIMIT 20;
  ```

- [ ] Expected output:
  ```
  unit_code | unit_name | facility_name     | student_count | total_eftsu
  ----------|-----------|-------------------|---------------|-------------
  MATH101   | Math 101  | Faculty of Science| 18            | 13.50
  MATH101   | Math 101  | Faculty of Eng    | 7             | 5.25
  PHYS101   | Physics   | Faculty of Science| 23            | 17.25
  ...
  ```

#### Additional Analytics Queries

- [ ] Query: Semester comparison
  ```sql
  SELECT 
      unit_code,
      unit_name,
      SUM(CASE WHEN semester = '2024-1' THEN student_count ELSE 0 END) as s1_count,
      SUM(CASE WHEN semester = '2024-2' THEN student_count ELSE 0 END) as s2_count,
      SUM(CASE WHEN semester = '2024-2' THEN student_count ELSE 0 END) - 
      SUM(CASE WHEN semester = '2024-1' THEN student_count ELSE 0 END) as growth
  FROM gold_analytics.student_load_by_unit
  GROUP BY unit_code, unit_name
  ORDER BY growth DESC;
  ```

- [ ] Query: Facility utilization
  ```sql
  SELECT 
      facility_name,
      SUM(student_count) as total_students,
      AVG(student_count) as avg_students_per_unit,
      MAX(student_count) as max_students_in_unit,
      unit_count
  FROM gold_analytics.student_load_by_facility
  GROUP BY facility_name, unit_count
  ORDER BY total_students DESC;
  ```

#### Export Capabilities

- [ ] CSV export
  - [ ] Sample query result → CSV file
  - [ ] Automated export to S3 (optional)

- [ ] Excel export (optional)
  - [ ] Athena result → Excel workbook
  - [ ] Formatted tables with headers

#### Documentation

- [ ] `docs/REPORTING-GUIDE.md`
  - [ ] Report definitions
  - [ ] Sample queries
  - [ ] How to run queries in Athena
  - [ ] How to export results

**Demonstration:**
- [ ] Run Report 1 query (student load by unit)
- [ ] Run Report 2 query (student load by facility)
- [ ] Run cross-mapping query
- [ ] Show CSV export
- [ ] Explain business meaning of results

---

## D6: Reusable Assets

**Requirement:**
> "Deployment templates, YAML mapping configuration, ingestion framework scripts, runbooks, MCDS mapping artefacts and team capability uplift."

**Acceptance Criteria:**
> "Assets packaged and delivered to University environment or shared repository."

### Implementation Checklist

#### AWS CDK Deployment Templates

- [ ] `infrastructure/bin/app.ts` - CDK app entry point
- [ ] `infrastructure/lib/s3-stack.ts` - S3 buckets
- [ ] `infrastructure/lib/glue-catalog-stack.ts` - Glue databases
- [ ] `infrastructure/lib/glue-jobs-stack.ts` - ETL jobs
- [ ] `infrastructure/lib/lake-formation-stack.ts` - Governance
- [ ] `infrastructure/lib/athena-stack.ts` - Workgroups
- [ ] `infrastructure/lib/iam-stack.ts` - Roles and policies
- [ ] `infrastructure/lib/kms-stack.ts` - Encryption keys
- [ ] `infrastructure/package.json` - Dependencies
- [ ] `infrastructure/cdk.json` - CDK config
- [ ] All stacks parameterized (environment, region, account)

#### YAML Configuration Files

- [ ] `config/bronze-mappings.yaml`
  ```yaml
  tables:
    - name: person
      source: s3://uc-mcds-bronze/landing/PERSON.csv
      schema:
        - person_id: bigint
        - surname: string
        - given_names: string
        - birth_dt: date
        - email_addr: string
      output: s3://uc-mcds-bronze/callista/person/
  ```

- [ ] `config/silver-mappings.yaml`
  ```yaml
  entities:
    - name: student
      source:
        table: bronze_callista.person
      mappings:
        student_id: "CAST(person_id AS STRING)"
        student_number: "CONCAT('STU', person_id)"
        first_name: "given_names"
        last_name: "surname"
        birth_date: "birth_dt"
  ```

- [ ] `config/gold-aggregations.yaml`
  ```yaml
  reports:
    - name: student_load_by_unit
      source: silver_mcds.student_unit_load
      aggregations:
        - student_count: "COUNT(DISTINCT student_id)"
        - total_eftsu: "SUM(eftsu)"
      group_by: [unit_code, semester]
      filters:
        - status IN (1, 2)
  ```

- [ ] `config/data-quality-rules.yaml`

#### ETL Framework Scripts

- [ ] `etl/landing-to-bronze.py` - Ingestion
- [ ] `etl/bronze-to-silver.py` - Transformation
- [ ] `etl/silver-to-gold.py` - Analytics
- [ ] `etl/common/utils.py` - Shared utilities
- [ ] `etl/common/schemas.py` - Schema definitions
- [ ] `etl/common/validators.py` - Data quality
- [ ] All scripts commented and documented

#### Runbooks

- [ ] `docs/runbooks/DEPLOYMENT.md`
  - [ ] Prerequisites
  - [ ] CDK deployment steps
  - [ ] Post-deployment verification
  - [ ] Rollback procedure

- [ ] `docs/runbooks/ETL-EXECUTION.md`
  - [ ] How to run Glue jobs manually
  - [ ] How to monitor job progress
  - [ ] How to troubleshoot failures
  - [ ] How to reprocess data

- [ ] `docs/runbooks/DATA-ONBOARDING.md`
  - [ ] How to add new table
  - [ ] How to update YAML configs
  - [ ] How to test new mappings
  - [ ] How to deploy changes

- [ ] `docs/runbooks/ATHENA-QUERIES.md`
  - [ ] How to access Athena console
  - [ ] Sample queries
  - [ ] How to save/share queries
  - [ ] Query optimization tips

#### MCDS Mapping Artefacts

- [ ] `docs/MCDS-MAPPING-SPECIFICATION.md`
  - [ ] Complete field-level mappings
  - [ ] Callista → MCDS entity mapping
  - [ ] Data type conversions
  - [ ] Business rules applied
  - [ ] Reference data lookups

- [ ] `docs/MCDS-COMPLIANCE-REPORT.md`
  - [ ] MCDS entities implemented
  - [ ] MCDS fields covered
  - [ ] Validation results
  - [ ] Gaps/future enhancements

#### Team Capability Uplift

- [ ] Knowledge transfer sessions
  - [ ] Session 1: Architecture overview (2 hours)
  - [ ] Session 2: AWS services hands-on (3 hours)
  - [ ] Session 3: ETL code walkthrough (2 hours)
  - [ ] Session 4: Athena queries workshop (1 hour)
  - [ ] Session 5: Troubleshooting scenarios (2 hours)

- [ ] Training materials
  - [ ] Slide deck: "UC MCDS Platform Overview"
  - [ ] Video recording: Architecture walkthrough
  - [ ] Video recording: Running ETL jobs
  - [ ] Video recording: Querying data in Athena

- [ ] Handover documentation
  - [ ] System architecture diagram
  - [ ] Data flow diagram
  - [ ] Lineage diagram
  - [ ] Operational procedures
  - [ ] Contact list (Cevo support)

#### Package Delivery

- [ ] Git repository
  - [ ] All code committed
  - [ ] README.md with setup instructions
  - [ ] Tagged release: `v1.0-eba`
  - [ ] Delivered to UC GitLab/GitHub

- [ ] Documentation package
  - [ ] All Markdown docs → PDF
  - [ ] Diagrams exported as PNG
  - [ ] Packaged as ZIP file

**Demonstration:**
- [ ] Show CDK code structure
- [ ] Show YAML config examples
- [ ] Show how to add new table (live demo)
- [ ] Show runbooks
- [ ] Confirm knowledge transfer sessions scheduled

---

## D7: Production Roadmap

**Requirement:**
> "Prioritised roadmap for production deployment and additional MCDS domains, including the NL AI query capability as a candidate future enhancement."

**Acceptance Criteria:**
> "Roadmap presented and endorsed by University and AWS stakeholders."

### Implementation Checklist

#### Production Deployment Roadmap

- [ ] `docs/PRODUCTION-ROADMAP.md` created
  - [ ] Phase 1: Productionization (Weeks 7-12)
  - [ ] Phase 2: Additional entities (Weeks 13-20)
  - [ ] Phase 3: AI query capability (Weeks 21-26)
  - [ ] Phase 4: Cross-institutional integration (Weeks 27+)

**Phase 1 content:**
- [ ] Real-time Callista ingestion (DMS CDC)
- [ ] Incremental ETL (process only changes)
- [ ] Automated scheduling (daily/weekly runs)
- [ ] Monitoring and alerting (CloudWatch)
- [ ] Disaster recovery procedures
- [ ] Cost optimization review

**Phase 2 content:**
- [ ] Additional MCDS entities:
  - [ ] Programme enrolments
  - [ ] Assessment results
  - [ ] Staff allocations
  - [ ] Fee structures
- [ ] Additional source systems:
  - [ ] Canvas LMS
  - [ ] CRM system
- [ ] Estimated effort: 12-16 weeks

**Phase 3 content:**
- [ ] Natural language query capability
  - [ ] Amazon Bedrock (Claude)
  - [ ] Bedrock Guardrails
  - [ ] Lake Formation access control integration
  - [ ] Example: "How many students are enrolled in MATH101 at Bruce Campus?"
- [ ] Estimated effort: 4-6 weeks

**Phase 4 content:**
- [ ] Cross-institutional data exchange
- [ ] MCDS as interoperability standard
- [ ] API layer for external systems
- [ ] Estimated effort: 12+ weeks

#### Cost Estimates

- [ ] EBA cost estimate (6 weeks): $235/month
- [ ] Production cost estimate (ongoing): $500-2,000/month
  - [ ] S3: $50/month
  - [ ] Glue: $200-1,000/month (depends on frequency)
  - [ ] Athena: $50-200/month (depends on queries)
  - [ ] Other: $200/month
- [ ] Optimization opportunities documented

#### Risk Assessment

- [ ] Production deployment risks:
  - [ ] Callista access approval delays
  - [ ] Data quality issues in production data
  - [ ] Performance at scale (10,000+ students)
  - [ ] UC staff availability for support
- [ ] Mitigation strategies for each risk

#### Success Metrics

- [ ] KPIs for production:
  - [ ] ETL success rate > 99%
  - [ ] Data freshness < 24 hours
  - [ ] Query performance < 10 seconds
  - [ ] Cost within budget
  - [ ] Zero data breaches

#### Governance Model

- [ ] Ongoing governance:
  - [ ] Monthly data quality reviews
  - [ ] Quarterly schema evolution reviews
  - [ ] Annual security audits
  - [ ] Change management process

**Demonstration:**
- [ ] Present roadmap document
- [ ] Walk through each phase
- [ ] Explain cost estimates
- [ ] Discuss risks and mitigations
- [ ] Get stakeholder feedback/endorsement

---

## Additional Success Criteria (Implied)

### Workshop Delivery (Nov 24-26)

- [ ] Day 1: Platform demonstration
  - [ ] AWS architecture walkthrough
  - [ ] Live demo: Ingest mock data
  - [ ] Live demo: Run ETL pipeline
  - [ ] Live demo: Query Gold tables

- [ ] Day 2: Hands-on workshop
  - [ ] UC team runs ETL jobs
  - [ ] UC team writes Athena queries
  - [ ] UC team adds new YAML mapping
  - [ ] UC team troubleshoots simulated failure

- [ ] Day 3: Knowledge transfer
  - [ ] Operational runbooks review
  - [ ] Handover documentation
  - [ ] Production roadmap discussion
  - [ ] Q&A session

### Mock Data Quality

- [ ] 500 realistic records generated
  - [ ] 50 students (Australian names)
  - [ ] 10 units (realistic course codes/names)
  - [ ] 5 facilities (UC campuses)
  - [ ] 500 load records (realistic EFTSU distribution)

- [ ] Data relationships maintained
  - [ ] Foreign key integrity
  - [ ] Realistic enrollment patterns
  - [ ] Seasonal distribution (2 semesters)

---

## Audit Trail Tags

**All AWS resources tagged with:**
- [ ] `project` = "uc-mcds"
- [ ] `environment` = "eba"
- [ ] `managed-by` = "cdk"
- [ ] `cost-center` = "data-platform"
- [ ] `owner` = "data-engineering-team"
- [ ] `created-by` = "sumana-pandi"
- [ ] `created-date` = "2026-10-19"

**All Glue tables tagged with:**
- [ ] `project` = "uc-mcds"
- [ ] `layer` = "bronze" | "silver" | "gold"
- [ ] `source-system` = "callista"
- [ ] `mcds-entity` = (entity name, if applicable)
- [ ] `contains-pii` = "true" | "false"
- [ ] `classification` = "public" | "internal" | "confidential"

**All S3 objects tagged with:**
- [ ] `project` = "uc-mcds"
- [ ] `layer` = "bronze" | "silver" | "gold"
- [ ] `data-format` = "csv" | "parquet" | "json"

---

## Final Acceptance Sign-Off

**Cevo Team:**
- [ ] All deliverables complete: D1-D7
- [ ] All acceptance criteria met
- [ ] Workshop delivered successfully
- [ ] UC team trained
- [ ] Assets delivered
- [ ] Sign-off: ______________________ Date: __________

**University of Canberra:**
- [ ] Platform demonstrated and validated
- [ ] Data onboarded successfully
- [ ] Reports generated and reviewed
- [ ] Team trained and confident
- [ ] Assets received
- [ ] Sign-off: ______________________ Date: __________

**AWS Team:**
- [ ] EBA funding approved
- [ ] Platform meets AWS standards
- [ ] Roadmap endorsed
- [ ] Sign-off: ______________________ Date: __________

---

**Document Control:**
- **Version:** 1.0
- **Date:** October 19, 2026
- **Status:** READY FOR IMPLEMENTATION
- **Next Review:** After Week 1 UC meeting
