import { api } from "@/api";
import { QUEUES, type QueueKey } from "@/router";
import type { ClientRow, QueueItem } from "@/types";

export interface LiveBill extends QueueItem {
  clientId: string;
  clientName: string;
  queue: QueueKey;
}

export async function loadFirm(): Promise<{ clients: ClientRow[]; bills: LiveBill[] }> {
  const { clients } = await api.clients();
  const lists = await Promise.all(clients.map((client) => loadClientBills(client)));
  return { clients, bills: lists.flat() };
}

export async function loadClientBills(client: ClientRow): Promise<LiveBill[]> {
  const pages = await Promise.all(QUEUES.map((queue) => api.queue(client.id, queue.key)));
  return pages.flatMap((page) =>
    page.items.map((item) => ({
      ...item,
      clientId: client.id,
      clientName: page.client.name || client.name,
      queue: (QUEUES.some((queue) => queue.key === page.queue) ? page.queue : "needs_review") as QueueKey,
    })),
  );
}
