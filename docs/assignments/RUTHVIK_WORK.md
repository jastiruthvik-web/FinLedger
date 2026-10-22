# Ruthvik — AI integration, controls and release QA

Updated 2026-10-22. This is Ruthvik's only active work file, combining his original release
assignment and the PR #39 review follow-ups. Own AI transport/accounting and runtime wiring,
durable adapter integration, controls/UI fixes, detailed Auth/workflow QA and release evidence.
[Harshith](HARSHITH_WORK.md) owns backend migration/consumer implementation and operations;
[Ryan](RYAN_WORK.md) retains approvals/private access and final acceptance. Do not duplicate work.

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

**Verdict: useful local milestone, not completion of the entire release assignment.**
No live provider, hosted Auth, deployment or full extraction-to-review proof was demonstrated.
Your report correctly records most limits but assigns some engineering verification to Ryan.
Use the ownership below; Ryan retains only his short owner checklist.

## 2. Next local PR: accounting correctness before activation

These items do not need real credentials or paid calls. Fix them with fake-HTTP regressions.

- [ ] **Account for reasoning usage.** `HttpGeminiTransport._parse_response` reads only
  `promptTokenCount` and `candidatesTokenCount`; additional `thoughtsTokenCount` is ignored.
  A local probe supplying input=3, candidates=4, thoughts=1000 returned input=3/output=4.
  Verify current official semantics for the selected model; preserve all chargeable usage
  in reservation reconciliation and cost calculation without double-counting totals.
- [ ] **Do not silently treat unknown usage as free output.** Missing/invalid usage metadata
  currently becomes zero/zero. A local probe with valid candidate text and no usage metadata
  returned zero/zero; the provider substitutes estimated input but still reports zero output.
  Choose a fail-closed/conservative settlement that preserves a hold or records unknown usage.
  Simply rejecting a response and releasing its reservation can also lose already-incurred usage.
  Cover absent, partial, negative, boolean and malformed counters.
- [ ] **Replace zero-cost success accounting before live use.** `GeminiProvider.complete`
  always reports `cost_usd = 0.0`. Wire the approved model/location tariff into usage or
  explicitly mark cost unavailable and prevent budget enforcement from treating it as free.
  Use deterministic fixture rates in tests; do not invent a live price or spending approval.
- [ ] **Bound output against the reservation.** Current reservation is estimated input + 256,
  but the HTTP request has no corresponding output-token generation limit. Test a response
  that exceeds that allowance, plus image-input and retry/ambiguous-response cases. Make
  output bounds and conservative accounting agree; do not claim token reservations prove
  a hard dollar cap or account for every failed provider attempt by themselves.

Acceptance: failing regressions first, then passing focused/full suites. Show a synthetic
reasoning response reconciles its full intended usage; missing metadata cannot erase a
paid call from the cap/audit; nonzero fixture usage yields correct nonzero fixture cost.
No staging/production guard is removed to satisfy these tests.

## 3. Complete the real HTTP boundary locally

- [ ] Implement the concrete HTTP callable behind `HttpGeminiTransport` (or document the
  approved existing client being used). PR #39 requires an injected `http_post`; it does
  not itself supply a socket-opening client or runtime credential-refresh integration.
- [ ] Enforce response-size limits while reading, not only after a complete byte buffer is
  returned. Test oversized streaming responses, timeouts, connection failures and safe errors.
- [ ] Keep explicit approved project/model/location, request bounds, no automatic region/model
  fallback, bounded retry/backoff and credential-free logs. Test redirect behavior so credentials
  are not forwarded to another host; do not permit arbitrary URL overrides.
- [ ] Ensure configuration validation rejects invalid/nonfinite timeouts and malformed bounds.
  Verify the selected live endpoint/model against current official documentation before activation.

Acceptance: local fake-server/client tests prove actual client behavior without contacting
Google or using real credentials. Passing injected-function tests alone is not network verification.

## 4. Integrate Harshith's work when ready

Harshith implements the numbered migration, queue consumer, statement/status handling,
restricted automation maker, runtime role, dependency proofs and approved deployment.
Do not author a competing migration/consumer.

- [ ] Agree schema/function signatures and PR links with Harshith. Connect the existing durable
  adapters to the reviewed real worker path, not the test-only SQL overlay or in-memory defaults.
- [ ] Verify reservation/usage persistence after restart, concurrent workers and tenant isolation.
  Define recovery for a provider response followed by DB failure so a retry cannot hide usage.
- [ ] Integrate extraction into scoring/mapping/review and test replay, lease expiry,
  late results, schema failures, scanner outage, caps and retry exhaustion on synthetic data.
- [ ] Independently verify automation-maker/human-editor separation with Harshith's implementation.
  Existing clerk self-approval denial is useful, but not proof of the new automation-maker semantics.

If the dependency is not ready, mark it **blocked on Harshith PR <link>**, not complete and
not reassigned to Ryan. Local provider/accounting and UI tests can continue independently.

## 5. Approved staging and final evidence

Owner approvals/private access remain prerequisites, not engineering tasks Ryan must implement.
Do not make paid calls, real invites, email sends or hosted changes from this checklist alone.

- [ ] After explicit provider/model/location/retention/budget approval and account setup,
  wire the reviewed runtime transport and run opt-in synthetic live extraction. Preserve
  fail-closed startup until the approved path exists; no silent mock fallback.
- [ ] Once Harshith supplies the approved staging runtime, run real synthetic-staff
  invite → password → login → TOTP → client list → logout. Verify AAL1 denial, stale/revoked
  cookies, idle/absolute expiry and cross-tenant denial. Fake Auth is not the hosted proof.
- [ ] Lead full synthetic upload → scan → extract → score/map → human correction/review;
  verify truthful queued/failed/budget/statement labels and negative/failure/recovery paths.
- [ ] Update `docs/RELEASE_EVIDENCE.md` in your PR: exact commit, environment, commands,
  pass/fail/skip counts, cleanup, actual hosted changes and blockers with named owners.
  Harshith owns implementation/deployment; you own integration/QA and its evidence.
- [ ] Remove stale assignments of maker/checker review, real Auth testing and engineering
  proof work to Ryan. Ryan supplies approvals/private access and final independent acceptance.
- [ ] Request independent review and green CI on the exact final head before merge.
  Label unverified work blocked/not run; do not claim customer readiness from local CI.

Read HANDOVER before work; no secrets or invoice payloads in Git/logs/chat, no uncommitted
work on handoff, no editing applied migrations, no RLS/MFA/scanner bypass and no Person 4 edits.
No changes to live services were made by this review.
