#!/usr/bin/env bash
# TWO-LAYER integrity gate. Exit 0 = PASS, non-zero = FAIL (do NOT tear down).
#   Layer 1 (artifact):  local sha256 of the downloaded .dump == source sha256  -> no transfer bit-rot
#   Layer 2 (logical):   clean pg_restore (--exit-on-error) + row counts & SHA-256 digests == source
# Usage: ./verify-dump.sh <env.dump> <env.manifest> <env.sha256>
set -euo pipefail
DUMP="${1:?.dump}"; SRC_MANIFEST="${2:?.manifest}"; SRC_SHA="${3:?.sha256 from source}"
PG_BIN="/opt/homebrew/opt/postgresql@16/bin"; export PATH="$PG_BIN:$PATH"
HERE="$(cd "$(dirname "$0")" && pwd)"; SCRATCH="verify_scratch_$$"
"$PG_BIN/pg_isready" -q || { echo "start local pg: brew services start postgresql@16"; exit 1; }

echo "== LAYER 1: artifact SHA-256 =="
# source .sha256 lines look like: "<hex>  db.dump". Pull the dump's expected hash.
WANT=$(awk '/db\.dump$/{print $1}' "$SRC_SHA"); [ -n "$WANT" ] || { echo "no db.dump hash in $SRC_SHA"; exit 3; }
GOT=$(shasum -a 256 "$DUMP" | awk '{print $1}')
echo "   source=$WANT"; echo "   local =$GOT"
[ "$WANT" = "$GOT" ] || { echo "   FAIL: dump sha256 mismatch (transfer corruption)"; exit 2; }
echo "   ok: archive bytes intact"

echo "== LAYER 2: clean restore + logical fingerprint =="
pg_restore --list "$DUMP" >/dev/null && echo "   TOC valid"
createdb "$SCRATCH"; trap 'dropdb --if-exists "$SCRATCH"' EXIT
pg_restore --exit-on-error --no-owner --no-privileges -d "$SCRATCH" "$DUMP"
echo "   restored with zero errors"
# Pin every GUC that affects ::text rendering so digests are canonical across servers/sessions
# (must match dump.sh exactly; unpinned TimeZone alone flips every timestamptz digest)
export PGOPTIONS="-c TimeZone=UTC -c DateStyle=ISO,YMD -c IntervalStyle=postgres -c extra_float_digits=3 -c bytea_output=hex -c lc_monetary=C"
psql "dbname=$SCRATCH" -At -f "$HERE/../dump-task/manifest.sql" | LC_ALL=C sort > restored-manifest.txt
# canonically re-sort BOTH sides (C collation) so sort-locale differences can never mask/flag anything
LC_ALL=C sort "$SRC_MANIFEST" > src-manifest.sorted
if diff -u src-manifest.sorted restored-manifest.txt; then
  echo "   PASS: row counts + SHA-256 digests identical for every table."
else
  echo "   FAIL: logical manifest differs (see diff)."; exit 2
fi
echo "ALL CHECKS PASSED"
