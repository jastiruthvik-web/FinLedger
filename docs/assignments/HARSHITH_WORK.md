# Harshith — Remaining staging and deployment work

Updated 2026-10-22 after [PR #41](https://github.com/ryanshaon/FinLedger/pull/41)
merged into main at `1c7d8a0`. This is your only active assignment file.

## 1. Completed — do not rebuild

- Migration `012_ai_durable_state.sql`: durable retrieval/usage/reservation schema,
  tenant RLS, worker functions/grants and restricted per-firm automation maker.
- `extract-worker`: statement/key guards, extraction, safe failure categories,
  idempotent replay, retries/dead letters and lease-safe atomic status/score-job settlement.
- Compose extraction service; AI durability tests now use numbered migrations, not the removed SQL overlay.
- Native local smoke reached upload → extracted → score queued, with local EICAR scanning.
  This is the contributor's recorded local proof, not real ClamAV or hosted verification.

[Inspected CI](https://github.com/ryanshaon/FinLedger/actions/runs/39772975721):
**71 AI / 356 platform / 55 UI tests passed**, mock **3/3 + 6/6**, test/image jobs green.
These are CI results for the reviewed PR, not a new local run.

**Local backend milestone completed. Hosted operations are not completed.**
Migration 012 is committed but documented as **not applied hosted**; verify actual history before any action.

## 2. Remaining work, in order

Read root [HANDOVER](../../HANDOVER.md), [deployment runbook](../DEPLOYMENT_RUNBOOK.md)
and [Auth design](../plans/AUTH_SUPABASE_DESIGN.md) first. Use synthetic data only.

| Task | Prerequisite | Completion evidence |
|---|---|---|
| Confirm current hosted state and access needs | Owner-approved access | Redacted checklist of schema/runtime/storage/Auth state; no secret values |
| Prepare migration 012 staging rollout | Independent SQL/security review and explicit hosted approval | Existing data checked for duplicate RAG refs; exact committed migration identified; recovery/compatible-image plan recorded |
| Apply migration 012 once, if approved and not already applied | Approved rollout and privately entered migration credentials | Recorded commit, migration-history result, schema/RLS/grant checks and rollback-only tenant proof |
| Create/verify restricted runtime login and worker roles | Owner supplies password privately; approved grants | Session-pooler connection uses non-owner/non-BYPASSRLS login; per-process least privilege and cross-tenant denial proven |
| Verify real private storage | Owner-private S3 configuration | Synthetic put/get/presign, unsigned-public denial and cleanup result; explicitly resolve any leftover test object |
| Verify real ClamAV | Reachable approved scanner/runtime | Healthy scan, test-signature rejection and fail-closed outage/retry behavior; EICAR stub alone does not count |
| Verify email delivery and inbound webhook | Verified sender domain, private keys and explicit synthetic-send approval | Synthetic outbox/webhook path, authentication rejection, retry/failure behavior and delivery evidence without payload logs |
| Deploy API, control UI and separate workers | Approved hosting account/budget/origins; compatible reviewed code | Immutable image/commit, HTTPS, safe proxy logging/limits, stable keys, process/dependency checks and monitoring |
| Verify recovery and hand off staging | Approved runtime plus tests above | Tested compatible-image rollback without deleting data; staging URL and safe synthetic setup for Ruthvik |

**Do now without live credentials:** prepare the rollout checklist, inspect code/role requirements,
review scanner/deployment configuration, identify exact missing inputs and agree integration PRs.
Do not wait silently or claim a hosted task complete because its local code exists.

**Do not** edit/reapply migrations 001–011, alter applied 012 SQL, apply uncommitted SQL,
reset hosted data, clear buckets or delete persistent volumes. Any additional fix uses a new reviewed
migration/PR. A real deployment cannot use mock AI; keep extraction disabled/fail-closed until Ruthvik's
approved live-provider/runtime path is ready. Do not weaken startup guards to make a demo work.

## 3. Coordinate with Ruthvik — do not duplicate his work

[Ruthvik's work](RUTHVIK_WORK.md) covers provider/accounting fixes, actual HTTP/runtime wiring,
durable-adapter integration, score/map → review completion and detailed Auth/UI/end-to-end QA.

- Give him migration/function signatures, the extract result/score payload contract
  (`canonical_invoice`, `maker_id`), reviewed commit links and operational dependency results.
- Coordinate who implements any score-consumer platform entry point; Ruthvik owns completing
  and verifying the scoring-to-review integration. Do not start a competing implementation.
- Support wiring `PostgresKillSwitch` and `PostgresUsageWriter` into the actual worker.
  Current `default_extract()` still uses in-memory usage; agree short tenant transactions
  and atomic usage/hold settlement with Ruthvik, not a transaction held across model calls.
- Support independent automation-maker/human-editor checks. The established requirement is
  that automation must not let a human editor approve their own work. Do not relax that
  requirement or invent automatic posting/payment permission.
- Supply the approved staging URL and private synthetic test setup. Ruthvik leads real Auth,
  browser/workflow and upload-to-review proofs; you fix backend/operational failures they expose.

Ryan's [short checklist](RYAN_WORK.md) remains approvals/private access and final acceptance,
not implementing hosted setup or repeating detailed QA.

## 4. Approval gates and reporting

Provider/model, processing location, retention, AI budget/capacity and hosting account/budget
still require approval. Private credentials belong in secret settings, not Git, chat or PR output.
No model calls, real invites, outbound messages or hosted mutations are authorized by this file alone.

Keep this file updated in place: check off verified work or move it to the concise completed record.
Each PR/HANDOVER update lists exact commands/pass/fail/skip counts, environment, cleanup,
actual hosted changes and named blockers. Require green CI on the exact final commit and
independent security review. P2 dependency changes require both P2/P3 lockfiles.

No RLS/MFA/scanner bypass, force-push cleanup, AI attribution trailers or `person4_tally/` edits.
Do not claim production readiness while integration or hosted verification remains blocked.
