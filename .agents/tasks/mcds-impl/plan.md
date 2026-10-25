# UC MCDS Data Platform - Implementation Plan

**Repository:** c:\Users\suman_3kw9zn1\OneDrive\Documents\CEVO\Clients\MCDS\uc-mcds-data-platform  
**Branch:** feature/callista-mcds-implementation  
**Technology:** AWS CDK via MDAA (YAML-driven configuration), Python 3.9+ for Glue jobs  
**Approach:** Mock data first, config-driven placeholders for 6 TBD items  
**Target:** SOW Acceptance Criteria D1-D7

---

## MCDS Scope Clarification (SIMPLIFIED)

**Schema:** Use `MCDS - v2.1.1/v2.1.1/schemas/parties.schema.json#/$defs/student` ONLY  
**Format:** Follow `student-sample.json` structure (simple, NO complex refdata)  
**Australian Reference Data:** NOT NEEDED for SOW D5 reports (student counts, unit codes, facility names come directly from Callista)

**MCDS Structure to Generate:**
```json
{
  "students": [
    {
      "studentID": "STU001",
      "studentNumber": "2005123456",
      "studentName": {
        "firstName": "Mary",
        "lastName": "Doe"
      },
      "unitOfLearningEnrolments": [
        {
          "studentID": "STU001",
          "programmeOfLearningEnrolmentID": "536412",
          "unitOfLearningAvailability": {
            "unitOfLearning": {
              "unitOfLearningCode": "MATH101",
              "unitOfLearningName": "Mathematics 101"
            },
            "location": {
              "locationName": "City Campus"
            }
          }
        }
      ]
    }
  ]
}
```

**DO NOT Generate:**
- `parties[]` array (complex entity)
- `persons[]` array (separate entity)
- `addresses[]` array (separate entity)
- Reference data classifications (countries, gender, disabilities, indigenous status from `reference/AU/`)

**Core Callista→MCDS Mappings:**
- `PERSON.PERSON_ID` → `student.studentID` (as "STU{PERSON_ID}")
- `PERSON.GIVEN_NAMES` → `student.studentName.firstName`
- `PERSON.SURNAME` → `student.studentName.lastName`
- `GOVT_STUDENT_LOAD.UNIT_CD` → `unitOfLearningAvailability.unitOfLearning.unitOfLearningCode`
- `UNIT_VERSION.TITLE` → `unitOfLearningAvailability.unitOfLearning.unitOfLearningName`
- `ORG_UNIT` OR `LOCATION` → `unitOfLearningAvailability.location.locationName` (TBD which source)

---

## SOW Acceptance Criteria Mapping

| Criterion | Files/Steps That Satisfy It |
|-----------|------------------------------|
| **D1** | Steps 1-3 (MDAA YAML configs → CDK infrastructure with audit tags) |
| **D2** | Steps 5-6 (Bronze-to-Silver ETL → MCDS JSON in Silver + validation) |
| **D3** | Steps 2-7 (Mock data generator + all ETL jobs + README deployment docs) |
| **D4** | Steps 1, 3, 8 (Lake Formation IAM + KMS + data quality checks) |
| **D5** | Step 7 (Silver-to-Gold ETL → 2 Gold reports queryable in Athena) |
| **D6** | Step 11 (All code committed to feature branch, not pushed) |
| **D7** | Step 10 (Roadmap documenting 6 TBD items in config/roadmap.md) |

---

## 6 TBD Placeholder Items (Config-Driven)

These business rules are PLACEHOLDERS until UC confirms. All stored in **config/business-rules.yaml**:

```yaml
# TBD Business Rules (Placeholders - NOT confirmed by UC)
student_number_source:
  # PLACEHOLDER: Real source unknown
  placeholder_formula: "STU{PERSON_ID}"
  confirmed: false
  notes: "Real source: STATE_GOVT_STUDENT_NUMBER in VET tables (TBD)"

student_load_metric:
  # PLACEHOLDER: Use COUNT, real metric TBD
  primary_metric: "COUNT"  # Alternative: SUM(EFTSU)
  confirmed: false
  notes: "SOW says 'how many students' - confirming interpretation"

facility_field:
  # PLACEHOLDER: Use organizational unit, real field TBD
  source_column: "TR_ORG_UNIT_CD"  # Alternative: GOVT_LOCATION_CD
  confirmed: false
  notes: "Facility = organizational or physical location?"

active_status_codes:
  # PLACEHOLDER: Mock values, real codes TBD
  unit_completion_status:
    - 1  # Mock: ENROLLED
    - 2  # Mock: CONTINUING
  confirmed: false
  notes: "Real UNIT_COMPLETION_STATUS values for 'active' TBD"

current_semester:
  # PLACEHOLDER: Mock value, real semester code TBD
  semester_code: "2024-S1"
  confirmed: false
  notes: "Current reporting semester for GOVT_SEMESTER field"

org_unit_description_column:
  # PLACEHOLDER: Use placeholder until real column confirmed
  column_name: "ORG_UNIT_START_DT"  # Placeholder field
  confirmed: false
  notes: "Real ORG_UNIT description column name TBD from UC schema"
```

---

## Implementation Plan

All steps build on EXISTING project structure (mdaa.yaml, dataops/, etl/ already present). Items leave codebase in buildable state.

---

- [ ] 1. **Create mock data generator for all 5 Callista tables**

  Generate realistic mock CSVs with referential integrity: 50 students (PERSON), 10 units (UNIT_VERSION), 5 facilities (ORG_UNIT), 3 locations (LOCATION), 500 student load records (GOVT_STUDENT_LOAD). Use Australian university patterns (names, dates, EFTSU values 0.125-1.0).

  **Files:**
  - Create `scripts/generate-mock-data.py` (Python script with Faker for Australian names/dates)
  - Create `config/business-rules.yaml` (6 TBD placeholders as shown above)
  - Output CSVs to `data/mock/landing/callista/2024-10-19/` (PERSON.csv, UNIT_VERSION.csv, ORG_UNIT.csv, LOCATION.csv, GOVT_STUDENT_LOAD.csv)

  **Verify:** Run `python scripts/generate-mock-data.py && ls data/mock/landing/callista/2024-10-19/*.csv | Measure-Object | Select-Object Count` → Expected: 5 CSV files. Check row counts with `Import-Csv data/mock/landing/callista/2024-10-19/PERSON.csv | Measure-Object` → Expected: 50 rows.

---

- [ ] 2. **Configure MDAA infrastructure YAMLs for S3, Glue Catalog, KMS, audit trail**

  Update existing MDAA YAML configs in governance/ and data/ directories to define: S3 buckets (uc-mcds-dev-landing, -bronze, -silver, -gold, -athena-results), Glue databases (mcds_bronze, mcds_silver, mcds_gold), KMS keys for each layer, CloudTrail logging. Add SOW audit tags to all resources: project=uc-mcds-data-platform, environment=dev, layer=[landing|bronze|silver|gold], managed-by=cdk, sow-deliverable=[D1|D2|D3|D4|D5], cost-center=university-analytics.

  **Files:**
  - Modify `data/datalake.yaml` (add 5 S3 buckets with KMS encryption, versioning, lifecycle policies, audit tags)
  - Modify `dataops/project.yaml` (add 3 Glue databases: mcds_bronze, mcds_silver, mcds_gold with audit tags)
  - Modify `data/audit-trail.yaml` (configure CloudTrail for S3 data events on all MCDS buckets)
  - Modify `governance/roles.yaml` (add Glue ETL service role with S3/Glue/KMS permissions, least-privilege IAM)

  **Verify:** Run `npx @aws-mdaa/cli synth` from repository root → Expected: No errors, CloudFormation templates generated in cdk.out/. Check synthesized stacks contain S3 buckets and Glue databases with correct audit tags.

---

- [ ] 3. **Define Glue ETL jobs in dataops/jobs.yaml for all 3 layers**

  Add Glue job definitions for landing-to-bronze.py, bronze-to-silver.py, silver-to-gold.py. Configure Glue 3.0 (Python 3.9), worker type G.1X, concurrent runs, timeout, retry, IAM role reference, script locations in etl/ directory.

  **Files:**
  - Modify `dataops/jobs.yaml` (add 3 Glue job definitions: landing-to-bronze, bronze-to-silver, silver-to-gold with worker config, timeout, retry, audit tags)

  **Verify:** Run `npx @aws-mdaa/cli synth` → Expected: Glue job resources in synthesized CloudFormation templates. Check job definitions reference correct script paths (etl/bronze/landing-to-bronze.py, etc.).

---

- [ ] 4. **Implement Bronze ETL: Landing CSV → Bronze Parquet with data quality checks**

  Read 5 CSVs from S3 landing bucket, apply explicit schemas (no inference), convert to Parquet (snappy compression), write partitioned by date to Bronze S3, register tables in Glue Catalog. Add data quality checks: row count logging, null checks on PKs (PERSON_ID, UNIT_CD, ORG_UNIT_CD, LOCATION_CD, GOVT_LOCATION_CD), referential integrity validation (all FKs exist).

  **Files:**
  - Create `etl/bronze/landing-to-bronze.py` (PySpark job: CSV→Parquet, 5 table loops, explicit schemas matching Sisprod_schema_metadata.csv, partition by ingestion_date, row count reconciliation)
  - Create `etl/common/schemas.py` (Spark StructType schemas for all 5 Callista tables based on actual Oracle data types)
  - Create `etl/common/data_quality.py` (DQ functions: check_row_counts, check_nulls, check_referential_integrity)

  **Verify:** Deploy to AWS (if available) or run locally with `spark-submit --master local[*] etl/bronze/landing-to-bronze.py --input data/mock/landing/callista/2024-10-19 --output data/mock/bronze/callista` → Expected: 5 Parquet directories created, row counts logged to stdout match CSVs (50 PERSON, 10 UNIT_VERSION, 5 ORG_UNIT, 3 LOCATION, 500 GOVT_STUDENT_LOAD). Check Parquet files readable with `pyspark` shell.

---

- [ ] 5. **Implement Silver ETL: Bronze Parquet → MCDS JSON with schema validation**

  Read Bronze Parquet tables, join GOVT_STUDENT_LOAD + PERSON + UNIT_VERSION + ORG_UNIT/LOCATION, map to SIMPLIFIED MCDS student structure following student-sample.json format: studentID, studentNumber, studentName (firstName/lastName), unitOfLearningEnrolments[] with nested unitOfLearning (code/name) and location (locationName). NO parties array, NO persons array, NO addresses array, NO Australian reference data classifications. Write JSON to Silver S3, validate against parties.schema.json#/$defs/student. Convert JSON → Parquet for queryability.

  **Files:**
  - Create `etl/silver/bronze-to-silver.py` (PySpark job: read Bronze tables, join logic, map to SIMPLIFIED MCDS structure per student-sample.json, write JSON + Parquet, call validator)
  - Create `etl/common/mcds_mappings.py` (Callista→MCDS SIMPLIFIED mappings: PERSON.PERSON_ID→studentID as "STU{PERSON_ID}", PERSON.GIVEN_NAMES+SURNAME→studentName.firstName/lastName, GOVT_STUDENT_LOAD.UNIT_CD→unitOfLearning.unitOfLearningCode, UNIT_VERSION.TITLE→unitOfLearning.unitOfLearningName, ORG_UNIT/LOCATION→location.locationName; NO refdata lookups)
  - Create `etl/common/mcds_validator.py` (JSON Schema validation using jsonschema library, load parties.schema.json, validate against #/$defs/student, log failures)

  **Verify:** Run Silver ETL locally with Bronze Parquet output as input → Expected: JSON files in data/mock/silver/mcds/student/, Parquet files queryable. Run `python -c "import jsonschema, json; schema=json.load(open('MCDS - v2.1.1/v2.1.1/schemas/parties.schema.json')); resolver=jsonschema.RefResolver.from_schema(schema); data=json.load(open('data/mock/silver/mcds/student/sample.json')); jsonschema.validate(data['students'][0], schema['$defs']['student'], resolver=resolver); print('VALID')"` → Expected: VALID printed, no validation errors.

---

- [ ] 6. **Create Bronze-to-Silver mapping configuration file**

  Document SIMPLIFIED field-level mappings from Callista Bronze tables to MCDS Silver student structure in YAML following student-sample.json format. Core mappings only: PERSON→student (studentID, studentNumber, studentName), GOVT_STUDENT_LOAD→unitOfLearningEnrolments[], UNIT_VERSION→unitOfLearning, ORG_UNIT/LOCATION→location. NO parties, NO persons, NO addresses, NO Australian reference data. Include all 6 TBD placeholders with explicit "PLACEHOLDER" markers.

  **Files:**
  - Create `config/silver-mappings.yaml` (SIMPLIFIED Callista→MCDS mappings: PERSON.PERSON_ID→studentID formula, PERSON.GIVEN_NAMES→studentName.firstName, PERSON.SURNAME→studentName.lastName, GOVT_STUDENT_LOAD.UNIT_CD→unitOfLearningAvailability.unitOfLearning.unitOfLearningCode, UNIT_VERSION.TITLE→unitOfLearning.unitOfLearningName, ORG_UNIT/LOCATION→location.locationName; Include placeholder formulas for studentNumber, facility field selection, active status filters referencing business-rules.yaml; NO refdata mappings)

  **Verify:** Read YAML with `python -c "import yaml; print(yaml.safe_load(open('config/silver-mappings.yaml')))"` → Expected: Valid YAML structure, 5 Callista tables mapped to simplified student structure (NOT separate entities), 6 TBD items explicitly marked as placeholders, NO references to parties/persons/addresses/refdata.

---

- [ ] 7. **Implement Gold ETL: Silver Parquet → 2 SOW reports (student load by unit, by facility)**

  Read Silver Parquet (student_unit_load fact table), aggregate for Report 1 (GROUP BY unitCode: COUNT DISTINCT studentId, SUM load), aggregate for Report 2 (GROUP BY facility: COUNT DISTINCT studentId, SUM load, COUNT DISTINCT unitCode). Apply filters from business-rules.yaml (active status, current semester). Write aggregated Parquet to Gold S3, register tables in Glue Catalog.

  **Files:**
  - Create `etl/gold/silver-to-gold.py` (PySpark job: read Silver student_unit_load, generate 2 reports, write Parquet to Gold, register in Glue Catalog)
  - Create `config/gold-aggregations.yaml` (Report definitions: student_load_by_unit, student_load_by_facility with GROUP BY columns, aggregation functions, filters referencing business-rules.yaml)

  **Verify:** Run Gold ETL locally → Expected: 2 Parquet directories in data/mock/gold/ (student_load_by_unit/, student_load_by_facility/). Query with `pyspark`: `spark.read.parquet('data/mock/gold/student_load_by_unit').show()` → Expected: 10 rows (10 units), columns: unit_code, unit_name, student_count, total_load, semester. Verify student_count > 0 for all units, total_load > 0.

---

- [ ] 8. **Implement data quality validation framework for all layers**

  Create standalone DQ validation job that runs reconciliation checks: Bronze row count = Landing row count (±0%), Silver row count ≥ Bronze × 0.95, Gold aggregations sum = Silver totals. Check nulls on required fields (studentId, unitCode, facility in Silver). Check referential integrity across layers. Log results to CloudWatch (or stdout for local).

  **Files:**
  - Create `etl/validation/data-quality-checks.py` (Standalone PySpark job: read Landing/Bronze/Silver/Gold, run 8 DQ rules, log pass/fail with details, exit non-zero on failures)
  - Modify `config/business-rules.yaml` (add dq_thresholds section: row_count_tolerance=0.0, silver_retention_min=0.95, required_fields=[studentId, unitCode, facility])

  **Verify:** Run DQ job against mock data outputs → Expected: All 8 checks PASS logged to stdout. Check specific assertions: Landing row count 500 = Bronze row count 500, Silver student count 50, Gold unit report has 10 rows, Gold facility report has 5 rows, no nulls in studentId/unitCode/facility columns.

---

- [ ] 9. **Create Athena sample queries for all Gold reports**

  Write SQL queries to demonstrate SOW D5 deliverables: query Gold tables for student load by unit (ORDER BY student_count DESC LIMIT 10), student load by facility (ORDER BY student_count DESC), cross-mapping (unit + facility JOIN). Document query patterns, expected results with mock data.

  **Files:**
  - Create `athena/queries/query-bronze-raw.sql` (Sample Bronze queries: SELECT from bronze tables, row counts, schema inspection)
  - Create `athena/queries/query-silver-mcds.sql` (Sample Silver queries: SELECT students with enrolments, filter active, join units)
  - Create `athena/queries/query-gold-reports.sql` (SOW deliverable queries: student_load_by_unit top 10, student_load_by_facility all, cross-mapping unit×facility)

  **Verify:** If Athena available, run queries against deployed tables. Locally, validate SQL syntax with `sqlparse` or manual inspection → Expected: All queries syntactically valid, reference correct database.table names (mcds_bronze.*, mcds_silver.*, mcds_gold.*), produce expected column sets documented in query comments.

---

- [ ] 10. **Document roadmap for 6 TBD items (SOW D7 deliverable)**

  Create production roadmap documenting all 6 placeholder business rules, their current mock values, the real source/logic needed from UC, and the config changes required when UC confirms. Include timeline estimate for each confirmation (Week 1 UC meeting), deployment impact (config-only, no code changes).

  **Files:**
  - Create `config/roadmap.md` (6 TBD items table: Item, Current Placeholder, Real Source TBD, Config File to Update, UC Confirmation Timeline, Deployment Impact. Add Phase 1: Productionization section from SOW-ACCEPTANCE-CRITERIA.md, Phase 2: Additional entities, Phase 3: NL query capability)

  **Verify:** Read `config/roadmap.md` → Expected: All 6 TBD items documented with current placeholder values matching business-rules.yaml, clear indication each is UNCONFIRMED, explicit call-out that only config changes needed (no code rewrite) when UC confirms.

---

- [ ] 11. **Create comprehensive tests for mock data and ETL pipeline**

  Write unit tests for mock data generator (row counts, referential integrity, EFTSU ranges), integration tests for each ETL job (Bronze/Silver/Gold transformations), end-to-end test (Landing CSV → Gold reports). Use pytest framework.

  **Files:**
  - Create `tests/unit/test_mock_data.py` (pytest: test_person_count=50, test_unit_count=10, test_load_count=500, test_referential_integrity all FKs valid, test_eftsu_range 0.0-1.0)
  - Create `tests/integration/test_bronze_etl.py` (pytest: test_csv_to_parquet_person, test_row_count_reconciliation, test_parquet_schema_matches_ddl)
  - Create `tests/integration/test_silver_etl.py` (pytest: test_mcds_json_validation, test_student_count_50, test_enrolment_mapping)
  - Create `tests/integration/test_gold_etl.py` (pytest: test_student_load_by_unit_aggregation, test_student_load_by_facility_aggregation, test_aggregation_totals_match_silver)
  - Create `tests/e2e/test_etl_pipeline.py` (pytest: test_end_to_end_landing_to_gold, calls all 3 ETL jobs sequentially, validates final Gold reports)

  **Verify:** Run `cd tests && pytest -v` → Expected: All tests PASS. Specific assertions: test_person_count passes with 50 rows, test_referential_integrity passes (all PERSON_IDs in GOVT_STUDENT_LOAD exist in PERSON), test_mcds_json_validation passes (no JSON schema errors), test_student_load_by_unit_aggregation passes (10 unit rows in Gold).

---

- [ ] 12. **Update repository README with deployment instructions and architecture overview**

  Document complete setup steps (prerequisites, CDK bootstrap, MDAA deploy, mock data generation, ETL execution), architecture diagram reference, SOW acceptance criteria mapping table (D1-D7 → implementation files), testing instructions, 6 TBD items call-out.

  **Files:**
  - Modify `README.md` (add sections: Quick Start with exact commands, SOW Acceptance Mapping table from this plan, 6 TBD Business Rules warning box, Testing section referencing pytest commands, Architecture section referencing Confluence docs, Cost Estimates section for mock vs production)

  **Verify:** Read README.md → Expected: Complete deployment steps present (npm install, cdk bootstrap, npx @aws-mdaa/cli deploy, python generate-mock-data.py, aws glue start-job-run commands), SOW D1-D7 mapping table matches this plan, prominent warning about 6 TBD placeholders, pytest test command documented.

---

- [ ] 13. **Create onboarding documentation for Callista data pattern (SOW D3 deliverable)**

  Write runbook documenting the reusable Callista onboarding pattern: Landing→Bronze (CSV→Parquet), Bronze→Silver (Parquet→MCDS JSON), configuration-driven mappings (YAML), how to add new Callista table (update YAML, no code changes), how to modify business rules (edit business-rules.yaml), troubleshooting common issues.

  **Files:**
  - Create `docs/ONBOARDING-PATTERN.md` (Sections: Pattern Overview, Landing→Bronze Steps, Bronze→Silver Steps, Configuration-Driven Design, How to Add New Table step-by-step, How to Change Business Rule step-by-step, Troubleshooting FAQ, Architecture Diagram reference)

  **Verify:** Read `docs/ONBOARDING-PATTERN.md` → Expected: Complete step-by-step guide for adding new Callista table (5 steps: add CSV to landing, update bronze schema, update silver mappings YAML, run ETL, validate), example YAML snippets for bronze-mappings.yaml and silver-mappings.yaml, troubleshooting section covers common errors (schema mismatch, referential integrity failures, JSON validation errors).

---

## Verification Summary

**Infrastructure:** `npx @aws-mdaa/cli synth` produces CloudFormation templates with S3 buckets, Glue databases, Glue jobs, IAM roles, KMS keys, CloudTrail, all with SOW audit tags.

**Mock Data:** `python scripts/generate-mock-data.py` produces 5 CSVs (50+10+5+3+500 rows) with referential integrity, Australian patterns, realistic EFTSU values.

**Bronze ETL:** Spark job processes 5 CSVs → 5 Parquet tables, row counts match (500 landing = 500 bronze for GOVT_STUDENT_LOAD), no nulls in PKs.

**Silver ETL:** Spark job joins Bronze tables → SIMPLIFIED MCDS JSON files per student-sample.json format (students[] with unitOfLearningEnrolments[], NO parties/persons/addresses/refdata), JSON schema validation PASSES against parties.schema.json#/$defs/student, 50 student records with enrolments[], Parquet queryable.

**Gold ETL:** Spark job aggregates Silver → 2 Gold reports, student_load_by_unit has 10 rows (10 units), student_load_by_facility has 5 rows (5 facilities), aggregations sum correctly.

**Data Quality:** DQ validation job runs 8 checks against Landing/Bronze/Silver/Gold, ALL PASS, logs row counts and null checks.

**Tests:** `pytest -v` runs all unit/integration/e2e tests, ALL PASS, coverage includes mock data integrity, ETL transformations, JSON validation, aggregation correctness.

**Documentation:** README.md has complete deployment steps, SOW D1-D7 mapping, 6 TBD warnings. docs/ONBOARDING-PATTERN.md has reusable Callista ingestion guide. config/roadmap.md documents all TBD items for D7.

**Athena Queries:** 3 SQL files (bronze/silver/gold) syntactically valid, demonstrate SOW D5 deliverables (student load by unit/facility).

---

## Build Order

1. **Mock Data + Config** (Steps 1, 6, 10) — Generates test data, establishes TBD placeholders in config files
2. **Infrastructure YAMLs** (Steps 2, 3) — MDAA configs for S3, Glue, IAM, CloudTrail
3. **Bronze Layer** (Step 4) — CSV→Parquet ingestion, data quality foundation
4. **Silver Layer** (Steps 5, 6) — Parquet→MCDS JSON transformation, schema validation
5. **Gold Layer** (Step 7) — MCDS→Reports aggregation (SOW D5 deliverables)
6. **Data Quality** (Step 8) — Cross-layer reconciliation checks
7. **Athena Queries** (Step 9) — SQL query patterns for Gold reports
8. **Tests** (Step 11) — Unit/integration/e2e test suite
9. **Documentation** (Steps 12, 13) — README, onboarding docs, roadmap (SOW D3, D7)

Dependencies: Step 4 requires Step 1 output (mock CSVs). Step 5 requires Step 4 output (Bronze Parquet). Step 7 requires Step 5 output (Silver Parquet). Step 8 requires Steps 4-7 outputs (all layers). Step 11 requires Steps 1-8 (full pipeline).

---

## Config Files Holding TBD Placeholders

All 6 TBD items stored in **`config/business-rules.yaml`** with explicit `confirmed: false` flags:

1. `student_number_source.placeholder_formula` = "STU{PERSON_ID}"
2. `student_load_metric.primary_metric` = "COUNT"
3. `facility_field.source_column` = "TR_ORG_UNIT_CD"
4. `active_status_codes.unit_completion_status` = [1, 2]
5. `current_semester.semester_code` = "2024-S1"
6. `org_unit_description_column.column_name` = "ORG_UNIT_START_DT"

Referenced by **`etl/common/mcds_mappings.py`** (Silver ETL), **`etl/gold/silver-to-gold.py`** (Gold ETL filters), and **`config/silver-mappings.yaml`** (mapping specs).

When UC confirms real values, update `config/business-rules.yaml` only, set `confirmed: true`, re-run ETL jobs — NO CODE CHANGES NEEDED.

---

## Notes

- **Analysis docs NOT for check-in:** .gitignore already updated in setup step to exclude analysis/ directory (SOW-ACCEPTANCE-CRITERIA.md, IMPLEMENTATION-PLAN.md, Sisprod_schema_metadata.csv remain accessible but not committed).

- **Branch strategy:** All work on feature/callista-mcds-implementation, local commits only (never push per user instruction), final merge after review.

- **MCDS schema location:** MCDS - v2.1.1/ directory exists in repo root, gitignored per existing .gitignore, Silver ETL validates against parties.schema.json#/$defs/student ONLY (NOT student-management.schema.json), following student-sample.json format (SIMPLIFIED structure, NO refdata).

- **Technology stack verified:** MDAA CLI via npx (package.json devDependencies), Python 3.9+ for Glue jobs (PySpark), pytest for tests, AWS Glue 3.0 (specified in jobs.yaml), no raw CDK TypeScript (MDAA generates CDK from YAML).

- **Mock data rationale:** Per Definitive-Analysis and Gap-Analysis docs, all 6 gaps are business rules not schema gaps — mock data approach unblocked, can build complete pipeline now, refine with UC confirmations later.

- **Audit trail tags on ALL resources:** Every S3 bucket, Glue database, Glue table, Glue job, IAM role, KMS key tagged with project, environment, layer, managed-by, sow-deliverable per SOW D1 requirement.

---

## SOW Deliverable Evidence

| SOW ID | Requirement | Files Providing Evidence |
|--------|-------------|--------------------------|
| **D1** | MDAA platform with audit trail | data/datalake.yaml (S3+KMS), dataops/project.yaml (Glue Catalog), data/audit-trail.yaml (CloudTrail), governance/roles.yaml (IAM), all with audit tags |
| **D2** | MCDS student model in Silver | etl/silver/bronze-to-silver.py (SIMPLIFIED MCDS mapping per student-sample.json), etl/common/mcds_validator.py (JSON schema validation against parties.schema.json#/$defs/student), config/silver-mappings.yaml (field mappings, NO refdata) |
| **D3** | Reusable Callista onboarding | scripts/generate-mock-data.py (mock pattern), etl/bronze/landing-to-bronze.py (ingestion), docs/ONBOARDING-PATTERN.md (runbook), config/*.yaml (config-driven) |
| **D4** | Governance framework | governance/roles.yaml (IAM roles), data/datalake.yaml (KMS encryption), etl/validation/data-quality-checks.py (DQ checks), data/audit-trail.yaml (CloudTrail) |
| **D5** | Two Gold reports in Athena | etl/gold/silver-to-gold.py (generates student_load_by_unit, student_load_by_facility), athena/queries/query-gold-reports.sql (query patterns) |
| **D6** | All code in Git repository | All 13 steps committed to feature/callista-mcds-implementation branch (local commits, not pushed) |
| **D7** | Production roadmap with TBD items | config/roadmap.md (6 TBD items documented, productionization phases, NL query future enhancement) |

---

**Plan Complete.** All steps concrete, ordered by dependency, independently verifiable with exact commands/assertions. Implementer follows steps 1-13 sequentially, verifies each before proceeding.
