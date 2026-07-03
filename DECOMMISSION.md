# Decommission Report — `wwbp-bcfg-chatbot`

**Date:** 2026-07-02/03 · **AWS account:** `336162656437` (us-east-1) · **Scope:** all environments (dev, test, prod)

The application (AWS Copilot: `web` + `worker` + `scheduler` per env, Aurora Serverless v2 PostgreSQL, ElastiCache Redis) is being decommissioned. All persistent data lives in the per-env Aurora `chatbot` databases — static assets are whitenoise (in-image), Redis is an ephemeral Celery broker, and there is no S3 media storage. Every database was backed up **two independent ways** and every backup was **cryptographically verified** before any deletion.

## 1. Backups (all verified ✅)

### RDS manual cluster snapshots (primary, AWS-native restore)
Manual snapshots survive cluster deletion indefinitely until explicitly deleted.

| Env | Snapshot ID | Status |
|---|---|---|
| dev | `wwbp-bcfg-chatbot-dev-final-20260702` | available |
| test | `wwbp-bcfg-chatbot-test-final-20260702` | available |
| prod | `wwbp-bcfg-chatbot-prod-final-20260702` | available |

### pg_dump archives (portable, restorable on any PostgreSQL ≥16)
Stored in `s3://wwbp-bcfg-decom-backups-336162656437/` (SSE-AES256, public access blocked) with local copies retained. Each env has three artifacts: `.dump` (pg_dump `-Fc`), `.manifest` (per-table row count + content digest), `.sha256` (artifact hashes computed at source, inside the VPC, before upload).

| Env | Dump size | `db.dump` SHA-256 | `db.manifest` SHA-256 |
|---|---|---|---|
| dev | 967 MB | `588fdbfc2503cd9eb3924e19612aa64224126cf73f806666d222cb41aa830905` | `86f8326fc71dea1818e23b6934a897eaee80fcedd8c4a2b33706886fbad432c1` |
| test | 17 MB | `992afd3b169b36ce61ae289d0dc62b4d0d876787dcf0fe0e8bf23f2c06a78e25` | `2ac29ff261a02f066550b19dfe8b6689124d266c3e0fbb80d3b57b90876a1357` |
| prod | 2.6 GB | `73f0875a62481cc0beb219dd8731b74adec0021d4e293047c9ac5915f9147a13` | `99ecff08159233d14dfaa983a63519a6b96bbe2bde42daf915d9d8661aa48578` |

Database credentials for all three clusters were exported from Secrets Manager before teardown (held privately offline, not in this repo).

## 2. Verification methodology

Tooling in [`decommission/`](decommission/). Each env was **quiesced** (all ECS services scaled to 0 and drained) before backup, so snapshot, dump, and manifest describe the same instant.

**Layer 1 — artifact integrity.** SHA-256 of the dump computed *inside the VPC* immediately after `pg_dump`, re-computed after download. Detects any transfer/storage corruption. All three envs: exact match.

**Layer 2 — logical integrity.** [`manifest.sql`](decommission/dump-task/manifest.sql) fingerprints every table: exact row count + an order-independent SHA-256 content digest (SHA-256 over the sorted per-row SHA-256s of `row::text`, rendered under pinned GUCs: `TimeZone=UTC, DateStyle=ISO, IntervalStyle=postgres, extra_float_digits=3, bytea_output=hex`). The dump is restored into a scratch server with `pg_restore --exit-on-error`, re-fingerprinted with the same file, and diffed against the source manifest. All three envs: every table identical (dev 50/50 tables; test all; prod all).

The gate caught (and we root-caused) three false-mismatch classes before declaring success — these are why the pinning above exists:
1. **Session `TimeZone`** flips `timestamptz::text` rendering (37 dev tables) → pinned UTC both sides.
2. **Sort collation** (Linux C vs macOS en_US.UTF-8) reorders manifest lines → `LC_ALL=C sort` both sides.
3. **libc `isspace()`**: on macOS, `record_out` quotes fields containing certain multibyte UTF-8 bytes (e.g. `0xA0` inside `☠️`), glibc does not — *same PostgreSQL version renders differently across libc*. Verified prod on a glibc `postgres:16.11` container matching Aurora exactly. **Logical verification must run on glibc.**

A cross-run consistency check also passed: two dump-task runs 1 hour apart (quiesced DB) produced byte-identical manifests.

## 3. Restore instructions

**From snapshot (full cluster):**
```bash
aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier <new-name> \
  --snapshot-identifier wwbp-bcfg-chatbot-<env>-final-20260702 \
  --engine aurora-postgresql
# then create a db.serverless writer instance in the new cluster
```

**From pg_dump (any PostgreSQL ≥ 16):**
```bash
aws s3 cp s3://wwbp-bcfg-decom-backups-336162656437/<env>-chatbot-20260702.dump .
shasum -a 256 <env>-chatbot-20260702.dump   # compare against table above
createdb chatbot && pg_restore --exit-on-error --no-owner --no-privileges -d chatbot <env>-chatbot-20260702.dump
# optional full re-verification:
decommission/verify/verify-dump.sh <env>-chatbot-20260702.{dump,manifest,sha256}
```

## 4. Teardown log

| Step | Status |
|---|---|
| dev services (web/worker/scheduler stacks) | ✅ deleted |
| dev addons stack (Aurora cluster, Redis, DB secret) | ✅ deleted (CFN also left an extra automatic final snapshot) |
| dev env stack (ALB, VPC, subnets) | 🔄 in progress at time of writing |
| test/prod services + env | ⏳ pending (order: purge ALB-logs bucket → addons stack → services → env) |
| `copilot app delete`, `task-django-bcfg-twilio` helper stack, ECR repos | ⏳ pending (last) |

Operational findings (for anyone repeating this):
- `copilot env delete` fails against env addons that import env exports (aws/copilot-cli#4730): **delete the addons CFN stack first**.
- The ALB access-logs buckets are **versioned**; copilot's bucket cleaner fails on them (and crashes on already-empty buckets — `--retain-resources` the `ELBAccessLogsBucketCleanerAction` custom resource on retry). Purge all versions + delete markers manually.
- Four hand-launched EC2 instances (3× Bitbucket CI runners from 2025-04, 1× DB-tunnel bastion from 2025-09) lived in the dev VPC outside CloudFormation and blocked subnet/IGW deletion; terminated with owner approval on 2026-07-03.
- The dump task needs `linux/amd64` images (`DOCKER_DEFAULT_PLATFORM=linux/amd64` when building on Apple Silicon) and an S3 `PutObject` grant on copilot's default task role.

## 5. Retained artifacts

- 3 manual RDS snapshots + CFN automatic finals (delete the automatics whenever; keep the manuals)
- `s3://wwbp-bcfg-decom-backups-336162656437/` — 9 verified artifacts
- Offline: local artifact copies + DB credential exports
- ACM certificate `34771f1b-e42a-4e00-b725-551b6459e3d8` (`*.wwbp-bcfg-chatbot.org`) — not deleted; decide separately with DNS
