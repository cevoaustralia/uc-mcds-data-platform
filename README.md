# UC MCDS Data Platform

**Institution:** University of Canberra  
**Project:** MortarCAPS Higher Education Data Standard (MCDS) v2.1.1  
**Engagement:** 6-week EBA (Oct 19 - Nov 29, 2026)  
**Status:** 🔄 In Development (Week 1)

---

## Overview

AWS data platform implementing MCDS v2.1.1 standard for University of Canberra student enrolment data, built on **AWS MDAA (Modern Data Architecture Accelerator)**.

### Architecture

**Medallion Data Lake:** Bronze → Silver → Gold  
**Source System:** Callista Student Management System (Oracle)  
**Target Standard:** MCDS v2.1.1 compliant analytics  
**Foundation:** AWS MDAA (configuration-driven deployment)

### Key Components

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Ingestion** | AWS DMS | Callista Oracle → S3 Bronze (CDC replication) |
| **Bronze** | S3 + Glue Catalog | Raw Callista data (6 tables, Parquet format) |
| **Silver** | Glue ETL (PySpark) | MCDS v2.1.1 transformed entities (6 entities) |
| **Gold** | Glue ETL (PySpark) | Analytics aggregations (student load by unit/facility) |
| **Governance** | Lake Formation | Fine-grained access control, PII protection |
| **Query** | Athena | SQL queries over Gold layer |

---

## Documentation

Comprehensive documentation maintained in Confluence:

**Confluence:** https://cevo.atlassian.net/wiki/spaces/DAI/pages/3672080388/MCDS+Data+Platform+Technical+Architecture+Guide

**Key Documents:**
- Architecture Overview & Data Flow
- MDAA Integration & Gap Analysis
- Entity Selection & Sample Data Analysis
- Local Implementation Requirements (Week 1-2)
- University Deployment Requirements (Week 3-6)

---

## Repository Structure

### MDAA Configuration-Based Structure

```
uc-mcds-data-platform/
├── README.md                              # Project overview (this file)
├── .gitignore                             # Ignore MCDS v2.1.1, venv, node_modules
│
├── mdaa.yaml                              # 🔧 MDAA Main Configuration
│
├── governance/                            # 🔐 IAM Roles & Access Control
│   ├── roles.yaml                         # Data admin, data user, Glue ETL roles
│   └── lakeformation-settings.yaml        # Lake Formation admin mode
│
├── data/                                  # 🗄️ Data Lake Infrastructure
│   ├── datalake.yaml                      # S3 buckets (Bronze/Silver/Gold) + KMS
│   ├── glue-catalog.yaml                  # Account-level Glue Catalog encryption
│   ├── athena-workgroup.yaml              # Athena workgroups for analysts
│   └── audit-trail.yaml                   # CloudTrail + S3 audit bucket
│
├── dataops/                               # 🔄 Data Operations (ETL, DMS, Quality)
│   ├── project.yaml                       # Glue databases (bronze_callista, silver_mcds, gold_analytics)
│   ├── dms.yaml                           # DMS replication (Callista → Bronze)
│   ├── jobs.yaml                          # Glue ETL job definitions
│   ├── crawler.yaml                       # Glue crawlers
│   └── data-quality.yaml                  # Glue Data Quality rulesets
│
├── etl/                                   # 🐍 Glue ETL Scripts (PySpark)
│   ├── common/                            # Shared utilities
│   │   ├── s3_utils.py                    # S3 read/write helpers
│   │   ├── glue_utils.py                  # Spark session, catalog utils
│   │   ├── logging_utils.py               # CloudWatch logging
│   │   └── mcds_validator.py              # JSON Schema validation
│   │
│   ├── bronze/                            # Landing → Bronze
│   │   └── landing_to_bronze.py           # DMS-triggered ingestion
│   │
│   ├── silver/                            # Bronze → Silver (MCDS)
│   │   ├── bronze_to_silver.py            # Main transformation job
│   │   └── transformations/               # 6 entity-specific transformers
│   │       ├── student.py                 # ST_STUDENT → Students
│   │       ├── student_name.py            # ST_STUDENT_NAME → StudentNames
│   │       ├── address.py                 # ST_ADDRESS → Addresses
│   │       ├── programme_enrol.py         # ST_PROGRAMME_ENROL → ProgrammeEnrolments
│   │       ├── unit_enrol.py              # ST_UNIT_ENROL → UnitEnrolments
│   │       └── unique_id.py               # ST_UNIQUE_ID → StudentUniqueIDs
│   │
│   └── gold/                              # Silver → Gold (Analytics)
│       ├── silver_to_gold.py              # Aggregation job
│       └── aggregations/                  # SOW requirements
│           ├── student_load_by_unit.py    # Unit enrolment aggregation
│           └── student_load_by_facility.py # Facility enrolment aggregation
│
├── sample-data/                           # 🎲 Mock Data Generator (Development)
│   ├── generators/                        # Generate 6 Callista tables
│   ├── generate_all.py                    # Generate full dataset (100 students)
│   └── upload_to_s3.py                    # Upload to Cevo AWS S3
│
├── tests/                                 # 🧪 Testing Suite
│   ├── unit/                              # Fast unit tests (no AWS)
│   ├── integration/                       # Integration tests (Cevo AWS)
│   └── e2e/                               # End-to-end tests (deployed stack)
│
├── scripts/                               # 🛠️ Utility Scripts
│   ├── setup_local_env.sh                 # Install dependencies
│   ├── deploy_cevo.sh                     # Deploy to Cevo AWS
│   └── deploy_university.sh               # Deploy to University AWS
│
├── MCDS - v2.1.1/                         # 📦 MCDS Reference Package (gitignored)
│   └── v2.1.1/
│       ├── schemas/                       # 19 JSON Schema files
│       ├── reference/AU/                  # 25 AU reference data files
│       └── examples/                      # Sample MCDS outputs
│
├── requirements.txt                       # Python dependencies
└── package.json                           # Node.js dependencies (MDAA CLI)
```

### Key Design Principles

1. **MDAA Configuration Model:** YAML-based module configs, not hand-coded CDK
2. **Layer Visibility:** Bronze/Silver/Gold explicit in folder structure
3. **MCDS Schema Integration:** Reference data and schemas linked in ETL
4. **Multi-Environment:** Cevo AWS (dev) → University AWS (prod)

---

## MDAA Integration

### What MDAA Provides

MDAA delivers pre-built, production-ready modules via declarative YAML configuration.

| Component | MDAA Module | Purpose | UC Usage |
|-----------|-------------|---------|----------|
| **S3 Data Lake** | `datalake` | KMS-encrypted S3 buckets | Bronze/Silver/Gold layers |
| **Glue Catalog** | `glue-catalog` | Account-level catalog encryption | Schema registry foundation |
| **Glue Databases** | `dataops-project` | Glue databases + Lake Formation grants | bronze_callista, silver_mcds, gold_analytics |
| **Lake Formation** | `lakeformation-settings` | Admin mode + IAM principals | PII protection, fine-grained access |
| **Athena** | `athena-workgroup` | Athena workgroups | Gold layer SQL queries |
| **IAM Roles** | `roles` | Pre-configured IAM roles | data-admin, data-user, glue-etl |
| **Audit Trail** | `audit-trail` | CloudTrail + S3 audit bucket | Compliance logging |
| **DMS** | `dataops-dms` | DMS replication instances + tasks | Callista Oracle → S3 Bronze |
| **Glue ETL** | `dataops-jobs` | Glue job definitions | Bronze→Silver→Gold transformations |
| **Data Quality** | `dataops-data-quality` | Glue Data Quality rulesets | MCDS validation |

### What We Build (Custom)

| Component | Why Custom | Location |
|-----------|------------|----------|
| **MCDS Transformations** | MCDS v2.1.1-specific logic | `etl/silver/transformations/` |
| **MCDS Validation** | JSON Schema validation | `etl/common/mcds_validator.py` |
| **AU Reference Data** | SACC, AQF, TCSI enrichment | Integrated in Silver ETL |
| **Mock Data Generator** | Testing support | `sample-data/generators/` |
| **Aggregations** | SOW-specific analytics | `etl/gold/aggregations/` |

### MDAA Starter Kit Options

**Available Kits:**
1. **Minimal** - Foundation only (IAM + Glue Catalog + Lake Formation)
2. **Basic Data Lake** - S3 + Glue + Lake Formation + Athena + Audit
3. **Health Data Accelerator** - Healthcare-focused with DMS CDC ingestion (⭐ includes DMS)
4. **Lakehouse Analytics** - Full stack with Redshift + QuickSight (overkill for our needs)
5. **DataZone Governed Lakehouse** - Enterprise governance with DataZone

**Recommended (TBD):** Health Data Accelerator OR Basic Data Lake + custom DMS module

---

## Data Entities

### Callista Source (6 Tables)

| Callista Table | Purpose | Sample Row Count |
|----------------|---------|------------------|
| `ST_STUDENT` | Student demographics | 100-1,000 |
| `ST_STUDENT_NAME` | Student names (current + historical) | 100-1,200 |
| `ST_ADDRESS` | Student addresses | 200-2,000 |
| `ST_PROGRAMME_ENROL` | Programme enrolments | 100-1,500 |
| `ST_UNIT_ENROL` | Unit enrolments | 500-10,000 |
| `ST_UNIQUE_ID` | USI (Unique Student Identifier) | 100-1,000 |

### MCDS Silver Entities (6 Entities)

| MCDS Entity | Source Table(s) | Validation |
|-------------|-----------------|------------|
| `Students` | ST_STUDENT | JSON Schema + business rules |
| `StudentNames` | ST_STUDENT_NAME | JSON Schema + business rules |
| `Addresses` | ST_ADDRESS | JSON Schema + business rules |
| `ProgrammeEnrolments` | ST_PROGRAMME_ENROL | JSON Schema + business rules |
| `UnitEnrolments` | ST_UNIT_ENROL | JSON Schema + business rules |
| `StudentUniqueIDs` | ST_UNIQUE_ID | JSON Schema + business rules |

### Gold Analytics (SOW Requirements)

| Aggregation | Purpose | Source |
|-------------|---------|--------|
| `student_load_by_unit` | Unit enrolment counts | UnitEnrolments + ProgrammeEnrolments |
| `student_load_by_facility` | Facility enrolment counts | UnitEnrolments + ProgrammeEnrolments + reference data |

---

## Quick Start

### Prerequisites

```bash
# Required tools
- Python 3.9+
- Node.js 20 LTS
- AWS CLI v2
- MDAA CLI (via npx)
- Git 2.x
```

### Cevo AWS Development Setup (Week 1-2)

```bash
# 1. Clone repository
git clone https://github.com/sumana-cevo/uc-mcds-data-platform.git
cd uc-mcds-data-platform

# 2. Install dependencies
npm install                    # MDAA CLI + CDK dependencies
pip install -r requirements.txt

# 3. Configure AWS credentials (Cevo AWS account)
aws configure --profile cevo-aws

# 4. Bootstrap CDK (one-time, per account/region)
npx cdk bootstrap --profile cevo-aws

# 5. Configure MDAA (edit mdaa.yaml, set organization, context values)
# Set organization: "uc-mcds-dev"
# Set context: vpc_id, subnet_ids, notification_email, etc.

# 6. Deploy MDAA modules
npx @aws-mdaa/cli deploy --profile cevo-aws

# 7. Generate mock data
cd sample-data
python generate_all.py
python upload_to_s3.py --profile cevo-aws

# 8. Run ETL pipeline
aws glue start-job-run --job-name landing-to-bronze --profile cevo-aws

# 9. Query Gold layer
aws athena start-query-execution \
  --query-string "SELECT unit_code, student_count FROM gold_analytics.student_load_by_unit" \
  --result-configuration OutputLocation=s3://uc-mcds-dev-athena-results/ \
  --profile cevo-aws
```

### University Deployment (Week 3-6)

```bash
# 1. Configure University AWS credentials
aws configure --profile university-prod

# 2. Deploy to University DEV
npx @aws-mdaa/cli deploy --profile university-prod --context env=dev

# 3. Set up DMS replication (configure dms.yaml with Callista endpoints)
# See Confluence: docs/03-implementation/dms-setup.md

# 4. Deploy to University PROD (manual approval required)
npx @aws-mdaa/cli deploy --profile university-prod --context env=prod
```

---

## Testing

### Run All Tests

```bash
# Unit tests (fast, no AWS)
cd tests
pytest unit/ -v

# Integration tests (Cevo AWS)
pytest integration/ -v --profile cevo-aws

# E2E tests (deployed stack)
pytest e2e/ -v --env cevo-aws
```

---

## Implementation Timeline

### Phase 1: Cevo AWS Development (Week 1-2, Oct 19 - Nov 1)

| Week | Deliverable | Status |
|------|-------------|--------|
| **Week 1** | MDAA deployment + Mock data + Bronze ingestion | 🔄 In Progress |
| **Week 2** | Silver transformations (6 entities) + Gold aggregations + Testing | ⏳ Planned |

### Phase 2: University Deployment (Week 3-6, Nov 2 - Nov 29)

| Week | Deliverable | Status |
|------|-------------|--------|
| **Week 3** | DMS setup + University DEV deployment + Sample data extraction | ⏳ Planned |
| **Week 4** | Integration testing + Data quality validation | ⏳ Planned |
| **Week 5** | University PROD deployment + Performance tuning | ⏳ Planned |
| **Week 6** | Handover + Training + Documentation finalization | ⏳ Planned |

---

## Cost Estimates

### Cevo AWS Development (Week 1-2)

Estimated **$15-25/month** for development testing with mock data (100 students).

**Services:** S3 storage, Glue ETL jobs (minimal usage), Glue Catalog, Athena queries (small datasets).

### University Production (Week 3+)

Estimated **$150-250/month** depending on data volume, query frequency, and DMS instance size.

**Services:** DMS replication instance (24/7), S3 storage (Bronze/Silver/Gold), Glue ETL jobs, Glue Catalog, Athena queries, Lake Formation, CloudWatch, KMS.

**Note:** Costs vary significantly based on:
- Student data volume (100 vs 1,000 vs 10,000 students)
- DMS instance size (t3.medium vs t3.large)
- Glue job frequency and DPU allocation
- Athena query patterns

---

## Security & Governance

### Data Classification

| Layer | Data Classification | Encryption | Access Control |
|-------|-------------------|------------|----------------|
| **Bronze** | Sensitive (raw Callista) | KMS (bronze-key) | Data engineers only |
| **Silver** | Sensitive (MCDS with PII) | KMS (silver-key) | Data engineers + analysts |
| **Gold** | Internal (aggregated) | KMS (gold-key) | All analysts + reports |

### PII Protection (Proposed - For UC Confirmation)

**Lake Formation Column-Level Security:**

**Proposed PII Columns:**
- `StudentNames.givenNames` → Restricted
- `StudentNames.surname` → Restricted
- `StudentNames.preferredName` → Restricted
- `Addresses.addressLine1` → Restricted
- `Addresses.addressLine2` → Restricted
- `Addresses.postalCode` → Restricted
- `StudentUniqueIDs.studentUniqueId` (USI) → Restricted
- `Students.dateOfBirth` → Restricted
- `Students.countryOfBirth` → Restricted
- `ContactMethods.emailAddress` → Restricted
- `ContactMethods.phoneNumber` → Restricted

**Access:** Requires explicit Lake Formation grant

**Note:** Full PII classification pending University of Canberra confirmation.

---

## Open Decisions

Items requiring confirmation before University deployment:

| Decision | Options | Status |
|----------|---------|--------|
| **Student Load Metric (Primary Display)** | EFTSL-first vs Headcount-first | ⏳ Get UC confirmation (both metrics provided) |
| **Data Ingestion Method** | DMS (real-time CDC) vs Parquet files (batch) | ⏳ DMS preferred, Parquet as fallback |
| **CI/CD Tool** | GitHub Actions vs AWS CodePipeline | ⏳ Get UC confirmation (GitHub Actions for Cevo dev) |
| **MDAA Starter Kit** | Health Data Accelerator vs Basic Data Lake | ⏳ Evaluate both options |
| **MDAA Version** | 1.8.1 (stable) vs 1.9.0 (latest) | ⏳ Assess stability |
| **Landing Layer** | DMS → Landing → Bronze vs DMS → Bronze | ⏳ Direct to Bronze (simpler) |
| **Facility Data Source** | Unknown | ⏳ Get UC confirmation (not in 6 Callista tables) |
| **Repo Transfer** | Personal GitHub → Cevo/UC organization | ⏳ Get UC confirmation before PROD deployment |
| **Sydney Region Support** | MDAA module compatibility | ⏳ Verify ap-southeast-2 support |

**Context:**
- **Cevo Environment (Week 1-2):** Uses Cevo AWS sandbox + GitHub Actions for local development
- **University Environment (Week 3+):** All decisions above require UC confirmation when environment details available

---

## Support & Contact

### Cevo Team

- **Lead Data Engineer:** Sumana Pandi (sumana.pandi@cevo.com.au)
- **Principal Data Consultant:** Stuart McGoldrick

### University of Canberra Team

- **Project Sponsor:** TBD
- **Technical Lead:** TBD
- **DBA Contact:** TBD

### Resources

- **Confluence:** https://cevo.atlassian.net/wiki/spaces/DAI/pages/3672080388
- **GitHub:** https://github.com/sumana-cevo/uc-mcds-data-platform
- **MCDS Spec:** https://www.mortarcaps.com.au/mcds-v2-1-1/
- **MDAA Documentation:** https://aws.github.io/modern-data-architecture-accelerator/

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-10-19 | Initial repository structure + MDAA config-based design |

---

**Status:** 🔄 In Development (Week 1)  
**Last Updated:** October 19, 2026
