# Invoice capture, three-way match, and department coding

This is an addition to the India accounts-payable desk. It does not replace extraction, GST checks, or the Tally connector, and it does not post to a live ERP.

Migration `016_ap_capture_match_coding.sql` is applied by the existing owner command `finledger-platform migrate`. It was not applied to Supabase or any hosted database in this change. Do not re-apply migrations `001`–`015`.

## What is working

| Capability | State | Where |
|---|---|---|
| Original file kept, SHA-256, company ownership | Working. Upload, email, and staff import all use the same intake path. | `person2_platform/src/finledger_platform/intake.py` |
| Scanned paper mail and a file downloaded from a portal | Working as an authenticated import. The screen says mail is a scan and the portal is not connected. | `POST /clients/{id}/imports` and the desk Capture page |
| Public vendor link | Already present. PDF, JPEG, PNG, XLSX, ZIP. Type is taken from the bytes. | `POST /i/{token}` |
| Inbound email | Code path present. A signed webhook can deliver MIME. No mailbox is opened or created. If the webhook secret is still a placeholder, the Capture page says configuration required. | `POST /inbound/email`, `email_in.py` |
| Vendor portal login | Not connected. There is no connector and this change does not add one. | Capture page |
| Line-level PO and goods receipt, manual or file-shaped JSON | Working. Labeled manual or file import, not a live purchasing sync. | `purchase_documents.py`, desk Purchasing page |
| Delivery note | Stored as `pending_review` until an approver accepts it. It is not treated as received goods before that. | `goods_receipts.status` |
| Duplicate receipt | A second accepted receipt with the same order, item, quantity, and unit is stored as `duplicate` and is not counted until someone accepts it. | `save_receipt` |
| Partial receipts, partial invoices, already invoiced quantity | Working. Accepted receipt lines are summed. Open quantity is received minus allocations. | `line_match.py` |
| Two bills cannot take the same received quantity | Working inside one database transaction, with a row lock and a constraint trigger. | `receipt_allocations` |
| Credit note | Working against quantity already invoiced. A credit larger than that is refused. | `line_match.py` |
| Tolerances | Version 0 is built in: exact quantity, 0.01 price, 0.01 amount, exact tax rate. A firm admin can save a later version. Old versions stay. | `match_tolerances` |
| Unknown unit, currency, tax, or price | Not a match. A person can record a reason. Quantity over the receipt, a supplier GSTIN clash, and a currency clash cannot be overridden. | `line_match.py`, `ControlService._guard_match` |
| Non-PO bill | Still reviewed. The desk does not invent a purchase order. | `ControlService._open_match` |
| Header-only order and receipt from the earlier screen | Still compared by the old header totals. Those rows do not reserve quantities. The screen says so. | `three_way.py` |
| Department routing | Working. Sign-off is separate from accounts approval. No mapped approver is flagged `no_approver`. A firm admin can record a fallback, which does not approve the voucher. | `bill_routes` |
| Maker-checker | An editor of the bill cannot approve it and cannot give department sign-off. An edit after approval cancels that approval and releases reserved quantity. | `workflow.py`, `service.py` |
| Expense ledger suggestion | Read from this company's saved expense corrections. A party-ledger correction is not used as an expense. Conflicting history abstains. Nothing is written until a person saves the line. | `gl_suggest.py` |
| Tally posting | Unchanged. GST drafts stay blocked in offline XML. This change does not post. | `three_way.posting_view` |

## What is still gated

- A real inbox needs a provider account, a webhook secret that is not a placeholder, and the provider's signature. This repository does not create that inbox.
- A vendor portal download has to be done by a person and then imported. There is no portal password and no scraper.
- Purchase orders are not pulled from Tally or another ERP.
- Suggestions do not call Qwen, Gemini, or any other paid model. Extraction is unchanged and is not rewritten by retrieval.
- Hosted Supabase still needs the owner to apply migration 016 when they choose to. This change did not apply it.

## Local checks

Synthetic data only. The tests start a throwaway Postgres cluster. No production database is used.

```bash
export PATH="/usr/lib/postgresql/16/bin:$PATH"
uv sync --project person2_platform --python 3.12 --locked --all-extras --dev
uv sync --project person3_control_ui --python 3.12 --locked --dev
PYTHONPATH=person2_platform/src person2_platform/.venv/bin/python -m pytest person2_platform/tests -q
PYTHONPATH=person2_platform/src:person3_control_ui/src person3_control_ui/.venv/bin/python -m pytest person3_control_ui/tests -q
PYTHONPATH=evals person2_platform/.venv/bin/python -m pytest packages evals -q
PYTHONPATH=evals person2_platform/.venv/bin/python evals/run_evals.py --provider-mode mock
node --experimental-strip-types --test desk/src/threeWay.test.ts desk/src/voucherView.test.ts
npx --prefix desk tsc --noEmit -p desk/tsconfig.json
```

`run_evals.py` uses the mock provider. It does not call OpenRouter or any paid model.

The desk is built with `npm --prefix desk run build`. The control server serves `desk/dist`.

## Manual pass

1. Sign in on the desk and open a company.
2. Open Capture. Email and the vendor portal should say they are not connected. Import a PDF or a photo as scanned mail or as a portal download. Importing the same message and file again should keep the original document.
3. Open Purchasing. Enter a purchase order and a goods receipt. A delivery note should stay pending until an approver accepts it.
4. Open the bill. Line quantities, the open receipt quantity, and any ignored receipt should be visible. Save an expense ledger separately from the party ledger. Route a department. Department sign-off should leave the bill in review until an accounts approver who did not edit it approves.

## Rollout and rollback

Rollout is the usual migrate-then-deploy order. Migration 016 only adds tables, columns, and the `mail_scan` channel. It does not change existing document bytes.

Rollback before the migration is applied is dropping the release. After it is applied, the new tables can be dropped and the channel check restored only if no `mail_scan` row exists. Do not delete `documents` rows to roll this back. Approvals and corrections already stored remain in their existing tables.
