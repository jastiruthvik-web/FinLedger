import { useCallback, useEffect, useState } from "react";
import { ApiError, api, errorMessage } from "./api";
import { LoginScreen } from "./components/LoginScreen";
import { Shell } from "./components/Shell";
import { ClientsPage, InvoicePage, MfaPage, MissingPage, QueuePage, StaffPage } from "./pages/Work";
import { parseRoute, type Route } from "./router";
import type { ClientRow, Session } from "./types";

type Phase = "checking" | "anon" | "in" | "down";

function routeId(route: Route): string {
  if (route.name === "queue") return `queue:${route.clientId}:${route.queue}`;
  if (route.name === "invoice") return `invoice:${route.clientId}:${route.documentId}`;
  return route.name;
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname, window.location.search));
  const [session, setSession] = useState<Session | null>(null);
  const [phase, setPhase] = useState<Phase>("checking");
  const [bootError, setBootError] = useState("");
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [search, setSearch] = useState("");
  const [trail, setTrail] = useState<string[]>(["Clients"]);

  const go = useCallback((url: string) => {
    const next = new URL(url, window.location.origin);
    const there = next.pathname + next.search;
    const here = window.location.pathname + window.location.search;
    if (there !== here) history.pushState({}, "", there);
    setRoute(parseRoute(next.pathname, next.search));
  }, []);

  const onTrail = useCallback((next: string[]) => setTrail(next), []);

  useEffect(() => {
    const sync = () => setRoute(parseRoute(window.location.pathname, window.location.search));
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  useEffect(() => {
    setSearch("");
  }, [routeId(route)]);

  useEffect(() => {
    let live = true;
    if (route.name === "login") {
      api.session().then((next) => {
        if (!live) return;
        setSession(next);
        go(next.aal === "aal2" ? "/" : "/mfa");
      }).catch((error: unknown) => {
        if (!live) return;
        setSession(null);
        if (error instanceof ApiError && (error.status === 401 || error.status === 404)) setPhase("anon");
        else {
          setBootError(errorMessage(error, "The desk could not reach the control server."));
          setPhase("down");
        }
      });
      return () => { live = false; };
    }
    api.session().then((next) => {
      if (!live) return;
      setSession(next);
      setPhase("in");
      if (next.aal !== "aal2" && route.name !== "mfa") go("/mfa");
      else if (next.aal === "aal2" && route.name === "mfa") go("/");
    }).catch((error: unknown) => {
      if (!live) return;
      setSession(null);
      if (error instanceof ApiError && error.status === 401) go("/login");
      else {
        setBootError(errorMessage(error, "The desk could not reach the control server."));
        setPhase("down");
      }
    });
    return () => { live = false; };
  }, [route, go]);

  useEffect(() => {
    if (!session || session.aal !== "aal2") return;
    let live = true;
    api.clients().then((data) => { if (live) setClients(data.clients); }).catch(() => { if (live) setClients([]); });
    return () => { live = false; };
  }, [session?.user_id, session?.aal]);

  async function signOut() {
    try {
      await api.logout();
    } catch {
      /* The session cookie is cleared when the server accepts the request. */
    }
    setSession(null);
    go("/login");
  }

  if (phase === "down") {
    return <div className="grid min-h-screen place-items-center px-6 text-center"><p role="alert">{bootError}</p></div>;
  }
  if (route.name === "login") {
    if (phase !== "anon") return <Splash />;
    return <LoginScreen onSignedIn={() => go("/")} />;
  }
  if (!session || phase === "checking") return <Splash />;

  const wide = route.name === "invoice";
  let page = <MissingPage onNavigate={go} />;
  if (route.name === "mfa") page = <MfaPage onNavigate={go} />;
  else if (route.name === "home") page = <ClientsPage search={search} onNavigate={go} onTrail={onTrail} />;
  else if (route.name === "queue") page = <QueuePage clientId={route.clientId} queue={route.queue} search={search} onNavigate={go} onTrail={onTrail} />;
  else if (route.name === "invoice") page = <InvoicePage clientId={route.clientId} documentId={route.documentId} onNavigate={go} onTrail={onTrail} />;
  else if (route.name === "staff") page = <StaffPage firmAdmin={session.firm_admin} onNavigate={go} onTrail={onTrail} />;

  return (
    <Shell session={session} route={route} clients={session.aal === "aal2" ? clients : []} search={search} onSearch={setSearch} trail={trail} wide={wide} onNavigate={go} onSignOut={() => { void signOut(); }}>
      {page}
    </Shell>
  );
}

function Splash() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg text-ink">
      <div className="text-sm font-medium tracking-tight">FinLedger</div>
    </div>
  );
}
