import { useMemo, useState } from "react";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { clientName, firmClients, formatDay, ledger, type LedgerLine, type MatchStatus } from "@/data/mock";
import { rupees } from "@/format";
import { PageHeader } from "@/pages/Placeholder";
import { bodyCell, EmptyState, headCell, TableScroll, TableSkeleton, useReady } from "@/pages/states";

const PAGE_SIZE = 8;
type SortKey = "date" | "client" | "narration" | "reference" | "debit" | "credit" | "status";

const statuses: Array<MatchStatus | "All"> = ["All", "Unmatched", "Suggested", "Matched"];

export function TransactionsPage() {
  const [status, setStatus] = useState<MatchStatus | "All">("All");
  const [clientId, setClientId] = useState("all");
  const [text, setText] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const ready = useReady();

  const filtered = useMemo(() => {
    const needle = text.trim().toLowerCase();
    const rows = ledger.filter((line) => {
      if (status !== "All" && line.status !== status) return false;
      if (clientId !== "all" && line.clientId !== clientId) return false;
      if (!needle) return true;
      const haystack = `${line.narration} ${line.reference} ${clientName(line.clientId)}`.toLowerCase();
      return haystack.includes(needle);
    });
    rows.sort((a, b) => compare(a, b, sortKey) * (sortDir === "asc" ? 1 : -1));
    return rows;
  }, [status, clientId, text, sortKey, sortDir]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pages - 1);
  const slice = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);
  const from = filtered.length === 0 ? 0 : safePage * PAGE_SIZE + 1;
  const to = Math.min(filtered.length, (safePage + 1) * PAGE_SIZE);

  function sortBy(key: SortKey) {
    if (sortKey === key) setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "date" ? "desc" : "asc");
    }
    setPage(0);
  }

  return (
    <div className="space-y-3">
      <PageHeader title="Reconciliation" description="Bank lines against purchase bills. Amounts are in rupees." />
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted-foreground">
          Status
          <select
            aria-label="Status"
            value={status}
            onChange={(event) => { setStatus(event.target.value as MatchStatus | "All"); setPage(0); }}
            className="ml-2 h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground"
          >
            {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Client
          <select
            aria-label="Client"
            value={clientId}
            onChange={(event) => { setClientId(event.target.value); setPage(0); }}
            className="ml-2 h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground"
          >
            <option value="all">All clients</option>
            {firmClients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
          </select>
        </label>
        <input
          aria-label="Narration or reference"
          value={text}
          placeholder="Narration or reference"
          onChange={(event) => { setText(event.target.value); setPage(0); }}
          className="h-8 min-w-48 flex-1 rounded-md border border-input bg-card px-2 text-[13px]"
        />
      </div>
      {!ready ? <TableSkeleton /> : (
      <TableScroll>
            <thead>
              <tr>
                <SortHead label="Date" sortKey="date" active={sortKey} dir={sortDir} onSort={sortBy} />
                <SortHead label="Client" sortKey="client" active={sortKey} dir={sortDir} onSort={sortBy} />
                <SortHead label="Narration" sortKey="narration" active={sortKey} dir={sortDir} onSort={sortBy} />
                <SortHead label="Reference" sortKey="reference" active={sortKey} dir={sortDir} onSort={sortBy} />
                <SortHead label="Debit" sortKey="debit" active={sortKey} dir={sortDir} onSort={sortBy} align="right" />
                <SortHead label="Credit" sortKey="credit" active={sortKey} dir={sortDir} onSort={sortBy} align="right" />
                <SortHead label="Status" sortKey="status" active={sortKey} dir={sortDir} onSort={sortBy} />
              </tr>
            </thead>
            <tbody>
              {slice.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      sentence="Nothing matches these filters."
                      action="Clear filters"
                      onAction={() => { setStatus("All"); setClientId("all"); setText(""); setPage(0); }}
                    />
                  </td>
                </tr>
              ) : slice.map((line) => (
                <tr key={line.id} className="border-b border-border last:border-0">
                  <td className={`${bodyCell} tabular-nums text-muted-foreground`}>{formatDay(line.date)}</td>
                  <td className={bodyCell}>{clientName(line.clientId)}</td>
                  <td className={bodyCell}>{line.narration}</td>
                  <td className={`${bodyCell} tabular-nums`}>{line.reference}</td>
                  <td className={`${bodyCell} text-right tabular-nums`}>{line.debit == null ? "—" : rupees(line.debit)}</td>
                  <td className={`${bodyCell} text-right tabular-nums`}>{line.credit == null ? "—" : rupees(line.credit)}</td>
                  <td className={bodyCell}><Badge tone={statusTone(line.status)}>{line.status}</Badge></td>
                </tr>
              ))}
            </tbody>
      </TableScroll>
      )}
      <div className="flex items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground tabular-nums">Showing {from}–{to} of {filtered.length}</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>Previous</Button>
          <Button variant="outline" size="sm" disabled={safePage >= pages - 1} onClick={() => setPage(safePage + 1)}>Next</Button>
        </div>
      </div>
    </div>
  );
}

function compare(a: LedgerLine, b: LedgerLine, key: SortKey) {
  if (key === "date") return a.date.localeCompare(b.date);
  if (key === "client") return clientName(a.clientId).localeCompare(clientName(b.clientId));
  if (key === "narration") return a.narration.localeCompare(b.narration);
  if (key === "reference") return a.reference.localeCompare(b.reference);
  if (key === "debit") return (a.debit ?? -1) - (b.debit ?? -1);
  if (key === "credit") return (a.credit ?? -1) - (b.credit ?? -1);
  return a.status.localeCompare(b.status);
}

function SortHead({
  label, sortKey, active, dir, onSort, align = "left",
}: {
  label: string;
  sortKey: SortKey;
  active: SortKey;
  dir: "asc" | "desc";
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}) {
  const selected = active === sortKey;
  return (
    <th className={align === "right" ? `${headCell} text-right` : headCell} aria-sort={selected ? (dir === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => onSort(sortKey)} className="font-medium uppercase tracking-wide text-muted-foreground">
        {label}{selected ? (dir === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );
}
