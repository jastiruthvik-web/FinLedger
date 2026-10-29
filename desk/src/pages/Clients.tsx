import { Badge, statusTone } from "@/components/ui/badge";
import { billsFor, clientById, firmClients, formatDay } from "@/data/mock";
import { rupees } from "@/format";
import { PageHeader } from "@/pages/Placeholder";
import { bodyCell, EmptyState, headCell, TableScroll, TableSkeleton, useReady } from "@/pages/states";

export function ClientsPage({ onNavigate }: { onNavigate: (url: string) => void }) {
  const ready = useReady();
  return (
    <div className="space-y-4">
      <PageHeader title="Clients" description="Companies on the firm’s books. Open one to see its bills." />
      {!ready ? <TableSkeleton /> : firmClients.length === 0 ? (
        <div className="rounded-xl border border-border bg-card">
          <EmptyState sentence="No clients are assigned to this firm." action="Back to the dashboard" onAction={() => onNavigate("/")} />
        </div>
      ) : (
        <TableScroll className="min-w-0">
          <thead>
            <tr>
              <th className={headCell}>Client</th>
              <th className={headCell}>GSTIN</th>
              <th className={`${headCell} text-right`}>Open bills</th>
              <th className={`${headCell} text-right`}>Needs review</th>
              <th className={`${headCell} text-right`}>Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {firmClients.map((client) => {
              const rows = billsFor(client.id);
              const open = rows.filter((bill) => bill.status !== "Posted");
              const review = rows.filter((bill) => bill.status === "Needs review" || bill.status === "New");
              const outstanding = open.reduce((sum, bill) => sum + bill.amount, 0);
              const href = `/clients/${client.id}`;
              return (
                <tr key={client.id} className="border-b border-border last:border-0 hover:bg-muted/70">
                  <td className={bodyCell}>
                    <a href={href} onClick={(event) => { event.preventDefault(); onNavigate(href); }} className="font-medium">
                      {client.name}
                    </a>
                    <span className="block text-xs text-muted-foreground">{client.city}</span>
                  </td>
                  <td className={`${bodyCell} tabular-nums text-muted-foreground`}>{client.gstin}</td>
                  <td className={`${bodyCell} text-right tabular-nums`}>{open.length}</td>
                  <td className={`${bodyCell} text-right tabular-nums`}>{review.length}</td>
                  <td className={`${bodyCell} text-right tabular-nums`}>{rupees(outstanding)}</td>
                </tr>
              );
            })}
          </tbody>
        </TableScroll>
      )}
    </div>
  );
}

export function ClientDetail({ clientId, onNavigate }: { clientId: string; onNavigate: (url: string) => void }) {
  const ready = useReady();
  const client = clientById(clientId);
  if (!client) {
    return (
      <div className="space-y-4">
        <PageHeader title="Client" description="This company is not on the firm’s list." />
        <div className="rounded-xl border border-border bg-card">
          <EmptyState sentence="This client is not on the desk." action="Back to clients" onAction={() => onNavigate("/clients")} />
        </div>
      </div>
    );
  }
  const rows = [...billsFor(client.id)].sort((a, b) => b.date.localeCompare(a.date));
  const open = rows.filter((bill) => bill.status !== "Posted");
  return (
    <div className="space-y-4">
      <PageHeader
        title={client.name}
        description={`${client.city} · ${client.gstin}. ${open.length} open ${open.length === 1 ? "bill" : "bills"}.`}
      />
      {!ready ? <TableSkeleton /> : rows.length === 0 ? (
        <div className="rounded-xl border border-border bg-card">
          <EmptyState sentence="No bills are on file for this client." action="Back to clients" onAction={() => onNavigate("/clients")} />
        </div>
      ) : (
        <TableScroll>
          <thead>
            <tr>
              <th className={headCell}>Invoice</th>
              <th className={headCell}>Vendor</th>
              <th className={headCell}>Date</th>
              <th className={`${headCell} text-right`}>Amount</th>
              <th className={headCell}>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((bill) => (
              <tr key={bill.id} className="border-b border-border last:border-0">
                <td className={`${bodyCell} font-medium`}>{bill.invoice}</td>
                <td className={bodyCell}>{bill.vendor}</td>
                <td className={`${bodyCell} tabular-nums text-muted-foreground`}>{formatDay(bill.date)}</td>
                <td className={`${bodyCell} text-right tabular-nums`}>{rupees(bill.amount)}</td>
                <td className={bodyCell}><Badge tone={statusTone(bill.status)}>{bill.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
    </div>
  );
}
