import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { bills, formatDay, clientName } from "@/data/mock";
import { rupees } from "@/format";
import { PageHeader } from "@/pages/Placeholder";
import { CardSkeleton, TableSkeleton, useReady } from "@/pages/states";

const acme = "11111111-1111-1111-1111-111111111111";

export function Dashboard({ onNavigate }: { onNavigate: (url: string) => void }) {
  const waiting = bills.filter((bill) => bill.status === "Needs review" || bill.status === "New");
  const exceptions = bills.filter((bill) => bill.status === "Exception");
  const openAmount = bills.filter((bill) => bill.status !== "Posted").reduce((sum, bill) => sum + bill.amount, 0);
  const postedThisMonth = bills
    .filter((bill) => bill.status === "Posted" && bill.date.startsWith("2026-10"))
    .reduce((sum, bill) => sum + bill.amount, 0);
  const recent = [...bills].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
  const ready = useReady();

  if (!ready) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dashboard" description="Accounts payable across the firm, as of 28 Oct 2026." />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
        </div>
        <TableSkeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader title="Dashboard" description="Accounts payable across the firm, as of 28 Oct 2026." />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => onNavigate("/clients")}>Clients</Button>
          <Button onClick={() => onNavigate(`/clients/${acme}`)}>Review Acme Steel</Button>
        </div>
      </div>
      <section className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Waiting for review" value={String(waiting.length)} detail="New and needs review" />
        <Metric label="Open amount" value={rupees(openAmount)} detail="Not yet posted" />
        <Metric label="Exceptions" value={String(exceptions.length)} detail="Held before posting" />
        <Metric label="Posted in October" value={rupees(postedThisMonth)} detail="Already in the books" />
      </section>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,0.8fr)]">
        <section className="rounded-xl border border-border bg-card">
          <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">Recent activity</h2>
          <ul>
            {recent.map((bill) => (
              <li key={bill.id} className="border-b border-border last:border-0">
                <a
                  href={`/clients/${bill.clientId}`}
                  onClick={(event) => { event.preventDefault(); onNavigate(`/clients/${bill.clientId}`); }}
                  className="flex items-start justify-between gap-3 px-3 py-2 text-[13px] hover:bg-muted/70"
                >
                  <span>
                    <span className="font-medium">{bill.invoice}</span>
                    <span className="text-muted-foreground"> · {bill.vendor}</span>
                    <span className="mt-0.5 block text-muted-foreground">{clientName(bill.clientId)} · {bill.status}</span>
                  </span>
                  <span className="shrink-0 text-right tabular-nums">
                    <span className="block">{rupees(bill.amount)}</span>
                    <span className="text-xs text-muted-foreground">{formatDay(bill.date)}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
        <div className="space-y-4">
          <section className="rounded-xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold">Note</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Four bills still need a person. Shree Ganesh Metals INV-42 is ₹11,800 and lines up with Acme Steel’s last steel purchase. Three other bills are exceptions and should not be posted until the vendor is confirmed.
            </p>
          </section>
          <section className="rounded-xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold">Quick actions</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Action href="/transactions" label="Reconcile the bank" onNavigate={onNavigate} />
              <Action href={`/clients/${acme}`} label="Open Acme Steel" onNavigate={onNavigate} />
              <Action href="/clients" label="See every client" onNavigate={onNavigate} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="rounded-xl border border-border bg-card px-3 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums tracking-tight">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
    </article>
  );
}

function Action({ href, label, onNavigate }: { href: string; label: string; onNavigate: (url: string) => void }) {
  return (
    <a href={href} onClick={(event) => { event.preventDefault(); onNavigate(href); }} className="flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-muted">
      {label}
      <ArrowRight className="size-4 text-muted-foreground" />
    </a>
  );
}
