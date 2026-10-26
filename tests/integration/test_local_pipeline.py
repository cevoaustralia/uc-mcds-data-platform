"""
End-to-end test: runs the whole pipeline locally on Spark against the mock extract and checks
DQ, reconciliation, MCDS conformance and that the validators reject broken payloads.
Skips if pyspark or the MCDS package is unavailable.

Run: pytest tests/integration -s
"""

import copy
import glob
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MCDS = ROOT / "MCDS - v2.1.1" / "v2.1.1"
sys.path.insert(0, str(ROOT / "etl" / "common"))

pytest.importorskip("pyspark")
if not (MCDS / "schemas").exists():
    pytest.skip("MCDS v2.1.1 package not present", allow_module_level=True)

import mcds_validation as V  # noqa: E402


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    work = tmp_path_factory.mktemp("lake")
    landing = tmp_path_factory.mktemp("landing")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate-mock-data.py"), "--out", str(landing)], check=True)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "run-local-pipeline.py"),
                           "--landing", str(landing), "--work", str(work), "--mcds", str(MCDS)],
                          capture_output=True, text=True)
    print(proc.stdout[-4000:])
    report = json.loads((work / "run-report.json").read_text())
    return proc, report, work


def test_pipeline_passes(run):
    proc, report, _ = run
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert report["ok"]


def test_every_dq_rule_passed(run):
    _, report, _ = run
    bad = [r for r in report["dq"] if r["status"] in ("FAIL", "ERROR")]
    assert not bad, bad


def test_submission_dedup_removed_rows(run):
    _, report, _ = run
    raw = report["stages"]["bronze"]["GOVT_STUDENT_LOAD"]["bronze_rows"]
    sel = report["stages"]["silver"]["_gsl_after_submission_selection"]
    assert sel < raw
    assert report["stages"]["silver"]["student_unit_load"] == sel


def test_person_filtered_to_students(run):
    _, report, _ = run
    assert report["stages"]["silver"]["student"] < report["stages"]["bronze"]["PERSON"]["bronze_rows"]


def test_validators_reject_broken_payloads(run):
    _, _, work = run
    doc = json.loads(open(glob.glob(str(work / "silver" / "mcds_json" / "*.json"))[0]).read())
    broken = copy.deepcopy(doc)
    del broken["students"][0]["unitOfLearningEnrolments"][0]["unitOfLearningAvailability"]["learningPeriod"]
    assert V.validate_student_documents(str(MCDS), [("ok", doc)])[0]["valid"]
    assert not V.validate_student_documents(str(MCDS), [("broken", broken)])[0]["valid"]

    defs = [(p, json.load(open(p))) for p in glob.glob(str(work / "gold" / "mcds_reporting" / "reportdefinitions" / "*.json"))]
    fact = json.load(open(glob.glob(str(work / "gold" / "mcds_reporting" / "factdata" / "*Campus*.json"))[0]))
    fact["facts"][0]["dimensions"]["dim.campus"] = "NOT-A-CAMPUS"
    assert not V.validate_reporting(str(MCDS), defs, [("bad", fact)])[-1]["valid"]
