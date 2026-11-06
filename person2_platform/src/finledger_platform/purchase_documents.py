"""Purchase orders and goods receipts for one client.

Callers run inside ``tenant(conn, client_id)``. The row stores that ``client_id``
and Row Level Security hides every other client. Nothing here inserts a client.

Header helpers stay for bills that only have a quantity and an amount.
Line helpers allocate accepted receipt quantities. A delivery note stays
``pending_review`` until a person accepts it.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from psycopg.types.json import Jsonb


def save_purchase_order(conn, *, po_number: str, quantity, amount, vendor_name: str = "") -> dict:
    row = conn.execute(
        """insert into purchase_orders (client_id, po_number, vendor_name, quantity, amount)
           values (app_client_id(), btrim(%s), btrim(%s), %s, %s)
           on conflict (client_id, po_number) do update
             set vendor_name = excluded.vendor_name,
                 quantity = excluded.quantity,
                 amount = excluded.amount
           returning po_number, vendor_name, quantity, amount""",
        (po_number, vendor_name, quantity, amount),
    ).fetchone()
    return dict(row)


def save_goods_receipt(conn, *, grn_number: str, po_number: str, quantity_received) -> dict:
    row = conn.execute(
        """insert into goods_receipts (client_id, grn_number, po_number, quantity_received)
           values (app_client_id(), btrim(%s), btrim(%s), %s)
           on conflict (client_id, grn_number) do update
             set po_number = excluded.po_number,
                 quantity_received = excluded.quantity_received
           returning grn_number, po_number, quantity_received""",
        (grn_number, po_number, quantity_received),
    ).fetchone()
    return dict(row)


def find_purchase_order(conn, po_number: str | None) -> dict | None:
    number = (po_number or "").strip()
    if not number:
        return None
    row = conn.execute(
        "select po_number, vendor_name, quantity, amount from purchase_orders where po_number = %s",
        (number,),
    ).fetchone()
    return dict(row) if row else None


def find_goods_receipt(conn, grn_number: str | None, po_number: str | None) -> dict | None:
    grn = (grn_number or "").strip()
    if grn:
        row = conn.execute(
            """select grn_number, po_number, quantity_received
               from goods_receipts where grn_number = %s""",
            (grn,),
        ).fetchone()
        return dict(row) if row else None
    po = (po_number or "").strip()
    if not po:
        return None
    rows = conn.execute(
        """select grn_number, po_number, quantity_received
           from goods_receipts where po_number = %s
           order by grn_number""",
        (po,),
    ).fetchall()
    if len(rows) != 1:
        return None
    return dict(rows[0])


class PurchasingError(ValueError):
    pass


class OverAllocated(PurchasingError):
    pass


_QTY = Decimal("0.001")
_PRICE = Decimal("0.0001")
_MONEY = Decimal("0.01")
_DEFAULT_TOLERANCE = {
    "version": 0,
    "qty_abs": Decimal("0"),
    "qty_pct": Decimal("0"),
    "price_abs": Decimal("0.01"),
    "price_pct": Decimal("0"),
    "tax_abs": Decimal("0"),
    "amount_abs": Decimal("0.01"),
    "note": "Built-in exact quantity, 0.01 price, 0.01 amount. Version 0 is not a saved row.",
}


def _q(value, places: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(places, rounding=ROUND_HALF_UP)


def _event(conn, action: str, actor_id, payload: dict) -> None:
    conn.execute(
        "insert into purchasing_events (client_id, action, actor_id, payload) values (app_client_id(), %s, %s, %s)",
        (action, actor_id, Jsonb(payload)),
    )


def _fingerprint(lines: list[dict]) -> tuple:
    return tuple(sorted(
        ((line.get("item_code") or "").casefold(), str(_q(line["quantity"], _QTY)), (line.get("uom") or "").casefold())
        for line in lines
    ))


def save_order(conn, *, po_number: str, vendor_name: str, supplier_gstin: str, currency: str,
               source: str, lines: list[dict], actor_id) -> dict:
    if source not in ("manual", "import"):
        raise PurchasingError("source must be manual or import")
    if not lines or len(lines) > 200:
        raise PurchasingError("a purchase order needs between 1 and 200 lines")
    number = po_number.strip()
    if not number or len(number) > 60:
        raise PurchasingError("purchase order number is required")
    qty = sum((_q(line["quantity"], _QTY) for line in lines), Decimal("0"))
    amount = sum((_q(Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"])), _MONEY) for line in lines), Decimal("0"))
    row = conn.execute(
        """insert into purchase_orders
             (client_id, po_number, vendor_name, quantity, amount, supplier_gstin, currency, source)
           values (app_client_id(), btrim(%s), btrim(%s), %s, %s, btrim(%s), %s, %s)
           on conflict (client_id, po_number) do update
             set vendor_name = excluded.vendor_name, quantity = excluded.quantity, amount = excluded.amount,
                 supplier_gstin = excluded.supplier_gstin, currency = excluded.currency, source = excluded.source
           returning id, po_number, vendor_name, supplier_gstin, currency, source, quantity, amount""",
        (number, vendor_name or "", qty, amount, supplier_gstin or "", currency or "INR", source),
    ).fetchone()
    conn.execute("delete from purchase_order_lines where purchase_order_id = %s", (row["id"],))
    saved = []
    for line in lines:
        saved.append(dict(conn.execute(
            """insert into purchase_order_lines
                 (client_id, purchase_order_id, line_no, item_code, description, uom, quantity, unit_price, tax_rate, currency)
               values (app_client_id(), %s, %s, btrim(%s), btrim(%s), btrim(%s), %s, %s, %s, %s)
               returning line_no, item_code, description, uom, quantity, unit_price, tax_rate, currency""",
            (row["id"], int(line["line_no"]), line.get("item_code") or "", line.get("description") or "",
             line.get("uom") or "", _q(line["quantity"], _QTY), _q(line["unit_price"], _PRICE),
             None if line.get("tax_rate") is None else _q(line["tax_rate"], Decimal("0.0001")),
             line.get("currency") or currency or "INR"),
        ).fetchone()))
    _event(conn, "purchase_order_saved", actor_id, {"po_number": number, "source": source, "lines": len(saved)})
    out = dict(row)
    out["lines"] = saved
    out["sync"] = "manual_or_file_import"
    return out


def save_receipt(conn, *, grn_number: str, po_number: str, document_kind: str, source: str,
                 supplier_gstin: str, currency: str, lines: list[dict], actor_id) -> dict:
    if document_kind not in ("goods_receipt", "delivery_note"):
        raise PurchasingError("document kind must be goods_receipt or delivery_note")
    if source not in ("manual", "import"):
        raise PurchasingError("source must be manual or import")
    if not lines or len(lines) > 200:
        raise PurchasingError("a receipt needs between 1 and 200 lines")
    grn = grn_number.strip()
    po = po_number.strip()
    if not grn or not po:
        raise PurchasingError("goods receipt and purchase order numbers are required")
    order = conn.execute("select id from purchase_orders where po_number = %s", (po,)).fetchone()
    if order is None:
        raise PurchasingError("purchase order is not on file for this company")
    po_lines = {row["line_no"] for row in conn.execute(
        "select line_no from purchase_order_lines where purchase_order_id = %s", (order["id"],)).fetchall()}
    for line in lines:
        if int(line["po_line_no"]) not in po_lines:
            raise PurchasingError(f"purchase order has no line {line['po_line_no']}")
    qty = sum((_q(line["quantity"], _QTY) for line in lines), Decimal("0"))
    fingerprint = _fingerprint(lines)
    duplicate = False
    others = conn.execute(
        """select id, status from goods_receipts
            where po_number = %s and grn_number <> %s and status = 'accepted'""",
        (po, grn),
    ).fetchall()
    for other in others:
        other_lines = conn.execute(
            "select item_code, quantity, uom from goods_receipt_lines where receipt_id = %s", (other["id"],)
        ).fetchall()
        if other_lines and _fingerprint(other_lines) == fingerprint:
            duplicate = True
            break
    if document_kind == "delivery_note":
        status = "duplicate" if duplicate else "pending_review"
    else:
        status = "duplicate" if duplicate else "accepted"
    row = conn.execute(
        """insert into goods_receipts
             (client_id, grn_number, po_number, quantity_received, supplier_gstin, currency, source, document_kind, status)
           values (app_client_id(), btrim(%s), btrim(%s), %s, btrim(%s), %s, %s, %s, %s)
           on conflict (client_id, grn_number) do update
             set po_number = excluded.po_number, quantity_received = excluded.quantity_received,
                 supplier_gstin = excluded.supplier_gstin, currency = excluded.currency,
                 source = excluded.source, document_kind = excluded.document_kind, status = excluded.status
           returning id, grn_number, po_number, quantity_received, document_kind, status, source""",
        (grn, po, qty, supplier_gstin or "", currency or "INR", source, document_kind, status),
    ).fetchone()
    allocated = conn.execute(
        """select count(*) as n from receipt_allocations a
            join goods_receipt_lines l on l.id = a.receipt_line_id
           where l.receipt_id = %s and a.released_at is null""",
        (row["id"],),
    ).fetchone()["n"]
    if allocated:
        raise PurchasingError("this receipt is already allocated to a bill")
    conn.execute("delete from goods_receipt_lines where receipt_id = %s", (row["id"],))
    saved = []
    for line in lines:
        saved.append(dict(conn.execute(
            """insert into goods_receipt_lines
                 (client_id, receipt_id, line_no, po_line_no, item_code, description, uom, quantity, unit_price)
               values (app_client_id(), %s, %s, %s, btrim(%s), btrim(%s), btrim(%s), %s, %s)
               returning id, line_no, po_line_no, item_code, description, uom, quantity, unit_price""",
            (row["id"], int(line["line_no"]), int(line["po_line_no"]), line.get("item_code") or "",
             line.get("description") or "", line.get("uom") or "", _q(line["quantity"], _QTY),
             None if line.get("unit_price") is None else _q(line["unit_price"], _PRICE)),
        ).fetchone()))
    _event(conn, "goods_receipt_saved", actor_id, {
        "grn_number": grn, "po_number": po, "document_kind": document_kind, "status": status, "source": source,
    })
    out = dict(row)
    out["lines"] = saved
    out["counts_as_received"] = status == "accepted"
    out["sync"] = "manual_or_file_import"
    return out


def set_receipt_status(conn, *, grn_number: str, status: str, actor_id, reason: str) -> dict:
    if status not in ("accepted", "rejected"):
        raise PurchasingError("status must be accepted or rejected")
    if len((reason or "").strip()) < 8:
        raise PurchasingError("a short reason is required")
    row = conn.execute(
        """update goods_receipts set status = %s
            where grn_number = %s and status in ('pending_review', 'duplicate')
            returning grn_number, po_number, document_kind, status, quantity_received""",
        (status, grn_number.strip()),
    ).fetchone()
    if row is None:
        raise PurchasingError("receipt is not waiting for review")
    _event(conn, "goods_receipt_reviewed", actor_id, {"grn_number": grn_number.strip(), "status": status, "reason": reason.strip()})
    return dict(row)


def current_tolerance(conn) -> dict:
    row = conn.execute(
        """select version, qty_abs, qty_pct, price_abs, price_pct, tax_abs, amount_abs, note, created_at
             from match_tolerances order by version desc limit 1"""
    ).fetchone()
    if row is None:
        return dict(_DEFAULT_TOLERANCE)
    return dict(row)


def save_tolerance(conn, *, qty_abs, qty_pct, price_abs, price_pct, tax_abs, amount_abs, note: str, actor_id) -> dict:
    version = conn.execute("select coalesce(max(version), 0) + 1 as version from match_tolerances").fetchone()["version"]
    row = conn.execute(
        """insert into match_tolerances
             (client_id, version, qty_abs, qty_pct, price_abs, price_pct, tax_abs, amount_abs, note, created_by)
           values (app_client_id(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
           returning version, qty_abs, qty_pct, price_abs, price_pct, tax_abs, amount_abs, note""",
        (version, qty_abs, qty_pct, price_abs, price_pct, tax_abs, amount_abs, (note or "").strip(), actor_id),
    ).fetchone()
    _event(conn, "tolerance_saved", actor_id, {"version": version})
    return dict(row)


def order_lines(conn, po_number: str | None) -> list[dict]:
    number = (po_number or "").strip()
    if not number:
        return []
    rows = conn.execute(
        """select l.line_no, l.item_code, l.description, l.uom, l.quantity, l.unit_price, l.tax_rate, l.currency,
                  p.po_number, p.supplier_gstin, p.vendor_name, p.currency as order_currency
             from purchase_order_lines l
             join purchase_orders p on p.id = l.purchase_order_id
            where p.po_number = %s
            order by l.line_no""",
        (number,),
    ).fetchall()
    return [dict(row) for row in rows]


def receipts_for_po(conn, po_number: str | None) -> list[dict]:
    number = (po_number or "").strip()
    if not number:
        return []
    headers = conn.execute(
        """select id, grn_number, po_number, document_kind, status, quantity_received, supplier_gstin, currency, source
             from goods_receipts where po_number = %s order by grn_number""",
        (number,),
    ).fetchall()
    out = []
    for header in headers:
        lines = conn.execute(
            """select id, line_no, po_line_no, item_code, description, uom, quantity, unit_price
                 from goods_receipt_lines where receipt_id = %s order by line_no""",
            (header["id"],),
        ).fetchall()
        item = dict(header)
        item.pop("id")
        item["lines"] = [dict(line) for line in lines]
        out.append(item)
    return out


def open_allocations(conn, receipt_line_ids: list, *, exclude_document=None) -> list[dict]:
    if not receipt_line_ids:
        return []
    rows = conn.execute(
        """select receipt_line_id, document_id, invoice_line_no, quantity, kind
             from receipt_allocations
            where released_at is null and receipt_line_id = any(%s)
              and (%s::uuid is null or document_id <> %s)""",
        (receipt_line_ids, exclude_document, exclude_document),
    ).fetchall()
    return [dict(row) for row in rows]


def line_facts(conn, document_id) -> dict[int, dict]:
    rows = conn.execute(
        "select line_no, uom, currency, item_code, po_line_no from invoice_line_facts where document_id = %s",
        (document_id,),
    ).fetchall()
    return {int(row["line_no"]): dict(row) for row in rows}


def save_line_fact(conn, *, document_id, line_no: int, uom: str, currency: str, item_code: str, po_line_no) -> dict:
    row = conn.execute(
        """insert into invoice_line_facts (client_id, document_id, line_no, uom, currency, item_code, po_line_no)
           values (app_client_id(), %s, %s, btrim(%s), btrim(%s), btrim(%s), %s)
           on conflict (document_id, line_no) do update
             set uom = excluded.uom, currency = excluded.currency, item_code = excluded.item_code,
                 po_line_no = excluded.po_line_no
           returning line_no, uom, currency, item_code, po_line_no""",
        (document_id, line_no, uom or "", currency or "", item_code or "", po_line_no),
    ).fetchone()
    return dict(row)


def release_allocations(conn, document_id) -> int:
    row = conn.execute(
        "update receipt_allocations set released_at = now() where document_id = %s and released_at is null",
        (document_id,),
    )
    return row.rowcount


def reserve_allocations(conn, *, document_id, specs: list[dict]) -> None:
    """Reserve or credit quantities. Two callers cannot consume the same received quantity."""
    if not specs:
        return
    line_ids = sorted({spec["receipt_line_id"] for spec in specs}, key=str)
    conn.execute(
        "select id from goods_receipt_lines where id = any(%s) order by id for update",
        (line_ids,),
    )
    existing = conn.execute(
        """select receipt_line_id, invoice_line_no from receipt_allocations
            where document_id = %s and released_at is null""",
        (document_id,),
    ).fetchall()
    if existing:
        return
    for spec in specs:
        try:
            conn.execute(
                """insert into receipt_allocations
                     (client_id, document_id, receipt_line_id, invoice_line_no, quantity, kind)
                   values (app_client_id(), %s, %s, %s, %s, %s)""",
                (document_id, spec["receipt_line_id"], int(spec["invoice_line_no"]),
                 _q(spec["quantity"], _QTY), spec["kind"]),
            )
        except Exception as exc:
            message = str(exc).lower()
            if "over-allocated" in message or "credit exceeds" in message:
                raise OverAllocated(str(exc)) from exc
            raise

