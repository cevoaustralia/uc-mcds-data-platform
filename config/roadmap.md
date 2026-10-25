# UC MCDS Data Platform - Production Roadmap

**Document:** SOW Deliverable D7 - Production Roadmap  
**Date:** October 25, 2026  
**Status:** EBA Phase Complete - Production Roadmap Defined

---

## Executive Summary

This roadmap outlines the path from EBA (Experience-Based Accelerator) delivery to production deployment and future enhancements. It addresses 6 unconfirmed business rules (TBD items), production deployment requirements, additional MCDS domains, and the Natural Language AI query capability as a future enhancement.

---

## 6 TBD Business Rules - Confirmation Required

All placeholder values are configuration-driven in `config/business-rules.yaml`. When UC confirms real values, **only the config file needs updating** - no code changes required.

| Item | Current Placeholder | Real Source TBD | Config File | UC Confirmation Timeline | Deployment Impact |
|------|-------------------|-----------------|-------------|-------------------------|-------------------|
| **1. Student Number Source** | `STU{PERSON_ID}` formula | `STATE_GOVT_STUDENT_NUMBER` in VET tables | `business-rules.yaml` | Week 3 (UC meeting) | Config-only change |
| **2. Student Load Metric** | `COUNT(DISTINCT studentId)` | Headcount vs `SUM(EFTSU)`? | `business-rules.yaml`, `gold-aggregations.yaml` | Week 3 (UC meeting) | Config-only change |
| **3. Facility Field** | `TR_ORG_UNIT_CD` (organizational) | `TR_ORG_UNIT_CD` vs `GOVT_LOCATION_CD`? | `business-rules.yaml`, `silver-mappings.yaml` | Week 3 (UC schema review) | Config-only change |
| **4. Active Status Codes** | `[1, 2]` mock values | Real `UNIT_COMPLETION_STATUS` codes for "active" | `business-rules.yaml`, `gold-aggregations.yaml` | Week 3 (UC data dictionary) | Config-only change |
| **5. Current Semester** | `2024-S1` mock value | Current reporting semester code | `business-rules.yaml`, `gold-aggregations.yaml` | Week 3 (UC data dictionary) | Config-only change |
| **6. ORG_UNIT Description Column** | `ORG_UNIT_START_DT` placeholder | Real description/name column in `ORG_UNIT` table | `business-rules.yaml`, `silver-mappings.yaml` | Week 3 (UC schema review) | Config-only change, ETL may need JOIN update |

**Priority:** ALL 6 items must be confirmed before production deployment (Week 3).

**Deployment Process (per TBD item):**
1. UC provides real source/value
2. Update `config/business-rules.yaml` (and related mapping YAMLs if needed)
3. Re-run Silver ETL job (if schema changes)
4. Re-run Gold ETL job (filters/aggregations updated)
5. Validate output in Athena
6. Mark item as `confirmed: true` in config

---

## Phase 1: Productionization (Weeks 7-12 post-EBA)

### Week 7-8: UC Environment Setup & Real Data Integration

**Goals:**
- Deploy MDAA stack to UC AWS account (DEV environment)
- Integrate with real Callista Oracle database

**Tasks:**
1. **AWS Account Setup**
   - UC provides AWS account ID and credentials
   - CDK bootstrap in UC AWS account
   - VPC configuration for DMS connectivity

2. **DMS Configuration**
   - Configure DMS replication instance (t3.medium recommended)
   - Set up source endpoint (Callista Oracle)
   - Set up target endpoint (S3 Landing bucket)
   - Configure table mappings for 5 Callista tables
   - Enable CDC (Change Data Capture) for real-time updates

3. **Confirm 6 TBD Business Rules**
   - Schedule UC workshop (Week 7)
   - Review Callista schema with UC DBA
   - Confirm all 6 TBD items (see table above)
   - Update `config/business-rules.yaml`

4. **Initial Data Load**
   - Full load from Callista to Landing
   - Run Bronze ETL (landing-to-bronze)
   - Run Silver ETL (bronze-to-silver)
   - Run Gold ETL (silver-to-gold)
   - Validate row counts and data quality

**Deliverables:**
- UC DEV environment deployed
- DMS replication operational
- All 6 TBD items confirmed and updated
- Initial real data load complete

**Cost Estimate:** $500-800/month (DMS instance + Glue jobs + S3 storage)

---

### Week 9-10: Incremental ETL & Automation

**Goals:**
- Implement incremental processing (not full reload every time)
- Automate ETL orchestration

**Tasks:**
1. **Incremental Bronze Processing**
   - Modify `landing-to-bronze.py` to detect new/changed files
   - Partition strategy (by ingestion date)
   - Avoid reprocessing unchanged data

2. **Incremental Silver Processing**
   - Implement upsert logic (merge new/changed records)
   - Handle deletes (soft delete pattern)
   - Optimize for performance at scale

3. **ETL Orchestration**
   - AWS Step Functions state machine:
     - Step 1: Trigger on S3 Landing file arrival (EventBridge)
     - Step 2: Run landing-to-bronze Glue job
     - Step 3: Run bronze-to-silver Glue job
     - Step 4: Run silver-to-gold Glue job
     - Step 5: Run data-quality-checks job
     - Step 6: Send SNS notification on success/failure
   - Schedule: Trigger on DMS file arrival (real-time) or daily batch (configurable)

4. **Monitoring & Alerting**
   - CloudWatch dashboards (job success rate, data freshness, cost)
   - CloudWatch alarms (job failures, DQ check failures, high cost)
   - SNS notifications to UC data engineering team

**Deliverables:**
- Incremental ETL operational
- Automated orchestration via Step Functions
- Monitoring dashboards and alarms configured

**Cost Estimate:** +$100/month (Step Functions, CloudWatch, SNS)

---

### Week 11-12: Performance Tuning & UC PROD Deployment

**Goals:**
- Optimize for production-scale data (10,000+ students)
- Deploy to UC PROD environment

**Tasks:**
1. **Performance Optimization**
   - Tune Glue job worker counts and types (test G.1X vs G.2X)
   - Optimize Spark SQL joins and aggregations
   - Implement partition pruning in queries
   - Benchmark query performance (<10s for Gold reports)

2. **Cost Optimization**
   - Right-size DMS instance (t3.medium vs t3.large)
   - Implement S3 lifecycle policies (archive to Glacier after 90 days)
   - Use Glue FLEX execution class where appropriate (up to 34% savings)
   - Review Athena query patterns (optimize scans)

3. **Disaster Recovery**
   - Enable cross-region replication for S3 (primary: ap-southeast-2, backup: ap-southeast-1)
   - Document rollback procedures (ETL job version management)
   - Test recovery from Bronze layer (re-run Silver/Gold ETL)

4. **UC PROD Deployment**
   - Deploy MDAA stack to UC PROD AWS account
   - Configure DMS replication from Callista PROD
   - Run full load with real production data
   - Validate all SOW acceptance criteria (D1-D6)

5. **Handover**
   - Knowledge transfer sessions (5 sessions, see SOW D6)
   - Operational runbooks delivery
   - Support transition plan (Cevo → UC team)

**Deliverables:**
- Optimized ETL pipeline (performance & cost)
- UC PROD environment operational
- Handover documentation and training complete

**Cost Estimate (PROD):** $800-1,500/month (depends on data volume and query frequency)

---

## Phase 2: Additional MCDS Entities (Weeks 13-20)

### Goal: Expand beyond student enrolment data to additional MCDS domains

**Priority 1: Additional Student Entities (Weeks 13-16)**
- `StudentNames` (historical name changes)
- `Addresses` (student addresses)
- `ContactMethods` (phone numbers, email history)
- `StudentUniqueIDs` (USI - Unique Student Identifier)

**Priority 2: Programme & Assessment (Weeks 17-18)**
- `ProgrammeEnrolments` (degree program enrolments)
- `Assessment` (assessment tasks and results)
- `UnitResults` (final unit grades)

**Priority 3: Staff & Resources (Weeks 19-20)**
- `StaffAllocations` (unit teaching allocations)
- `FeeStructures` (unit fees and charges)

**Implementation Approach (per entity):**
1. Identify Callista source tables (workshop with UC)
2. Create Bronze schema definitions
3. Update `config/silver-mappings.yaml` with MCDS mappings
4. Extend Bronze/Silver ETL jobs (reuse existing framework)
5. Create Gold reports as needed
6. Validate against MCDS JSON schemas

**Effort:** 2 weeks per group of related entities (4 entities/group)

**Cost Impact:** +$200-400/month (additional Glue job runs, S3 storage)

---

## Phase 3: Natural Language AI Query Capability (Weeks 21-26)

### Goal: Enable analysts to query Gold layer using natural language (SOW D7 future enhancement)

**Architecture:**
```
User Question
    ↓
Amazon Bedrock (Claude 3 Sonnet)
    ↓
Text-to-SQL Generation
    ↓
Bedrock Guardrails (SQL injection prevention)
    ↓
Lake Formation Access Control (row/column-level security)
    ↓
Amazon Athena Query Execution
    ↓
Results Display
```

**Implementation (Weeks 21-26):**

**Week 21-22: Foundation**
- Enable Amazon Bedrock in UC AWS account
- Select foundation model (Claude 3 Sonnet recommended)
- Create Bedrock knowledge base with Glue Data Catalog metadata
- Test basic text-to-SQL generation

**Week 23-24: Security & Governance**
- Configure Bedrock Guardrails:
  - SQL injection prevention
  - PII data masking
  - Query complexity limits (prevent expensive queries)
- Integrate Lake Formation access control:
  - Respect user's row-level permissions
  - Respect column-level security (PII redaction)
  - Audit all AI-generated queries

**Week 25: UI Development**
- Build web interface (React + API Gateway + Lambda)
- Question input box
- SQL preview (show generated SQL before execution)
- Results table display
- Query history

**Week 26: Testing & Tuning**
- Test with 50+ common questions:
  - "How many students are enrolled in MATH1001 at Bruce Campus?"
  - "What is the total EFTSU for Faculty of Science in Semester 1 2024?"
  - "Show me the top 10 units by student count"
- Fine-tune prompts for accuracy
- Performance testing (response time <5 seconds)
- User acceptance testing with UC analysts

**Example Questions:**
- "How many students are enrolled in MATH1001?"
- "Show me student load by faculty for 2024"
- "Which units have more than 100 students?"
- "What is the average EFTSU per student in Faculty of Engineering?"

**Cost Estimate:** $300-600/month (Bedrock API calls + Lambda + API Gateway)

**Benefits:**
- Democratize data access (no SQL knowledge required)
- Faster insights (seconds vs hours)
- Reduced analyst workload (no manual SQL writing)
- MCDS standard promotes cross-institutional queries

---

## Phase 4: Cross-Institutional Integration (Weeks 27+)

### Goal: Enable data exchange between UC and other Australian universities using MCDS as interoperability standard

**Potential Use Cases:**
- Sector benchmarking (compare unit enrolments across universities)
- Student transfer data exchange (MCDS as standard format)
- National reporting (aggregated MCDS data to TEQSA/AQIS)

**Technical Approach:**
1. **API Layer**
   - Build REST API on top of Gold layer (API Gateway + Lambda)
   - Authentication (OAuth 2.0 for institutional users)
   - MCDS JSON format responses (standardized across institutions)

2. **Data Sharing Agreements**
   - Privacy impact assessment
   - Data sharing agreements between institutions
   - Define allowed aggregation levels (no student-level PII sharing)

3. **MCDS Compliance Validation**
   - Automated MCDS JSON schema validation
   - Reference data validation (Australian codes: AQF, SACC, TCSI)
   - Compliance reporting dashboard

**Effort:** 12+ weeks (highly dependent on stakeholder engagement)

**Benefit:** UC becomes MCDS early adopter, influence future MCDS spec evolution

---

## Success Metrics (Production)

### Data Quality KPIs
- **ETL Success Rate:** > 99% (target: 1 failure per 100 runs)
- **Data Freshness:** < 24 hours (from Callista update to Gold report)
- **DQ Check Pass Rate:** 100% (zero tolerance for referential integrity failures)

### Performance KPIs
- **Bronze ETL Duration:** < 5 minutes (for 5 tables)
- **Silver ETL Duration:** < 15 minutes (including MCDS validation)
- **Gold ETL Duration:** < 5 minutes (2 reports)
- **Athena Query Performance:** < 10 seconds (Gold layer queries)

### Cost KPIs
- **Monthly AWS Cost:** $800-1,500 (PROD environment)
- **Cost per Student Record:** < $0.01/month

### Governance KPIs
- **Zero Data Breaches:** No unauthorized data access
- **Audit Trail Completeness:** 100% of operations logged in CloudTrail
- **MCDS Compliance Rate:** 100% of Silver records pass JSON schema validation

---

## Governance Model (Ongoing)

### Monthly Reviews
- Data quality dashboard review
- Cost review and optimization opportunities
- ETL failure root cause analysis
- Performance trend analysis

### Quarterly Reviews
- Schema evolution planning (new Callista tables, MCDS updates)
- Security audit (IAM policies, Lake Formation permissions)
- Capacity planning (data volume growth, query patterns)

### Annual Reviews
- Full security audit (penetration testing, access reviews)
- MCDS spec version upgrade assessment (v2.1.1 → v2.2.0)
- Cost-benefit analysis (platform value vs cost)

### Change Management
1. **Minor Changes** (config updates, adding tables):
   - Data engineer approval
   - DEV testing
   - PROD deployment (next maintenance window)

2. **Major Changes** (schema changes, new entities):
   - Data architect approval
   - UC stakeholder review
   - DEV testing (2 weeks)
   - UAT in PROD-like environment
   - PROD deployment (scheduled maintenance)

3. **Emergency Changes** (data quality issues, security):
   - Immediate approval by data admin
   - Rollback plan prepared
   - Post-mortem within 48 hours

---

## Risk Assessment & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| **Callista access delays** | High | Medium | Early engagement with UC DBA (Week 3), backup plan: Parquet file export |
| **Data quality issues in PROD** | High | Medium | Comprehensive DQ checks, Bronze layer preservation for reprocessing |
| **Performance at scale (10,000+ students)** | Medium | Low | Performance testing in DEV with synthetic 10K dataset, Glue auto-scaling |
| **UC staff availability** | Medium | Medium | Cross-train multiple UC staff members, detailed runbooks |
| **MCDS spec changes** | Low | Low | Monitor MortarCAPS releases, version control MCDS schemas in repo |
| **AWS cost overrun** | Medium | Low | Monthly cost reviews, CloudWatch billing alarms, optimization playbook |

---

## Contact & Support

**Cevo Team:**
- Lead Data Engineer: Sumana Pandi (sumana.pandi@cevo.com.au)
- Principal Data Consultant: Stuart McGoldrick

**UC Team:** (TBD)
- Project Sponsor
- Technical Lead
- DBA Contact

**Support Model:**
- **EBA Phase (Weeks 1-6):** Cevo full support
- **Productionization (Weeks 7-12):** Cevo + UC collaboration
- **Post-Handover (Week 13+):** UC primary, Cevo advisory (optional retainer)

---

## Appendix A: Estimated Costs

### EBA Phase (Mock Data)
- **Total:** $25-50/month
- S3 storage: $5/month
- Glue jobs: $15-30/month (development testing)
- Athena: $5/month

### Production (Real Data)
- **Total:** $800-1,500/month
- DMS replication instance (t3.medium, 24/7): $200-300/month
- S3 storage (Bronze/Silver/Gold): $100-200/month
- Glue ETL jobs: $300-600/month (daily runs)
- Athena queries: $50-200/month (depends on query frequency)
- CloudWatch, Step Functions, SNS: $50-100/month
- Data transfer: $50-100/month

### Phase 3: NL AI Query (Additional)
- **Total:** +$300-600/month
- Amazon Bedrock API calls: $200-400/month
- Lambda + API Gateway: $50-100/month
- UI hosting (Amplify/CloudFront): $50-100/month

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-25 | Sumana Pandi | Initial roadmap (SOW D7 deliverable) |

**Next Review:** Week 3 (after UC confirmation of 6 TBD items)

