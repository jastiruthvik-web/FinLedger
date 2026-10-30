import { useEffect, useState } from "react";
import { errorMessage } from "@/api";
import { loadFirm } from "@/live";
import { PageHeader } from "@/pages/Placeholder";
import { EmptyState, TableSkeleton } from "@/pages/states";
import type { ClientRow } from "@/types";

export function TransactionsPage({ onNavigate }: { onNavigate: (url: string) => void }) {
  const [clients, setClients] = useState<ClientRow[] | null>(null);
  const [clientId, setClientId] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    loadFirm()
      .then((firm) => { if (live) setClients(firm.clients); })
      .catch((reason: unknown) => {
        if (live) setError(errorMessage(reason, "The desk could not load clients."));
      });
    return () => { live = false; };
  }, []);

  const selected = clients?.find((client) => client.id === clientId);
  return (
    <div className="space-y-3">
      <PageHeader title="Reconciliation" description="Bank lines against purchase bills. Amounts are in rupees." />
      {error ? <p role="alert" className="rounded-xl border border-border bg-card px-4 py-6 text-sm">{error}</p> : null}
      {!clients ? <TableSkeleton /> : (
        <>
          <label className="text-xs text-muted-foreground">
            Client
            <select
              aria-label="Client"
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              className="ml-2 h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground"
            >
              <option value="all">All clients</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
            </select>
          </label>
          <div className="rounded-xl border border-border bg-card">
            <EmptyState
              sentence={selected ? `No bank lines are on file for ${selected.name}.` : "No bank lines are on file."}
              action="Back to the dashboard"
              onAction={() => onNavigate("/")}
            />
          </div>
        </>
      )}
    </div>
  );
}
