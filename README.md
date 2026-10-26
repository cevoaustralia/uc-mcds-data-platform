# UC MCDS Data Platform

University of Canberra × Cevo × AWS — MCDS Data Foundation EBA (19 Oct – 29 Nov 2026).

Callista (Oracle) enrolment data, delivered as **CSV extracts**, is onboarded to a governed AWS
data lake built with **AWS MDAA**, conformed to **MCDS v2.1.1**, and reported as
**standardised student load by unit and facility** (SOW D5): Athena Gold tables plus MCDS
Reporting Framework files.

Design, mapping and status documents live outside the repo in
`Docs/published-docs/` (also published to Confluence). Start with `README-Document-Guide.md`.
This README is the operational runbook (SOW D6).

---

## Pipeline

```
Callista CSV extract          Bronze (mcds_bronze)        Silver (mcds_silver, MCDS)        Gold (mcds_gold)
landing/callista/<date>/  ->  7 tables, Parquet,     ->   student                      ->   student_load_by_unit
  GOVT_STUDENT_LOAD.csv       append-only by              unit_of_learning                  student_load_by_campus
  STUDENT_UNIT_ATTEMPT.csv    _extract_date               organisation                      student_load_by_teaching_org_unit
  PERSON.csv                                              location                          student_load_by_unit_campus
  UNIT_VERSION.csv                                        learning_period                   reporting_period
  ORG_UNIT.csv                                            student_unit_load (fact)          + MCDS Reporting Framework
  LOCATION.csv                                            + MCDS JSON (studentlifecycle)      definitions + fact data
  CAL_INSTANCE.csv
        landing-to-bronze           bronze-to-silver                       silver-to-gold
        (Bronze DQ)                 (Silver DQ, lineage comments)          (reconciliation DQ)
```

All three Glue jobs call the same functions in `etl/common/pipeline.py` as the local runner,
so what passes locally is what runs in Glue.

## Repository layout

| Path | What |
|---|---|
| `mdaa.yaml`, `governance/`, `data/`, `dataops/` | MDAA 1.9.0 deployment config (roles, Lake Formation, Glue Catalog, audit + CloudTrail, S3 data lake, Athena, Glue databases + grants, Glue jobs). All files validate against the MDAA module schemas. |
| `config/business-rules.yaml` | Rules and EBA defaults awaiting UC confirmation (`confirmed: false`) |
| `config/silver-mappings.yaml` | Callista → MCDS field mappings (executed, also the D6 mapping artefact and D4 lineage source) |
| `config/gold-aggregations.yaml` | Gold report definitions (dimensions, measures, filters) + MCDS reporting mapping |
| `config/data-quality-rules.yaml` | 19 data quality rules (completeness, keys, FKs, domains, reconciliation) |
| `etl/common/` | `schemas.py` (Callista columns), `pipeline.py` (transforms + exports), `data_quality.py`, `mcds_validation.py`, `glue_io.py` |
| `etl/bronze|silver|gold/` | Glue job entry points |
| `scripts/` | `generate-mock-data.py`, `run-local-pipeline.py`, `validate-mcds-json.py` |
| `docs/model/` | Model diagrams: `lineage-explorer.html` (interactive, open in a browser) and Mermaid sources + PNGs for the flow, Callista source model and MCDS Silver model |
| `athena/queries/query-gold-reports.sql` | D5 demo queries, reconciliation, lineage and access-control checks |
| `tests/` | unit tests (no Spark) + end-to-end integration test (local Spark) |
| `analysis/Sisprod_schema_metadata.csv` | Real Callista schema export (3,914 tables) — ground truth for column names (git-ignored) |

## 1. Run locally (no AWS)

Prerequisites: Python 3.10+, Java 17+, and the MCDS package unzipped at `MCDS - v2.1.1/v2.1.1/`.

```bash
pip install -r requirements.txt
python scripts/generate-mock-data.py            # mock Callista CSV extract (masked, no PII)
python scripts/run-local-pipeline.py            # landing -> bronze -> silver -> gold + DQ + MCDS validation
pytest tests                                    # 23 tests incl. end-to-end
```

Outputs in `.local-lake/`: Parquet per layer, `exports/*.csv` (D5 report exports),
`silver/mcds_json/` (MCDS payloads), `gold/mcds_reporting/` (report definitions + fact data),
`run-report.json` (row counts per stage, every DQ result, every validation result).
Exit code 0 only if every fail-severity DQ rule and every MCDS validation passes.

To run on a real UC extract: put the 7 CSVs under `<landing>/callista/<YYYY-MM-DD>/` and pass
`--landing <landing>`.

## 2. Deploy to AWS (MDAA)

```bash
npm install                                     # @aws-mdaa/cli 1.9.0
export AWS_PROFILE=<uc-or-cevo-sandbox>
npx @aws-mdaa/cli synth                         # first run: confirm SSM parameter paths (see note)
npx @aws-mdaa/cli deploy -d shared              # roles, Lake Formation, catalog, audit
npx @aws-mdaa/cli deploy -d datalake            # buckets + Athena workgroup
npx @aws-mdaa/cli deploy -d dataops             # Glue databases + grants + jobs
```

Note: cross-module references use MDAA's default SSM layout
(`/{{org}}/<domain>/<module>/...`, `/{{org}}/shared/generated-role/<role>/arn`). The configs pass
MDAA's schemas but have not yet been synthesised against an AWS account; confirm the
parameter names on the first `synth`.

## 3. Run the pipeline in AWS

1. Upload the extract: `aws s3 cp ./extract/ s3://<landing-bucket>/callista/2026-10-25/ --recursive`
2. Run `landing-to-bronze` (optional `--EXTRACT_DATE`; default = latest folder), then
   `bronze-to-silver`, then `silver-to-gold` (Glue console or `aws glue start-job-run`).
3. Each job fails (non-zero) if a fail-severity DQ rule fails; DQ results are in the job log and
   `s3://<silver-bucket>/_dq_results/`.
4. Validate MCDS conformance of the exports:
   ```bash
   aws s3 sync s3://<silver-bucket>/mcds_json/2026-10-25/ ./out/json
   aws s3 sync s3://<gold-bucket>/mcds_reporting/2026-10-25/ ./out/rep
   python scripts/validate-mcds-json.py --students "out/json/*.json" \
     --definitions "out/rep/reportdefinitions/*.json" --factdata "out/rep/factdata/*.json"
   ```
5. Query Gold in Athena: `athena/queries/query-gold-reports.sql`.

## 4. Onboarding pattern (SOW D3): common changes

| Change | Edit | Code change? |
|---|---|---|
| UC confirms a rule (status codes, submission selection, student number, facility) | `config/business-rules.yaml` | No |
| Map another Callista column to an MCDS field | `etl/common/schemas.py` (extract column) + `config/silver-mappings.yaml` | Column list only |
| New Gold report / new dimension / new measure | `config/gold-aggregations.yaml` | No |
| New DQ rule | `config/data-quality-rules.yaml` | No |
| New Callista table | `schemas.py` spec + mapping entity + (if a new join) `pipeline.build_silver` | Yes (small) |

After editing config: re-run locally (`run-local-pipeline.py`), then `mdaa deploy -d dataops`
(ships the YAML with the jobs) and re-run the jobs.

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `fact_no_fanout` fails | STUDENT_UNIT_ATTEMPT key not unique in the extract | Check `bronze_sua_key_unique`; confirm SUA key with UC DBA |
| `fk_location` fails | Load row with no matching unit attempt | Extract SUA for the same calendar instances as the load |
| `fk_unit` / `fk_teaching_org_unit` fails | UNIT_VERSION / ORG_UNIT extract missing versions or start dates | Extract all versions / all ORG_UNIT start dates referenced by the load |
| `gold_eftsl_reconciles` fails | A Gold report dropped rows (null dimension) | Look for null `location_id` / `teaching_org_unit_code` in Silver |
| EFTSL higher than the government load file | `submission_selection: all` with overlapping submissions | Use `latest_per_unit_attempt` (default) |
| MCDS JSON fails `learningPeriod` / `location` required | CAL_INSTANCE or LOCATION missing rows | Include them in the extract |
| CSV read fails (FAILFAST) | Column order or date format differs from `schemas.py` | Align the extract or update `TABLE_SPECS` / `csv_options` |
