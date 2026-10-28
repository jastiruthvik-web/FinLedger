import { ApiError, api, errorMessage, isMfaRequired } from "./api";
import { followLink, h, setTitle } from "./dom";
import { bandText, percent, rupees, safeSource, shown } from "./format";
import { invoiceHref, queueHref, rememberQueue, QUEUES, type QueueKey } from "./router";
import type { InvoiceDetail, Mark, PageContext } from "./types";

const LOCKED = new Set(["scheduled", "paid", "posted", "reconciled", "closed"]);

let mfaSetup: { factorId: string; secret: string } | null = null;

export function leaveMfa() {
  mfaSetup = null;
}

export function errorPage(error: unknown): HTMLElement {
  setTitle("Desk unavailable");
  return h("main", { class: "page page-narrow" }, [
    h("h1", {}, ["Desk unavailable"]),
    h("p", { class: "context", role: "alert" }, [errorMessage(error, "Something went wrong on the desk.")]),
  ]);
}

export function missingPage(ctx: PageContext): HTMLElement {
  setTitle("Not found");
  const link = h("a", { href: "/" }, ["Back to clients"]);
  link.addEventListener("click", (event) => followLink(event, ctx.go, "/"));
  return h("main", { class: "page page-narrow" }, [
    h("h1", {}, ["This page is not on the desk"]),
    h("p", { class: "context" }, ["Choose a client from the menu."]),
    link,
  ]);
}

export async function loginPage(ctx: PageContext): Promise<HTMLElement | null> {
  setTitle("Sign in");
  let tokenError = "";
  try {
    await api.csrf();
  } catch (error) {
    if (!ctx.alive()) return null;
    tokenError = error instanceof ApiError && error.status === 404
      ? "Sign-in is not configured on this control server."
      : errorMessage(error, "The desk could not start sign-in.");
  }
  if (!ctx.alive()) return null;
  const main = h("main", { class: "page page-narrow" });
  main.append(
    h("div", { class: "page-head" }, [
      h("h1", {}, ["Sign in"]),
      h("p", { class: "context" }, ["Use the work email and password for your firm."]),
    ]),
  );
  if (tokenError) main.append(h("p", { class: "alert", role: "alert" }, [tokenError]));
  const form = h("form", { class: "stack", method: "post", action: "/login" });
  const email = h("input", { name: "email", type: "email", autocomplete: "username", required: "true", maxlength: "320" });
  const password = h("input", { name: "password", type: "password", autocomplete: "current-password", required: "true", maxlength: "1024" });
  form.append(
    h("label", {}, ["Email", email]),
    h("label", {}, ["Password", password]),
    h("button", { class: "solid", type: "submit" }, ["Sign in"]),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    clearAlert(form);
    try {
      await api.login(email.value, password.value);
      if (ctx.alive()) ctx.go("/");
    } catch (error) {
      if (button?.isConnected) button.disabled = false;
      showAlert(form, error instanceof ApiError && error.status === 404
        ? "Sign-in is not configured on this control server."
        : errorMessage(error, "Sign-in failed."));
    }
  });
  main.append(form);
  return main;
}

export async function mfaPage(ctx: PageContext): Promise<HTMLElement | null> {
  setTitle("Two-step verification");
  let factorId = mfaSetup?.factorId || "";
  let loadError = "";
  if (!mfaSetup) {
    try {
      const state = await api.mfa();
      if (!ctx.alive()) return null;
      factorId = state.factor_id || "";
    } catch (error) {
      if (!ctx.alive()) return null;
      if (leaveIfBlocked(error, ctx)) return null;
      loadError = errorMessage(error, "Two-step verification is unavailable.");
    }
  }
  if (!ctx.alive()) return null;
  const secret = mfaSetup?.secret || "";
  const hasFactor = Boolean(factorId);
  const main = h("main", { class: "page page-narrow" });
  main.append(h("div", { class: "page-head" }, [
    h("h1", {}, ["Two-step verification"]),
    h("p", { class: "context" }, [hasFactor
      ? "Enter the code from your authenticator app before you open a client."
      : "Set up an authenticator app. You will enter a code from it each time you sign in."]),
  ]));
  if (loadError) main.append(h("p", { class: "alert", role: "alert" }, [loadError]));
  if (secret) {
    main.append(h("p", {}, ["Add this setup key to your authenticator app."]));
    main.append(h("p", {}, [h("code", {}, [secret])]));
  }
  if (!hasFactor) {
    const start = h("button", { class: "solid", type: "button" }, ["Start setup"]);
    start.addEventListener("click", async () => {
      start.disabled = true;
      try {
        const enrolled = await api.enroll();
        if (!ctx.alive()) return;
        mfaSetup = { factorId: enrolled.factor_id, secret: enrolled.secret };
        ctx.rerender();
      } catch (error) {
        if (start.isConnected) start.disabled = false;
        if (leaveIfBlocked(error, ctx)) return;
        showAlert(main, errorMessage(error, "MFA setup is unavailable."));
      }
    });
    main.append(start);
    return main;
  }
  const form = h("form", { class: "stack" });
  const code = h("input", {
    name: "code", inputmode: "numeric", autocomplete: "one-time-code",
    pattern: "[0-9]{6}", maxlength: "6", required: "true",
  });
  form.append(
    h("label", {}, ["Authenticator code", code]),
    h("button", { class: "solid", type: "submit" }, ["Verify code"]),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    clearAlert(form);
    try {
      await api.verify(factorId, code.value.trim());
      mfaSetup = null;
      if (ctx.alive()) ctx.go("/");
    } catch (error) {
      if (button?.isConnected) button.disabled = false;
      if (leaveIfBlocked(error, ctx)) return;
      showAlert(form, errorMessage(error, "Code could not be verified. Try again."));
    }
  });
  main.append(form);
  return main;
}

export async function clientsPage(ctx: PageContext): Promise<HTMLElement | null> {
  setTitle("Clients");
  try {
    const data = await api.clients();
    if (!ctx.alive()) return null;
    const list = h("ul", { class: "client-list" });
    for (const client of data.clients) {
      const href = queueHref(client.id, "needs_review");
      const link = h("a", { href }, [client.name]);
      link.addEventListener("click", (event) => followLink(event, ctx.go, href));
      list.append(h("li", {}, [link]));
    }
    return h("main", { class: "page" }, [
      h("div", { class: "page-head" }, [
        h("h1", {}, ["Clients"]),
        h("p", { class: "context" }, ["Open a client to work its queues."]),
      ]),
      data.clients.length ? list : h("p", { class: "empty" }, ["No clients are assigned to you."]),
    ]);
  } catch (error) {
    if (!ctx.alive()) return null;
    if (leaveIfBlocked(error, ctx)) return null;
    return errorPage(error);
  }
}

export async function queuePage(ctx: PageContext, clientId: string, queue: QueueKey): Promise<HTMLElement | null> {
  const meta = QUEUES.find((item) => item.key === queue) || QUEUES[1];
  rememberQueue(clientId, queue);
  try {
    const data = await api.queue(clientId, queue);
    if (!ctx.alive()) return null;
    setTitle(data.client.name || meta.label);
    const body = data.items.length ? queueTable(ctx, clientId, data.items) : h("p", { class: "empty" }, ["Nothing is waiting in this queue."]);
    return h("main", { class: "page" }, [
      h("div", { class: "page-head" }, [
        h("h1", {}, [data.client.name || "Client"]),
        h("p", { class: "context" }, [meta.context]),
      ]),
      h("h2", { id: "queue-title" }, [meta.label]),
      body,
    ]);
  } catch (error) {
    if (!ctx.alive()) return null;
    if (leaveIfBlocked(error, ctx)) return null;
    return errorPage(error);
  }
}

export async function invoicePage(ctx: PageContext, clientId: string, documentId: string): Promise<HTMLElement | null> {
  try {
    const data = await api.invoice(clientId, documentId);
    if (!ctx.alive()) return null;
    const invoice = data.invoice;
    const title = invoice.filename || invoice.invoice?.invoice_no || "Invoice";
    setTitle(title);
    const roles = new Set(data.roles);
    const main = h("main", { class: "page page-review" });
    main.append(h("div", { class: "page-head" }, [
      h("h1", {}, [title]),
      h("p", { class: "context" }, [`${invoice.state_label} for ${data.client.name}.`]),
    ]));
    const grid = h("div", { class: "review" });
    grid.append(sourceColumn(invoice), readColumn(invoice), voucherColumn(ctx, clientId, documentId, invoice, roles));
    main.append(grid);
    return main;
  } catch (error) {
    if (!ctx.alive()) return null;
    if (leaveIfBlocked(error, ctx)) return null;
    if (error instanceof ApiError && error.status === 404) {
      setTitle("Invoice");
      return h("main", { class: "page page-narrow" }, [
        h("h1", {}, ["Invoice"]),
        h("p", { class: "context", role: "alert" }, ["This bill is not ready to open yet."]),
      ]);
    }
    return errorPage(error);
  }
}

export async function staffPage(ctx: PageContext, firmAdmin: boolean): Promise<HTMLElement | null> {
  setTitle("Staff");
  const main = h("main", { class: "page page-staff" });
  main.append(h("div", { class: "page-head" }, [
    h("h1", {}, ["Staff"]),
    h("p", { class: "context" }, ["Invite someone at the firm and choose the clients they can work on."]),
  ]));
  if (!firmAdmin) {
    main.append(h("p", { class: "alert", role: "alert" }, ["Staff invites are for a firm admin."]));
    return main;
  }
  try {
    const data = await api.staff();
    if (!ctx.alive()) return null;
    main.append(inviteForm(ctx, data.clients));
    return main;
  } catch (error) {
    if (!ctx.alive()) return null;
    if (leaveIfBlocked(error, ctx)) return null;
    main.append(h("p", { class: "alert", role: "alert" }, [errorMessage(error, "Staff invites are unavailable.")]));
    return main;
  }
}

function queueTable(ctx: PageContext, clientId: string, items: { document_id: string; invoice_no: string | null; filename: string | null; vendor_name: string | null; total: string | number | null; band: string | null; score: number | string | null; state_label: string }[]): HTMLElement {
  const body = h("tbody");
  for (const item of items) {
    const href = invoiceHref(clientId, item.document_id);
    const label = item.invoice_no || item.filename || "Untitled";
    const link = h("a", { class: "invoice", href }, [label]);
    link.addEventListener("click", (event) => followLink(event, ctx.go, href));
    body.append(h("tr", {}, [
      h("td", {}, [link]),
      h("td", {}, [item.vendor_name || "Unresolved vendor"]),
      h("td", { class: "num" }, [rupees(item.total)]),
      h("td", { class: "num" }, [bandText(item.band, item.score)]),
      h("td", {}, [item.state_label]),
    ]));
  }
  return h("div", { class: "table-wrap" }, [
    h("table", { "aria-labelledby": "queue-title" }, [
      h("thead", {}, [h("tr", {}, [
        h("th", { scope: "col" }, ["Invoice"]),
        h("th", { scope: "col" }, ["Vendor"]),
        h("th", { class: "num", scope: "col" }, ["Amount"]),
        h("th", { class: "num", scope: "col" }, ["Risk"]),
        h("th", { scope: "col" }, ["State"]),
      ])]),
      body,
    ]),
  ]);
}

function sourceColumn(invoice: InvoiceDetail): HTMLElement {
  const source = safeSource(invoice.source_url);
  const frame = source
    ? h("iframe", { class: "source-frame", title: "Source", src: source })
    : h("p", { class: "missing" }, ["The source file is not available on this bill."]);
  return h("section", { class: "column", "aria-labelledby": "source-heading" }, [
    h("h2", { id: "source-heading" }, ["Source"]),
    frame,
  ]);
}

function readColumn(invoice: InvoiceDetail): HTMLElement {
  const inv = invoice.invoice || {};
  const vendor = inv.vendor || {};
  const confidence = inv.confidences || {};
  const marks = invoice.risk?.marks || [];
  const fields = [
    fieldBlock("Vendor", vendor.name, "vendor.name", null, marks),
    fieldBlock("GSTIN", vendor.gstin, "vendor.gstin", confidence.gstin, marks),
    fieldBlock("Invoice number", inv.invoice_no, "invoice_no", confidence.invoice_no, marks),
    fieldBlock("Invoice date", inv.invoice_date, "invoice_date", confidence.date, marks),
    fieldBlock("Buyer GSTIN", inv.buyer_gstin, "buyer_gstin", null, marks),
    fieldBlock("PO number", inv.po_number, "po_number", null, marks),
    fieldBlock("Grand total", rupees(inv.total), "total", confidence.total, marks, true),
  ];
  return h("section", { class: "column", "aria-labelledby": "read-heading" }, [
    h("h2", { id: "read-heading" }, ["What we read"]),
    h("div", { class: "fields" }, fields),
  ]);
}

function voucherColumn(
  ctx: PageContext,
  clientId: string,
  documentId: string,
  invoice: InvoiceDetail,
  roles: Set<string>,
): HTMLElement {
  const draft = invoice.draft || {};
  const lines = (draft.lines || []).map((line) => `${line.ledger || "Unmapped"} — ${rupees(line.amount ?? 0)}`).join("; ");
  const gst = draft.gst?.treatment === "intra" ? "Intra-state" : draft.gst?.treatment === "inter" ? "Inter-state" : shown(draft.gst?.treatment);
  const tds = draft.tds?.applicable ? "Applicable" : "Not applicable";
  const column = h("section", { class: "column", "aria-labelledby": "voucher-heading" });
  column.append(h("h2", { id: "voucher-heading" }, ["Voucher to post"]));
  const fields = h("div", { class: "fields" }, [
    textField("Risk", bandText(invoice.risk?.band, invoice.risk?.score), true),
    textField("Party ledger", shown(draft.party_ledger)),
    textField("Voucher lines", lines || "—"),
    textField("GST treatment", gst),
    textField("TDS", tds),
    textField("Bill reference", shown(draft.bill_wise?.ref)),
  ]);
  column.append(fields);
  if (invoice.ai_paragraph) column.append(h("p", { class: "summary" }, [invoice.ai_paragraph]));
  const reasons = draft.reasons || [];
  if (reasons.length) {
    column.append(h("div", { class: "reasons" }, reasons.map((reason) => h("p", { class: "reason" }, [reason]))));
  }
  const editable = !LOCKED.has(invoice.status);
  const canEdit = editable && (roles.has("ap_clerk") || roles.has("approver") || roles.has("firm_admin"));
  const canDecide = roles.has("approver") || roles.has("firm_admin");
  if (canEdit) column.append(editForm(ctx, clientId, documentId, invoice.revision, draft.party_ledger || ""));
  if (canDecide) column.append(decisionButtons(ctx, clientId, documentId, invoice.revision));
  return column;
}

function editForm(ctx: PageContext, clientId: string, documentId: string, revision: number, current: string): HTMLElement {
  const form = h("form", { class: "edit stack" });
  const input = h("input", { name: "value", value: current, maxlength: "4000" });
  const button = h("button", { class: "ghost", type: "submit" }, ["Save change"]);
  form.append(h("label", {}, ["Party ledger", input]), button);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    clearAlert(form);
    try {
      await api.saveChange(clientId, documentId, revision, input.value);
      if (ctx.alive()) ctx.rerender();
    } catch (error) {
      if (button.isConnected) button.disabled = false;
      if (leaveIfBlocked(error, ctx)) return;
      showAlert(form, errorMessage(error, "The change was not saved."));
    }
  });
  return form;
}

function decisionButtons(ctx: PageContext, clientId: string, documentId: string, revision: number): HTMLElement {
  const actions = h("div", { class: "actions" });
  const approve = h("button", { class: "solid", type: "button" }, ["Approve and post"]);
  const sendBack = h("button", { class: "ghost", type: "button" }, ["Send back"]);
  approve.addEventListener("click", async () => {
    approve.disabled = true;
    sendBack.disabled = true;
    clearAlert(actions);
    try {
      await api.approveAndPost(clientId, documentId, revision);
      if (ctx.alive()) ctx.rerender();
    } catch (error) {
      if (approve.isConnected) {
        approve.disabled = false;
        sendBack.disabled = false;
      }
      if (leaveIfBlocked(error, ctx)) return;
      showAlert(actions, errorMessage(error, "This bill was not approved."));
    }
  });
  sendBack.addEventListener("click", async () => {
    approve.disabled = true;
    sendBack.disabled = true;
    clearAlert(actions);
    try {
      await api.sendBack(clientId, documentId, revision);
      if (ctx.alive()) ctx.go(queueHref(clientId, "exception"));
    } catch (error) {
      if (approve.isConnected) {
        approve.disabled = false;
        sendBack.disabled = false;
      }
      if (leaveIfBlocked(error, ctx)) return;
      showAlert(actions, errorMessage(error, "This bill was not sent back."));
    }
  });
  actions.append(approve, sendBack);
  return actions;
}

function inviteForm(ctx: PageContext, clients: { id: string; name: string }[]): HTMLFormElement {
  const form = h("form", { class: "stack" });
  const email = h("input", { name: "email", type: "email", required: "true", maxlength: "254", autocomplete: "off" });
  const name = h("input", { name: "name", maxlength: "200", autocomplete: "off" });
  const admin = h("input", { type: "checkbox", name: "firm_admin" });
  form.append(
    h("label", {}, ["Work email", email]),
    h("label", {}, ["Name", name]),
    h("label", { class: "check" }, [admin, "Firm admin. They see every client and can invite staff."]),
  );
  const roles = [["ap_clerk", "AP clerk"], ["approver", "Approver"], ["payer", "Payer"]] as const;
  if (clients.length) {
    const body = h("tbody");
    for (const client of clients) {
      const cells = [h("td", {}, [client.name])];
      for (const [role, label] of roles) {
        const box = h("input", { type: "checkbox", name: "membership", value: `${client.id}:${role}` });
        box.setAttribute("aria-label", `${label} for ${client.name}`);
        cells.push(h("td", { class: "role" }, [box]));
      }
      body.append(h("tr", {}, cells));
    }
    form.append(h("div", { class: "table-wrap" }, [
      h("table", {}, [
        h("thead", {}, [h("tr", {}, [
          h("th", { scope: "col" }, ["Client"]),
          ...roles.map(([, label]) => h("th", { class: "role", scope: "col" }, [label])),
        ])]),
        body,
      ]),
    ]));
  } else {
    form.append(h("p", { class: "context" }, ["No clients yet. A firm admin still sees every client without a membership."]));
  }
  const button = h("button", { class: "solid", type: "submit" }, ["Send invitation"]);
  form.append(button);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    clearAlert(form);
    const memberships = [...form.querySelectorAll<HTMLInputElement>("input[name=membership]:checked")].map((box) => {
      const [client_id, role] = box.value.split(":");
      return { client_id, role };
    });
    try {
      const result = await api.invite({
        email: email.value,
        name: name.value,
        firm_admin: admin.checked,
        memberships,
      });
      if (!ctx.alive()) return;
      email.value = "";
      name.value = "";
      admin.checked = false;
      form.querySelectorAll<HTMLInputElement>("input[name=membership]").forEach((box) => { box.checked = false; });
      showNotice(form, result.notice);
    } catch (error) {
      if (leaveIfBlocked(error, ctx)) return;
      showAlert(form, errorMessage(error, "Invitation not sent."));
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  });
  return form;
}

function fieldBlock(label: string, value: unknown, field: string, confidence: number | null | undefined, marks: Mark[], numeric = false): HTMLElement {
  const bare = field.replace(/^vendor\./, "");
  const failed = marks.filter((mark) => !mark.ok && (mark.field === field || mark.field === bare));
  const head = h("div", { class: "field-name" }, [h("span", {}, [label])]);
  if (confidence !== undefined && confidence !== null) head.append(h("span", { class: "num" }, [percent(confidence)]));
  const block = h("div", { class: "field" }, [
    head,
    h("div", { class: numeric ? "field-value num" : "field-value" }, [numeric ? shown(value) : shown(value)]),
  ]);
  for (const mark of failed) block.append(h("div", { class: "mark" }, [markText(mark)]));
  return block;
}

function textField(label: string, value: string, numeric = false): HTMLElement {
  return h("div", { class: "field" }, [
    h("div", { class: "field-name" }, [h("span", {}, [label])]),
    h("div", { class: numeric ? "field-value num" : "field-value" }, [value]),
  ]);
}

function markText(mark: Mark): string {
  const check = mark.check || "Control";
  const note = mark.note?.trim();
  return note ? `${check}: ${note}` : check;
}

function leaveIfBlocked(error: unknown, ctx: PageContext): boolean {
  if (error instanceof ApiError && error.status === 401) {
    ctx.go("/login");
    return true;
  }
  if (isMfaRequired(error)) {
    ctx.go("/mfa");
    return true;
  }
  return false;
}

function clearAlert(host: ParentNode) {
  host.querySelectorAll(".alert, .notice").forEach((node) => node.remove());
}

function showAlert(host: HTMLElement, message: string) {
  clearAlert(host);
  host.prepend(h("p", { class: "alert", role: "alert" }, [message]));
}

function showNotice(host: HTMLElement, message: string) {
  clearAlert(host);
  host.prepend(h("p", { class: "notice", role: "status" }, [message]));
}
