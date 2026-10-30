import { useEffect, useState } from "react";
import { api, errorMessage } from "@/api";
import { PageHeader } from "@/pages/Placeholder";
import { BillTable } from "@/pages/Clients";
import { EmptyState, TableSkeleton } from "@/pages/states";
import { QUEUES, queueHref, type QueueKey } from "@/router";
import type { LiveBill } from "@/live";

export function QueuePage({
  clientId,
  queue,
  onNavigate,
}: {
  clientId: string;
  queue: QueueKey;
  onNavigate: (url: string) => void;
}) {
  const current = QUEUES.find((item) => item.key === queue) ?? QUEUES[1];
  const [name, setName] = useState("");
  const [rows, setRows] = useState<LiveBill[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    api.queue(clientId, queue)
      .then((page) => {
        if (!live) return;
        setName(page.client.name);
        setRows(page.items.map((item) => ({
          ...item,
          clientId,
          clientName: page.client.name,
          queue,
        })));
      })
      .catch((reason: unknown) => {
        if (live) setError(errorMessage(reason, "The desk could not load this queue."));
      });
    return () => { live = false; };
  }, [clientId, queue]);

  return (
    <div className="space-y-4">
      <PageHeader title={name || current.label} description={current.context} />
      <div className="flex flex-wrap gap-2">
        {QUEUES.map((item) => (
          <a
            key={item.key}
            href={queueHref(clientId, item.key)}
            aria-current={item.key === queue ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); onNavigate(queueHref(clientId, item.key)); }}
            className={`rounded-full border px-3 py-1 text-xs ${item.key === queue ? "border-foreground bg-foreground text-background" : "border-border text-muted-foreground hover:bg-muted"}`}
          >
            {item.label}
          </a>
        ))}
      </div>
      {error ? <p role="alert" className="rounded-xl border border-border bg-card px-4 py-6 text-sm">{error}</p> : null}
      {!rows ? <TableSkeleton /> : rows.length === 0 ? (
        <div className="rounded-xl border border-border bg-card">
          <EmptyState sentence={`No bills are in ${current.label.toLowerCase()}.`} action="Back to the client" onAction={() => onNavigate(`/clients/${clientId}`)} />
        </div>
      ) : (
        <BillTable rows={rows} onNavigate={onNavigate} />
      )}
    </div>
  );
}
