export interface MatchLine {
  invoice_line_no: number;
  po_line_no: number;
  method: string;
  invoice_qty: string | null;
  po_qty: string | null;
  received_qty: string | null;
  already_invoiced_qty: string | null;
  available_qty: string | null;
  uom: string | null;
  currency: string | null;
  notes: string[];
  problems: string[];
}

export interface ThreeWayMatch {
  applicable: boolean;
  matched: boolean;
  holds_review: boolean;
  match_mode: string;
  differences: string[];
  review_note: string;
  purchase_order: { po_number: string | null; quantity: string | null; amount: string | null };
  goods_receipt: { grn_number: string | null; quantity_received: string | null };
  invoice: { quantity: string | null; amount: string | null };
  basis?: string;
  path?: string;
  partial?: boolean;
  source_label?: string;
  blocked?: string[];
  overridable?: string[];
  admin_overridable?: string[];
  lines?: MatchLine[];
  ignored_receipts?: { grn_number?: string; status?: string; document_kind?: string }[];
}

export interface PostingBlock {
  blocked: boolean;
  reason: string | null;
}

export interface MatchRow {
  side: string;
  reference: string;
  quantity: string;
  amount: string;
}

export type ApproveChoice = "hold" | "override" | "approve" | "approve_and_post";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function shown(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function rupees(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return money.format(amount);
}

export function matchRows(match: ThreeWayMatch): MatchRow[] {
  return [
    {
      side: "Purchase order",
      reference: match.purchase_order.po_number || "",
      quantity: shown(match.purchase_order.quantity),
      amount: rupees(match.purchase_order.amount),
    },
    {
      side: "Goods receipt",
      reference: match.goods_receipt.grn_number || "",
      quantity: shown(match.goods_receipt.quantity_received),
      amount: "—",
    },
    {
      side: "Invoice",
      reference: "",
      quantity: shown(match.invoice.quantity),
      amount: rupees(match.invoice.amount),
    },
  ];
}

export function matchHeadline(match: ThreeWayMatch): string {
  if (match.path === "non_po") return "Non-PO bill. Review continues without a purchase order.";
  if (!match.applicable) return "No purchase order or goods receipt is linked to this bill.";
  if (match.matched && match.partial) return "The invoice is within the open receipt. Quantity still on the order stays open.";
  if (match.matched) return "Purchase order, goods receipt, and invoice agree.";
  const detail = match.differences.join(" ");
  if (!match.holds_review) return detail || "The purchase order, goods receipt, and invoice do not agree.";
  return detail ? `Needs review. ${detail}` : "Needs review.";
}

export function approveChoice(match: ThreeWayMatch | undefined, posting: PostingBlock | undefined): ApproveChoice {
  if (match?.blocked && match.blocked.length > 0) return "hold";
  if (match?.holds_review && ((match.overridable?.length || 0) > 0 || (match.admin_overridable?.length || 0) > 0)) return "override";
  if (match?.holds_review) return "hold";
  if (posting?.blocked) return "approve";
  return "approve_and_post";
}
