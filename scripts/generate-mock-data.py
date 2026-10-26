#!/usr/bin/env python3
"""
Generate a mock Callista CSV extract for the UC MCDS EBA.

The extract mirrors the real Callista schema (analysis/Sisprod_schema_metadata.csv) for the
7 tables in etl/common/schemas.py, with realistic structure:
  * composite keys (UNIT_VERSION, ORG_UNIT) incl. a unit with two versions and an org unit
    that was restructured (two START_DT rows)
  * GOVT_STUDENT_LOAD split by teaching responsibility (some units shared 50/50)
  * a later SUBMISSION_NUMBER re-reporting some semester-1 attempts (must not double count)
  * unit attempts discontinued before census (in STUDENT_UNIT_ATTEMPT, not in load)
  * PERSON rows that are not students (staff/applicants)
  * masked names only, no birth dates/emails (SOW: no PII)

Pure standard library; deterministic (seeded).

Usage:
  python scripts/generate-mock-data.py [--extract-date 2026-10-25] [--students 150] [--out DIR]
Output:
  data/mock/landing/callista/<extract-date>/<TABLE>.csv
"""

import argparse
import csv
import hashlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl" / "common"))
from schemas import TABLE_SPECS, columns  # noqa: E402

YEAR = 2026

ORG_UNITS = [  # code, start, end, description, type
    ("FAC-ADE", "2015-01-01", None, "Faculty of Arts and Design", "FACULTY"),
    ("FAC-BGL", "2015-01-01", None, "Faculty of Business, Government and Law", "FACULTY"),
    ("FAC-EDU", "2015-01-01", None, "Faculty of Education", "FACULTY"),
    ("FAC-HLT", "2015-01-01", None, "Faculty of Health", "FACULTY"),
    ("FAC-STE", "2015-01-01", None, "Faculty of Science and Technology", "FACULTY"),
    # restructured school: old row ended 2025, new row from 2026 (composite key test)
    ("SCH-ITS", "2018-01-01", "2025-12-31", "School of IT and Systems", "SCHOOL"),
    ("SCH-ITS", "2026-01-01", None, "School of Information Technology and Systems", "SCHOOL"),
]
CURRENT_OU_START = {code: start for code, start, end, _, _ in ORG_UNITS if end is None}

LOCATIONS = [  # code, description, type, govt code, closed
    ("BRUCE", "Bruce Campus", "CAMPUS", "G2601", "N"),
    ("ONLINE", "Online", "ONLINE", None, "N"),
    ("SYDNEY", "Sydney Study Centre (mock)", "CAMPUS", "G2602", "N"),
    ("PARTNER", "Partner Campus (mock)", "CAMPUS", "G2603", "N"),
    ("OLDSITE", "Former Site (mock, closed)", "CAMPUS", "G2699", "Y"),
]
HOME_CAMPUS_WEIGHTS = [("BRUCE", 65), ("ONLINE", 20), ("SYDNEY", 10), ("PARTNER", 5)]

CALENDARS = [  # cal type, seq, start, end, alternate code, govt semester
    ("TEACH-S1", 250, "2025-02-10", "2025-06-13", "S1 2025", None),
    ("TEACH-S2", 251, "2025-07-28", "2025-11-21", "S2 2025", None),
    ("TEACH-S1", 260, "2026-02-09", "2026-06-12", "S1 2026", 1),
    ("TEACH-S2", 261, "2026-07-27", "2026-11-20", "S2 2026", 2),
]

UNIT_TITLES = {
    "FAC-ADE": ["Design Thinking", "Visual Communication", "Writing for Media", "Digital Storytelling", "Creative Industries", "Typography"],
    "FAC-BGL": ["Accounting Principles", "Business Law", "Economics for Managers", "Public Policy", "Marketing Foundations", "Corporate Finance"],
    "FAC-EDU": ["Learning and Development", "Curriculum Studies", "Inclusive Education", "Literacy Foundations", "Numeracy Foundations", "Professional Experience"],
    "FAC-HLT": ["Human Anatomy", "Health Promotion", "Clinical Practice", "Nutrition Science", "Mental Health", "Sport Physiology"],
    "FAC-STE": ["Calculus", "Chemistry Foundations", "Environmental Science", "Statistics for Science", "Physics Foundations", "Biology of Cells"],
    "SCH-ITS": ["Programming Fundamentals", "Database Design", "Networks and Security", "Software Engineering", "Data Science", "Cloud Computing"],
}
COURSES = [  # code, faculty
    ("ADE-BDES", "FAC-ADE"), ("BGL-BBUS", "FAC-BGL"), ("EDU-BED", "FAC-EDU"),
    ("HLT-BHSC", "FAC-HLT"), ("STE-BSC", "FAC-STE"), ("ITS-BIT", "SCH-ITS"),
]


def masked(prefix, pid):
    return f"{prefix}-{hashlib.sha256(f'{prefix}{pid}'.encode()).hexdigest()[:8].upper()}"


def build(n_students, seed=42):
    rnd = random.Random(seed)
    t = {name: [] for name in TABLE_SPECS}

    for code, start, end, desc, typ in ORG_UNITS:
        t["ORG_UNIT"].append(dict(ORG_UNIT_CD=code, START_DT=start, END_DT=end, DESCRIPTION=desc,
                                  ORG_TYPE=typ, ORG_STATUS="ACTIVE" if end is None else "INACTIVE"))
    for code, desc, typ, govt, closed in LOCATIONS:
        t["LOCATION"].append(dict(LOCATION_CD=code, DESCRIPTION=desc, LOCATION_TYPE=typ,
                                  GOVT_LOCATION_CD=govt, CLOSED_IND=closed))
    for cal, seq, s, e, alt, _ in CALENDARS:
        t["CAL_INSTANCE"].append(dict(CAL_TYPE=cal, SEQUENCE_NUMBER=seq, START_DT=s, END_DT=e,
                                      ALTERNATE_CODE=alt, CAL_STATUS="ACTIVE"))

    # Units: 6 per org; first unit of each org gets a revised version 2 from semester 2
    units = []          # dicts with code, owner, cp, shared_with, v2
    for owner, titles in UNIT_TITLES.items():
        prefix = owner.split("-")[1][:3]
        for i, title in enumerate(titles):
            level = 1 + (i % 3)
            code = f"{prefix}{level}{100 + i}"
            cp = 6 if i == 5 else 3
            shared = None
            if i in (2, 4):  # shared teaching responsibility with another org unit
                shared = rnd.choice([o for o in UNIT_TITLES if o != owner])
            units.append(dict(code=code, owner=owner, cp=cp, shared=shared, v2=(i == 0), title=title, level=level))
            t["UNIT_VERSION"].append(dict(
                UNIT_CD=code, VERSION_NUMBER=1, TITLE=title, SHORT_TITLE=title[:40], UNIT_LEVEL=str(level),
                ENROLLED_CREDIT_POINTS=f"{cp:.3f}", OWNER_ORG_UNIT_CD=owner,
                OWNER_OU_START_DT="2018-01-01" if owner == "SCH-ITS" else CURRENT_OU_START[owner],
                UNIT_STATUS="ACTIVE", START_DT="2020-01-01"))
            if i == 0:
                t["UNIT_VERSION"].append(dict(
                    UNIT_CD=code, VERSION_NUMBER=2, TITLE=f"{title} (revised)", SHORT_TITLE=f"{title} (rev)"[:40],
                    UNIT_LEVEL=str(level), ENROLLED_CREDIT_POINTS=f"{cp:.3f}", OWNER_ORG_UNIT_CD=owner,
                    OWNER_OU_START_DT=CURRENT_OU_START[owner], UNIT_STATUS="ACTIVE", START_DT="2026-07-01"))
    by_owner = {}
    for u in units:
        by_owner.setdefault(u["owner"], []).append(u)

    # People: students + non-students (staff/applicants, no load)
    pids = [3100001 + i for i in range(n_students)]
    for pid in pids + [3900001 + i for i in range(max(10, n_students // 8))]:
        t["PERSON"].append(dict(PERSON_ID=pid, SURNAME=masked("SURNAME", pid),
                                GIVEN_NAMES=None if pid % 23 == 0 else masked("GIVEN", pid),
                                UPDATE_ON="2026-10-20"))

    uoo = {}

    def uoo_id(code, ver, cal, seq, loc, cls):
        return uoo.setdefault((code, ver, cal, seq, loc, cls), 1000001 + len(uoo))

    sem_cals = [c for c in CALENDARS if c[5] is not None]
    for pid in pids:
        course, faculty = rnd.choice(COURSES)
        home = rnd.choices([c for c, _ in HOME_CAMPUS_WEIGHTS], [w for _, w in HOME_CAMPUS_WEIGHTS])[0]
        r = rnd.random()
        sems = sem_cals if r > 0.2 else ([sem_cals[0]] if r > 0.1 else [sem_cals[1]])
        for cal, seq, start, end, alt, gsem in sems:
            n_units = rnd.choice([2, 3, 3, 4])
            pool = by_owner[faculty] * 3 + [u for u in units if u["owner"] != faculty]
            chosen = []
            while len(chosen) < n_units:
                u = rnd.choice(pool)
                if u not in chosen:
                    chosen.append(u)
            for u in chosen:
                ver = 2 if (u["v2"] and gsem == 2) else 1
                loc = home if rnd.random() > 0.15 else "ONLINE"
                cls = "ONLINE" if loc == "ONLINE" else "ON-CAMPUS"
                pre_census_drop = rnd.random() < 0.04
                sua_status = "DISCONTIN" if pre_census_drop else ("ENROLLED" if gsem == 2 else "COMPLETED")
                t["STUDENT_UNIT_ATTEMPT"].append(dict(
                    PERSON_ID=pid, COURSE_CD=course, UNIT_CD=u["code"], VERSION_NUMBER=ver, CAL_TYPE=cal,
                    CI_SEQUENCE_NUMBER=seq, LOCATION_CD=loc, UNIT_CLASS=cls,
                    UOO_ID=uoo_id(u["code"], ver, cal, seq, loc, cls), UNIT_ATTEMPT_STATUS=sua_status))
                if pre_census_drop:
                    continue  # withdrew before census: no government load
                eftsu = u["cp"] / 24.0
                splits = [(u["owner"], 1.0)] if not u["shared"] else [(u["owner"], 0.5), (u["shared"], 0.5)]
                if gsem == 1:
                    status = rnd.choices([3, 2, 1, 4], [80, 10, 5, 5])[0]
                    submissions = [(1, status)]
                    if status == 4 or rnd.random() < 0.03:   # re-reported with final outcome
                        submissions.append((2, rnd.choices([3, 2], [85, 15])[0]))
                else:
                    submissions = [(2, rnd.choices([4, 1], [93, 7])[0])]
                for sub, st in submissions:
                    for org, share in splits:
                        t["GOVT_STUDENT_LOAD"].append(dict(
                            SUBMISSION_YR=YEAR, SUBMISSION_NUMBER=sub, PERSON_ID=pid, COURSE_CD=course,
                            CRV_VERSION_NUMBER=1, GOVT_SEMESTER=gsem, UNIT_CD=u["code"], UV_VERSION_NUMBER=ver,
                            SUA_CAL_TYPE=cal, SUA_CI_SEQUENCE_NUMBER=seq, TR_ORG_UNIT_CD=org,
                            TR_OU_START_DT=CURRENT_OU_START[org],
                            DISCIPLINE_GROUP_CD=f"DG{list(UNIT_TITLES).index(u['owner']) + 1:02d}",
                            EFTSU=f"{eftsu * share:.6f}", UNIT_COMPLETION_STATUS=st,
                            GOVT_LOCATION_CD=next(l[3] for l in LOCATIONS if l[0] == loc),
                            UPDATE_ON="2026-10-20" if sub == 2 else "2026-04-01"))
    return t


def write(tables, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=columns(name))
            w.writeheader()
            for row in rows:
                w.writerow({k: ("" if v is None else v) for k, v in row.items()})
        print(f"  {name:22s} {len(rows):6d} rows")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extract-date", default="2026-10-25")
    ap.add_argument("--students", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None, help="landing root (default data/mock/landing)")
    a = ap.parse_args()
    root = Path(a.out) if a.out else ROOT / "data" / "mock" / "landing"
    out_dir = root / "callista" / a.extract_date
    print(f"Writing mock Callista extract to {out_dir}")
    write(build(a.students, a.seed), out_dir)


if __name__ == "__main__":
    main()
