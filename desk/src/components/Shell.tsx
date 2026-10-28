import {
  Bell, Building2, ChevronDown, LogOut, Menu, Moon, PanelLeft, Search, Sun, Users, X,
} from "lucide-react";
import { useEffect, useId, useState, type MouseEvent, type ReactNode } from "react";
import { clientIdOf, queueHref, QUEUES, type QueueKey, type Route } from "../router";
import { currentTheme, toggleTheme } from "../theme";
import type { ClientRow, Session } from "../types";
import { cn } from "../lib/cn";
import { Button } from "./ui";

export function Shell({
  session,
  route,
  clients,
  search,
  onSearch,
  trail,
  wide,
  onNavigate,
  onSignOut,
  children,
}: {
  session: Session;
  route: Route;
  clients: ClientRow[];
  search: string;
  onSearch: (value: string) => void;
  trail: string[];
  wide?: boolean;
  onNavigate: (url: string) => void;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [alerts, setAlerts] = useState(false);
  const [night, setNight] = useState(currentTheme() === "night");
  const searchId = useId();
  const clientId = clientIdOf(route);
  const activeQueue = currentQueue(route);

  useEffect(() => {
    setOpen(false);
    setAlerts(false);
  }, [route]);

  function follow(event: MouseEvent, url: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(url);
  }

  return (
    <div className="flex min-h-screen bg-bg text-ink">
      {open && (
        <button aria-label="Close menu" className="fixed inset-0 z-30 bg-[#0E1216]/40 lg:hidden" onClick={() => setOpen(false)} />
      )}
      <aside
        id="desk-menu"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-sidebar transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
          collapsed && "lg:w-[76px]",
        )}
      >
        <div className="flex h-16 items-center gap-2 px-4">
          <div className="grid size-8 place-items-center rounded-lg bg-[#0B3A66] text-sm font-semibold text-white night:bg-[#1E3A5F] night:text-[#8FB4D9]">
            F
          </div>
          <div className={cn("min-w-0", collapsed && "lg:hidden")}>
            <div className="truncate text-sm font-semibold tracking-tight">FinLedger</div>
            <div className="truncate text-xs text-muted">Review desk</div>
          </div>
        </div>
        <nav aria-label="Pages" className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 pb-4">
          <NavLink href="/" current={route.name === "home"} collapsed={collapsed} icon={<Building2 size={18} />} onClick={(event) => follow(event, "/")}>
            Clients
          </NavLink>
          <div className={cn("mt-4 px-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted", collapsed && "lg:sr-only")}>
            Review
          </div>
          {clientId ? (
            <div role="group" aria-label="Review" className="mt-1 flex flex-col gap-0.5">
              {QUEUES.map((queue) => (
                <NavLink
                  key={queue.key}
                  href={queueHref(clientId, queue.key)}
                  current={activeQueue === queue.key}
                  collapsed={collapsed}
                  nested
                  onClick={(event) => follow(event, queueHref(clientId, queue.key))}
                >
                  {queue.label}
                </NavLink>
              ))}
            </div>
          ) : (
            <p className={cn("px-2 text-xs text-muted", collapsed && "lg:hidden")}>Open a client to see queues.</p>
          )}
          <div className="mt-auto flex flex-col gap-1 pt-6">
            {session.firm_admin && (
              <NavLink href="/staff" current={route.name === "staff"} collapsed={collapsed} icon={<Users size={18} />} onClick={(event) => follow(event, "/staff")}>
                Staff
              </NavLink>
            )}
            <button
              type="button"
              onClick={onSignOut}
              className="flex h-10 items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-ink/5"
            >
              <LogOut size={18} />
              <span className={cn(collapsed && "lg:sr-only")}>Sign out</span>
            </button>
          </div>
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur">
          <Button variant="ghost" size="sm" className="lg:hidden" aria-label="Menu" aria-expanded={open} aria-controls="desk-menu" onClick={() => setOpen((value) => !value)}>
            {open ? <X size={18} /> : <Menu size={18} />}
          </Button>
          <Button variant="ghost" size="sm" className="hidden lg:inline-flex" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed((value) => !value)}>
            <PanelLeft size={18} />
          </Button>
          <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1 text-sm text-muted sm:flex">
            {trail.map((part, index) => (
              <span key={`${part}-${index}`} className="flex min-w-0 items-center gap-1">
                {index > 0 && <span aria-hidden="true">/</span>}
                <span className={cn("truncate", index === trail.length - 1 && "font-medium text-ink")}>{part}</span>
              </span>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <label htmlFor={searchId} className="relative hidden md:block">
              <span className="sr-only">Search this page</span>
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                id={searchId}
                value={search}
                onChange={(event) => onSearch(event.target.value)}
                placeholder="Search this page"
                className="h-9 w-56 rounded-lg border border-line bg-bg pl-9 pr-3 text-sm"
              />
            </label>
            {clients.length > 0 && (
              <label className="relative hidden items-center lg:flex">
                <span className="sr-only">Client</span>
                <select
                  className="h-9 appearance-none rounded-lg border border-line bg-bg py-0 pl-3 pr-8 text-sm"
                  value={clientId ?? ""}
                  onChange={(event) => {
                    if (event.target.value) onNavigate(queueHref(event.target.value, "needs_review"));
                  }}
                >
                  <option value="">All clients</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>{client.name}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-2 text-muted" />
              </label>
            )}
            <div className="relative">
              <Button variant="ghost" size="sm" aria-expanded={alerts} aria-label="Alerts" onClick={() => setAlerts((value) => !value)}>
                <Bell size={18} />
              </Button>
              {alerts && (
                <div className="absolute right-0 mt-2 w-64 rounded-xl border border-line bg-surface p-3 text-sm shadow-[var(--fl-shadow)]">
                  No alerts right now.
                </div>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              aria-pressed={night}
              onClick={() => setNight(toggleTheme() === "night")}
            >
              {night ? <Sun size={16} /> : <Moon size={16} />}
              <span className="hidden sm:inline">{night ? "Day" : "Night"}</span>
            </Button>
            <div className="hidden items-center gap-2 rounded-full border border-line py-1 pl-1 pr-3 text-sm sm:flex">
              <span className="grid size-7 place-items-center rounded-full bg-[#0B3A66] text-xs text-white night:bg-[#1E3A5F] night:text-[#8FB4D9]">
                {session.firm_admin ? "A" : "S"}
              </span>
              {session.firm_admin ? "Firm admin" : "Staff"}
            </div>
          </div>
        </header>
        <main className={cn("mx-auto w-full flex-1 px-4 py-6 sm:px-6", wide ? "max-w-[1440px]" : "max-w-6xl")}>
          {children}
        </main>
      </div>
    </div>
  );
}

function NavLink({
  href, current, collapsed, nested, icon, children, onClick,
}: {
  href: string;
  current: boolean;
  collapsed: boolean;
  nested?: boolean;
  icon?: ReactNode;
  children: string;
  onClick: (event: MouseEvent) => void;
}) {
  return (
    <a
      href={href}
      aria-current={current ? "page" : undefined}
      onClick={onClick}
      className={cn(
        "flex h-10 items-center gap-2 rounded-lg px-2 text-sm transition-colors hover:bg-ink/5",
        nested && "pl-3 text-[13px]",
        current && "bg-ink/8 font-medium",
        collapsed && "lg:justify-center lg:px-0",
      )}
    >
      {icon}
      <span className={cn("truncate", collapsed && "lg:sr-only")}>{children}</span>
    </a>
  );
}

function currentQueue(route: Route): QueueKey | null {
  if (route.name === "queue") return route.queue;
  if (route.name !== "invoice") return null;
  try {
    const raw = JSON.parse(sessionStorage.getItem("finledger-queue") || "") as { clientId?: string; queue?: QueueKey };
    return raw.clientId === route.clientId ? raw.queue ?? null : null;
  } catch {
    return null;
  }
}

export function PageHeader({
  title, description, actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
