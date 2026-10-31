"""Purchase orders and goods receipts for one client.

Callers run inside ``tenant(conn, client_id)``. The row stores that ``client_id``
and Row Level Security hides every other client. Nothing here inserts a client.
"""
from __future__ import annotations


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
