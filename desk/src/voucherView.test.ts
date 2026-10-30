import assert from "node:assert/strict";
import test from "node:test";
import { partyLedgerName, voucherRows } from "./voucherView.ts";

test("the bill page keeps the party ledger and voucher lines mapping produced", () => {
  assert.equal(partyLedgerName({ party_ledger: " Shree Ganesh Metals " }), "Shree Ganesh Metals");
  assert.equal(partyLedgerName({}), "");
  const rows = voucherRows([
    { ledger: "Purchases - Steel", amount: "5000.0", is_debit: true },
    { ledger: "Input CGST", amount: "450.0", is_debit: true },
    { ledger: "", amount: "10", is_debit: false },
  ]);
  assert.deepEqual(rows, [
    { ledger: "Purchases - Steel", side: "Debit", amount: "5000.0" },
    { ledger: "Input CGST", side: "Debit", amount: "450.0" },
    { ledger: "Unmapped", side: "Credit", amount: "10" },
  ]);
});
