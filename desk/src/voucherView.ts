export interface VoucherLineInput {
  ledger?: string | null;
  amount?: string | number | null;
  is_debit?: boolean | null;
}

export interface VoucherRow {
  ledger: string;
  side: "Debit" | "Credit";
  amount: string | number | null | undefined;
}

export function partyLedgerName(draft: { party_ledger?: string | null } | null | undefined): string {
  return draft?.party_ledger?.trim() || "";
}

export function voucherRows(lines: VoucherLineInput[] | null | undefined): VoucherRow[] {
  return (lines || []).map((line) => ({
    ledger: line.ledger?.trim() || "Unmapped",
    side: line.is_debit === false ? "Credit" : "Debit",
    amount: line.amount,
  }));
}
