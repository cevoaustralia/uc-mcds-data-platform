#!/usr/bin/env bash
# Compile the MCDS schema bundle from a licensed MCDS package and upload it to the artifacts bucket.
# Run once per environment (and again when the MCDS version or the set of entities changes) by someone
# who holds the MCDS package, using their own AWS credentials. The bundle is never committed to git.
#   scripts/upload_mcds_bundle.sh <path-to-MCDS-v2.1.1-package> <env>
set -euo pipefail
PKG="$1"; ENV="${2:?environment name, e.g. cevo-aws-mcds}"
cd "$(dirname "$0")/.."
python3 scripts/compile_mcds_bundle.py --package "$PKG" --out mcds/compiled/mcds-v2.1.1-uc-bundle.json
ORG=$(python3 scripts/env_value.py --env "$ENV" organization)
REGION=$(python3 scripts/env_value.py --env "$ENV" aws.region)
BUCKET=$(aws ssm get-parameter --region "$REGION" --name "/$ORG/datalake/datalake/bucket/artifacts/name" --query Parameter.Value --output text)
aws s3 cp --region "$REGION" mcds/compiled/mcds-v2.1.1-uc-bundle.json "s3://$BUCKET/mcds/mcds-v2.1.1-uc-bundle.json"
echo "uploaded to s3://$BUCKET/mcds/mcds-v2.1.1-uc-bundle.json"
