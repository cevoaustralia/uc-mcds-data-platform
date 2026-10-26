# UC MCDS EBA Demo Guide & Confirmations Needed

**Date:** October 26, 2026  
**Purpose:** Comprehensive guide for UC demo including what we built, why we chose each table, what we're unsure of, and what confirmations we need.

---

## Part 1: What We Built (Demo Overview)

### The Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 7 Callista Tables (Raw Data)                                         │
├─────────────────────────────────────────────────────────────────────┤
│ ✓ GOVT_STUDENT_LOAD (1098 rows)  ← Core fact table                   │
│ ✓ STUDENT_UNIT_ATTEMPT (827 rows) ← Adds campus & offering details   │
│ ✓ PERSON (168 rows)               ← Student information              │
│ ✓ UNIT_VERSION (42 rows)          ← Unit definitions                 │
│ ✓ ORG_UNIT (7 rows)               ← Faculties & schools              │
│ ✓ LOCATION (5 rows)               ← Campuses                         │
│ ✓ CAL_INSTANCE (4 rows)           ← Teaching periods                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 6 MCDS Silver Entities (Standardized Data Model)                     │
├─────────────────────────────────────────────────────────────────────┤
│ ✓ student_unit_load (1061 rows)  ← FACT: unit enrollments & load    │
│ ✓ student (150 rows)              ← Students with gov't load         │
│ ✓ unit_of_learning (42 rows)     ← Units taught                      │
│ ✓ organisation (7 rows)           ← Teaching departments             │
│ ✓ location (5 rows)               ← Delivery campuses                │
│ ✓ learning_period (4 rows)        ← Teaching periods                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 4 Gold Reports (Business Insights)                                   │
├─────────────────────────────────────────────────────────────────────┤
│ ✓ Student Load by Unit (72 rows)          ← "How many in each unit?" │
│ ✓ Student Load by Campus (8 rows)         ← "Load per campus?"       │
│ ✓ Student Load by Teaching Org (12 rows)  ← "Load per faculty?"      │
│ ✓ Student Load by Unit+Campus (190 rows)  ← "Cross-mapping"          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ MCDS-Compliant JSON Files (Ready for Submission)                     │
├─────────────────────────────────────────────────────────────────────┤
│ ✓ students-2026-10-25-0001.json (150 students)                       │
│ ✓ 4 Report Definitions (metadata)                                    │
│ ✓ 8 Fact Data files (4 reports × 2 semesters)                        │
│ ✓ All 13 files validated against MCDS schemas ✓✓✓                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Demo Outcomes

1. **✅ Data Quality:** 19/19 checks passed
2. **✅ MCDS Validation:** 13/13 schema validations passed
3. **✅ Reconciliation:** Bronze → Silver → Gold totals match
4. **✅ Reports Generated:** 4 ready-to-submit reports

---

## Part 2: Why We Chose These 7 Tables

### Table Selection Rationale

| Table | Why Chosen | What It Provides | Confidence Level |
|-------|------------|------------------|------------------|
| **GOVT_STUDENT_LOAD** | ✅ **Mandatory** - Core government census data | • Student unit enrollments<br>• EFTSL values<br>• Teaching splits<br>• Completion status | **HIGH** - Required by TCSI |
| **STUDENT_UNIT_ATTEMPT** | ✅ **Mandatory** - Provides campus delivery location | • Campus (LOCATION_CD)<br>• Unit offering ID<br>• Attempt status | **HIGH** - Only source of campus |
| **PERSON** | ✅ **Mandatory** - Student identifiers & names | • Student names<br>• **PERSON_ID** → studentID, personID, studentNumber<br>• All three MCDS identifiers derived from same field | **MEDIUM** - Need UC to confirm PERSON_ID is student-facing number |
| **UNIT_VERSION** | ✅ **Mandatory** - Unit definitions | • Unit names<br>• Credit points<br>• Unit levels<br>• Owner faculty | **HIGH** - Composite key prevents fan-out |
| **ORG_UNIT** | ✅ **Mandatory** - Teaching department attribution | • Faculty/school names<br>• Org hierarchy<br>• Effective dates | **MEDIUM** - Need UC confirmation on splits |
| **LOCATION** | ✅ **Mandatory** - Campus names & types | • Campus names<br>• Online vs physical<br>• Closed status | **HIGH** - Straightforward mapping |
| **CAL_INSTANCE** | ✅ **Mandatory** - Teaching period dates | • Semester start/end<br>• Period codes<br>• Calendar years | **HIGH** - MCDS required field |

### Tables We Did NOT Choose (And Why)

| Excluded Table | Why NOT Chosen | When We'd Need It |
|----------------|----------------|-------------------|
| **COURSE** | Not in Sisprod extract metadata | If UC requires program details beyond code |
| **UNIT_OFFERING** | Not in metadata, redundant with SUA.UOO_ID | If we need more offering attributes |
| **STAFF** | No staff teaching data in scope | Phase 2: Staff FTE reporting |
| **ENROLMENT** | Redundant - covered by GOVT_STUDENT_LOAD | Never needed for student load |

---

## Part 3: What We're Confident About

### ✅ Strong Confidence (Validated by Standards)

1. **Composite Keys Are Correct**
   - `UNIT_CD + VERSION_NUMBER` (prevents join fan-out)
   - `ORG_UNIT_CD + START_DT` (handles org restructures)
   - `CAL_TYPE + SEQUENCE_NUMBER` (uniquely identifies periods)
   - **Evidence:** DQ check `silver_pk_unique` passed

2. **Submission Selection Rule**
   - Filter: `COMMENCING_SUBMISSION_CD IN ('Y', 'A')`
   - Rationale: TCSI standard for counting only "commencing" submissions
   - **Result:** 1098 → 1061 rows (37 filtered out)
   - **Evidence:** Aligns with government reporting guidelines

3. **Foreign Key Relationships**
   - All joins validated: student, unit, campus, period, org unit
   - **Evidence:** DQ checks `fk_student`, `fk_unit`, `fk_location`, `fk_teaching_org_unit`, `fk_learning_period` all passed

4. **No Join Fan-Out**
   - Fact row count = GOVT_STUDENT_LOAD count after selection
   - **Evidence:** DQ check `fact_no_fanout` passed

5. **MCDS Schema Compliance**
   - All required fields present
   - All JSON structures valid
   - **Evidence:** 13/13 MCDS validations passed

---

## Part 4: What We're Unsure About (Need UC Confirmation)

### ⚠️ Assumptions Needing Validation

#### 1. EFTSL Calculation (CRITICAL)
**Current State:** All EFTSL values showing **0.000** in reports

**What we assumed:**
```sql
-- Option A: Direct from field (current implementation)
SELECT EFTSU FROM GOVT_STUDENT_LOAD  -- Currently returns 0.000

-- Option B: Calculate from credit points
SELECT ENROLLED_CREDIT_POINTS / 48.0 AS eftsu 
FROM UNIT_VERSION
```

**Questions for UC:**
- ✅ Does `GOVT_STUDENT_LOAD.EFTSU` contain the correct EFTSL value?
- ✅ Or should we calculate it from `UNIT_VERSION.ENROLLED_CREDIT_POINTS`?
- ✅ What's UC's formula? (Standard: 1 year full-time = 48 credit points = 1.0 EFTSL)
- ✅ Are there special cases? (Research units, cross-institutional?)

**Impact if wrong:** Government funding calculations will be incorrect

---

#### 2. Student Type Mapping

**Current assumption:**
```
Callista Code → MCDS Value
D (Domestic)  → "domestic"
I (International) → "international"  
O (Offshore)  → "international" (treated same as I)
```

**Questions for UC:**
- ✅ Is this mapping correct?
- ✅ How should "O" (Offshore) be classified? (Currently: international)
- ✅ Are there other student types we're missing?
- ✅ What about exchange students or cross-institutional enrollments?

**Impact if wrong:** Government reporting categories will be miscategorized

---

#### 3. Attendance Mode Logic

**Current assumption:**
```python
ATTENDANCE_TYPE + ATTENDANCE_MODE → MCDS mode_of_attendance

F (Full-time) + INT (Internal)  → "full_time_on_campus"
F (Full-time) + EXT (External)  → "full_time_online"
P (Part-time) + INT (Internal)  → "part_time_on_campus"
P (Part-time) + EXT (External)  → "part_time_online"
```

**Questions for UC:**
- ✅ Is this mapping correct?
- ✅ What about mixed-mode delivery? (F + EXT = full-time but external?)
- ✅ Does UC have non-standard combinations?
- ✅ Should "online" vs "on_campus" be determined by LOCATION_CD instead?

**Impact if wrong:** Student mode classification will be incorrect

---

#### 4. Teaching Split Interpretation

**Current understanding:**
```
GOVT_STUDENT_LOAD has multiple rows per unit attempt when:
- Teaching responsibility is split between departments
- TR_ORG_UNIT_CD = the teaching faculty/school
- EFTSU = the load share for that teaching split
```

**Questions for UC:**
- ✅ Is our interpretation correct?
- ✅ Do teaching splits always sum to 100% per student-unit?
- ✅ Are there cases where TR_ORG_UNIT_CD is NULL?
- ✅ How should we handle cross-faculty teaching?

**Impact if wrong:** Faculty workload reports will be incorrect

---

#### 5. Unit Offering Identification

**Current assumption:**
```
Unit Offering Composite Key:
- UNIT_CD
- VERSION_NUMBER  
- CAL_TYPE
- CI_SEQUENCE_NUMBER
- LOCATION_CD
- ORG_UNIT_CD (teaching org)

Retrieved from: STUDENT_UNIT_ATTEMPT.UOO_ID
```

**Questions for UC:**
- ✅ Is `UOO_ID` the correct unique identifier for a unit offering?
- ✅ Or should we construct our own from the composite key above?
- ✅ Can the same unit be offered multiple times in the same period/campus? (e.g., different class times)

**Impact if wrong:** Unit availability reporting will be ambiguous

---

#### 6. Program/Course Identification

**Current assumption:**
```
Program ID = COURSE_CD
No COURSE lookup table in scope
```

**Questions for UC:**
- ✅ Is `COURSE_CD` sufficient for program identification?
- ✅ Do we need program names? (Currently only have code)
- ✅ Is there a `COURSE` table we should be using?
- ✅ Are there program version numbers like unit versions?

**Impact if wrong:** Cannot link students to their degree programs properly

---

#### 7. Student Number Identification

**Current assumption:**
```
All three MCDS student identifiers derived from PERSON.PERSON_ID:

studentID     = "STU-{PERSON_ID}"  (MCDS internal record ID with prefix)
personID      = "{PERSON_ID}"       (MCDS person identifier, raw value)
studentNumber = "{PERSON_ID}"       (MCDS student-facing number, raw value)
```

**Questions for UC:**
- ✅ Is `PERSON_ID` the correct student-facing number UC uses?
- ✅ Or does UC use a different field for the student number students see?
- ✅ Does UC have `ALTERNATE_PERSON_ID` with different ID types?
- ✅ Should studentNumber come from a different table/field?

**Impact if wrong:** Student records won't match UC's student-facing identifiers

---

#### 8. Historical Data Range

**Current state:** Mock data only covers 2026

**Questions for UC:**
- ✅ How many years of history should we migrate?
- ✅ Recommended: Current year + 2 prior years? (2024-2026)
- ✅ Or full history? (May impact performance)
- ✅ When is the cutoff for "historical" vs "current"?

**Impact:** Determines initial data load size and migration timeline

---

## Part 4.1: Student Identifier Clarification

**IMPORTANT:** The PERSON table provides **all three** MCDS student identifiers:

| MCDS Field | Current Value | Source | Purpose |
|------------|--------------|--------|---------|
| `studentID` | `STU-{PERSON_ID}` | PERSON.PERSON_ID with prefix | MCDS internal record identifier (required) |
| `personID` | `{PERSON_ID}` | PERSON.PERSON_ID raw | MCDS person identifier (optional) |
| `studentNumber` | `{PERSON_ID}` | PERSON.PERSON_ID raw | Student-facing number (required) |

**Example:**
- If `PERSON.PERSON_ID = 123456`, then:
  - `studentID = "STU-123456"`
  - `personID = "123456"`
  - `studentNumber = "123456"`

**UC Needs to Confirm:**
- Is `PERSON_ID` the number students see on their student cards/portal?
- Or does UC use a different identifier that should be mapped from `ALTERNATE_PERSON_ID`?

**Configuration Location:** `config/business-rules.yaml`
```yaml
identity:
  student_id_format: "STU-{PERSON_ID}"
  person_id_format: "{PERSON_ID}"
  student_number:
    format: "{PERSON_ID}"
    confirmed: false  # ← Awaiting UC confirmation
```

---

## Part 5: Interactive Lineage Explorer

**Open in browser:** `file:///C:/Users/suman_3kw9zn1/OneDrive/Documents/CEVO/Clients/MCDS/uc-mcds-data-platform/docs/model/lineage-explorer.html`

### What It Shows

1. **Four-Column View:**
   - Column 1: Callista source tables (orange)
   - Column 2: MCDS Silver entities (blue)
   - Column 3: Gold reports (green)
   - Column 4: MCDS outputs (purple)

2. **Click any table to see:**
   - ✓ All fields and their mappings
   - ✓ Which fields are primary keys (marked "pk")
   - ✓ Which fields are required by MCDS (marked "req")
   - ✓ Upstream sources (where data comes from)
   - ✓ Downstream consumers (where data flows to)

3. **Interactive Features:**
   - Click `GOVT_STUDENT_LOAD` → See all 20+ fields and how they map to MCDS
   - Click `student_unit_load` → See the complete fact table structure
   - Click `student_load_by_unit` → See how the report is aggregated

### What's Documented

Every table shows:
- **Key structure** (composite keys highlighted)
- **Description** (why it exists, what it does)
- **All columns** with Callista source → MCDS destination
- **Data lineage** (visual arrows showing flow)

---

## Part 6: Demo Script (What to Show UC)

### Section 1: The Problem We Solved (2 minutes)

**Say:**
> "UC needs to report student load data to the MCDS Hub for government funding and planning. The challenge: Callista data is complex, has teaching splits, and needs transformation to meet MCDS standards."

**Show:**
- Lineage explorer
- Point to 7 Callista tables (orange) → 6 Silver entities (blue)

---

### Section 2: The Data Flow (5 minutes)

**Show 1: Source Data**
```bash
# Show mock data we generated
ls data/mock/landing/callista/2026-10-25/
```

**Say:**
> "We start with 7 Callista tables. Here's the main fact table:"

**Show 2: Run the pipeline**
```bash
cd uc-mcds-data-platform
wsl python3 scripts/run-local-pipeline.py
```

**Narrate the output:**
> "Watch the data flow through three layers:
> 1. **Landing → Bronze:** Raw data (1098 GOVT_STUDENT_LOAD rows)
> 2. **Bronze → Silver:** Transformed to MCDS model (1061 load rows after filtering)
> 3. **Silver → Gold:** Aggregated into 4 business reports"

---

### Section 3: The Reports (10 minutes)

**Show:** Generated reports
```bash
wsl python3 scripts/show-all-reports.py
```

**Walk through each report:**

1. **Student Load by Unit**
   - "Which units have the most students?"
   - Top unit: EDU3105 with 18 students

2. **Student Load by Campus**
   - "How is load distributed across campuses?"
   - Bruce Campus: 91 students (51%)
   - Online: 73 students (41%)

3. **Student Load by Teaching Org Unit**
   - "Which faculties are teaching the most?"
   - Health: 71 students
   - IT School: 70 students

4. **Student Load by Unit AND Campus**
   - "Cross-mapping: Which units are taught where?"
   - EDU3105 @ Bruce: 13 students
   - HLT2101 @ Bruce: 11 students

---

### Section 4: Data Quality & Validation (5 minutes)

**Say:**
> "Every pipeline run performs 19 data quality checks and validates against 13 MCDS schemas."

**Show:** Run report summary
```json
{
  "dq_passed": 19,
  "dq_failed": 0,
  "mcds_validated": 13,
  "reconciliation": "PASS"
}
```

**Highlight:**
- ✅ All foreign keys valid
- ✅ No join fan-out (row counts match)
- ✅ EFTSL totals reconcile across all layers
- ✅ All MCDS required fields present

---

### Section 5: What We Need from UC (10 minutes)

**Say:**
> "The platform is technically complete and validated. To finalize, we need confirmation on 7 business rules where we made educated guesses."

**Show:** This document, Part 4 "What We're Unsure About"

**Walk through:**
1. EFTSL calculation (CRITICAL - currently showing 0.000)
2. Student type mapping
3. Attendance mode logic
4. Teaching split interpretation
5. Unit offering identification
6. Program identification
7. Historical data range

**Ask:**
> "Can we schedule a follow-up session with your Callista/business rules expert to confirm these?"

---

### Section 6: Next Steps (3 minutes)

**Say:**
> "To complete the EBA milestone, we need three things from UC:"

1. **Real Callista Extract**
   - De-identified extract file
   - Validate pipeline with actual UC data
   - Identify any edge cases we missed

2. **Reference Totals** (for accuracy validation)
   - Current semester headcount & EFTSL
   - We'll compare our reports to your baseline

3. **AWS Access** (for hands-on capability demo)
   - Provision UC team access to DEV environment
   - UC adds a 5th report via YAML config
   - Proves UC can extend platform independently

---

## Part 7: Files to Share with UC

### For the Demo

1. **This Document**
   - `UC-Demo-Guide-and-Confirmations-Needed.md`

2. **Lineage Explorer** (interactive HTML)
   - `docs/model/lineage-explorer.html`

3. **Generated Reports** (JSON files)
   - `.local-lake/gold/mcds_reporting/factdata/*.json`

4. **Run Report** (validation summary)
   - `.local-lake/run-report.json`

### For UC Review

5. **Published Confluence Pages**
   - Entity Selection & Sample Data Analysis
   - What We Have Ready
   - University Requirements - What We Need
   - MCDS Complete Technical Architecture

6. **Configuration Files** (show how to add reports)
   - `config/reports/*.yaml`

---

## Part 8: Success Criteria for Demo

### What "Success" Looks Like

✅ **UC Understands:**
- What the pipeline does (Callista → MCDS)
- Why we chose each table
- What the 4 reports show
- How data quality is ensured

✅ **UC Provides:**
- Confirmation on the 7 business rule assumptions
- Real Callista extract file (de-identified)
- Reference totals for validation
- AWS access for hands-on session

✅ **UC Agrees:**
- The approach is correct
- The reports are useful
- They're ready to see it in AWS DEV

---

## Part 9: Risk Mitigation

### If UC Says "We're Not Sure" About Business Rules

**Fallback Plan:**
- Document as "UC to confirm"
- Implement toggleable config flags for each assumption
- Example: `config/business-rules.yaml`
  ```yaml
  eftsl_calculation:
    method: "direct_field"  # or "calculate_from_credit_points"
    field: "GOVT_STUDENT_LOAD.EFTSU"
  ```

### If Real Data Reveals Issues

**Response Plan:**
- Mock data proves the **technical approach** works
- Real data may reveal **business rule adjustments** needed
- These are **configuration changes**, not code rewrites
- Estimated effort: 1-3 days per adjustment

---

## Part 10: Questions to Ask UC During Demo

### Critical Questions

1. **EFTSL:** "Do you see your EFTSL values in `GOVT_STUDENT_LOAD.EFTSU`, or do you calculate from credit points?"

2. **Baseline:** "What were your actual headcount and EFTSL totals for Semester 1 2026?"

3. **Accuracy Tolerance:** "What's an acceptable variance? ±1% or tighter?"

4. **Timeline:** "When can you provide a de-identified Callista extract?"

5. **AWS Access:** "Who from your team needs AWS DEV access for hands-on training?"

### Nice-to-Have Questions

6. "Are there any other reports you'd like to see beyond these 4?"

7. "What's your current manual process for generating these reports?"

8. "How often do you need to submit data to MCDS Hub?"

---

## Appendix A: Table Selection Decision Matrix

| Table | MCDS Required | TCSI Required | UC Specific | Alternative? | Decision |
|-------|---------------|---------------|-------------|--------------|----------|
| GOVT_STUDENT_LOAD | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| STUDENT_UNIT_ATTEMPT | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| PERSON | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| UNIT_VERSION | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| ORG_UNIT | ✓ |  | ✓ | None | **MUST HAVE** |
| LOCATION | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| CAL_INSTANCE | ✓ | ✓ | ✓ | None | **MUST HAVE** |
| COURSE |  |  | Maybe | COURSE_CD only | **DEFER** |
| UNIT_OFFERING |  |  | Maybe | UOO_ID only | **DEFER** |

---

## Appendix B: Quick Reference - Row Counts

### Bronze (Raw)
- GOVT_STUDENT_LOAD: 1098
- STUDENT_UNIT_ATTEMPT: 827
- PERSON: 168
- UNIT_VERSION: 42
- ORG_UNIT: 7
- LOCATION: 5
- CAL_INSTANCE: 4

### Silver (Standardized)
- student_unit_load: 1061 (37 filtered out by submission rule)
- student: 150
- unit_of_learning: 42
- organisation: 7
- location: 5
- learning_period: 4

### Gold (Reports)
- student_load_by_unit: 72 rows (36 units × 2 periods)
- student_load_by_campus: 8 rows (4 campuses × 2 periods)
- student_load_by_teaching_org_unit: 12 rows (6 orgs × 2 periods)
- student_load_by_unit_campus: 190 rows (99 combinations × ~2 periods)

---

**Document Owner:** Cevo Data Engineering  
**Last Updated:** October 26, 2026  
**Version:** 1.0 (EBA Demo)
