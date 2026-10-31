# Release evidence — 2026-10-27 local journey

Branch `feat/local-journey-proof`. Base is `b8cf3a37e221f24cec8b6b9402e434ad005e5b8f` (`b8cf3a3`).
Behavior commit these commands ran against: `e58901872aef26f66bd3771ae4ec0cdb8292b2ed`.
That commit is the local upload-to-review suite and the opt-in live Gemini switch.
This file is documentation on top of that commit and does not change runtime behavior.
The pull request head is the commit that contains this report.
CI `test` and `image` on the exact head are still required before merge. These local runs are
not an independent security review.

`b8cf3a3` already had migration `014`, `score-worker`, and `default_extract(conn)` durable
wiring. This run does not redo them.

Environment: Linux 6.12.94+ x86_64, Python 3.12.3, uv 0.13.6.
`initdb` was not on the default `PATH`. It was available as PostgreSQL 16.15 at
`/usr/lib/postgresql/16/bin/initdb`, and the suites ran with that directory on `PATH`.
No `FINLEDGER_TEST_OWNER_DSN` was set, so platform and control-UI tests booted a throwaway
cluster. No hosted database, Auth, S3, Resend, or model endpoint was contacted. No secrets
were printed. `person4_tally/` was not edited. Migrations `001`–`014` were not edited.
Nothing was applied to hosted SQL. `--live-synthetic-eval` was not run.

## Commands and results

`uv sync --project person2_platform --python 3.12 --locked --all-extras --dev` and
`uv sync --project person3_control_ui --python 3.12 --locked --dev` completed before the run.

| Command | `e589018` |
|---|---|
| `PYTHONPATH=evals person2_platform/.venv/bin/python -m pytest packages evals -q --basetemp=/tmp/pytest-person1b` | **176 passed**, 0 failed, 0 skipped |
| `PYTHONPATH=evals person2_platform/.venv/bin/python evals/run_evals.py --provider-mode mock --report /tmp/pytest-person1b/eval_report.md` | **3/3 structural, 6/6 exact** |
| `PYTHONPATH=person2_platform/src person2_platform/.venv/bin/python -m pytest person2_platform/tests -q --basetemp=/tmp/pytest-person2` | **372 passed**, 0 failed, 0 skipped, 1 existing Starlette warning |
| `PYTHONPATH=person2_platform/src:person3_control_ui/src person3_control_ui/.venv/bin/python -m pytest person3_control_ui/tests -q --basetemp=/tmp/pytest-person3` | **78 passed**, 0 failed, 0 skipped, same warning |
| `docker build -t finledger:ci .` | **skipped** — no Docker CLI. The PR `image` job is still required |
| `evals/run_evals.py --live-synthetic-eval` | **not run** |

`git diff --check` was clean on the behavior tree. The mock report was written under `/tmp`,
so `evals/latest_report.md` was not rewritten. `docs/assignments/` still contains exactly
`RYAN_WORK.md`, `HARSHITH_WORK.md`, and `RUTHVIK_WORK.md`.

The platform and UI commands above ran on the same behavior tree. The packages command was
repeated after the last behavior edit and is the count in the table.

## What this tree proves

- Upload of a synthetic text-layer invoice, ingest, `default_extract(conn)` with the mock
  provider, and `default_score()` reach `scored`. A clerk correction of `party_ledger` and a
  different human's draft approval reach `approved`. The clerk who edited cannot approve.
  On `received`, the desk says `Queued for extraction`, not a success. After scoring it says
  `Scored`.
- Replaying the same extract job does not call the model again, does not add a usage row, and
  does not enqueue a second score job. Replaying the score job does not add a risk assessment
  or bump the canonical revision. Replaying both after approval does not add a correction or
  an approval.
- A lost extract lease leaves the document `received` and writes no score job. A lost score
  lease leaves it `extracted` and writes no canonical invoice or risk row.
- A schema-invalid invoice (extract succeeds, Person 3's boundary rejects it) becomes
  `canonical_invoice_rejected`. The score job is `done`. Another claim does not retry it.
  A manual requeue is `skipped` and still writes no canonical row.
- A scanner outage (`clamd` on a closed port) leaves `virus_ok` null, status `received`, and
  no extract job, with `last_error` `virus scanner unavailable`. Restoring the dev scanner
  retries the same job to `prepared`.
- A per-bill cap of 1 becomes `ai_budget_exceeded`, the extract job is `done`, the model body
  is not generated, and the desk says `AI budget exhausted`.
- Provider timeouts (`provider_transient`) retry and the extract job is `dead` after 5
  attempts. The document stays `received`. The desk says `Extraction failed`.
- A statement never calls the model and becomes `statement_not_extracted` (`Statement excluded`
  on the desk). An object key outside `{client_id}/` never calls the model and becomes
  `object_key_rejected`.

## Opt-in live Gemini — present, not run

`ModelRouter` still refuses `mock` in `staging` and `production`. It refuses `gemini` there
unless the transport is an `HttpGeminiTransport` whose client is a `GeminiHttpClient`. It does
not construct that client. `default_extract` builds one only when `FINLEDGER_GEMINI_LIVE=1`.
That switch also requires `FINLEDGER_LLM_PROVIDER=gemini` and explicit
`FINLEDGER_MODEL_EXTRACT`, `FINLEDGER_GEMINI_LOCATION`, `FINLEDGER_GEMINI_PROJECT`, and
`FINLEDGER_GEMINI_CREDENTIAL`. A missing value fails before a socket. There is no mock, region,
or model fallback. The credential is not written into errors.

`evals/run_evals.py --live-synthetic-eval --provider-mode gemini` is the separate command.
It is off unless passed. CI still runs `--provider-mode mock` only. This run did not pass the
live flag and did not set a credential.

## Not done — owners and blockers

Hosted checklist items stay open. Local CI is not customer readiness.

| Item | Owner |
|---|---|
| Approve provider, model, processing location, retention, budget, capacity, and any tariff | Ryan (`RYAN_WORK.md`). Not approved. The live switch stays off |
| Private credentials, kept out of Git and chat | Ryan |
| Final acceptance and any customer-launch decision | Ryan. Local CI is not that acceptance |
| Hosted apply, app login, storage, scanner, email, deploy, and the staging URL | Harshith. Open |
| Run `--live-synthetic-eval` on synthetic or redacted invoices and record model, location, tokens, and cost | Ruthvik, only after Ryan's approval and an account you control. Not this run |
| Real synthetic-staff invite → password → login → TOTP → client list → logout, plus AAL1, cookie, expiry, and cross-tenant checks | Ruthvik, after Harshith's staging runtime and Ryan's Auth settings. The fake Auth test is not this proof |
| Green CI `test` and `image` on the exact pull request head | Required before merge. Not claimed here |

## Rollback

Revert the pull request. There is no migration to roll back and no hosted configuration to restore.
