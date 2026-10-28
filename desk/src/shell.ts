import { followLink, h } from "./dom";
import { clientIdOf, queueHref, QUEUES, type Route } from "./router";
import { currentTheme, toggleTheme } from "./theme";

export function topbar(signedIn: boolean, onMenu: () => void, go: (url: string) => void): HTMLElement {
  const bar = h("header", { class: "topbar" });
  if (signedIn) {
    const menu = h("button", {
      class: "menu-button",
      type: "button",
      "aria-label": "Menu",
      "aria-expanded": "false",
      "aria-controls": "desk-menu",
    });
    menu.append(h("span"), h("span"), h("span"));
    menu.addEventListener("click", onMenu);
    bar.append(menu);
    const brand = h("a", { class: "brand", href: "/" }, ["FinLedger"]);
    brand.addEventListener("click", (event) => followLink(event, go, "/"));
    bar.append(brand);
  } else {
    bar.append(h("div", { class: "brand" }, ["FinLedger"]));
  }
  bar.append(h("div", { class: "spacer" }));
  const mode = h("button", {
    class: "ghost mode",
    type: "button",
    "aria-pressed": currentTheme() === "night" ? "true" : "false",
  }, [currentTheme() === "night" ? "Day" : "Night"]);
  mode.addEventListener("click", () => {
    const next = toggleTheme();
    mode.textContent = next === "night" ? "Day" : "Night";
    mode.setAttribute("aria-pressed", next === "night" ? "true" : "false");
  });
  bar.append(mode);
  return bar;
}

export function menuParts(
  route: Route,
  firmAdmin: boolean,
  go: (url: string) => void,
  onSignOut: () => void,
  onClose: () => void,
): { scrim: HTMLElement; panel: HTMLElement } {
  const clientId = clientIdOf(route);
  const scrim = h("div", { class: "scrim" });
  scrim.addEventListener("click", onClose);
  const panel = h("nav", { class: "panel", id: "desk-menu", "aria-label": "Pages" });
  const clients = h("a", { href: "/" }, ["Clients"]);
  if (route.name === "home") clients.setAttribute("aria-current", "page");
  clients.addEventListener("click", (event) => goFromMenu(event, go, "/"));
  panel.append(clients);

  const review = h("div", {});
  review.append(h("div", { class: "menu-label", id: "review-label" }, ["Review"]));
  if (clientId) {
    const group = h("div", { role: "group", "aria-labelledby": "review-label" });
    const active = route.name === "queue" ? route.queue : remembered(clientId, route);
    for (const queue of QUEUES) {
      const href = queueHref(clientId, queue.key);
      const link = h("a", { class: "queue", href }, [queue.label]);
      if (active === queue.key) link.setAttribute("aria-current", "page");
      link.addEventListener("click", (event) => goFromMenu(event, go, href));
      group.append(link);
    }
    review.append(group);
  }
  panel.append(review);

  if (firmAdmin) {
    const staff = h("a", { href: "/staff" }, ["Staff"]);
    if (route.name === "staff") staff.setAttribute("aria-current", "page");
    staff.addEventListener("click", (event) => goFromMenu(event, go, "/staff"));
    panel.append(staff);
  }

  const signOut = h("button", { class: "row sign-out", type: "button" }, ["Sign out"]);
  signOut.addEventListener("click", onSignOut);
  panel.append(signOut);
  panel.addEventListener("keydown", (event) => trap(panel, event));
  return { scrim, panel };
}

function remembered(clientId: string, route: Route): string | null {
  if (route.name !== "invoice") return null;
  try {
    const raw = JSON.parse(sessionStorage.getItem("finledger-queue") || "") as { clientId?: string; queue?: string };
    return raw.clientId === clientId ? raw.queue || null : null;
  } catch {
    return null;
  }
}

function goFromMenu(event: MouseEvent, go: (url: string) => void, url: string) {
  followLink(event, go, url);
}

function trap(panel: HTMLElement, event: KeyboardEvent) {
  if (event.key !== "Tab") return;
  const items = [...panel.querySelectorAll<HTMLElement>("a, button")];
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
