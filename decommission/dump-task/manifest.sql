-- manifest.sql — logical integrity fingerprint of every table in a database.
-- Per table: exact row count + order-independent SHA-256 content digest
-- (SHA-256 over the SORTED SHA-256 of every row, so row order / physical layout don't matter).
-- sha256() is a Postgres built-in since v11 (no pgcrypto extension needed).
-- Run against SOURCE (static) and against each RESTORE; diff the outputs.
--   psql "$CONN" -At -f manifest.sql | sort > manifest.txt      (output: schema.table|rows|sha256hex)
-- No text-emitting meta-commands: output stays pure data so the fingerprint is byte-identical
-- regardless of which psql build runs it (container vs local).

SELECT format(
  'SELECT %L AS k, count(*)::text AS rows, '
  || 'coalesce(encode(sha256(convert_to('
  || 'string_agg(encode(sha256(convert_to(t.*::text, ''UTF8'')), ''hex''), '''' '
  || 'ORDER BY encode(sha256(convert_to(t.*::text, ''UTF8'')), ''hex'')), '
  || '''UTF8'')), ''hex''), ''EMPTY'') AS digest '
  || 'FROM %I.%I t',
  n.nspname || '.' || c.relname, n.nspname, c.relname)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname
\gexec
