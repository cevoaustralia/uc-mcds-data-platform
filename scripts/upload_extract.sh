#!/usr/bin/env bash
# Upload one Callista extract drop to the landing bucket (run with your own AWS credentials).
#   scripts/upload_extract.sh data/landing/callista/extract_date=2026-10-26 2026-10-26 cevo-aws-mcds
# Files must be named as in pipeline/sources/callista.yaml (e.g. student_unit_attempt.csv).
set -euo pipefail
SRC="$1"; DATE="$2"; ENV="${3:?environment name, e.g. cevo-aws-mcds}"
cd "$(dirname "$0")/.."
ORG=$(python3 scripts/env_value.py --env "$ENV" organization)
REGION=$(python3 scripts/env_value.py --env "$ENV" aws.region)
BUCKET=$(aws ssm get-parameter --region "$REGION" --name "/$ORG/datalake/datalake/bucket/landing/name" --query Parameter.Value --output text)
aws s3 cp --region "$REGION" --recursive "$SRC" "s3://$BUCKET/callista/extract_date=$DATE/" --exclude "*" --include "*.csv"
echo "uploaded to s3://$BUCKET/callista/extract_date=$DATE/ - now run the run-pipeline workflow"
