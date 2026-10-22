# Release evidence — 2026-10-22 local integration

Branch `feat/release-integration`, based on `origin/main` `0b58982` (PR #38).
Environment: Linux, Python 3.12.3, uv 0.10.9, PostgreSQL 16 client tools (`initdb` on `PATH`).
No hosted database, S3, Auth, Resend, or model endpoint was contacted. No secrets were printed.
`person4_tally/` was not edited. Migrations `001`–`011` were not edited or reapplied.

The commit that contains this report is the tree these commands ran against. The pull request
records that commit’s SHA.

## Commands and results

| Command | Result |
|---|---|
| `uv sync --project person2_platform --python 3.12 --locked --all-extras --dev` | completed |
| `PYTHONPATH=evals person2_platform/.venv/bin/python -m pytest packages evals -q --basetemp=.pytest-person1` | **91 passed** |
| `PYTHONPATH=evals person2_platform/.venv/bin/python evals/run_evals.py --provider-mode mock --report .pytest-person1/eval_report.md` | **3/3 structural, 6/6 exact** |
| `PYTHONPATH=person2_platform/src person2_platform/.venv/bin/python -m pytest person2_platform/tests -q --basetemp=.pytest-person2` | **333 passed**, 1 existing Starlette deprecation warning |
| `uv sync --project person3_control_ui --python 3.12 --locked --dev` | completed |
| `PYTHONPATH=person2_platform/src:person3_control_ui/src person3_control_ui/.venv/bin/python -m pytest person3_control_ui/tests -q --basetemp=.pytest-person3` | **64 passed**, same Starlette warning |
| `docker build -t finledger:ci .` | **skipped** — no Docker daemon or CLI in this environment |
| `evals/run_evals.py --live-synthetic-eval` | **not run** — owner approval required; CI stays on mock |

`git diff --check` was clean. The mock report was written outside the repo so `evals/latest_report.md` was not rewritten.

Historical comparison, not a claim that those runs were repeated on older commits: PR #37 CI was 71 AI / 333 platform / 55 UI, mock 3/3 + 6/6. Platform count is unchanged. AI and UI counts rose because this branch adds tests.

## What this tree proves

- `HttpGeminiTransport` builds one Vertex-style URL from the explicit location, model and project. Tests inject HTTP. Timeouts, 429 and 5xx stay retryable inside `GeminiProvider` up to `max_retries`. 401/403 are not retried. Error strings omit the credential, the response body and the invoice canary. An oversized request never reaches HTTP.
- Passing that transport into `ModelRouter` still raises in `FINLEDGER_ENV=production`. Gemini still requires an explicit transport. There is no mock fallback and no location rewrite.
- A page-image key that is not strictly under `{client_id}/` raises `object_key_rejected` before `complete(...)`. A `statement` document still raises `statement_not_extracted` with no model call.
- Review HTTP coverage: invalid approve form returns 422 HTML (`Nothing was saved`) and does not echo the posted field; a stale revision returns 409 and writes no approval; a second identical draft approval does not add another approval or a post job; a clerk edit writes one correction and cannot self-approve; approver resubmit lands on the exception queue labeled `Resubmit requested`.
- Inbox labels: `Queued for extraction`, `Extraction failed`, `AI budget exhausted`, `Statement excluded`, `Quarantined`. Accepted/queued work is not labeled success. Quarantined rows are in the exception queue and its count.
- Fake Auth journey: invite, set password, failed sign-in (password not echoed), AAL1 blocked from the client list and review queue, TOTP upgrades the cookie, the previous cookie is rejected, client list renders, logout, and the revoked cookie cannot list clients.
- Existing platform session tests still pass, including idle and absolute expiry in `person2_platform/tests/test_staff_sessions.py` (part of the 333). That is local Postgres, not a hosted 8-hour / 30-minute browser proof.

## Not done — left to the named owner

No open pull request existed for the platform migration or extract consumer. This branch does not add a competing `012_*.sql` or `finledger-platform extract-worker`.

| Item | Owner |
|---|---|
| Next migration after `011` for `docs/proposals/AI_DURABLE_RETRIEVAL_USAGE_SCHEMA.md`, tested on fresh and upgraded local databases, then reviewed before any hosted apply | Friend 2 (platform). Friend 1 overlay SQL stays test-only |
| `extract-worker`: claim/lease, tenant context, `load_extract_input`, `extract_document`, statement row → `exception` without a model call, score/map handoff, idempotent replay, compare-and-set, bounded retries/dead letters, lease expiry, late-result rejection, atomic settlement, invoice-free diagnostics | Friend 2. Integrate that PR instead of rewriting it |
| Per-firm non-login automation maker (no Auth subject, bearer token, or admin privilege) and independent maker/checker review | Friend 2 implements; Ryan reviews |
| Durable adapters bound to that reviewed migration on the real worker path | After Friend 2’s migration. Ephemeral proof already exists in `packages/usage/tests/test_durable_postgres.py` |
| Live Gemini transport wiring and `--live-synthetic-eval` | Owner, after provider, location, retention, budget and capacity approval. Do not remove the staging/production guard to demo it |
| Restricted staging login via the session pooler, S3 put/get/presign/unsigned-denial/cleanup, ClamAV readiness, Resend synthetic mail, API/UI/worker deploy, rollback | Owner. Not inspected or changed here |
| Synthetic staff invite → password → TOTP on real staging Auth; customer launch | Owner / Ryan. Fake Auth above is not that proof |
| Final independent acceptance | Ryan |

## Rollback

This change is application code and tests only. Revert the pull request. There is no migration to roll back and no hosted configuration to restore. Queued documents that were already accepted still wait for the missing extract consumer; the desk now says so instead of showing a bare `received` status.
