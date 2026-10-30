import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { bandText, rupees, safeSource, shown } from "@/format";
import { PageHeader } from "@/pages/Placeholder";
import { queueHref } from "@/router";
import type { InvoiceResponse } from "@/types";
import { partyLedgerName, voucherRows } from "@/voucherView";

const CLOSED = new Set(["scheduled", "paid", "posted", "reconciled", "closed"]);

export function InvoicePage({
  clientId,
  documentId,
  onNavigate,
}: {
  clientId: string;
  documentId: string;
  onNavigate: (url: string) => void;
}) {
  const [page, setPage] = useState<InvoiceResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ledger, setLedger] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    setPage(null);
    setError("");
    setNotice("");
    api.invoice(clientId, documentId)
      .then((next) => {
        if (!live) return;
        setPage(next);
        setLedger(next.invoice.draft?.party_ledger || "");
      })
      .catch((reason: unknown) => {
        if (live) setError(errorMessage(reason, "This bill is not ready for review yet."));
      });
    return () => { live = false; };
  }, [clientId, documentId]);

  async function reload() {
    const next = await api.invoice(clientId, documentId);
    setPage(next);
    setLedger(next.invoice.draft?.party_ledger || "");
  }

  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await reload();
      setNotice(done);
    } catch (reason) {
      setError(errorMessage(reason, "The desk could not save that."));
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    if (!page) return;
    void run(
      () => api.saveChange(clientId, documentId, page.invoice.revision, ledger),
      "Party ledger saved.",
    );
  }

  if (error && !page) {
    return (
      <div className="space-y-4">
        <PageHeader title="Invoice" description="Review stays on this desk." />
        <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
          <p role="alert" className="text-sm">{error}</p>
          <Button variant="outline" className="mt-4" onClick={() => onNavigate(queueHref(clientId, "needs_review"))}>Back to the queue</Button>
        </div>
      </div>
    );
  }

  if (!page) {
    return (
      <div className="space-y-4">
        <PageHeader title="Invoice" description="Opening the bill." />
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      </div>
    );
  }

  const detail = page.invoice;
  const invoice = detail.invoice || {};
  const vendor = invoice.vendor || {};
  const draft = detail.draft || {};
  const risk = detail.risk || {};
  const conf = invoice.confidences || {};
  const source = safeSource(detail.source_url);
  const partyLedger = partyLedgerName(draft);
  const rows = voucherRows(draft.lines);
  const editable = !CLOSED.has(detail.status);
  const canApprove = page.roles.includes("approver") || page.roles.includes("firm_admin");
  const back = queueHref(clientId, "needs_review");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <PageHeader
          title={detail.filename || invoice.invoice_no || "Invoice"}
          description={`${page.client.name} · Revision ${detail.revision} · ${detail.state_label}`}
        />
        <Button variant="outline" onClick={() => onNavigate(back)}>Back to the queue</Button>
      </div>
      {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-md border border-border bg-card px-3 py-2 text-sm">{notice}</p> : null}
      <div className="grid gap-3 xl:grid-cols-3">
        <section className="rounded-xl border border-border bg-card" aria-label="Source document">
          <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">Source document</h2>
          {source ? (
            <iframe title="Source document" src={source} className="h-80 w-full rounded-b-xl bg-background" />
          ) : (
            <p className="px-4 py-8 text-sm text-muted-foreground">Source preview is unavailable. The extracted fields are on this page.</p>
          )}
        </section>
        <section className="rounded-xl border border-border bg-card" aria-label="Extracted fields">
          <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">Extracted fields</h2>
          <dl className="divide-y divide-border px-4">
            <Field label="Vendor" value={shown(vendor.name)} />
            <Field label="GSTIN" value={shown(vendor.gstin)} extra={percent(conf.gstin)} />
            <Field label="Invoice number" value={shown(invoice.invoice_no)} extra={percent(conf.invoice_no)} />
            <Field label="Invoice date" value={shown(invoice.invoice_date)} extra={percent(conf.date)} />
            <Field label="Buyer GSTIN" value={shown(invoice.buyer_gstin)} />
            <Field label="PO number" value={shown(invoice.po_number)} />
            <Field label="Grand total" value={rupees(invoice.total)} extra={percent(conf.total)} />
          </dl>
        </section>
        <section className="rounded-xl border border-border bg-card" aria-label="Proposed voucher">
          <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">Proposed voucher</h2>
          <div className="space-y-4 p-4">
            <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
              <span className="block text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">Risk gate</span>
              <span className="font-medium">{bandText(risk.band, risk.score)}</span>
            </p>
            {(risk.marks || []).filter((mark) => mark.ok === false).map((mark, index) => (
              <p key={`${mark.check}-${index}`} className="text-sm text-muted-foreground">
                {mark.check || "control"}: {mark.note || ""}
              </p>
            ))}
            <div className="space-y-3">
              <div>
                <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">Party ledger</h3>
                <p className="mt-1 text-sm font-medium">{shown(partyLedger)}</p>
              </div>
              <table className="w-full border-collapse text-sm" aria-label="Voucher lines">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    <th className="py-1.5 font-medium">Ledger</th>
                    <th className="py-1.5 font-medium">Side</th>
                    <th className="py-1.5 text-right font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-2 text-muted-foreground">No voucher lines</td>
                    </tr>
                  ) : rows.map((row, index) => (
                    <tr key={`${row.ledger}-${index}`} className="border-b border-border last:border-0">
                      <td className="py-1.5">{row.ledger}</td>
                      <td className="py-1.5">{row.side}</td>
                      <td className="py-1.5 text-right">{rupees(row.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="divide-y divide-border">
              <Field label="GST treatment" value={shown(draft.gst?.treatment)} />
              <Field label="TDS" value={draft.tds?.applicable ? "Applicable" : "Not applicable"} />
              <Field label="Bill reference" value={shown(draft.bill_wise?.ref)} />
            </dl>
            {detail.ai_paragraph ? <p className="text-sm leading-6 text-muted-foreground">{detail.ai_paragraph}</p> : null}
            <ul className="space-y-1 text-sm text-muted-foreground">
              {(draft.reasons || []).length === 0
                ? <li>No mapping reasons supplied.</li>
                : draft.reasons?.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
            {editable && (
              <form className="space-y-2" onSubmit={save}>
                <label className="block text-sm font-medium">
                  Edit party ledger
                  <Input className="mt-1.5" value={ledger} maxLength={4000} onChange={(event) => setLedger(event.target.value)} />
                </label>
                <Button type="submit" variant="outline" disabled={busy}>Save edit</Button>
              </form>
            )}
            {canApprove && (
              <div className="flex flex-wrap gap-2">
                <Button disabled={busy} onClick={() => void run(() => api.approveAndPost(clientId, documentId, detail.revision), "Approved and queued to post.")}>
                  Approve & post
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => void run(() => api.sendBack(clientId, documentId, detail.revision), "Sent back for a correction.")}>
                  Ask vendor to resend
                </Button>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Field({ label, value, extra }: { label: string; value: string; extra?: string }) {
  return (
    <div className="py-2">
      <dt className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
        {label}{extra ? <span className="ml-2 normal-case tracking-normal">{extra}</span> : null}
      </dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

function percent(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  return `${Math.round(value * 100)}%`;
}
