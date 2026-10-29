export type BillStatus = "New" | "Needs review" | "Approved" | "Exception" | "Posted";
export type MatchStatus = "Matched" | "Unmatched" | "Suggested";

export interface FirmClient {
  id: string;
  name: string;
  gstin: string;
  city: string;
}

export interface Bill {
  id: string;
  clientId: string;
  invoice: string;
  vendor: string;
  date: string;
  amount: number;
  status: BillStatus;
}

export interface LedgerLine {
  id: string;
  date: string;
  clientId: string;
  narration: string;
  reference: string;
  debit: number | null;
  credit: number | null;
  status: MatchStatus;
}

export const firmClients: FirmClient[] = [
  { id: "11111111-1111-1111-1111-111111111111", name: "Acme Steel", gstin: "27AAPFU0939F1ZV", city: "Mumbai" },
  { id: "22222222-2222-2222-2222-222222222222", name: "Bharat Textiles", gstin: "24AABCU9603R1ZM", city: "Surat" },
  { id: "33333333-3333-3333-3333-333333333333", name: "Mehta Pharma", gstin: "27AADCM1234F1Z5", city: "Pune" },
  { id: "44444444-4444-4444-4444-444444444444", name: "Coastal Cements", gstin: "32AABCC1111A1Z2", city: "Kochi" },
  { id: "55555555-5555-5555-5555-555555555555", name: "Northspan Logistics", gstin: "07AABCN2222B1Z8", city: "Delhi" },
];

export const bills: Bill[] = [
  { id: "b1", clientId: firmClients[0].id, invoice: "INV-42", vendor: "Shree Ganesh Metals", date: "2026-10-05", amount: 11800, status: "Needs review" },
  { id: "b2", clientId: firmClients[0].id, invoice: "INV-38", vendor: "Tata Steel", date: "2026-10-12", amount: 245000, status: "Approved" },
  { id: "b3", clientId: firmClients[0].id, invoice: "INV-19", vendor: "JSW Steel", date: "2026-09-28", amount: 86000, status: "Posted" },
  { id: "b4", clientId: firmClients[0].id, invoice: "INV-44", vendor: "Bharat Electricals", date: "2026-10-21", amount: 6400, status: "Exception" },
  { id: "b5", clientId: firmClients[1].id, invoice: "BT-2201", vendor: "Raymond Mills", date: "2026-10-08", amount: 54000, status: "Needs review" },
  { id: "b6", clientId: firmClients[1].id, invoice: "BT-2188", vendor: "Grasim Industries", date: "2026-10-02", amount: 31250, status: "Posted" },
  { id: "b7", clientId: firmClients[1].id, invoice: "BT-2210", vendor: "Surat Dyes", date: "2026-10-18", amount: 9750, status: "New" },
  { id: "b8", clientId: firmClients[2].id, invoice: "MP-901", vendor: "Sun Pharma", date: "2026-10-11", amount: 128400, status: "Needs review" },
  { id: "b9", clientId: firmClients[2].id, invoice: "MP-888", vendor: "Cipla", date: "2026-09-15", amount: 76000, status: "Posted" },
  { id: "b10", clientId: firmClients[2].id, invoice: "MP-910", vendor: "Pune Packaging", date: "2026-10-22", amount: 15400, status: "Exception" },
  { id: "b11", clientId: firmClients[3].id, invoice: "CC-77", vendor: "UltraTech Cement", date: "2026-10-09", amount: 410000, status: "Approved" },
  { id: "b12", clientId: firmClients[3].id, invoice: "CC-70", vendor: "Kochi Freight", date: "2026-10-16", amount: 22800, status: "New" },
  { id: "b13", clientId: firmClients[3].id, invoice: "CC-65", vendor: "Malabar Quarry", date: "2026-09-30", amount: 96000, status: "Posted" },
  { id: "b14", clientId: firmClients[4].id, invoice: "NS-14", vendor: "HPCL", date: "2026-10-19", amount: 48200, status: "Needs review" },
  { id: "b15", clientId: firmClients[4].id, invoice: "NS-11", vendor: "Delhi Tyres", date: "2026-10-07", amount: 12650, status: "Posted" },
  { id: "b16", clientId: firmClients[4].id, invoice: "NS-15", vendor: "Workshop 14", date: "2026-10-25", amount: 8900, status: "Exception" },
];

export const ledger: LedgerLine[] = [
  { id: "l1", date: "2026-10-05", clientId: firmClients[0].id, narration: "Purchase — Shree Ganesh Metals", reference: "INV-42", debit: 11800, credit: null, status: "Suggested" },
  { id: "l2", date: "2026-10-06", clientId: firmClients[0].id, narration: "Payment — Shree Ganesh Metals", reference: "NEFT-8841", debit: null, credit: 11800, status: "Unmatched" },
  { id: "l3", date: "2026-10-12", clientId: firmClients[0].id, narration: "Purchase — Tata Steel", reference: "INV-38", debit: 245000, credit: null, status: "Matched" },
  { id: "l4", date: "2026-10-13", clientId: firmClients[0].id, narration: "Bank — Tata Steel", reference: "RTGS-1902", debit: null, credit: 245000, status: "Matched" },
  { id: "l5", date: "2026-09-28", clientId: firmClients[0].id, narration: "Purchase — JSW Steel", reference: "INV-19", debit: 86000, credit: null, status: "Matched" },
  { id: "l6", date: "2026-10-21", clientId: firmClients[0].id, narration: "Purchase — Bharat Electricals", reference: "INV-44", debit: 6400, credit: null, status: "Unmatched" },
  { id: "l7", date: "2026-10-08", clientId: firmClients[1].id, narration: "Purchase — Raymond Mills", reference: "BT-2201", debit: 54000, credit: null, status: "Suggested" },
  { id: "l8", date: "2026-10-09", clientId: firmClients[1].id, narration: "Payment — Raymond Mills", reference: "NEFT-2201", debit: null, credit: 50000, status: "Unmatched" },
  { id: "l9", date: "2026-10-02", clientId: firmClients[1].id, narration: "Purchase — Grasim", reference: "BT-2188", debit: 31250, credit: null, status: "Matched" },
  { id: "l10", date: "2026-10-03", clientId: firmClients[1].id, narration: "Bank — Grasim", reference: "NEFT-2188", debit: null, credit: 31250, status: "Matched" },
  { id: "l11", date: "2026-10-18", clientId: firmClients[1].id, narration: "Purchase — Surat Dyes", reference: "BT-2210", debit: 9750, credit: null, status: "Unmatched" },
  { id: "l12", date: "2026-10-11", clientId: firmClients[2].id, narration: "Purchase — Sun Pharma", reference: "MP-901", debit: 128400, credit: null, status: "Suggested" },
  { id: "l13", date: "2026-10-14", clientId: firmClients[2].id, narration: "Payment — Sun Pharma", reference: "RTGS-901", debit: null, credit: 128400, status: "Suggested" },
  { id: "l14", date: "2026-09-15", clientId: firmClients[2].id, narration: "Purchase — Cipla", reference: "MP-888", debit: 76000, credit: null, status: "Matched" },
  { id: "l15", date: "2026-09-18", clientId: firmClients[2].id, narration: "Bank — Cipla", reference: "NEFT-888", debit: null, credit: 76000, status: "Matched" },
  { id: "l16", date: "2026-10-22", clientId: firmClients[2].id, narration: "Purchase — Pune Packaging", reference: "MP-910", debit: 15400, credit: null, status: "Unmatched" },
  { id: "l17", date: "2026-10-09", clientId: firmClients[3].id, narration: "Purchase — UltraTech", reference: "CC-77", debit: 410000, credit: null, status: "Matched" },
  { id: "l18", date: "2026-10-10", clientId: firmClients[3].id, narration: "Bank — UltraTech", reference: "RTGS-77", debit: null, credit: 410000, status: "Matched" },
  { id: "l19", date: "2026-10-16", clientId: firmClients[3].id, narration: "Freight — Kochi", reference: "CC-70", debit: 22800, credit: null, status: "Unmatched" },
  { id: "l20", date: "2026-09-30", clientId: firmClients[3].id, narration: "Purchase — Malabar Quarry", reference: "CC-65", debit: 96000, credit: null, status: "Matched" },
  { id: "l21", date: "2026-10-01", clientId: firmClients[3].id, narration: "Bank — Malabar Quarry", reference: "NEFT-65", debit: null, credit: 96000, status: "Matched" },
  { id: "l22", date: "2026-10-19", clientId: firmClients[4].id, narration: "Fuel — HPCL", reference: "NS-14", debit: 48200, credit: null, status: "Suggested" },
  { id: "l23", date: "2026-10-20", clientId: firmClients[4].id, narration: "Payment — HPCL", reference: "NEFT-14", debit: null, credit: 48200, status: "Suggested" },
  { id: "l24", date: "2026-10-07", clientId: firmClients[4].id, narration: "Purchase — Delhi Tyres", reference: "NS-11", debit: 12650, credit: null, status: "Matched" },
  { id: "l25", date: "2026-10-08", clientId: firmClients[4].id, narration: "Bank — Delhi Tyres", reference: "NEFT-11", debit: null, credit: 12650, status: "Matched" },
  { id: "l26", date: "2026-10-25", clientId: firmClients[4].id, narration: "Workshop 14", reference: "NS-15", debit: 8900, credit: null, status: "Unmatched" },
];

export function clientById(id: string) {
  return firmClients.find((client) => client.id === id);
}

export function billsFor(clientId: string) {
  return bills.filter((bill) => bill.clientId === clientId);
}

export function clientName(id: string) {
  return clientById(id)?.name ?? "Unknown client";
}

const day = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });

export function formatDay(iso: string) {
  const [year, month, date] = iso.split("-").map(Number);
  return day.format(new Date(year, month - 1, date));
}
