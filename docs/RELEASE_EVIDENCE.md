# Release evidence — 2026-10-22 post-Harshith settlement

Branch `feat/ruthvik-post-harshith`, [PR #7](https://github.com/jastiruthvik-web/FinLedger/pull/7).
Behavior commit these commands ran against: `614d47d87475ea611722bdb247e345cb7c490556`.
That commit is the settlement, the score-payload alignment, and the approval check.
This file is documentation on top of that commit and does not change runtime behavior.
The pull request head is the commit that contains this report.
CI `test` and `image` on that exact head are still required before merge. These local runs are
not an independent security review of the reservation settlement or the approval change.

Environment: Linux 6.12.94+ x86_64, Python 3.12.3, uv 0.10.9.
`initdb` was not on the default `PATH`. It was available as PostgreSQL 16.15 at
`/usr/lib/postgresql/16/bin/initdb`, and the suites ran with that directory on `PATH`.
No hosted database, Auth, S3, Resend, or model endpoint was contacted. No secrets were printed.
`person4_tally/` was not edited. Migrations `001`–`013` were not edited, and no migration `014`
was added. Nothing was applied to hosted SQL. `default_extract()` was not edited.
`--live-synthetic-eval` was not run.

## Commands and results

Step 0, before any behavior change, on `dbdf307fe5a825adf3eddc0f26ea0973f72c9785`
(`224f683`, `1c7d8a0`, and `0a40ac6` are ancestors). Platform is **360**, not the older
333 or 356 counts from other parents.

| Command | `dbdf307` | `614d47d` |
|---|---|---|
| `uv sync --project person2_platform --python 3.12 --locked --all-extras --dev` | completed | not repeated (tree already synced) |
| `uv sync --project person3_control_ui --python 3.12 --locked --dev` | completed | not repeated |
| `PYTHONPATH=evals person2_platform/.venv/bin/python -m pytest packages evals -q --basetemp=.pytest-person1` | **154 passed**, 0 failed, 0 skipped | **165 passed**, 0 failed, 0 skipped |
| `PYTHONPATH=evals person2_platform/.venv/bin/python evals/run_evals.py --provider-mode mock --report .pytest-person1/eval_report.md` | **3/3 structural, 6/6 exact** | **3/3 structural, 6/6 exact** |
| `PYTHONPATH=person2_platform/src person2_platform/.venv/bin/python -m pytest person2_platform/tests -q --basetemp=.pytest-person2` | **360 passed**, 0 failed, 0 skipped, 1 existing Starlette warning | **360 passed**, 0 failed, 0 skipped, same warning |
| `PYTHONPATH=person2_platform/src:person3_control_ui/src person3_control_ui/.venv/bin/python -m pytest person3_control_ui/tests -q --basetemp=.pytest-person3` | **64 passed**, 0 failed, 0 skipped, same warning | **69 passed**, 0 failed, 0 skipped, same warning |
| `docker build -t finledger:ci .` | **skipped** — no Docker CLI | **skipped** — no Docker CLI. The PR `image` job is still required |
| `evals/run_evals.py --live-synthetic-eval` | **not run** | **not run** |

`git diff --check` was clean. The mock report was written to `.pytest-person1/eval_report.md`, so `evals/latest_report.md` was not rewritten. `docs/assignments/` still contains exactly `RYAN_WORK.md`, `HARSHITH_WORK.md`, and `RUTHVIK_WORK.md`.

## Expired-hold choice

Option 3: accept the rule shipped in migration `013`. Expired holds stay in the table for audit and do not count toward the bill's cap. `llm_reserve_tokens` still counts only `held`. With `jobs.max_attempts` defaulting to 5, five dead attempts that had already reached the provider can leave the cap, so one bill can be charged about five times its token cap. That conflicts with the PR #6 rule that a call which reached the provider is not erased from the cap. It is accepted because `013` is already on main and editing it would split the blob operators apply (`6a0fdf8d5e0ce39a76000f87404bbace72763800`). This branch does not request a new migration for this rule. The existing expiry tests remain the regression. A timeout with no body is a different case and can stay uncounted: release runs only when the attempt received no body.

Token holds are not a dollar cap. An unpriced Gemini cost is not a measured `0`. Until a column can store "unpriced", that success does not insert a usage row, and the hold stays `held` so the estimate still counts. A fixture tariff stores that fixture's nonzero `cost_usd` on the real reservation id. `MockProvider` may still store its explicit `0.0`. The researched `$1.65` / `$9.90` figures are not configuration.

## What this tree proves

- `PostgresKillSwitch.reserve` / `release` / `settle_usage` open a short `tenant()` transaction and commit it. The model call is outside that transaction. `settle_usage` inserts `llm_usage_rows` with the hold's `reservation_id` and then calls `llm_reconcile_tokens` in the same transaction. A second connection sees the row and `reconciled`. Two overlapping reserves of one bill produce one `ai_budget_exceeded`. A connection under client B, as `fl_app` (member of `finledger_app` and `finledger_worker_extract`, not the owner, not `BYPASSRLS`), cannot read client A's usage row and cannot reconcile A's reservation (`unknown_reservation`). A settle that fails after a body existed leaves the hold `held`, not `released` and not `expired`. A later settle of that hold, or of a new hold, does not delete a usage row that already committed. A timeout with no body can remain `released` and uncounted.
- Thoughts in a fixture body are stored inside `tokens_out` (3 + 4 + 1000 → output 1004). Unknown usage with a fixture tariff is a reconciled row at the reservation (estimated input plus 256), not a release and not 0/0. An unpriced Gemini result inserts no `cost_usd = 0` row.
- `ModelRouter(settings, gemini_transport=None, kill_switch=None)` accepts an injected `PostgresKillSwitch` and still raises in `staging` and `production` for `mock` and `gemini`. It does not construct a socket client. `GeminiHttpClient` stays unwired unless the caller passes it.
- `default_extract()` still calls `ExtractWorker(UsageWriter())`, and `ExtractWorker` still calls `ModelRouter()` with no arguments. Harshith wires the injected switch and writer after this PR.
- A `CanonicalInvoice` from `MockProvider._extract` for a synthetic invoice with a positive total and at least one line validates through `validate_invoice`. Person 1's golden shape, including `vendor.pan`, `vendor.state`, and a string `bank_upi`, also validates. `extra="forbid"` remains. An unknown vendor field still fails. No score-worker command was added.
- A human whose id is `voucher_drafts.created_by` or `correction_events.actor_id` is refused approval while `canonical_invoices.maker_id` stays the automation user. A different human approver, who did not create the draft and did not write a correction, can approve. The automation user still has no Auth subject, no API token, no `firm_admin` flag, and no client role. `test_edit_and_reject_forms_keep_maker_checker` passed. No migration diff.

## Not done — owners and blockers

Hosted checklist items stay open. Local CI is not customer readiness.

| Item | Owner |
|---|---|
| Approve provider, model, processing location, retention, budget, capacity, and any tariff | Ryan (`RYAN_WORK.md`). Not approved. Live calls stay off. The researched rates are not a tariff and are not configuration |
| Private credentials, kept out of Git and chat | Ryan |
| Final acceptance and any customer-launch decision | Ryan. Local CI is not that acceptance |
| Migrations `012` and `013`, `extract-worker`, the automation maker in SQL, and the rollout notes | Harshith, landed ([PR #41](https://github.com/ryanshaon/FinLedger/pull/41), [PR #45](https://github.com/ryanshaon/FinLedger/pull/45), [PR #46](https://github.com/ryanshaon/FinLedger/pull/46), [PR #47](https://github.com/ryanshaon/FinLedger/pull/47)). Hosted apply, app login, storage, scanner, email, deploy, and the staging URL stay his and stay open |
| Wire `PostgresKillSwitch` and `PostgresUsageWriter` into `default_extract()` with the worker pool and short `tenant()` transactions | Harshith, after this PR. Signature: `ModelRouter(settings, gemini_transport=None, kill_switch=PostgresKillSwitch(conn, limit=..., enabled=...))` and `ExtractWorker(PostgresUsageWriter(conn), router)`. The connection must not already be inside a transaction that spans the model call |
| Migration `014` for an unpriced call (nullable `cost_usd`, or a separate status). Not for the expired-hold rule | Harshith. This branch does not write it. Until it exists, an unpriced Gemini success does not insert `cost_usd = 0` |
| `score` consumer, and any `map` or `post` platform process | Not agreed. This branch does not add one. The invoice boundary mismatch for a later consumer is fixed here |
| Wire `GeminiHttpClient` into an approved runtime and run `--live-synthetic-eval` | Ruthvik, only after Ryan's approval. Not this branch |
| Real synthetic-staff invite → password → login → TOTP → client list → logout, plus AAL1, cookie, expiry, and cross-tenant checks | Ruthvik, after Harshith's staging runtime and Ryan's Auth settings and app-login password. The fake Auth test is not this proof |
| Full upload → scan → extract → score/map → human review | Ruthvik, after a score consumer exists |

## Rollback

Revert the pull request. There is no migration to roll back and no hosted configuration to restore.
