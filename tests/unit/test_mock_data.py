"""
Unit tests for the mock Callista extract and the pure-Python helpers (no Spark needed).
Run: python scripts/generate-mock-data.py && pytest tests/unit
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "etl" / "common"))
from schemas import TABLE_SPECS, TABLES, columns, key_columns  # noqa: E402
import pipeline as P  # noqa: E402

LANDING = ROOT / "data" / "mock" / "landing" / "callista"


@pytest.fixture(scope="module")
def t():
    dates = sorted(p for p in LANDING.iterdir() if p.is_dir()) if LANDING.exists() else []
    if not dates:
        pytest.skip("no mock extract: run scripts/generate-mock-data.py")
    return {name: pd.read_csv(dates[-1] / f"{name}.csv", keep_default_na=False, na_values=[""])
            for name in TABLES}


def test_all_tables_present_with_real_callista_columns(t):
    for name in TABLES:
        assert list(t[name].columns) == columns(name), name


def test_no_pii_columns():
    banned = {"BIRTH_DT", "EMAIL_ADDR", "SEX", "TITLE_NAME", "ADDR"}
    for name, spec in TABLE_SPECS.items():
        assert not banned & {c[0] for c in spec}, name


def test_names_are_masked(t):
    assert t["PERSON"]["SURNAME"].str.startswith("SURNAME-").all()


@pytest.mark.parametrize("name", TABLES)
def test_natural_keys_unique(t, name):
    assert not t[name].duplicated(key_columns(name)).any(), name


def test_required_columns_populated(t):
    for name, spec in TABLE_SPECS.items():
        for col, _, nullable, _ in spec:
            if not nullable:
                assert t[name][col].notna().all(), f"{name}.{col}"


def test_load_joins_to_unit_attempt_one_to_one(t):
    g, s = t["GOVT_STUDENT_LOAD"], t["STUDENT_UNIT_ATTEMPT"]
    m = g.merge(s, left_on=["PERSON_ID", "COURSE_CD", "UNIT_CD", "UV_VERSION_NUMBER", "SUA_CAL_TYPE", "SUA_CI_SEQUENCE_NUMBER"],
                right_on=["PERSON_ID", "COURSE_CD", "UNIT_CD", "VERSION_NUMBER", "CAL_TYPE", "CI_SEQUENCE_NUMBER"], how="left")
    assert len(m) == len(g) and m["LOCATION_CD"].notna().all()


def test_composite_foreign_keys(t):
    g = t["GOVT_STUDENT_LOAD"]
    uv = set(zip(t["UNIT_VERSION"].UNIT_CD, t["UNIT_VERSION"].VERSION_NUMBER))
    assert set(zip(g.UNIT_CD, g.UV_VERSION_NUMBER)) <= uv
    ou = set(zip(t["ORG_UNIT"].ORG_UNIT_CD, t["ORG_UNIT"].START_DT))
    assert set(zip(g.TR_ORG_UNIT_CD, g.TR_OU_START_DT)) <= ou
    ci = set(zip(t["CAL_INSTANCE"].CAL_TYPE, t["CAL_INSTANCE"].SEQUENCE_NUMBER))
    assert set(zip(g.SUA_CAL_TYPE, g.SUA_CI_SEQUENCE_NUMBER)) <= ci
    assert set(g.PERSON_ID) <= set(t["PERSON"].PERSON_ID)


def test_edge_cases_present(t):
    """The extract must exercise the traps found in the real schema."""
    assert t["UNIT_VERSION"].duplicated("UNIT_CD").any(), "a unit with two versions"
    assert t["ORG_UNIT"].duplicated("ORG_UNIT_CD").any(), "an org unit with two START_DT rows"
    g = t["GOVT_STUDENT_LOAD"]
    attempt = ["SUBMISSION_YR", "GOVT_SEMESTER", "PERSON_ID", "COURSE_CD", "UNIT_CD", "UV_VERSION_NUMBER",
               "SUA_CAL_TYPE", "SUA_CI_SEQUENCE_NUMBER", "TR_ORG_UNIT_CD"]
    assert g.duplicated(attempt).any(), "an attempt re-reported in a later submission"
    assert g.duplicated(attempt[:-1]).any(), "a unit attempt split across teaching org units"
    assert len(set(t["PERSON"].PERSON_ID) - set(g.PERSON_ID)) > 0, "PERSON rows that are not students"


def test_value_domains(t):
    g = t["GOVT_STUDENT_LOAD"]
    assert g.EFTSU.between(0, 1).all()
    assert set(g.UNIT_COMPLETION_STATUS) <= {1, 2, 3, 4, 5}
    assert set(g.GOVT_SEMESTER) <= {1, 2}


def test_format_to_sql():
    assert P.format_to_sql("STU-{PERSON_ID}") == "concat('STU-', CAST(PERSON_ID AS STRING))"
    assert P.format_to_sql("{PERSON_ID}") == "CAST(PERSON_ID AS STRING)"
    assert P.format_to_sql("{SUBMISSION_YR}-{GOVT_SEMESTER}") == \
        "concat(CAST(SUBMISSION_YR AS STRING), '-', CAST(GOVT_SEMESTER AS STRING))"


def test_resolve_tokens():
    rules = P.load_yaml(ROOT / "config" / "business-rules.yaml")
    assert P.resolve_tokens("x IN ({government_load.include_completion_status})", rules) == "x IN (1, 2, 3, 4, 5)"
    assert P.resolve_tokens("'{reporting_period.pattern}'", rules) == "'^[0-9]{4}-[12]$'"
    assert "concat('STU-'" in P.resolve_tokens("{identity.student_id_format}", rules)


def test_status_rule_is_not_withdrawn_and_failed():
    """Regression: the earlier config treated codes 1,2 as 'active'. In TCSI E355 they are
    withdrew and failed."""
    rules = P.load_yaml(ROOT / "config" / "business-rules.yaml")
    assert rules["completion_status"][1]["mcds_status"] == "Withdrawn"
    assert rules["completion_status"][2]["mcds_status"] == "Failed"
    assert rules["government_load"]["include_completion_status"] != [1, 2]
