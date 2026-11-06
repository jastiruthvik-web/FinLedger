export interface Session {
  user_id: string;
  firm_id: string;
  firm_admin: boolean;
  aal: string;
  mfa_required?: boolean;
  csrf_token: string;
}

export interface ClientRow {
  id: string;
  name: string;
  gstin?: string;
}

export interface QueueItem {
  document_id: string;
  invoice_no: string | null;
  filename: string | null;
  vendor_name: string | null;
  invoice_date?: string | null;
  total: string | number | null;
  band: string | null;
  score: number | string | null;
  state_label: string;
}

export interface QueueResponse {
  client: ClientRow;
  queue: string;
  counts: Record<string, number>;
  items: QueueItem[];
}

export interface Mark {
  field?: string;
  check?: string;
  ok?: boolean;
  note?: string;
}

export interface InvoiceDetail {
  document_id: string;
  filename: string | null;
  status: string;
  state_label: string;
  revision: number;
  source_url?: string;
  ai_paragraph?: string;
  invoice: {
    invoice_no?: string | null;
    invoice_date?: string | null;
    buyer_gstin?: string | null;
    po_number?: string | null;
    total?: string | number | null;
    vendor?: { name?: string | null; gstin?: string | null };
    confidences?: Record<string, number>;
  };
  risk?: { score?: number | string | null; band?: string | null; marks?: Mark[] };
  draft?: {
    party_ledger?: string | null;
    lines?: { ledger?: string | null; amount?: string | number | null; is_debit?: boolean | null; cost_centre?: string | null }[];
    gst?: { treatment?: string | null };
    tds?: { applicable?: boolean };
    bill_wise?: { ref?: string | null };
    reasons?: string[];
  };
  department?: DepartmentRoute;
  suggestions?: GlSuggestion[];
}

import type { PostingBlock, ThreeWayMatch } from "./threeWay";

export type { PostingBlock, ThreeWayMatch };

export interface GlSuggestion {
  line: number;
  ledger: string | null;
  confidence: string;
  scope: string;
  abstained: boolean;
  explanation: string;
}

export interface DepartmentRoute {
  status: string;
  revision: number;
  department_code: string | null;
  department_name: string | null;
  cost_centre: string | null;
  note: string;
  approvers: { user_id: string; email: string }[];
}

export interface InvoiceResponse {
  client: ClientRow;
  roles: string[];
  csrf_token: string;
  invoice: InvoiceDetail;
  match?: ThreeWayMatch;
  posting?: PostingBlock;
}

export interface CaptureChannel {
  connected?: boolean;
  mailbox_connected?: boolean;
  webhook?: string;
  mode?: string;
  address?: string;
  detail: string;
}

export interface CaptureStatus {
  upload_link: string;
  mail: CaptureChannel;
  email: CaptureChannel;
  vendor_portal: CaptureChannel;
}

export interface ImportResult {
  received: { document_id: string; filename: string; replayed?: boolean }[];
  rejected: { filename: string; reason: string }[];
  mailbox_connected: boolean;
  vendor_portal_connected: boolean;
}

export interface PurchasingView {
  sync: string;
  source_label: string;
  tolerance: { version: number; note?: string };
  purchase_orders: { po_number: string; vendor_name: string; quantity: string; amount: string; source: string }[];
  goods_receipts: { grn_number: string; po_number: string; document_kind: string; status: string; quantity_received: string; source: string }[];
  departments: { code: string; name: string; cost_centre: string; approver_ids: string[] }[];
}

export interface BankLine {
  date: string;
  narration: string;
  reference: string;
  debit: string | null;
  credit: string | null;
  status: "matched" | "unmatched";
  invoice_no: string | null;
  document_id: string | null;
}

export interface OpenBillMatch {
  document_id: string;
  invoice_no: string;
  amount: string | null;
  vendor_name: string;
  workflow_status: string;
  status: "matched" | "unmatched";
}

export interface ReconciliationResponse {
  client: ClientRow;
  lines: BankLine[];
  bills: OpenBillMatch[];
}

export interface PageContext {
  alive: () => boolean;
  go: (url: string) => void;
  rerender: () => void;
}
