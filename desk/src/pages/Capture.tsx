import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/pages/Placeholder";
import type { CaptureStatus } from "@/types";

export function CapturePage({ clientId }: { clientId: string }) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [source, setSource] = useState<"mail_scan" | "portal_download">("mail_scan");
  const [messageId, setMessageId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api.capture(clientId).then((next) => { if (live) setStatus(next); }).catch((reason: unknown) => {
      if (live) setError(errorMessage(reason, "Capture status is unavailable."));
    });
    return () => { live = false; };
  }, [clientId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const list = event.currentTarget.elements.namedItem("files");
    if (!(list instanceof HTMLInputElement) || !list.files?.length) {
      setError("Choose a PDF or image.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.importBills(clientId, source, messageId, list.files);
      const kept = result.received.map((row) => row.filename).join(", ");
      const rejected = result.rejected.map((row) => `${row.filename}: ${row.reason}`).join(" ");
      setNotice(`${kept ? `Kept ${kept}. ` : ""}${rejected}`.trim() || "Nothing was stored.");
    } catch (reason) {
      setError(errorMessage(reason, "The file was not imported."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Invoice capture"
        description="Original files stay on this company, with their hash. Mail means a scan. Portals and inboxes are not connected from here."
      />
      {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-md border border-border bg-card px-3 py-2 text-sm">{notice}</p> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <Card title="Physical mail" body={status?.mail.detail || "Loading."} state="Upload a scan" />
        <Card title="Email" body={status?.email.detail || "Loading."} state={status?.email.mailbox_connected ? "Mailbox connected" : status?.email.webhook === "configured" ? "Webhook configured, mailbox not connected" : "Configuration required"} />
        <Card title="Vendor portal" body={status?.vendor_portal.detail || "Loading."} state="Not connected" />
      </div>
      {status?.upload_link ? <p className="text-sm text-muted-foreground">Vendor upload link: {status.upload_link}</p> : null}
      {status?.email.address ? <p className="text-sm text-muted-foreground">Address pattern for a future provider: {status.email.address}. This does not open a mailbox.</p> : null}
      <form className="space-y-3 rounded-xl border border-border bg-card p-4" onSubmit={(event) => { void submit(event); }}>
        <h2 className="text-sm font-semibold">Import a file</h2>
        <label className="block text-sm">
          Where the file came from
          <select className="mt-1.5 h-9 w-full rounded-md border border-border bg-background px-2 text-sm" value={source} onChange={(event) => setSource(event.target.value as "mail_scan" | "portal_download")}>
            <option value="mail_scan">Scanned paper mail</option>
            <option value="portal_download">Downloaded from a vendor portal</option>
          </select>
        </label>
        <label className="block text-sm">
          Message or download reference, if you have one
          <Input className="mt-1.5" value={messageId} maxLength={200} onChange={(event) => setMessageId(event.target.value)} />
        </label>
        <label className="block text-sm">
          PDF or image
          <input name="files" type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" multiple className="mt-1.5 block text-sm" />
        </label>
        <Button type="submit" disabled={busy}>Import</Button>
      </form>
    </div>
  );
}

function Card({ title, body, state }: { title: string; body: string; state: string }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{state}</p>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    </section>
  );
}
