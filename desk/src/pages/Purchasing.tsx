import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/pages/Placeholder";
import type { PurchasingView } from "@/types";

const blankLine = { line_no: 1, item_code: "", description: "", uom: "NOS", quantity: "1", unit_price: "0", tax_rate: "18", po_line_no: 1 };

export function PurchasingPage({ clientId }: { clientId: string }) {
  const [view, setView] = useState<PurchasingView | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [po, setPo] = useState("PO-1");
  const [vendor, setVendor] = useState("");
  const [gstin, setGstin] = useState("");
  const [description, setDescription] = useState("");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("0");
  const [grn, setGrn] = useState("GRN-1");
  const [kind, setKind] = useState("goods_receipt");
  const [dept, setDept] = useState("STORES");
  const [deptName, setDeptName] = useState("Stores");
  const [approver, setApprover] = useState("");

  async function load() {
    setView(await api.purchasing(clientId));
  }

  useEffect(() => {
    let live = true;
    api.purchasing(clientId).then((next) => { if (live) setView(next); }).catch((reason: unknown) => {
      if (live) setError(errorMessage(reason, "Purchasing is unavailable."));
    });
    return () => { live = false; };
  }, [clientId]);

  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      setNotice(done);
    } catch (reason) {
      setError(errorMessage(reason, "That was not saved."));
    } finally {
      setBusy(false);
    }
  }

  function saveOrder(event: FormEvent) {
    event.preventDefault();
    void run(() => api.saveOrder(clientId, {
      po_number: po,
      vendor_name: vendor,
      supplier_gstin: gstin,
      currency: "INR",
      source: "manual",
      lines: [{ ...blankLine, description, quantity: qty, unit_price: price, tax_rate: "18" }],
    }), "Purchase order saved from manual entry. This is not a live ERP sync.");
  }

  function saveReceipt(event: FormEvent) {
    event.preventDefault();
    void run(() => api.saveReceipt(clientId, {
      grn_number: grn,
      po_number: po,
      document_kind: kind,
      source: "manual",
      supplier_gstin: gstin,
      currency: "INR",
      lines: [{ line_no: 1, po_line_no: 1, item_code: "", description, uom: "NOS", quantity: qty, unit_price: price }],
    }), kind === "delivery_note"
      ? "Delivery note saved as pending review. It is not an accepted goods receipt."
      : "Goods receipt saved from manual entry.");
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Purchasing" description={view?.source_label || "Manual or file import. Not a live purchasing sync."} />
      {error ? <p role="alert" className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{error}</p> : null}
      {notice ? <p role="status" className="rounded-md border border-border bg-card px-3 py-2 text-sm">{notice}</p> : null}
      <p className="text-sm text-muted-foreground">Tolerance version {view?.tolerance.version ?? "…"}. Version 0 is the built-in exact quantity and 0.01 price rule until a firm admin saves a new version.</p>
      <form className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2" onSubmit={saveOrder}>
        <h2 className="md:col-span-2 text-sm font-semibold">Purchase order</h2>
        <Field label="PO number" value={po} onChange={setPo} />
        <Field label="Supplier" value={vendor} onChange={setVendor} />
        <Field label="Supplier GSTIN" value={gstin} onChange={setGstin} />
        <Field label="Description" value={description} onChange={setDescription} />
        <Field label="Quantity" value={qty} onChange={setQty} />
        <Field label="Unit price" value={price} onChange={setPrice} />
        <Button type="submit" disabled={busy}>Save purchase order</Button>
      </form>
      <form className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2" onSubmit={saveReceipt}>
        <h2 className="md:col-span-2 text-sm font-semibold">Goods receipt or delivery note</h2>
        <Field label="Receipt number" value={grn} onChange={setGrn} />
        <label className="block text-sm">
          Kind
          <select className="mt-1.5 h-9 w-full rounded-md border border-border bg-background px-2" value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="goods_receipt">Goods receipt</option>
            <option value="delivery_note">Delivery note, needs review</option>
          </select>
        </label>
        <Button type="submit" disabled={busy}>Save receipt</Button>
      </form>
      <form className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2" onSubmit={(event) => {
        event.preventDefault();
        void run(() => api.saveDepartment(clientId, {
          code: dept, name: deptName, cost_centre: dept, approver_ids: approver ? [approver] : [],
        }), "Department saved.");
      }}>
        <h2 className="md:col-span-2 text-sm font-semibold">Department</h2>
        <Field label="Code" value={dept} onChange={setDept} />
        <Field label="Name" value={deptName} onChange={setDeptName} />
        <label className="block text-sm md:col-span-2">
          Approver user id, if they already have the approver role
          <Input className="mt-1.5" value={approver} onChange={(event) => setApprover(event.target.value)} />
        </label>
        <Button type="submit" variant="outline" disabled={busy}>Save department</Button>
      </form>
      <section className="rounded-xl border border-border bg-card p-4 text-sm">
        <h2 className="font-semibold">On file</h2>
        <ul className="mt-2 space-y-1 text-muted-foreground">
          {(view?.purchase_orders || []).map((row) => <li key={row.po_number}>{row.po_number} · {row.vendor_name} · qty {row.quantity} · {row.source}</li>)}
          {(view?.goods_receipts || []).map((row) => <li key={row.grn_number}>{row.grn_number} · {row.document_kind} · {row.status} · qty {row.quantity_received}</li>)}
          {(view?.departments || []).map((row) => <li key={row.code}>{row.code} · {row.name} · cost centre {row.cost_centre || "—"}</li>)}
          {view && view.purchase_orders.length === 0 && view.goods_receipts.length === 0 ? <li>Nothing entered yet.</li> : null}
        </ul>
      </section>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm">
      {label}
      <Input className="mt-1.5" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
