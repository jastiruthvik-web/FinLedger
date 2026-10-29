export interface Session {
  user_id: string;
  firm_id: string;
  firm_admin: boolean;
  aal: string;
  csrf_token: string;
}

export interface ClientRow {
  id: string;
  name: string;
}

export interface QueueItem {
  document_id: string;
  invoice_no: string | null;
  filename: string | null;
  vendor_name: string | null;
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
    lines?: { ledger?: string | null; amount?: string | number | null }[];
    gst?: { treatment?: string | null };
    tds?: { applicable?: boolean };
    bill_wise?: { ref?: string | null };
    reasons?: string[];
  };
}

export interface InvoiceResponse {
  client: ClientRow;
  roles: string[];
  csrf_token: string;
  invoice: InvoiceDetail;
}

export interface PageContext {
  alive: () => boolean;
  go: (url: string) => void;
  rerender: () => void;
}
