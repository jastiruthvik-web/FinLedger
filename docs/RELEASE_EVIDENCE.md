# Release evidence — 2026-10-22 local review follow-ups

Branch `feat/ruthvik-review-followups`, cut from `origin/main` `d519e480658ec868039b375b30076f9bb5523837`.
Code commit these commands ran against: `8a0c6bebf9d83fef86765361f165f1b36eb73a7c`.
That commit cherry-picks `8a4d97b4facf73d455e2470aba50e60a0123ad25` and adds reasoning-token
accounting plus a stdlib HTTP client. This file is documentation on top of that commit and does
not change runtime behavior. The pull request head is the commit that contains this report.
CI `test` and `image` on that exact head are still required before merge. These local runs are
not an independent security review.

Environment: Linux 6.12.94+ x86_64, Python 3.12.3, uv 0.10.9.
`initdb` was not on the default `PATH`. It was available as PostgreSQL 16.15 at
`/usr/lib/postgresql/16/bin/initdb` and the suites ran with that directory on `PATH`.
No hosted database, Auth, S3, Resend, or model endpoint was contacted. No secrets were printed.
`person4_tally/` was not edited. Migrations `001`–`011` were not edited, and no new numbered
migration was added. Nothing was applied to hosted SQL.

## Commands and results

| Command | Result |
|---|---|
| `uv sync --project person2_platform --python 3.12 --locked --all-extras --dev` | completed |
| `uv sync --project person3_control_ui --python 3.12 --locked --dev` | completed |
| `PYTHONPATH=evals person2_platform/.venv/bin/python -m pytest packages evals -q --basetemp=.pytest-person1` | **154 passed**, 0 failed, 0 skipped |
| `PYTHONPATH=evals person2_platform/.venv/bin/python evals/run_evals.py --provider-mode mock --report .pytest-person1/eval_report.md` | **3/3 structural, 6/6 exact**, 0 failed |
| `PYTHONPATH=person2_platform/src person2_platform/.venv/bin/python -m pytest person2_platform/tests -q --basetemp=.pytest-person2` | **333 passed**, 0 failed, 0 skipped, 1 existing Starlette warning |
| `PYTHONPATH=person2_platform/src:person3_control_ui/src person3_control_ui/.venv/bin/python -m pytest person3_control_ui/tests -q --basetemp=.pytest-person3` | **64 passed**, 0 failed, 0 skipped, same Starlette warning |
| `docker build -t finledger:ci .` | **skipped** — no Docker CLI in this environment. The PR `image` job is still required |
| `evals/run_evals.py --live-synthetic-eval` | **not run** |

`git diff --check` was clean on the code diff. The mock report was written to `.pytest-person1/eval_report.md`, so `evals/latest_report.md` was not rewritten.

Step 0 on `d519e48`, before the cherry-pick, was **71 passed / 333 passed / 55 passed**, mock **3/3 + 6/6**. The cherry-pick alone, before accounting and the socket client, was **91 / 333 / 64**, mock **3/3 + 6/6**. Platform and UI counts are unchanged after that cherry-pick. The AI count rose from 91 to 154 because of the new accounting and loopback-client tests only.

## What this tree proves

- `HttpGeminiTransport` still builds one Vertex URL from the explicit location, model, and project. Injected `http_post` tests still pass. `staging` and `production` still refuse both `mock` and `gemini`, including when an HTTP transport or the new client object is supplied to `ModelRouter`. `ModelRouter` does not construct the socket client and still has no network fallback.
- `GeminiHttpClient.exchange` does not take a raw URL. Socket tests open `127.0.0.1` only. An oversized body is rejected while it is being read. A server that accepts and does not write maps to `timeout`. A refused connection maps to `transport_unavailable`. A 301/302/303/307/308 does not send `Authorization` to the redirect target. Error text does not include the bearer, the body, or the `Location` value. Credential refresh and key-file reads are outside this branch and still wait on owner activation.
- Usage metadata follows the Vertex `generateContent` `UsageMetadata` description checked on 2026-10-22 at <https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1beta1/GenerateContentResponse>. `thoughtsTokenCount` is billed output and is counted once inside `tokens_out`. `cachedContentTokenCount` is already inside `promptTokenCount` and is not added again. `toolUsePromptTokenCount` is outside the prompt and inside `totalTokenCount`, so it is added to input once and `totalTokenCount` is not added on top. `generationConfig.maxOutputTokens` is the request field from <https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference>, checked the same day. The value sent is 256, the same output allowance the reservation holds. Code defaults stay `gemini-1.5-flash` and `gemini-1.5-pro`.
- A synthetic body of prompt 3, candidates 4, and thoughts 1000 reconciles to 1007. Missing or malformed usage is reconciled at the reservation (estimated input plus 256), not released, and is not stored as 0/0. A response larger than the 256 output allowance is reconciled at the larger actual. Image input uses a fixed fixture allowance per image, not `json.dumps(..., default=str)` of the raw bytes. A retry that already received a body settles that attempt and holds the next one separately. A timeout with no body can remain uncounted.
- There is no dollar cap. Token reservations are not a dollar cap. With no injected tariff, a Gemini success does not log `cost_usd == 0.0`. A test-only positive fixture rate produces a nonzero cost for nonzero fixture tokens. The researched $1.65 / $9.90 figures are not configuration and are not a spending approval. `MockProvider` still logs its zero default.
- Object keys outside `{client_id}/` still fail as `object_key_rejected` before a model call. A statement still raises `statement_not_extracted` with no model call. Review labels and the fake Auth journey from the cherry-pick are unchanged. The fake journey is a local test, not the hosted invite proof.

## Not done — owners and blockers

Hosted checklist items in `docs/assignments/RUTHVIK_WORK.md` §4 and the staging bullets in §5 stay open.
No Harshith pull request exists, so none of his items are linked or reassigned.

| Item | Owner |
|---|---|
| Approve provider, model, processing location, retention, budget, and capacity | Ryan (`RYAN_WORK.md`). Not approved. Live calls stay off |
| Enter private credentials and keep them out of Git and chat | Ryan |
| Final acceptance and any customer-launch decision | Ryan. Local CI is not that acceptance |
| Numbered migration after `011` from `docs/proposals/AI_DURABLE_RETRIEVAL_USAGE_SCHEMA.md`, including fresh and upgraded databases | Harshith. Blocked. No PR yet. His `llm_reconcile_tokens` should take the proposal §5.2 arguments, store chargeable tokens with thoughts inside output, and must not store an unpriced Gemini call as `cost_usd = 0` |
| `finledger-platform extract-worker`, statement row handling, queue replay, leases, and settlement | Harshith. Blocked. No PR yet |
| Per-firm non-login automation maker | Harshith. Blocked. No PR yet. The existing clerk self-approval test is not that proof |
| Restricted app login, S3, ClamAV, Resend, API/UI/worker deploy, and rollback | Harshith. Blocked. No PR yet |
| Wire the reviewed client into the runtime and run `--live-synthetic-eval` | Ruthvik, only after Ryan's approval and an account. Not this branch |
| Real synthetic-staff invite → password → TOTP → client list → logout on staging, plus AAL1, cookie, expiry, and cross-tenant checks | Ruthvik, after Harshith supplies the staging runtime and Ryan supplies Auth settings and the app-login password. The fake Auth test is not this proof |

## Rollback

This change is application code, tests, and this evidence file. Revert the pull request. There is no migration to roll back and no hosted configuration to restore.
