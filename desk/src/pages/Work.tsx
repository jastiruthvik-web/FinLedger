import { FileSearch } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, api, errorMessage, isMfaRequired } from "../api";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Input, toneFor } from "../components/ui";
import { bandText, percent, rupees, safeSource, shown } from "../format";
import { invoiceHref, queueHref, rememberQueue, QUEUES, type QueueKey } from "../router";
import type { InvoiceDetail, Mark, QueueItem } from "../types";

const LOCKED = new Set(["scheduled", "paid", "posted", "reconciled", "closed"]);

export function ClientsPage({
  search, onNavigate, onTrail,
}: {
  search: string;
  onNavigate: (url: string) => void;
  onTrail: (trail: string[]) => void;
}) {
  const [rows, setRows] = useState<{ id: string; name: string }[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Clients · FinLedger";
    onTrail(["Clients"]);
    let live = true;
    api.clients().then((data) => {
      if (live) setRows(data.clients);
    }).catch((reason: unknown) => {
      if (!live) return;
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else if (isMfaRequired(reason)) onNavigate("/mfa");
      else setError(errorMessage(reason, "Clients could not be loaded."));
    });
    return () => { live = false; };
  }, [onNavigate, onTrail]);

  const visible = (rows ?? []).filter((row) => row.name.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <>
      <PageHeader title="Clients" description="Open a client to work its queues." />
      {error && <p role="alert" className="mb-4 text-sm">{error}</p>}
      <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[var(--fl-shadow)]">
        {rows === null && !error ? <p className="p-8 text-sm text-muted">Loading clients.</p> : null}
        {rows && visible.length === 0 ? <Empty text={rows.length === 0 ? "No clients are assigned to you." : "No client matches that search."} /> : null}
        {visible.length > 0 && (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">Client</th>
                <th className="px-4 py-3 font-medium">Next step</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((client) => {
                const href = queueHref(client.id, "needs_review");
                return (
                  <tr key={client.id} className="border-b border-line last:border-0 hover:bg-ink/4">
                    <td className="px-4 py-3.5 font-medium">
                      <a href={href} onClick={(event) => { event.preventDefault(); onNavigate(href); }}>{client.name}</a>
                    </td>
                    <td className="px-4 py-3.5 text-muted">Needs review</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

export function QueuePage({
  clientId, queue, search, onNavigate, onTrail,
}: {
  clientId: string;
  queue: QueueKey;
  search: string;
  onNavigate: (url: string) => void;
  onTrail: (trail: string[]) => void;
}) {
  const meta = QUEUES.find((item) => item.key === queue) ?? QUEUES[1];
  const [name, setName] = useState("Client");
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    rememberQueue(clientId, queue);
    let live = true;
    api.queue(clientId, queue).then((data) => {
      if (!live) return;
      setName(data.client.name || "Client");
      setItems(data.items);
      document.title = `${data.client.name || meta.label} · FinLedger`;
      onTrail(["Clients", data.client.name || "Client", meta.label]);
    }).catch((reason: unknown) => {
      if (!live) return;
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else if (isMfaRequired(reason)) onNavigate("/mfa");
      else setError(errorMessage(reason, "This queue could not be loaded."));
    });
    return () => { live = false; };
  }, [clientId, queue, meta.label, onNavigate, onTrail]);

  const needle = search.trim().toLowerCase();
  const visible = (items ?? []).filter((item) => {
    const haystack = `${item.invoice_no ?? ""} ${item.filename ?? ""} ${item.vendor_name ?? ""} ${item.state_label}`.toLowerCase();
    return haystack.includes(needle);
  });

  return (
    <>
      <PageHeader title={name} description={meta.context} />
      <h2 id="queue-title" className="mb-3 text-sm font-semibold">{meta.label}</h2>
      {error && <p role="alert" className="mb-4 text-sm">{error}</p>}
      <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[var(--fl-shadow)]">
        {items === null && !error ? <p className="p-8 text-sm text-muted">Loading the queue.</p> : null}
        {items && visible.length === 0 ? <Empty text={items.length === 0 ? "Nothing is waiting in this queue." : "Nothing on this page matches that search."} /> : null}
        {visible.length > 0 && (
          <div className="overflow-x-auto">
            <table aria-labelledby="queue-title" className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">Invoice</th>
                  <th className="px-4 py-3 font-medium">Vendor</th>
                  <th className="px-4 py-3 text-right font-medium">Amount</th>
                  <th className="px-4 py-3 text-right font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">State</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => {
                  const href = invoiceHref(clientId, item.document_id);
                  const label = item.invoice_no || item.filename || "Untitled";
                  return (
                    <tr key={item.document_id} className="border-b border-line last:border-0 hover:bg-ink/4">
                      <td className="px-4 py-3.5 font-medium">
                        <a className="underline decoration-line underline-offset-4" href={href} onClick={(event) => { event.preventDefault(); onNavigate(href); }}>{label}</a>
                      </td>
                      <td className="px-4 py-3.5">{item.vendor_name || "Unresolved vendor"}</td>
                      <td className="px-4 py-3.5 text-right tabular-nums">{rupees(item.total)}</td>
                      <td className="px-4 py-3.5 text-right tabular-nums">{bandText(item.band, item.score)}</td>
                      <td className="px-4 py-3.5"><Badge tone={toneFor(item.state_label)}>{item.state_label}</Badge></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

export function InvoicePage({
  clientId, documentId, onNavigate, onTrail,
}: {
  clientId: string;
  documentId: string;
  onNavigate: (url: string) => void;
  onTrail: (trail: string[]) => void;
}) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.invoice>> | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [ledger, setLedger] = useState("");
  const [busy, setBusy] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    api.invoice(clientId, documentId).then((payload) => {
      if (!live) return;
      setData(payload);
      setLedger(payload.invoice.draft?.party_ledger || "");
      const title = payload.invoice.filename || payload.invoice.invoice?.invoice_no || "Invoice";
      document.title = `${title} · FinLedger`;
      onTrail(["Clients", payload.client.name, title]);
    }).catch((reason: unknown) => {
      if (!live) return;
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else if (isMfaRequired(reason)) onNavigate("/mfa");
      else if (reason instanceof ApiError && reason.status === 404) setError("This bill is not ready to open yet.");
      else setError(errorMessage(reason, "This bill could not be opened."));
    });
    return () => { live = false; };
  }, [clientId, documentId, tick, onNavigate, onTrail]);

  if (error) {
    return (
      <>
        <PageHeader title="Invoice" description={error} />
      </>
    );
  }
  if (!data) return <p className="text-sm text-muted">Loading the bill.</p>;

  const invoice = data.invoice;
  const title = invoice.filename || invoice.invoice?.invoice_no || "Invoice";
  const roles = new Set(data.roles);
  const editable = !LOCKED.has(invoice.status) && (roles.has("ap_clerk") || roles.has("approver") || roles.has("firm_admin"));
  const canDecide = roles.has("approver") || roles.has("firm_admin");

  async function run(name: string, task: () => Promise<void>) {
    setBusy(name);
    setActionError("");
    try {
      await task();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else if (isMfaRequired(reason)) onNavigate("/mfa");
      else setActionError(errorMessage(reason, "That action did not finish."));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader
        title={title}
        description={`${invoice.state_label} for ${data.client.name}.`}
        actions={canDecide ? (
          <>
            <Button disabled={busy !== ""} onClick={() => run("approve", async () => {
              await api.approveAndPost(clientId, documentId, invoice.revision);
              setTick((value) => value + 1);
            })}>Approve and post</Button>
            <Button variant="outline" disabled={busy !== ""} onClick={() => run("back", async () => {
              await api.sendBack(clientId, documentId, invoice.revision);
              onNavigate(queueHref(clientId, "exception"));
            })}>Send back</Button>
          </>
        ) : null}
      />
      {actionError && <p role="alert" className="mb-4 rounded-lg border border-line bg-surface px-3 py-2 text-sm">{actionError}</p>}
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(260px,1.05fr)_minmax(240px,0.95fr)_minmax(280px,1.05fr)]">
        <Panel title="Source">
          {safeSource(invoice.source_url)
            ? <iframe title="Source" src={safeSource(invoice.source_url) || undefined} className="h-[70vh] w-full border-0 bg-bg" />
            : <p className="m-4 rounded-xl border border-dashed border-line px-4 py-10 text-center text-sm text-muted">The source file is not available on this bill.</p>}
        </Panel>
        <Panel title="What we read">
          <div className="divide-y divide-line px-4">
            {readFields(invoice).map((field) => (
              <div key={field.label} className="py-3">
                <div className="flex justify-between gap-3 text-xs text-muted">
                  <span>{field.label}</span>
                  {field.confidence ? <span className="tabular-nums">{field.confidence}</span> : null}
                </div>
                <div className="mt-1 text-sm">{field.value}</div>
                {field.marks.map((mark) => (
                  <div key={mark} className="mt-2 border-l-2 border-ink px-2 text-xs">{mark}</div>
                ))}
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Voucher to post">
          <div className="divide-y divide-line px-4">
            <Field label="Risk" value={bandText(invoice.risk?.band, invoice.risk?.score)} />
            <Field label="Party ledger" value={shown(invoice.draft?.party_ledger)} />
            <Field label="Voucher lines" value={lineText(invoice)} />
            <Field label="GST treatment" value={gstLabel(invoice.draft?.gst?.treatment)} />
            <Field label="TDS" value={invoice.draft?.tds?.applicable ? "Applicable" : "Not applicable"} />
            <Field label="Bill reference" value={shown(invoice.draft?.bill_wise?.ref)} />
          </div>
          {invoice.ai_paragraph && <p className="px-4 py-3 text-sm">{invoice.ai_paragraph}</p>}
          {(invoice.draft?.reasons ?? []).map((reason) => (
            <p key={reason} className="border-t border-line px-4 py-2 text-sm">{reason}</p>
          ))}
          {editable && (
            <form className="space-y-2 border-t border-line p-4" onSubmit={(event) => {
              event.preventDefault();
              void run("save", async () => {
                await api.saveChange(clientId, documentId, invoice.revision, ledger);
                setTick((value) => value + 1);
              });
            }}>
              <label className="block text-sm font-medium">
                Party ledger
                <Input name="value" className="mt-1.5" maxLength={4000} value={ledger} onChange={(event) => setLedger(event.target.value)} />
              </label>
              <Button type="submit" variant="outline" disabled={busy !== ""}>Save change</Button>
            </form>
          )}
        </Panel>
      </div>
    </>
  );
}

export function StaffPage({
  firmAdmin, onNavigate, onTrail,
}: {
  firmAdmin: boolean;
  onNavigate: (url: string) => void;
  onTrail: (trail: string[]) => void;
}) {
  const [clients, setClients] = useState<{ id: string; name: string }[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [admin, setAdmin] = useState(false);
  const [busy, setBusy] = useState(false);
  const roles = [["ap_clerk", "AP clerk"], ["approver", "Approver"], ["payer", "Payer"]] as const;

  useEffect(() => {
    document.title = "Staff · FinLedger";
    onTrail(["Staff"]);
    if (!firmAdmin) return;
    let live = true;
    api.staff().then((data) => { if (live) setClients(data.clients); }).catch((reason: unknown) => {
      if (!live) return;
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else if (isMfaRequired(reason)) onNavigate("/mfa");
      else setError(errorMessage(reason, "Staff invites are unavailable."));
    });
    return () => { live = false; };
  }, [firmAdmin, onNavigate, onTrail]);

  if (!firmAdmin) {
    return <PageHeader title="Staff" description="Staff invites are for a firm admin." />;
  }

  return (
    <>
      <PageHeader title="Staff" description="Invite someone at the firm and choose the clients they can work on." />
      <form className="max-w-3xl space-y-4 rounded-2xl border border-line bg-surface p-5 shadow-[var(--fl-shadow)]" onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        setBusy(true);
        setError("");
        setNotice("");
        const memberships = [...form.querySelectorAll<HTMLInputElement>("input[name=membership]:checked")].map((box) => {
          const [clientId, role] = box.value.split(":");
          return { client_id: clientId, role };
        });
        try {
          const result = await api.invite({ email, name, firm_admin: admin, memberships });
          setNotice(result.notice);
          setEmail("");
          setName("");
          setAdmin(false);
          form.reset();
        } catch (reason) {
          if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
          else if (isMfaRequired(reason)) onNavigate("/mfa");
          else setError(errorMessage(reason, "Invitation not sent."));
        } finally {
          setBusy(false);
        }
      }}>
        {error && <p role="alert" className="text-sm">{error}</p>}
        {notice && <p role="status" className="text-sm">{notice}</p>}
        <label className="block text-sm font-medium">Work email<Input className="mt-1.5" type="email" required maxLength={254} autoComplete="off" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="block text-sm font-medium">Name<Input className="mt-1.5" maxLength={200} autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={admin} onChange={(event) => setAdmin(event.target.checked)} />
          Firm admin. They see every client and can invite staff.
        </label>
        {clients && clients.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                  <th className="py-2 pr-3 font-medium">Client</th>
                  {roles.map(([, label]) => <th key={label} className="px-3 py-2 text-center font-medium">{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr key={client.id} className="border-b border-line">
                    <td className="py-3 pr-3">{client.name}</td>
                    {roles.map(([role, label]) => (
                      <td key={role} className="px-3 py-3 text-center">
                        <input type="checkbox" name="membership" value={`${client.id}:${role}`} aria-label={`${label} for ${client.name}`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {clients && clients.length === 0 && <p className="text-sm text-muted">No clients yet. A firm admin still sees every client without a membership.</p>}
        <Button type="submit" disabled={busy}>Send invitation</Button>
      </form>
    </>
  );
}

export function MfaPage({ onNavigate }: { onNavigate: (url: string) => void }) {
  const [factorId, setFactorId] = useState("");
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    document.title = "Two-step verification · FinLedger";
    let live = true;
    api.mfa().then((state) => {
      if (!live) return;
      setFactorId(state.factor_id || "");
      setReady(true);
    }).catch((reason: unknown) => {
      if (!live) return;
      if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
      else setError(errorMessage(reason, "Two-step verification is unavailable."));
      setReady(true);
    });
    return () => { live = false; };
  }, [onNavigate]);

  const hasFactor = Boolean(factorId || secret);
  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-[var(--fl-shadow)]">
      <h1 className="text-2xl font-semibold tracking-tight">Two-step verification</h1>
      <p className="mt-2 text-sm text-muted">
        {hasFactor ? "Enter the code from your authenticator app before you open a client." : "Set up an authenticator app. You will enter a code from it each time you sign in."}
      </p>
      {error && <p role="alert" className="mt-4 text-sm">{error}</p>}
      {secret && <p className="mt-4 text-sm">Add this setup key to your authenticator app.</p>}
      {secret && <p className="mt-2 break-all font-mono text-sm">{secret}</p>}
      {!hasFactor && ready && (
        <Button className="mt-6" onClick={async () => {
          try {
            const enrolled = await api.enroll();
            setFactorId(enrolled.factor_id);
            setSecret(enrolled.secret);
          } catch (reason) {
            if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
            else setError(errorMessage(reason, "MFA setup is unavailable."));
          }
        }}>Start setup</Button>
      )}
      {hasFactor && (
        <form className="mt-6 space-y-3" onSubmit={async (event) => {
          event.preventDefault();
          try {
            await api.verify(factorId, code.trim());
            onNavigate("/");
          } catch (reason) {
            if (reason instanceof ApiError && reason.status === 401) onNavigate("/login");
            else setError(errorMessage(reason, "Code could not be verified. Try again."));
          }
        }}>
          <label className="block text-sm font-medium">
            Authenticator code
            <Input className="mt-1.5" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} />
          </label>
          <Button type="submit">Verify code</Button>
        </form>
      )}
    </div>
  );
}

export function MissingPage({ onNavigate }: { onNavigate: (url: string) => void }) {
  useEffect(() => { document.title = "Not found · FinLedger"; }, []);
  return (
    <PageHeader title="This page is not on the desk" description="Choose a client from the sidebar." actions={<Button variant="outline" onClick={() => onNavigate("/")}>Back to clients</Button>} />
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  const id = title.toLowerCase().replace(/\s+/g, "-");
  return (
    <section aria-labelledby={id} className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[var(--fl-shadow)]">
      <h2 id={id} className="border-b border-line px-4 py-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-sm">{value}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="grid place-items-center px-6 py-16 text-center">
      <FileSearch className="text-muted" size={22} />
      <p className="mt-3 text-sm">{text}</p>
    </div>
  );
}

function readFields(invoice: InvoiceDetail) {
  const inv = invoice.invoice || {};
  const vendor = inv.vendor || {};
  const confidence = inv.confidences || {};
  const marks = invoice.risk?.marks || [];
  return [
    row("Vendor", shown(vendor.name), "vendor.name", null, marks),
    row("GSTIN", shown(vendor.gstin), "vendor.gstin", confidence.gstin, marks),
    row("Invoice number", shown(inv.invoice_no), "invoice_no", confidence.invoice_no, marks),
    row("Invoice date", shown(inv.invoice_date), "invoice_date", confidence.date, marks),
    row("Buyer GSTIN", shown(inv.buyer_gstin), "buyer_gstin", null, marks),
    row("PO number", shown(inv.po_number), "po_number", null, marks),
    row("Grand total", rupees(inv.total), "total", confidence.total, marks),
  ];
}

function row(label: string, value: string, field: string, confidence: number | null | undefined, marks: Mark[]) {
  const bare = field.replace(/^vendor\./, "");
  return {
    label,
    value,
    confidence: confidence == null ? "" : percent(confidence),
    marks: marks.filter((mark) => !mark.ok && (mark.field === field || mark.field === bare)).map(markText),
  };
}

function markText(mark: Mark): string {
  const check = mark.check || "Control";
  const note = mark.note?.trim();
  return note ? `${check}: ${note}` : check;
}

function lineText(invoice: InvoiceDetail): string {
  const lines = invoice.draft?.lines || [];
  if (!lines.length) return "—";
  return lines.map((line) => `${line.ledger || "Unmapped"} — ${rupees(line.amount ?? 0)}`).join("; ");
}

function gstLabel(treatment: string | null | undefined): string {
  if (treatment === "intra") return "Intra-state";
  if (treatment === "inter") return "Inter-state";
  return shown(treatment);
}
