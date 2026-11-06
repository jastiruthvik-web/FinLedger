"""Purchasing, department routing, and expense suggestions for one company.

Callers already hold the tenant transaction. These functions do not post to an ERP.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from psycopg.types.json import Jsonb

from finledger_platform import purchase_documents as books

from .gl_suggest import suggest_expense_ledgers
from .line_match import SOURCE_LABEL, assess_lines

_GSTIN = re.compile(r"^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]Z[0-9A-Z]$")


class BooksError(ValueError):
    pass


def _money(value, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BooksError(f"{name} is not a number") from exc
    if not number.is_finite() or number < 0:
        raise BooksError(f"{name} must be zero or more")
    return number


def _clean_lines(lines, *, receipt: bool) -> list[dict]:
    if not isinstance(lines, list):
        raise BooksError("lines must be a list")
    cleaned = []
    seen = set()
    for raw in lines:
        if not isinstance(raw, dict):
            raise BooksError("each line must be an object")
        line_no = raw.get("line_no")
        if isinstance(line_no, bool) or not isinstance(line_no, int) or line_no < 1:
            raise BooksError("line_no must be a positive integer")
        if line_no in seen:
            raise BooksError("line numbers must be unique")
        seen.add(line_no)
        item = {
            "line_no": line_no,
            "item_code": str(raw.get("item_code") or "")[:80],
            "description": str(raw.get("description") or "")[:400],
            "uom": str(raw.get("uom") or "")[:20],
            "quantity": _money(raw.get("quantity"), "quantity"),
            "unit_price": None if receipt and raw.get("unit_price") in (None, "") else _money(raw.get("unit_price") or 0, "unit_price"),
        }
        if not receipt:
            tax = raw.get("tax_rate")
            item["tax_rate"] = None if tax in (None, "") else _money(tax, "tax_rate")
            item["currency"] = str(raw.get("currency") or "INR")[:8]
        else:
            po_line = raw.get("po_line_no")
            if isinstance(po_line, bool) or not isinstance(po_line, int):
                raise BooksError("po_line_no is required on a receipt line")
            item["po_line_no"] = po_line
        cleaned.append(item)
    return cleaned


def _gstin(value: str) -> str:
    text = (value or "").strip().upper()
    if text and not _GSTIN.match(text):
        raise BooksError("supplier GSTIN is not valid")
    return text


def save_order(conn, *, po_number, vendor_name, supplier_gstin, currency, source, lines, actor_id):
    try:
        return books.save_order(
            conn, po_number=str(po_number or ""), vendor_name=str(vendor_name or "")[:200],
            supplier_gstin=_gstin(str(supplier_gstin or "")), currency=str(currency or "INR")[:8],
            source=source, lines=_clean_lines(lines, receipt=False), actor_id=actor_id,
        )
    except books.PurchasingError as exc:
        raise BooksError(str(exc)) from exc


def save_receipt(conn, *, grn_number, po_number, document_kind, source, supplier_gstin, currency, lines, actor_id):
    try:
        return books.save_receipt(
            conn, grn_number=str(grn_number or ""), po_number=str(po_number or ""),
            document_kind=document_kind, source=source, supplier_gstin=_gstin(str(supplier_gstin or "")),
            currency=str(currency or "INR")[:8], lines=_clean_lines(lines, receipt=True), actor_id=actor_id,
        )
    except books.PurchasingError as exc:
        raise BooksError(str(exc)) from exc


def review_receipt(conn, *, grn_number, status, actor_id, reason):
    try:
        return books.set_receipt_status(conn, grn_number=grn_number, status=status, actor_id=actor_id, reason=reason)
    except books.PurchasingError as exc:
        raise BooksError(str(exc)) from exc


def save_tolerance(conn, body: dict, actor_id):
    try:
        return books.save_tolerance(
            conn,
            qty_abs=_money(body.get("qty_abs", 0), "qty_abs"),
            qty_pct=_money(body.get("qty_pct", 0), "qty_pct"),
            price_abs=_money(body.get("price_abs", "0.01"), "price_abs"),
            price_pct=_money(body.get("price_pct", 0), "price_pct"),
            tax_abs=_money(body.get("tax_abs", 0), "tax_abs"),
            amount_abs=_money(body.get("amount_abs", "0.01"), "amount_abs"),
            note=str(body.get("note") or "")[:500],
            actor_id=actor_id,
        )
    except books.PurchasingError as exc:
        raise BooksError(str(exc)) from exc


def purchasing_view(conn) -> dict:
    orders = conn.execute(
        """select po_number, vendor_name, supplier_gstin, currency, source, quantity, amount
             from purchase_orders order by po_number"""
    ).fetchall()
    receipts = conn.execute(
        """select grn_number, po_number, document_kind, status, source, quantity_received
             from goods_receipts order by grn_number"""
    ).fetchall()
    return {
        "sync": "manual_or_file_import",
        "source_label": SOURCE_LABEL,
        "tolerance": books.current_tolerance(conn),
        "purchase_orders": [dict(row) for row in orders],
        "goods_receipts": [dict(row) for row in receipts],
        "departments": list_departments(conn),
    }


def match_document(conn, document_id, invoice: dict, match_mode: str) -> dict | None:
    po_lines = books.order_lines(conn, invoice.get("po_number"))
    if not po_lines:
        return None
    facts = books.line_facts(conn, document_id)
    enriched = dict(invoice)
    items = []
    for index, line in enumerate(invoice.get("line_items") or [], start=1):
        item = dict(line) if isinstance(line, dict) else {}
        fact = facts.get(index)
        if fact:
            item["_facts"] = fact
        items.append(item)
    enriched["line_items"] = items
    receipts = books.receipts_for_po(conn, invoice.get("po_number"))
    line_ids = [line["id"] for receipt in receipts for line in receipt.get("lines") or []]
    allocations = books.open_allocations(conn, line_ids, exclude_document=document_id)
    return assess_lines(
        invoice=enriched, po_lines=po_lines, receipts=receipts, allocations=allocations,
        tolerance=books.current_tolerance(conn), match_mode=match_mode,
    )


def reserve(conn, document_id, specs: list[dict]) -> None:
    numeric = []
    for spec in specs:
        numeric.append({
            "receipt_line_id": spec["receipt_line_id"],
            "invoice_line_no": int(spec["invoice_line_no"]),
            "quantity": spec["quantity"],
            "kind": spec["kind"],
        })
    books.reserve_allocations(conn, document_id=document_id, specs=numeric)


def release(conn, document_id) -> None:
    books.release_allocations(conn, document_id)


def expense_suggestions(conn, document_id) -> list[dict]:
    invoice = conn.execute("select payload from canonical_invoices where document_id = %s", (document_id,)).fetchone()
    draft = conn.execute("select payload from voucher_drafts where document_id = %s", (document_id,)).fetchone()
    if not invoice or not draft:
        return []
    payload = invoice["payload"] if isinstance(invoice["payload"], dict) else {}
    lines_payload = draft["payload"].get("lines") if isinstance(draft["payload"], dict) else []
    vendor_gstin = str((payload.get("vendor") or {}).get("gstin") or "")
    invoice_lines = payload.get("line_items") or []
    rows = []
    for index, line in enumerate(lines_payload or []):
        source = invoice_lines[index] if index < len(invoice_lines) and isinstance(invoice_lines[index], dict) else {}
        rows.append({
            "description": source.get("desc") or "",
            "hsn": source.get("hsn_sac") or "",
            "ledger": (line or {}).get("ledger") if isinstance(line, dict) else "",
        })
    corrections = conn.execute(
        """select id, field, new_value, vendor_gstin, description, hsn, created_at
             from correction_events where field = 'expense_ledger' order by id"""
    ).fetchall()
    return suggest_expense_ledgers(rows, [dict(row) for row in corrections], vendor_gstin=vendor_gstin)


def list_departments(conn) -> list[dict]:
    rows = conn.execute(
        "select id, code, name, cost_centre, active from departments order by code"
    ).fetchall()
    out = []
    for row in rows:
        approvers = conn.execute(
            "select user_id from department_approvers where department_id = %s order by user_id",
            (row["id"],),
        ).fetchall()
        item = dict(row)
        item["approver_ids"] = [str(person["user_id"]) for person in approvers]
        out.append(item)
    return out


def save_department(conn, *, code: str, name: str, cost_centre: str, actor_id) -> dict:
    cleaned = code.strip().upper()
    if not cleaned or len(cleaned) > 20 or not re.fullmatch(r"[A-Z0-9_-]+", cleaned):
        raise BooksError("department code must be short letters or numbers")
    if not name.strip():
        raise BooksError("department name is required")
    row = conn.execute(
        """insert into departments (client_id, code, name, cost_centre)
           values (app_client_id(), %s, btrim(%s), btrim(%s))
           on conflict (client_id, code) do update
             set name = excluded.name, cost_centre = excluded.cost_centre, active = true
           returning id, code, name, cost_centre, active""",
        (cleaned, name[:120], (cost_centre or "")[:80]),
    ).fetchone()
    conn.execute(
        "insert into purchasing_events (client_id, action, actor_id, payload) values (app_client_id(), 'department_saved', %s, %s)",
        (actor_id, Jsonb({"code": cleaned})),
    )
    return dict(row)


def map_approver(conn, *, code: str, user_id, actor_roles_for) -> None:
    department = conn.execute("select id from departments where code = %s and active", (code.strip().upper(),)).fetchone()
    if department is None:
        raise BooksError("department is not on file")
    roles = actor_roles_for(user_id) or []
    if "approver" not in roles and "firm_admin" not in roles:
        raise BooksError("that person is not an approver for this company")
    conn.execute(
        """insert into department_approvers (client_id, department_id, user_id)
           values (app_client_id(), %s, %s) on conflict do nothing""",
        (department["id"], user_id),
    )


def _authorized_approvers(conn, department_id) -> list[dict]:
    rows = conn.execute(
        "select user_id from department_approvers where department_id = %s",
        (department_id,),
    ).fetchall()
    labels = {str(row["user_id"]): row["email"] for row in conn.execute(
        "select user_id, email from client_member_labels(app_client_id())"
    ).fetchall()}
    people = []
    for row in rows:
        # Role check is done by the caller with user_client_roles. Here we only list mapped ids.
        people.append({"user_id": str(row["user_id"]), "email": labels.get(str(row["user_id"]), "")})
    return people


def route_for(conn, document_id) -> dict:
    row = conn.execute(
        """select r.status, r.revision, r.note, r.decided_by, d.code, d.name, d.cost_centre, d.id as department_id
             from bill_routes r
             left join departments d on d.id = r.department_id
            where r.document_id = %s""",
        (document_id,),
    ).fetchone()
    if row is None:
        return {"status": "unassigned", "revision": 0, "department_code": None, "department_name": None,
                "cost_centre": None, "note": "", "approvers": []}
    approvers = _authorized_approvers(conn, row["department_id"]) if row["department_id"] else []
    return {
        "status": row["status"],
        "revision": row["revision"],
        "department_code": row["code"],
        "department_name": row["name"],
        "cost_centre": row["cost_centre"],
        "note": row["note"] or "",
        "approvers": approvers,
    }


def assign_department(conn, *, document_id, code: str, actor_id, role_lookup) -> dict:
    department = conn.execute(
        "select id, code from departments where code = %s and active", (code.strip().upper(),)
    ).fetchone()
    if department is None:
        raise BooksError("department is not on file")
    mapped = conn.execute(
        "select user_id from department_approvers where department_id = %s", (department["id"],)
    ).fetchall()
    authorized = [row["user_id"] for row in mapped if {"approver", "firm_admin"} & set(role_lookup(row["user_id"]) or [])]
    status = "pending" if authorized else "no_approver"
    current = conn.execute("select revision, status from bill_routes where document_id = %s for update", (document_id,)).fetchone()
    revision = 1 if current is None else int(current["revision"]) + 1
    if current is None:
        conn.execute(
            """insert into bill_routes (document_id, client_id, department_id, status, revision, note)
               values (%s, app_client_id(), %s, %s, 1, '')""",
            (document_id, department["id"], status),
        )
    else:
        conn.execute(
            """update bill_routes set department_id = %s, status = %s, revision = %s, note = '',
                      decided_by = null, decided_at = null
                where document_id = %s""",
            (department["id"], status, revision, document_id),
        )
    conn.execute(
        """insert into workflow_events (client_id, document_id, from_status, to_status, action, actor_id, metadata)
           values (app_client_id(), %s, %s, %s, 'department_routed', %s, %s)""",
        (document_id, current["status"] if current else "unassigned", status, actor_id,
         Jsonb({"department": department["code"]})),
    )
    return route_for(conn, document_id)


def department_decision(conn, *, document_id, decision: str, expected_revision: int, actor_id,
                        actor_roles: set[str], editors: set[str], note: str, role_lookup) -> dict:
    if decision not in ("approve", "reject", "admin_fallback"):
        raise BooksError("unknown department decision")
    if str(actor_id) in editors:
        raise PermissionError("editor cannot approve their own bill")
    row = conn.execute(
        "select department_id, status, revision from bill_routes where document_id = %s for update",
        (document_id,),
    ).fetchone()
    if row is None:
        raise BooksError("this bill is not routed to a department")
    if int(row["revision"]) != int(expected_revision):
        raise BooksError("department route changed; refresh before deciding")
    mapped = []
    if row["department_id"]:
        mapped = conn.execute(
            "select user_id from department_approvers where department_id = %s", (row["department_id"],)
        ).fetchall()
    authorized_ids = {str(item["user_id"]) for item in mapped if {"approver", "firm_admin"} & set(role_lookup(item["user_id"]) or [])}
    if decision == "admin_fallback":
        if row["status"] != "no_approver":
            raise PermissionError("admin fallback is only for a department with no approver")
        if "firm_admin" not in actor_roles:
            raise PermissionError("firm admin role required")
        new_status = "admin_fallback"
    elif str(actor_id) not in authorized_ids or not ({"approver", "firm_admin"} & actor_roles):
        raise PermissionError("not the department approver for this company")
    else:
        new_status = "approved" if decision == "approve" else "rejected"
    updated = conn.execute(
        """update bill_routes set status = %s, revision = revision + 1, note = %s, decided_by = %s, decided_at = now()
            where document_id = %s and revision = %s
            returning revision""",
        (new_status, (note or "")[:500], actor_id, document_id, expected_revision),
    ).fetchone()
    if updated is None:
        raise BooksError("department route changed; refresh before deciding")
    conn.execute(
        """insert into workflow_events (client_id, document_id, from_status, to_status, action, actor_id, metadata)
           values (app_client_id(), %s, %s, %s, %s, %s, %s)""",
        (document_id, row["status"], new_status, f"department_{decision}", actor_id, Jsonb({"note": (note or "")[:500]})),
    )
    return route_for(conn, document_id)


def invalidate_department(conn, document_id, actor_id, role_lookup) -> None:
    row = conn.execute(
        "select department_id, status, revision from bill_routes where document_id = %s for update",
        (document_id,),
    ).fetchone()
    if row is None or row["status"] not in ("approved", "admin_fallback", "rejected"):
        return
    mapped = []
    if row["department_id"]:
        mapped = conn.execute(
            "select user_id from department_approvers where department_id = %s", (row["department_id"],)
        ).fetchall()
    authorized = [item for item in mapped if {"approver", "firm_admin"} & set(role_lookup(item["user_id"]) or [])]
    status = "pending" if authorized else "no_approver"
    conn.execute(
        """update bill_routes set status = %s, revision = revision + 1, decided_by = null, decided_at = null,
                  note = 'Cleared because the bill was edited.'
            where document_id = %s""",
        (status, document_id),
    )
    conn.execute(
        """insert into workflow_events (client_id, document_id, from_status, to_status, action, actor_id, metadata)
           values (app_client_id(), %s, %s, %s, 'department_approval_invalidated', %s, '{}')""",
        (document_id, row["status"], status, actor_id),
    )
