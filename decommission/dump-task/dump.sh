#!/usr/bin/env bash
# Runs INSIDE the Copilot env VPC (Fargate) to reach the private Aurora cluster.
# Emits THREE artifacts to S3 (DB must be quiesced/static first):
#   <env>.dump       pg_dump custom-format archive (portable backup)
#   <env>.manifest   per-table row count + SHA-256 content digest (logical fingerprint)
#   <env>.sha256     SHA-256 of the .dump and .manifest (artifact fingerprint, computed AT SOURCE)
set -euo pipefail
: "${DB_SECRET:?}"; : "${DUMP_BUCKET:?}"; : "${DUMP_KEY:?}"; : "${MANIFEST_KEY:?}"; : "${SHA_KEY:?}"

j(){ printf '%s' "$DB_SECRET" | python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }
HOST=$(j host); PORT=$(j port); USER=$(j username); DB=$(j dbname); export PGPASSWORD; PGPASSWORD=$(j password)
[ -n "$PORT" ] || PORT=5432; [ -n "$DB" ] || DB=chatbot
CONN="host=$HOST port=$PORT user=$USER dbname=$DB sslmode=${PGSSLMODE:-require}"

echo ">> pg_dump -> /tmp/db.dump"
pg_dump "$CONN" -Fc --no-owner --no-privileges -f /tmp/db.dump

echo ">> source logical manifest -> /tmp/db.manifest"
# Pin every GUC that affects ::text rendering (must match verify-dump.sh exactly)
PGOPTIONS="-c TimeZone=UTC -c DateStyle=ISO,YMD -c IntervalStyle=postgres -c extra_float_digits=3 -c bytea_output=hex -c lc_monetary=C" \
  psql "$CONN" -At -f /manifest.sql | LC_ALL=C sort > /tmp/db.manifest

echo ">> source SHA-256 (artifact fingerprint)"
( cd /tmp && sha256sum db.dump db.manifest ) > /tmp/db.sha256
cat /tmp/db.sha256

echo ">> upload to s3://$DUMP_BUCKET/"
aws s3 cp /tmp/db.dump     "s3://$DUMP_BUCKET/$DUMP_KEY"
aws s3 cp /tmp/db.manifest "s3://$DUMP_BUCKET/$MANIFEST_KEY"
aws s3 cp /tmp/db.sha256   "s3://$DUMP_BUCKET/$SHA_KEY"
echo ">> done"
