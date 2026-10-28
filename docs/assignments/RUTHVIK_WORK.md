# Ruthvik — AI integration, controls and release QA

Updated 2026-10-27. This is Ruthvik's only active work file, combining his original release
assignment and the PR #39 review follow-ups. Own AI transport/accounting and runtime wiring,
durable adapter integration, controls/UI fixes, detailed Auth/workflow QA and release evidence.
[Harshith](HARSHITH_WORK.md) owns backend migration/consumer implementation and operations;
[Ryan](RYAN_WORK.md) retains approvals/private access and final acceptance. Do not duplicate work.

## Current

Base is `b8cf3a3`. That main already has migration `014`, the `score-worker` command, and
`default_extract(conn)` durable wiring (`PostgresKillSwitch` and `PostgresUsageWriter` on the
worker connection). `default_extract()` with no connection is still the in-memory path for
local tools. There is a score consumer.

`feat/local-journey-proof` behavior commit `e589018` proves upload → ingest → extract → score
→ human correction and approval on a throwaway cluster with the mock provider, including the
failure paths in section 4. It also adds the opt-in live Gemini switch. That switch was not turned on.
Live and hosted boxes in section 5 stay open. Counts are in [RELEASE_EVIDENCE.md](../RELEASE_EVIDENCE.md).

## Start here

Read root [HANDOVER](../../HANDOVER.md), the [deployment runbook](../DEPLOYMENT_RUNBOOK.md),
[Auth design](../plans/AUTH_SUPABASE_DESIGN.md), [schema proposal](../proposals/AI_DURABLE_RETRIEVAL_USAGE_SCHEMA.md)
and [provider proposal](../decisions/ADR-001-AI_PROVIDER.md). Use Python 3.12, uv and PostgreSQL tools.

```powershell
git switch main
git pull --ff-only
git switch -c feat/ruthvik-review-followups
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Reuse `packages/`, `evals/` and `person3_control_ui/`; coordinate shared interfaces with
Harshith. Preserve extraction schema validation, input minimization, bounded image handling,
safe diagnostics, retrieval tenant isolation and existing regression fixtures. Fix callers,
fixtures and tests together. If P2 dependencies change, update/check both P2/P3 lockfiles.
Never point test-owner configuration at hosted data.

## 1. Status and evidence

[PR #39](https://github.com/ryanshaon/FinLedger/pull/39) was **open** at reviewed head
`1eb9544477722e78e8e154e4c0466d0e6f73e13a`. Its
[CI run](https://github.com/ryanshaon/FinLedger/actions/runs/39767884426) passed test and image jobs:
**91 AI / 333 platform / 64 UI tests**, mock **3/3 structural + 6/6 exact**.
Those counts were read from CI logs, not rerun locally during review.

Delivered: injected-HTTP Gemini request/response handling and tests, object-key validation,
clearer queue/failure labels, safer form-validation output, review regressions and fake
invite/password/MFA/logout coverage. Keep those tests; do not repeat completed implementation.

**Verdict at that review: useful local milestone, not completion of the entire release assignment.**
At that review, no live provider, hosted Auth, deployment, or full extraction-to-review proof
was demonstrated. The local journey proof has since landed; live and hosted proof have not.
Your report correctly records most limits but assigns some engineering verification to Ryan.
Use the ownership below; Ryan retains only his short owner checklist.

## 2. Next local PR: accounting correctness before activation

These items do not need real credentials or paid calls. Fix them with fake-HTTP regressions.
Landed in [PR #6](https://github.com/jastiruthvik-web/FinLedger/pull/6) (`224f683` on main). This branch
does not reimplement them.

- [x] **Account for reasoning usage.** `HttpGeminiTransport._parse_response` reads only
  `promptTokenCount` and `candidatesTokenCount`; additional `thoughtsTokenCount` is ignored.
  A local probe supplying input=3, candidates=4, thoughts=1000 returned input=3/output=4.
  Verify current official semantics for the selected model; preserve all chargeable usage
  in reservation reconciliation and cost calculation without double-counting totals.
- [x] **Do not silently treat unknown usage as free output.** Missing/invalid usage metadata
  currently becomes zero/zero. A local probe with valid candidate text and no usage metadata
  returned zero/zero; the provider substitutes estimated input but still reports zero output.
  Choose a fail-closed/conservative settlement that preserves a hold or records unknown usage.
  Simply rejecting a response and releasing its reservation can also lose already-incurred usage.
  Cover absent, partial, negative, boolean and malformed counters.
- [x] **Replace zero-cost success accounting before live use.** `GeminiProvider.complete`
  always reports `cost_usd = 0.0`. Wire the approved model/location tariff into usage or
  explicitly mark cost unavailable and prevent budget enforcement from treating it as free.
  Use deterministic fixture rates in tests; do not invent a live price or spending approval.
- [x] **Bound output against the reservation.** Current reservation is estimated input + 256,
  but the HTTP request has no corresponding output-token generation limit. Test a response
  that exceeds that allowance, plus image-input and retry/ambiguous-response cases. Make
  output bounds and conservative accounting agree; do not claim token reservations prove
  a hard dollar cap or account for every failed provider attempt by themselves.

Acceptance: failing regressions first, then passing focused/full suites. Show a synthetic
reasoning response reconciles its full intended usage; missing metadata cannot erase a
paid call from the cap/audit; nonzero fixture usage yields correct nonzero fixture cost.
No staging/production guard is removed to satisfy these tests.

## 3. Complete the real HTTP boundary locally

Landed in [PR #6](https://github.com/jastiruthvik-web/FinLedger/pull/6). `GeminiHttpClient` stays unwired
unless the caller passes it. This branch does not construct it from `ModelRouter`.

- [x] Implement the concrete HTTP callable behind `HttpGeminiTransport` (or document the
  approved existing client being used). PR #39 requires an injected `http_post`; it does
  not itself supply a socket-opening client or runtime credential-refresh integration.
- [x] Enforce response-size limits while reading, not only after a complete byte buffer is
  returned. Test oversized streaming responses, timeouts, connection failures and safe errors.
- [x] Keep explicit approved project/model/location, request bounds, no automatic region/model
  fallback, bounded retry/backoff and credential-free logs. Test redirect behavior so credentials
  are not forwarded to another host; do not permit arbitrary URL overrides.
- [x] Ensure configuration validation rejects invalid/nonfinite timeouts and malformed bounds.
  Verify the selected live endpoint/model against current official documentation before activation.

Acceptance: local fake-server/client tests prove actual client behavior without contacting
Google or using real credentials. Passing injected-function tests alone is not network verification.

## 4. Integrate Harshith's work when ready

Harshith implements the numbered migration, queue consumer, statement/status handling,
restricted automation maker, runtime role, dependency proofs and approved deployment.
Do not author a competing migration/consumer.

- [x] Agree schema/function signatures and PR links with Harshith. Connect the existing durable
  adapters to the reviewed real worker path, not the test-only SQL overlay or in-memory defaults.
  `ModelRouter(..., kill_switch=...)` accepts `PostgresKillSwitch`. `complete()` reserves, calls the
  model, then inserts `llm_usage_rows` and calls `llm_reconcile_tokens` in one short `tenant()`
  transaction on that hold's id. On `b8cf3a3`, `default_extract(conn)` passes that connection into
  `PostgresKillSwitch` and `PostgresUsageWriter`. `default_extract()` with no connection stays in
  memory. Migration `014` on that same main stores an unpriced call with `cost_usd` null. An
  unpriced success is not inserted as `cost_usd = 0`.
- [x] Verify reservation/usage persistence after restart, concurrent workers and tenant isolation.
  Define recovery for a provider response followed by DB failure so a retry cannot hide usage.
  Proved on a throwaway cluster only. A failed settle leaves the hold `held`. A timeout with no
  body can stay `released`. No hosted SQL.
- [x] **Decide the expired-hold budget rule (migration 013, merged in
  [PR #47](https://github.com/ryanshaon/FinLedger/pull/47) at `0a40ac6`).** **Choice: option 3, accept
  the shipped rule.** Options 1 and 2 are not implemented. When a worker dies between
  `llm_reserve_tokens` and settlement, the next claim marks its hold `expired`. Expired holds stay in
  the table for audit and no longer count toward the bill's cap (`llm_reserve_tokens` still counts only
  `held`). With `jobs.max_attempts` defaulting to 5, five dead attempts that had already reached the
  provider can leave the cap: one bill can be charged about 5× its token cap before a later attempt is
  refused. That conflicts with §2, which says a call that reached the provider must not be erased from
  the cap. The shipped rule is accepted anyway. Migration `013` is already on main; editing it would
  split the blob operators apply (`6a0fdf8d5e0ce39a76000f87404bbace72763800`). Keeping or bounding
  expired holds would be a new migration by Harshith. This branch does not request one for this rule.
  The existing expiry tests remain the regression. A timeout with no body is a separate case and can
  stay uncounted: release runs only when the attempt received no body.
- [x] Integrate extraction into scoring/mapping/review and test replay, lease expiry,
  late results, schema failures, scanner outage, caps and retry exhaustion on synthetic data.
  The mock score payload passes `validate_invoice` (`extra="forbid"` kept; unknown vendor
  fields still fail). `score-worker` claims `score`, writes `scored` or `exception`, and is a
  CLI command on `b8cf3a3`. Mapping stays in the review service; there is no `map-worker`.
  `person3_control_ui/tests/test_local_journey.py` on `e589018` runs the local journey on a
  throwaway cluster: happy path upload → ingest → extract → score → human correction and
  approval; desk label `Queued for extraction` on `received`, then `Scored`; replay does not
  double-write; a lost lease does not settle a late result; a schema-invalid invoice becomes
  `canonical_invoice_rejected` and does not retry; scanner failure stays unscanned and can
  retry; `ai_budget_exceeded` is permanent; provider timeouts go `dead` after 5; a statement
  and an object key outside `{client_id}/` do not call the model. Mock provider only.
- [x] Independently verify automation-maker/human-editor separation with Harshith's implementation.
  Existing clerk self-approval denial is useful, but not proof of the new automation-maker semantics.
  `approve` now also refuses the human on `voucher_drafts.created_by` or `correction_events.actor_id`.
  `maker_id` stays the automation user. A different human approver can approve. No migration.

If the dependency is not ready, mark it **blocked on Harshith PR <link>**, not complete and
not reassigned to Ryan. Local provider/accounting and UI tests can continue independently.

## 5. Approved staging and final evidence

Owner approvals/private access remain prerequisites, not engineering tasks Ryan must implement.
Do not make paid calls, real invites, email sends or hosted changes from this checklist alone.

- [ ] After explicit provider/model/location/retention/budget approval and account setup,
  wire the reviewed runtime transport and run opt-in synthetic live extraction. Preserve
  fail-closed startup until the approved path exists; no silent mock fallback.
  The switch is present and off. `FINLEDGER_GEMINI_LIVE=1` plus an explicit provider, model,
  location, project, and credential builds `GeminiHttpClient`. `ModelRouter` still refuses
  `mock` in `staging` and `production`, and refuses `gemini` there unless that process was
  given an `HttpGeminiTransport` whose client is `GeminiHttpClient`. No region or model
  fallback. `evals/run_evals.py --live-synthetic-eval` stays opt-in and was not run. CI stays
  mock-only. Do not commit the key.
- [ ] Once Harshith supplies the approved staging runtime, run real synthetic-staff
  invite → password → login → TOTP → client list → logout. Verify AAL1 denial, stale/revoked
  cookies, idle/absolute expiry and cross-tenant denial. Fake Auth is not the hosted proof.
- [x] Lead full synthetic upload → scan → extract → score/map → human correction/review;
  verify truthful queued/failed/budget/statement labels and negative/failure/recovery paths.
  Done locally on `e589018` (`test_local_journey.py`). This is not the hosted proof.
- [x] Update `docs/RELEASE_EVIDENCE.md` in your PR: exact commit, environment, commands,
  pass/fail/skip counts, cleanup, actual hosted changes and blockers with named owners.
  Harshith owns implementation/deployment; you own integration/QA and its evidence.
  Local evidence for `e589018` is in that file. Hosted results are not in it.
- [x] Remove stale assignments of maker/checker review, real Auth testing and engineering
  proof work to Ryan. Ryan supplies approvals/private access and final independent acceptance.
  Already done on main by `d519e48`. This branch does not put that work back on `RYAN_WORK.md`.
- [ ] Request independent review and green CI on the exact final head before merge.
  Label unverified work blocked/not run; do not claim customer readiness from local CI.

Read HANDOVER before work; no secrets or invoice payloads in Git/logs/chat, no uncommitted
work on handoff, no editing applied migrations, no RLS/MFA/scanner bypass and no Person 4 edits.
No changes to live services were made by this review.
