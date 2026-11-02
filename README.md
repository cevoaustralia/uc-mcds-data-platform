# UC MCDS Data Platform

University of Canberra · MCDS Data Foundation EBA (Cevo / AWS).
Callista student data → **MCDS v2.1.1** Silver entities → curated Gold datasets for **use case A (student load by
unit and campus)** and **use case B (course enrolment profile)**, on an **AWS MDAA 1.9.0** platform.

Everything is **config-driven** and **account-agnostic**:

| To… | Change | Code change? | Redeploy? |
|---|---|---|---|
| add a Callista table | `pipeline/sources/callista.yaml` (`scripts/generate_source_config.py`) | no | no |
| add / change an MCDS entity | `pipeline/silver/<entity>.yaml` | no | no |
| add a report / dataset | `pipeline/gold/<report>.yaml` | no | no |
| change a business rule or code mapping | `pipeline/rules/*.yaml`, `pipeline/crosswalks/*.yaml` | no | no |
| add a DQ rule | `pipeline/dq/<layer>.yaml` | no | no |
| add a dashboard / visual | `quicksight/dashboards.yaml` | no | re-run deploy |
| deploy to another AWS account | `config/environments/<env>.yaml` (or GitHub Environment variables) | no | run deploy |

## Architecture

```
Callista (Oracle) CSV extract
   │  s3://<landing>/callista/extract_date=YYYY-MM-DD/<table>.csv
   ▼
Bronze  mcds_bronze.*   typed Parquet per Callista table, one partition per extract   (sources/*.yaml)
   ▼
Silver  mcds_silver.*   MCDS v2.1.1 entities, validated against MCDS JSON Schema      (silver/*.yaml)
   ▼
Gold    mcds_gold.*     use-case datasets + MCDS Reporting Framework files            (gold/*.yaml)
Ops     mcds_ops.*      pipeline runs, row counts, DQ results, MCDS validation          (monitoring)
   ▼
Athena (athena/queries) · QuickSight (quicksight/) · SageMaker Unified Studio (optional) · Bedrock DQ advisor (optional)
```

One generic Glue script (`etl/jobs/run_stage.py`) runs each stage; the engine (`etl/common/`) knows nothing about
specific tables or entities. Step Functions (`infra/dataops/stepfunction.yaml`) runs Bronze → Silver → Gold → advisor.

### MDAA modules (`infra/`, rendered into `mdaa.yaml`)

| Domain | Module | SOW |
|---|---|---|
| shared | roles, glue-catalog†, lakeformation-settings†, audit†, audit-trail† | D1, D4 |
| datalake | datalake (landing, bronze, silver, gold, artifacts buckets + KMS), athena | D1, D5 |
| dataops | project (Glue DBs + Lake Formation grants), jobs, orchestration (Step Functions), data-quality*, dq-advisor* | D2, D3, D4 |
| ai | bedrock-settings*† (model invocation logging) | add-on |
| consumption | quicksight-account*, quicksight-project* | add-on |
| smus | sagemaker (SageMaker Unified Studio)* | add-on |

\* optional, switched by `features.*` in `config/environments/<env>.yaml`.
† account-wide settings: deployed only when `features.account_level_settings: true` (dedicated account).

## Environments

| File / GitHub Environment | Account | `account_level_settings` | Status |
|---|---|---|---|
| `config/environments/cevo-aws-mcds.yaml` | Cevo shared account `cevo-dev25`, ap-southeast-2, prefix `cevo-dev25-mcds` | `false` (shared) | values set; deploy role ARN pending |
| `config/environments/uc-aws-mcds.yaml` | UC account | `true` (dedicated) | placeholders until UC provides values |

Moving from Cevo to UC = fill `uc-aws-mcds.yaml` (or its GitHub Environment variables) and run `deploy` with
`environment: uc-aws-mcds`. No code or config changes. All resources and SSM parameters are prefixed with the
organisation, so deployments never collide.

### Shared account (Cevo): one manual step

With `account_level_settings: false` the deployment does not change Lake Formation account settings (other teams
depend on them). The Glue databases' Lake Formation grants are created by CloudFormation during the `dataops/project`
deployment, so the identities creating them must be Lake Formation administrators **before** that module is deployed.
Anyone with Lake Formation admin rights in the dev account (no one else needed) adds, in
Lake Formation > Administrative roles and tasks > Data lake administrators:

1. the CDK CloudFormation execution role `cdk-hnb659fds-cfn-exec-role-<ACCOUNT>-<REGION>` (MDAA deploys through it);
2. the generated data-admin role `<org>-dev-shared-roles-data-admin` (look up the exact name in IAM after the
   `shared/roles` module is deployed).

Deploy order in a shared account: `shared` + `datalake` domains first -> add the two LF admins -> remaining domains.
Verify the exact role names on the first deployment - MDAA's generated names are the source of truth.

## Cost

Serverless and pay-per-use; nothing runs between pipeline runs except S3 storage and the KMS keys.

| Driver | Control in this repo |
|---|---|
| Glue job time | 2-3 G.1X workers, 30-min timeout, no retries (`infra/dataops/jobs.yaml`) |
| Athena scans | 10 GB per-query cutoff (`infra/data/athena-workgroup.yaml`); Gold tables are a few MB |
| QuickSight | Author/Reader per user per month; no Pro users / Q&A (avoids the per-account Q fee); DIRECT_QUERY (no SPICE) |
| Bedrock advisor | `amazon.nova-micro-v1:0` (lowest-cost text model, In-Region Sydney), metadata-only prompt, run on demand |
| CloudTrail | only in dedicated accounts (`account_level_settings`); shared accounts use the existing trail |
| S3 | landing extracts move to Glacier IR after 90 days, expire after 2 years |
| Guardrails | `bootstrap/cost-and-tag-guardrails.yaml`: monthly budget + anomaly alerts scoped to tag `project=uc-mcds` |

## Business rules (all in `pipeline/rules/load.yaml`, each flagged for UC confirmation)

- EFTSL per unit enrolment = `TRUNC(NVL(OVERRIDE_EFTSU, credit points / 24), 3)` - mirrors UC view `UC_SUA_EFTSU_FULL_V`;
  24 CP standard annual load inferred from the data (Callista `COURSE_VERSION.STD_ANNUAL_LOAD` not extracted).
- Counts as load: `ENROLLED`, `COMPLETED`, and `DISCONTIN` with `WD-LATE-LD` / `WD-FAIL` (after census);
  `WD-EARLY`, `INVALID`, `DUPLICATE`, `UNCONFIRM` and UNCONFIRM course attempts carry no load.
- Scope: HE coursework (incl. UC College and offshore partner delivery, flagged ONSHORE/OFFSHORE);
  HDR and ELICOS reported separately (`pipeline/crosswalks/calendar_type.yaml`).
- Faculty = unit's owning org unit (`UNIT_VERSION.OWNER_ORG_UNIT_CD`); school split = `TEACHING_RESPONSIBILITY` %.
- MCDS identifiers: organisation `ABN 81633873422`, system `CALLISTA-SISPROD` (`pipeline/pipeline.yaml`, to confirm).

## Local development (no AWS)

Prerequisites: Python 3.11+, Java 17, Node 20+; `pip install -r requirements-dev.txt`; `npm ci`.

```bash
# 1. MCDS schemas (licensed - never committed): compile the intermediate bundle from the package
python scripts/compile_mcds_bundle.py --package "<path>/v2.1.1-MCDS Schema"
# 2. Put an extract under data/landing/callista/extract_date=YYYY-MM-DD/ (git-ignored)
# 3. Run the whole pipeline locally (same engine and config as Glue)
python scripts/run_local.py --extract-date 2026-10-26
# 4. Tests (synthetic data) and infrastructure config validation (placeholders allowed)
python -m pytest -q tests
python scripts/render_mdaa.py --env cevo-aws-mcds --allow-placeholders && python scripts/validate_infra.py
```

Local output: `.local-lake/<layer>/<table>/` (Parquet) and `.local-lake/gold/_mcds_reporting/` (MCDS Reporting Framework JSON).

## Deploying to an AWS account (GitHub Actions)

1. **Once per account (administrator):** `npx cdk bootstrap aws://<ACCOUNT>/<REGION>` and deploy
   `bootstrap/github-oidc-deploy-role.yaml` (GitHub OIDC role - no stored credentials).
2. **Environment values:** fill `config/environments/<env>.yaml` placeholders, or set GitHub Environment variables
   `MDAA_AWS_ACCOUNT_ID`, `MDAA_AWS_REGION`, `MDAA_AWS_DEPLOY_ROLE_ARN`, `MDAA_ORGANIZATION`,
   `MDAA_NOTIFICATION_EMAIL`, `MDAA_QUICKSIGHT_IDENTITY_REGION`, `MDAA_BEDROCK_MODEL_ID`.
   Optional: deploy `bootstrap/cost-and-tag-guardrails.yaml` and activate the tag keys as cost allocation tags.
   Rendering refuses to deploy while any used value is still a `<PLACEHOLDER>`.
3. **Workflow `deploy`** (`action: diff` first, then `deploy`): renders + validates `mdaa.yaml`, runs MDAA,
   syncs `pipeline/` to `s3://<artifacts>/pipeline/`, deploys QuickSight assets when enabled.
4. **MCDS bundle (once, licensed):** `scripts/upload_mcds_bundle.sh "<MCDS package>" <env>`.
5. **Extract:** `scripts/upload_extract.sh <folder> <YYYY-MM-DD> <env>` (or UC drops files into the landing bucket).
6. **Workflow `run-pipeline`**: starts the Step Function for the extract date; optional Bedrock advisor.
7. Bedrock (if `features.bedrock_advisor`): enable model access for the configured model in the Bedrock console.
8. After the first run: set `features.glue_dq_rulesets: true` and re-run `deploy` (Glue DQ rulesets need the tables).

Workflow `ci` runs tests and MDAA config validation on every push, without AWS access.

## Demonstrating the use cases

| Where | What |
|---|---|
| Athena | `athena/queries/01-05` use cases A and B, `06` reconciliation, `07` lineage trace, `08` pipeline monitoring |
| Glue Data Catalog | every Silver column comment = Callista source → MCDS path; table properties = MCDS definition, keys, PII |
| QuickSight | dashboards 1-4: ingestion/Bronze, Silver conformance, student load (A), course enrolment (B) |
| SageMaker Unified Studio | optional (`features.smus`): lineage graph and notebooks over the same catalog |
| Bedrock | optional advisor: plain-English summary of each run's DQ results (advisory only, metadata only) |

## Repository layout

```
config/environments/   one file per target account         pipeline/   all pipeline behaviour (YAML)
infra/                 MDAA module configs + mdaa.template.yaml        etl/        engine (common/) + Glue entry (jobs/)
quicksight/            datasets + dashboards as config                 lambdas/    Bedrock DQ advisor
athena/queries/        demo SQL                                        scripts/    render, validate, run, deploy helpers
bootstrap/             one-time GitHub OIDC role                       tests/      unit + synthetic end-to-end tests
.github/workflows/     ci, deploy, run-pipeline                        docs/       Kiro-era docs (to be updated)
```

Git-ignored by design: `mdaa.yaml` (rendered), `mcds/` (licensed schemas/bundle), `data/landing/` (student data),
`.local-lake/`.
