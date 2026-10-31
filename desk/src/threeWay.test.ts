import assert from "node:assert/strict";
import test from "node:test";
import { approveChoice, matchHeadline, matchRows } from "./threeWay.ts";
import type { ThreeWayMatch } from "./types.ts";

function match(overrides: Partial<ThreeWayMatch> = {}): ThreeWayMatch {
  return {
    applicable: true,
    matched: true,
    holds_review: false,
    match_mode: "three_way",
    differences: [],
    review_note: "",
    purchase_order: { po_number: "PO-HG-1103", quantity: "10", amount: "5900.00" },
    goods_receipt: { grn_number: "GRN-HG-1103", quantity_received: "10" },
    invoice: { quantity: "10", amount: "5900.00" },
    ...overrides,
  };
}

test("the bill shows purchase-order quantity and amount, goods-receipt quantity, and the invoice", () => {
  const rows = matchRows(match());
  assert.deepEqual(rows.map((row) => [row.side, row.quantity, row.amount]), [
    ["Purchase order", "10", "₹5,900.00"],
    ["Goods receipt", "10", "—"],
    ["Invoice", "10", "₹5,900.00"],
  ]);
  assert.equal(rows[0].reference, "PO-HG-1103");
  assert.equal(rows[1].reference, "GRN-HG-1103");
  assert.equal(matchHeadline(match()), "Purchase order, goods receipt, and invoice agree.");
  assert.equal(approveChoice(match(), { blocked: true, reason: "Posting is blocked. Offline Tally XML refuses intra-GST drafts." }), "approve");
});

test("a mismatch stays needs review and names the side that differs", () => {
  const differed = match({
    matched: false,
    holds_review: true,
    differences: ["Goods receipt quantity differs."],
    review_note: "Needs review. Goods receipt quantity differs.",
    goods_receipt: { grn_number: "GRN-HG-1104", quantity_received: "8" },
  });
  assert.equal(matchHeadline(differed), "Needs review. Goods receipt quantity differs.");
  assert.equal(matchRows(differed)[1].quantity, "8");
  assert.equal(approveChoice(differed, { blocked: true, reason: "Posting is blocked. Offline Tally XML refuses intra-GST drafts." }), "hold");
});

test("an unlinked bill does not pretend the three sides were compared", () => {
  const open = match({
    applicable: false,
    matched: false,
    match_mode: "invoice_only",
    purchase_order: { po_number: null, quantity: null, amount: null },
    goods_receipt: { grn_number: null, quantity_received: null },
    invoice: { quantity: "1", amount: "11800.00" },
  });
  assert.equal(matchHeadline(open), "No purchase order or goods receipt is linked to this bill.");
  assert.equal(approveChoice(open, { blocked: false, reason: null }), "approve_and_post");
});
