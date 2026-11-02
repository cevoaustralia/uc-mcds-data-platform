"""
End-to-end on a tiny synthetic extract that exercises the load rules (no real data in the repo):

  P1 U1 3CP SEM-1 BRUCE  ENROLLED                  -> 0.125 EFTSL
  P1 U2 6CP SEM-1 HANU   DISCONTIN / WD-LATE-LD     -> 0.250 (withdrawn after census: counts)
  P2 U1 3CP SEM-1 BRUCE  DISCONTIN / WD-EARLY       -> 0     (withdrawn before census)
  P2 R1 12CP RES-1 BRUCE ENROLLED override 0.334    -> 0.334 but HDR cohort (outside HE scope)
  P2 U2 6CP SEM-1 BRUCE  INVALID                    -> 0
HE coursework EFTSL = 0.375; teaching split U1 60/40 (DIS-A/DIS-B), U2 100 DIS-A.
"""
import csv
import os

import pytest

from conftest import CONFIG, ROOT
from mcds_config import PipelineConfig
from mcds_store import LocalStore
import mcds_run as RUN

EXTRACT = "2026-10-26"
ROWS = {
    "person": [{"PERSON_ID": "101", "SURNAME": "MASKED", "GIVEN_NAMES": "A", "SEX": "F", "BIRTH_DT": "15-Mar-75"},
               {"PERSON_ID": "102", "SURNAME": "MASKED", "GIVEN_NAMES": "B", "SEX": "M", "BIRTH_DT": "1-Jan-05"}],
    "student_course_attempt": [
        {"PERSON_ID": "101", "COURSE_CD": "C1", "VERSION_NUMBER": "1", "COURSE_ATTEMPT_STATUS": "ENROLLED",
         "COMMENCEMENT_DT": "1-Feb-26", "ATTENDANCE_TYPE": "FT", "FEE_CAT": "DOM-CSP", "LOCATION_CD": "BRUCE"},
        {"PERSON_ID": "102", "COURSE_CD": "C1", "VERSION_NUMBER": "1", "COURSE_ATTEMPT_STATUS": "ENROLLED",
         "COMMENCEMENT_DT": "1-Feb-25", "ATTENDANCE_TYPE": "PT", "FEE_CAT": "INT-FEE", "LOCATION_CD": "BRUCE"},
        {"PERSON_ID": "999", "COURSE_CD": "C1", "VERSION_NUMBER": "1", "COURSE_ATTEMPT_STATUS": "COMPLETED",
         "COMMENCEMENT_DT": "1-Feb-15"}],          # historic student: not in PERSON -> filtered in Silver
    "unit_version": [
        {"UNIT_CD": "U1", "VERSION_NUMBER": "1", "TITLE": "Unit one", "ENROLLED_CREDIT_POINTS": "3", "OWNER_ORG_UNIT_CD": "FCY-HLT", "OWNER_OU_START_DT": "01/JAN/20", "UNIT_STATUS": "ACTIVE", "VET_IND": "N"},
        {"UNIT_CD": "U2", "VERSION_NUMBER": "1", "TITLE": "Unit two", "ENROLLED_CREDIT_POINTS": "6", "OWNER_ORG_UNIT_CD": "FCY-HLT", "OWNER_OU_START_DT": "01/JAN/20", "UNIT_STATUS": "ACTIVE", "VET_IND": "N"},
        {"UNIT_CD": "R1", "VERSION_NUMBER": "1", "TITLE": "Research", "ENROLLED_CREDIT_POINTS": "12", "OWNER_ORG_UNIT_CD": "RESSERV", "OWNER_OU_START_DT": "01/JAN/20", "UNIT_STATUS": "ACTIVE", "VET_IND": "N"}],
    "teaching_responsibility": [
        {"UNIT_CD": "U1", "VERSION_NUMBER": "1", "ORG_UNIT_CD": "DIS-A", "OU_START_DT": "01/JAN/20", "PERCENTAGE": "60"},
        {"UNIT_CD": "U1", "VERSION_NUMBER": "1", "ORG_UNIT_CD": "DIS-B", "OU_START_DT": "01/JAN/20", "PERCENTAGE": "40"},
        {"UNIT_CD": "U2", "VERSION_NUMBER": "1", "ORG_UNIT_CD": "DIS-A", "OU_START_DT": "01/JAN/20", "PERCENTAGE": "100"},
        {"UNIT_CD": "R1", "VERSION_NUMBER": "1", "ORG_UNIT_CD": "DIS-A", "OU_START_DT": "01/JAN/20", "PERCENTAGE": "100"}],
    "org_unit": [{"ORG_UNIT_CD": c, "START_DT": "01/JAN/20", "DESCRIPTION": d, "ORG_STATUS": "ACTIVE", "ORG_TYPE": "ACADEMIC", "MEMBER_TYPE": m}
                 for c, d, m in [("FCY-HLT", "Faculty of Health", "FACULTY"), ("DIS-A", "School A", "DISCIPLINE"),
                                 ("DIS-B", "School B", "DISCIPLINE"), ("RESSERV", "Research", "SECTION")]],
    "location": [{"LOCATION_CD": "BRUCE", "DESCRIPTION": "Bruce", "LOCATION_TYPE": "CAMPUS", "GOVT_OFFSHR_DLVRY_CD": "00", "CLOSED_IND": "N"},
                 {"LOCATION_CD": "HANU", "DESCRIPTION": "Hanoi", "LOCATION_TYPE": "CAMPUS", "GOVT_OFFSHR_DLVRY_CD": "02", "CLOSED_IND": "N"}],
    "cal_instance": [{"CAL_TYPE": "SEM-1", "SEQUENCE_NUMBER": "1", "START_DT": "16/FEB/26", "END_DT": "15/MAY/26", "CAL_STATUS": "ACTIVE", "ALTERNATE_CODE": "S1"},
                     {"CAL_TYPE": "RES-1", "SEQUENCE_NUMBER": "2", "START_DT": "01/JAN/26", "END_DT": "30/JUN/26", "CAL_STATUS": "ACTIVE", "ALTERNATE_CODE": "R1"}],
}
SUA = [("101", "U1", "SEM-1", "1", "1", "BRUCE", "ENROLLED", "", ""),
       ("101", "U2", "SEM-1", "1", "2", "HANU", "DISCONTIN", "WD-LATE-LD", ""),
       ("102", "U1", "SEM-1", "1", "1", "BRUCE", "DISCONTIN", "WD-EARLY", ""),
       ("102", "R1", "RES-1", "2", "3", "BRUCE", "ENROLLED", "", "0.334"),
       ("102", "U2", "SEM-1", "1", "4", "BRUCE", "INVALID", "", "")]
ROWS["student_unit_attempt"] = [
    {"PERSON_ID": p, "COURSE_CD": "C1", "UNIT_CD": u, "VERSION_NUMBER": "1", "CAL_TYPE": ct, "CI_SEQUENCE_NUMBER": seq,
     "UOO_ID": uoo, "LOCATION_CD": loc, "UNIT_CLASS": "ON", "UNIT_ATTEMPT_STATUS": st, "ADMINISTRATIVE_UNIT_STATUS": adm,
     "OVERRIDE_EFTSU": ov, "CI_START_DT": "16-Feb-26", "CI_END_DT": "15-May-26", "ENROLLED_DT": "1-Feb-26",
     "DISCONTINUED_DT": "20-Mar-26" if st == "DISCONTIN" else ""}
    for p, u, ct, seq, uoo, loc, st, adm, ov in SUA]


@pytest.fixture(scope="module")
def run(spark, tmp_path_factory):
    cfg = PipelineConfig(CONFIG)
    tmp = tmp_path_factory.mktemp("e2e")
    folder = tmp / "landing" / "callista" / f"extract_date={EXTRACT}"
    folder.mkdir(parents=True)
    for table, src in cfg.sources.items():
        with open(folder / src["file"], "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(src["columns"]))
            w.writeheader()
            for r in ROWS[table]:
                w.writerow(r)
    store = LocalStore(spark, str(tmp / "lake"))
    bundle = os.path.join(ROOT, cfg.settings["mcds"]["schema_root"])
    ok = (RUN.run_bronze(spark, cfg, store, str(tmp / "landing"), EXTRACT),
          RUN.run_silver(spark, cfg, store, EXTRACT, bundle),
          RUN.run_gold(spark, cfg, store, EXTRACT, bundle, str(tmp / "reporting")))
    return spark, store, ok


HAS_MCDS = os.path.exists(os.path.join(ROOT, PipelineConfig(CONFIG).settings["mcds"]["schema_root"]))


def test_all_stages_pass(run):
    _, _, ok = run
    assert ok == (True, True, True)


@pytest.mark.skipif(not HAS_MCDS, reason="licensed MCDS schema bundle not present (e.g. GitHub CI)")
def test_mcds_conformance_validated(run):
    spark, store, _ = run
    rows = store.read("ops", "dq_results").collect()
    conf = [r for r in rows if r["rule_id"].endswith("_mcds_conformance") or r["rule_id"] == "gold_mcds_reporting_conformance"]
    assert len(conf) >= 10 and all(r["status"] == "PASS" for r in conf)
    assert not [r for r in rows if r["rule_id"].endswith("_mcds_schemas_available")]


def test_load_rules(run):
    spark, store, _ = run
    f = {r["unit_of_learning_enrolment_id"]: r for r in store.read("silver", "unit_of_learning_enrolment").collect()}
    assert float(f["101|C1|1"]["eftsl"]) == 0.125
    assert float(f["101|C1|2"]["eftsl"]) == 0.25 and f["101|C1|2"]["counts_as_load"]
    assert float(f["102|C1|1"]["eftsl"]) == 0 and f["102|C1|1"]["load_exclusion_reason"] == "WITHDRAWN_BEFORE_CENSUS"
    assert float(f["102|C1|3"]["eftsl"]) == 0.334 and f["102|C1|3"]["cohort"] == "HDR"
    assert f["102|C1|4"]["load_exclusion_reason"] == "STATUS_INVALID"


def test_gold_use_case_a(run):
    spark, store, _ = run
    uc = store.read("gold", "student_load_by_unit_campus").collect()
    assert round(sum(float(r["eftsl"]) for r in uc), 3) == 0.375          # HE coursework only
    by_school = {r["teaching_org_code"]: float(r["eftsl"]) for r in store.read("gold", "student_load_by_school").collect()}
    assert by_school == {"DIS-A": 0.325, "DIS-B": 0.05}
    deliv = {r["delivery"] for r in store.read("gold", "student_load_by_faculty").collect()}
    assert deliv == {"ONSHORE", "OFFSHORE"}


def test_silver_filters_history_and_past_century_dates(run):
    spark, store, _ = run
    poles = store.read("silver", "programme_of_learning_enrolment").collect()
    assert {r["student_id"] for r in poles} == {"101", "102"}               # historic 999 excluded
    years = {r["person_id"]: r["birth_year"] for r in store.read("silver", "person").collect()}
    assert years == {"101": 1975, "102": 2005}                              # '75' is 1975, not 2075


def test_course_profile_use_case_b(run):
    spark, store, _ = run
    rows = store.read("gold", "course_enrolment_profile").collect()
    assert sum(r["commencing_students"] for r in rows) == 1                 # P1 commenced 2026
