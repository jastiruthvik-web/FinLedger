import { ApiError, api, isMfaRequired } from "./api";
import { h } from "./dom";
import { clientsPage, errorPage, invoicePage, leaveMfa, loginPage, mfaPage, missingPage, queuePage, staffPage } from "./pages";
import { parseRoute, type Route } from "./router";
import { menuParts, topbar } from "./shell";
import type { PageContext, Session } from "./types";

let generation = 0;
let menuOpen = false;
let session: Session | null = null;
let route: Route = { name: "home" };

function alive(gen: number): () => boolean {
  return () => gen === generation;
}

function context(gen: number): PageContext {
  return { alive: alive(gen), go, rerender: () => { void render(); } };
}

function go(url: string) {
  closeMenu();
  const next = new URL(url, window.location.origin);
  const there = next.pathname + next.search;
  const here = window.location.pathname + window.location.search;
  if (here !== there) history.pushState({}, "", there);
  void render();
}

function mount(signedIn: boolean, content: HTMLElement) {
  const root = h("div", { class: "app" });
  root.append(topbar(signedIn, () => setMenu(!menuOpen), go), content);
  if (signedIn && menuOpen && session) {
    const menu = menuParts(route, session.firm_admin, go, () => { void signOut(); }, () => setMenu(false));
    root.append(menu.scrim, menu.panel);
  }
  document.querySelector("#app")?.replaceChildren(root);
  document.body.style.overflow = menuOpen ? "hidden" : "";
  if (menuOpen) document.querySelector<HTMLElement>(".panel a, .panel button")?.focus();
}

function setMenu(open: boolean) {
  menuOpen = open;
  const root = document.querySelector(".app");
  const button = document.querySelector<HTMLButtonElement>(".menu-button");
  if (!root || !session) {
    void render();
    return;
  }
  root.querySelector(".scrim")?.remove();
  root.querySelector(".panel")?.remove();
  button?.setAttribute("aria-expanded", open ? "true" : "false");
  document.body.style.overflow = open ? "hidden" : "";
  if (!open) {
    button?.focus();
    return;
  }
  const menu = menuParts(route, session.firm_admin, go, () => { void signOut(); }, () => setMenu(false));
  root.append(menu.scrim, menu.panel);
  menu.panel.querySelector<HTMLElement>("a, button")?.focus();
}

function closeMenu() {
  menuOpen = false;
  document.body.style.overflow = "";
}

async function signOut() {
  closeMenu();
  try {
    await api.logout();
  } catch (error) {
    mount(true, errorPage(error));
    return;
  }
  session = null;
  go("/login");
}

async function render() {
  const gen = ++generation;
  route = parseRoute(window.location.pathname, window.location.search);
  if (route.name !== "mfa") leaveMfa();
  if (route.name === "login") {
    await renderLogin(gen);
    return;
  }
  let current: Session;
  try {
    current = await api.session();
  } catch (error) {
    if (gen !== generation) return;
    session = null;
    if (error instanceof ApiError && error.status === 401) {
      go("/login");
      return;
    }
    mount(false, errorPage(error));
    return;
  }
  if (gen !== generation) return;
  session = current;
  if (current.aal !== "aal2" && route.name !== "mfa") {
    go("/mfa");
    return;
  }
  if (current.aal === "aal2" && route.name === "mfa") {
    go("/");
    return;
  }
  const ctx = context(gen);
  let page: HTMLElement | null = null;
  if (route.name === "mfa") page = await mfaPage(ctx);
  else if (route.name === "home") page = await clientsPage(ctx);
  else if (route.name === "queue") page = await queuePage(ctx, route.clientId, route.queue);
  else if (route.name === "invoice") page = await invoicePage(ctx, route.clientId, route.documentId);
  else if (route.name === "staff") page = await staffPage(ctx, current.firm_admin);
  else page = missingPage(ctx);
  if (!page || gen !== generation) return;
  mount(true, page);
}

async function renderLogin(gen: number) {
  try {
    const current = await api.session();
    if (gen !== generation) return;
    session = current;
    go(current.aal === "aal2" ? "/" : "/mfa");
  } catch (error) {
    if (gen !== generation) return;
    session = null;
    if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
      const page = await loginPage(context(gen));
      if (!page || gen !== generation) return;
      mount(false, page);
      return;
    }
    if (isMfaRequired(error)) {
      go("/mfa");
      return;
    }
    mount(false, errorPage(error));
  }
}

window.addEventListener("popstate", () => {
  closeMenu();
  void render();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menuOpen) setMenu(false);
});

void render();
