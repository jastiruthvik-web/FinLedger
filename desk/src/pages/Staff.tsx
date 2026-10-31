import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/pages/Placeholder";
import type { ClientRow } from "@/types";

const ROLES = [
  { role: "ap_clerk", label: "AP clerk" },
  { role: "approver", label: "Approver" },
  { role: "payer", label: "Payer" },
] as const;

export function StaffPage() {
  const [clients, setClients] = useState<ClientRow[] | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [firmAdmin, setFirmAdmin] = useState(false);
  const [picked, setPicked] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api.staff()
      .then((page) => { if (live) setClients(page.clients); })
      .catch((reason: unknown) => {
        if (live) setError(errorMessage(reason, "Staff invites are not available for this sign-in."));
      });
    return () => { live = false; };
  }, []);

  function toggle(clientId: string, role: string) {
    const key = `${clientId}:${role}`;
    setPicked((current) => ({ ...current, [key]: !current[key] }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const memberships = Object.entries(picked)
      .filter(([, on]) => on)
      .map(([key]) => {
        const split = key.indexOf(":");
        return { client_id: key.slice(0, split), role: key.slice(split + 1) };
      });
    try {
      const result = await api.invite({ email, name, firm_admin: firmAdmin, memberships });
      setNotice(result.notice);
      setEmail("");
      setName("");
      setFirmAdmin(false);
      setPicked({});
    } catch (reason) {
      setError(errorMessage(reason, "The invitation was not sent."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Staff" description="Invite someone at the firm and choose the clients they can work on." />
      {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-md border border-border bg-card px-3 py-2 text-sm">{notice}</p> : null}
      {!clients ? <div className="h-40 animate-pulse rounded-xl border border-border bg-card" /> : (
        <form className="space-y-4 rounded-xl border border-border bg-card p-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Work email
            <Input className="mt-1.5 max-w-sm" type="email" required maxLength={320} autoComplete="off" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Name
            <Input className="mt-1.5 max-w-sm" maxLength={200} autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={firmAdmin} onChange={(event) => setFirmAdmin(event.target.checked)} />
            Firm admin (every client, can invite staff)
          </label>
          {clients.length === 0 ? (
            <p className="text-sm text-muted-foreground">No clients yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3">Client</th>
                    {ROLES.map((role) => <th key={role.role} className="py-2 pr-3">{role.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {clients.map((client) => (
                    <tr key={client.id} className="border-b border-border last:border-0">
                      <td className="py-2 pr-3">{client.name}</td>
                      {ROLES.map((role) => (
                        <td key={role.role} className="py-2 pr-3">
                          <input
                            type="checkbox"
                            aria-label={`${role.label} for ${client.name}`}
                            checked={Boolean(picked[`${client.id}:${role.role}`])}
                            onChange={() => toggle(client.id, role.role)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Button type="submit" disabled={busy}>Send invitation</Button>
        </form>
      )}
    </div>
  );
}
