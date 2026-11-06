"""Compare invoice lines with purchase-order lines and accepted receipts.

Unknown unit, currency, or tax is not a match. Pending delivery notes and
duplicate receipts do not count as received goods. Quantity above the open
receipt cannot be overridden.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_QTY = Decimal("0.001")
_PRICE = Decimal("0.0001")
_MONEY = Decimal("0.01")

_UOM = {
    "nos": "nos", "no": "nos", "pcs": "nos", "pc": "nos", "piece": "nos", "pieces": "nos",
    "unit": "nos", "units": "nos", "kg": "kg", "kgs": "kg", "kilogram": "kg",
    "mtr": "mtr", "meter": "mtr", "metre": "mtr", "ltr": "ltr", "litre": "ltr", "liter": "ltr",
}
_CCY = {"inr": "INR", "rs": "INR", "₹": "INR", "rupee": "INR", "rupees": "INR", "usd": "USD", "eur": "EUR"}

SOURCE_LABEL = "Manual or file import. Not a live purchasing sync."


def assess_lines(*, invoice: dict, po_lines: list[dict], receipts: list[dict], allocations: list[dict],
                 tolerance: dict, match_mode: str) -> dict:
    po_number = _text(invoice.get("po_number")) or _text((po_lines[0] if po_lines else {}).get("po_number"))
    invoice_lines = _invoice_lines(invoice)
    linked, unlink_notes = _link(invoice_lines, po_lines)
    accepted = [row for row in receipts if row.get("status") == "accepted" and row.get("lines")]
    ignored = [
        {"grn_number": row.get("grn_number"), "status": row.get("status"), "document_kind": row.get("document_kind")}
        for row in receipts if row.get("status") != "accepted"
    ]
    credit = (invoice.get("document_type") or "") == "credit_note"
    supplier = _supplier_problem(invoice, po_lines)
    blocked: list[str] = []
    overridable: list[str] = []
    admin_overridable: list[str] = []
    differences: list[str] = []
    if supplier:
        blocked.append(supplier)
        differences.append("Supplier on the invoice is not the supplier on the purchase order.")
    comparisons = []
    reservation: list[dict] = []
    for pair in linked:
        comparison, plan, pair_blocked, pair_over, pair_admin = _compare_pair(
            pair, accepted, allocations, tolerance, credit=credit,
        )
        comparisons.append(comparison)
        for spec in plan:
            spec["invoice_line_no"] = pair["invoice"]["line_no"]
        reservation.extend(plan)
        for code in pair_blocked:
            if code not in blocked:
                blocked.append(code)
        for code in pair_over:
            if code not in overridable:
                overridable.append(code)
        for code in pair_admin:
            if code not in admin_overridable:
                admin_overridable.append(code)
        differences.extend(comparison["problems"])
    if unlink_notes:
        overridable.append("unlinked_lines")
        differences.extend(unlink_notes)
    if not po_lines:
        blocked.append("purchase_order_lines_missing")
        differences.append("Purchase order lines are not on file.")
    if po_lines and not accepted and not credit:
        blocked.append("accepted_receipt_missing")
        differences.append("No accepted goods receipt is on file. A delivery note stays out until someone accepts it.")
    partial = any("partial invoice" in note for row in comparisons for note in row.get("notes") or [])
    matched = not blocked and not overridable and not admin_overridable and bool(linked) and not unlink_notes
    policy_hold = match_mode == "three_way" and not matched
    quantity_hold = any(code.startswith("quantity_") or code.startswith("credit_") or code in {
        "supplier_mismatch", "accepted_receipt_missing", "purchase_order_lines_missing",
    } for code in blocked)
    holds = policy_hold or quantity_hold
    received_qty = sum((_dec(line.get("quantity")) or Decimal("0") for row in accepted for line in row.get("lines") or []), Decimal("0"))
    invoice_qty = sum((_dec(line.get("qty")) or Decimal("0") for line in invoice_lines), Decimal("0"))
    return {
        "basis": "lines",
        "path": "po",
        "applicable": True,
        "matched": matched,
        "partial": partial,
        "holds_review": holds,
        "match_mode": match_mode,
        "differences": differences,
        "review_note": ("Needs review. " + " ".join(differences)) if holds and differences else "",
        "blocked": blocked,
        "overridable": overridable,
        "admin_overridable": admin_overridable,
        "lines": comparisons,
        "reservation": [_jsonable_spec(spec) for spec in reservation] if not quantity_hold else [],
        "ignored_receipts": ignored,
        "tolerance": _tolerance_view(tolerance),
        "source_label": SOURCE_LABEL,
        "purchase_order": {
            "po_number": po_number or None,
            "quantity": _fmt_qty(_sum_po_qty(po_lines)) if po_lines else None,
            "amount": _fmt_money(_sum_po_amount(po_lines)) if po_lines else None,
        },
        "goods_receipt": {
            "grn_number": ", ".join(row["grn_number"] for row in accepted) or None,
            "quantity_received": _fmt_qty(received_qty) if accepted else None,
        },
        "invoice": {
            "quantity": _fmt_qty(invoice_qty) if invoice_lines else None,
            "amount": _fmt_money(_dec(invoice.get("total"))),
        },
    }


def _compare_pair(pair, accepted, allocations, tolerance, *, credit: bool):
    invoice_line = pair["invoice"]
    po_line = pair["po"]
    notes: list[str] = []
    blocked: list[str] = []
    overridable: list[str] = []
    admin_overridable: list[str] = []
    po_currency = _currency(po_line.get("currency") or po_line.get("order_currency"))
    inv_currency = _currency(invoice_line.get("currency"))
    if po_currency and inv_currency and po_currency != inv_currency:
        blocked.append("currency_mismatch")
        notes.append(f"Line {invoice_line['line_no']} currency {inv_currency} is not {po_currency}.")
    elif not po_currency or not inv_currency:
        overridable.append("currency_unknown")
        notes.append(f"Line {invoice_line['line_no']} currency is unknown.")
    po_uom = _uom(po_line.get("uom"))
    inv_uom = _uom(invoice_line.get("uom"))
    if po_uom and inv_uom and po_uom != inv_uom:
        admin_overridable.append("uom_mismatch")
        notes.append(f"Line {invoice_line['line_no']} unit {inv_uom} is not {po_uom}.")
    elif not po_uom or not inv_uom:
        overridable.append("uom_unknown")
        notes.append(f"Line {invoice_line['line_no']} unit of measure is unknown.")
    price_ok = _within(invoice_line.get("rate"), po_line.get("unit_price"), tolerance["price_abs"], tolerance["price_pct"])
    if price_ok is None:
        overridable.append("price_unknown")
        notes.append(f"Line {invoice_line['line_no']} price is unknown.")
    elif not price_ok:
        admin_overridable.append("price_outside_tolerance")
        notes.append(f"Line {invoice_line['line_no']} price is outside the saved tolerance.")
    tax_ok = _within(invoice_line.get("tax_rate"), po_line.get("tax_rate"), tolerance["tax_abs"], Decimal("0"))
    if tax_ok is None:
        overridable.append("tax_unknown")
        notes.append(f"Line {invoice_line['line_no']} tax rate is unknown.")
    elif not tax_ok:
        admin_overridable.append("tax_outside_tolerance")
        notes.append(f"Line {invoice_line['line_no']} tax rate is outside the saved tolerance.")
    pools = _pools(accepted, allocations, int(po_line["line_no"]))
    invoice_qty = _dec(invoice_line.get("qty")) or Decimal("0")
    received = sum((pool["received"] for pool in pools), Decimal("0"))
    already = sum((pool["allocated"] for pool in pools), Decimal("0"))
    available = received - already
    plan: list[dict] = []
    if credit:
        plan, left = _draw(pools, invoice_qty, credit=True)
        if left > _limit(invoice_qty, tolerance["qty_abs"], tolerance["qty_pct"]):
            blocked.append("credit_exceeds_invoiced")
            notes.append(f"Line {invoice_line['line_no']} credits more than the quantity already invoiced.")
            plan = []
    else:
        remaining_order = (_dec(po_line.get("quantity")) or Decimal("0")) - already
        if invoice_qty - remaining_order > _limit(invoice_qty, tolerance["qty_abs"], tolerance["qty_pct"]):
            blocked.append("quantity_over_order")
            notes.append(f"Line {invoice_line['line_no']} is above the open purchase-order quantity.")
        if invoice_qty - available > _limit(invoice_qty, tolerance["qty_abs"], tolerance["qty_pct"]):
            blocked.append("quantity_over_received")
            notes.append(f"Line {invoice_line['line_no']} is above the accepted receipt quantity still open.")
        else:
            plan, left = _draw(pools, invoice_qty, credit=False)
            if left > _limit(invoice_qty, tolerance["qty_abs"], tolerance["qty_pct"]):
                blocked.append("quantity_over_received")
                notes.append(f"Line {invoice_line['line_no']} is above the accepted receipt quantity still open.")
                plan = []
            elif invoice_qty < (_dec(po_line.get("quantity")) or Decimal("0")):
                notes.append(f"Line {invoice_line['line_no']} is a partial invoice. Uninvoiced quantity stays open.")
    problems = [note for note in notes if "partial invoice" not in note]
    comparison = {
        "invoice_line_no": invoice_line["line_no"],
        "po_line_no": po_line["line_no"],
        "method": pair["method"],
        "invoice_qty": _fmt_qty(invoice_qty),
        "po_qty": _fmt_qty(_dec(po_line.get("quantity"))),
        "received_qty": _fmt_qty(received),
        "already_invoiced_qty": _fmt_qty(already),
        "available_qty": _fmt_qty(available),
        "uom": inv_uom or po_uom or None,
        "currency": inv_currency or po_currency or None,
        "problems": problems,
        "notes": notes,
    }
    return comparison, plan, blocked, overridable, admin_overridable


def _pools(accepted, allocations, po_line_no: int) -> list[dict]:
    pools = []
    for receipt in accepted:
        for line in receipt.get("lines") or []:
            if int(line["po_line_no"]) != po_line_no:
                continue
            allocated = sum(
                (_dec(row.get("quantity")) or Decimal("0") for row in allocations if str(row.get("receipt_line_id")) == str(line["id"])),
                Decimal("0"),
            )
            pools.append({
                "id": line["id"],
                "grn_number": receipt.get("grn_number"),
                "received": _dec(line.get("quantity")) or Decimal("0"),
                "allocated": allocated,
                "line_no": int(line["line_no"]),
            })
    pools.sort(key=lambda pool: (pool["grn_number"] or "", pool["line_no"]))
    return pools


def _draw(pools, need: Decimal, *, credit: bool):
    plan = []
    left = need
    for pool in pools:
        if left <= 0:
            break
        room = pool["allocated"] if credit else pool["received"] - pool["allocated"]
        take = min(room, left)
        if take <= 0:
            continue
        plan.append({
            "receipt_line_id": pool["id"],
            "quantity": -take if credit else take,
            "kind": "credit" if credit else "reserve",
        })
        left -= take
    return plan, left


def _link(invoice_lines, po_lines):
    used: set[int] = set()
    pairs = []
    notes = []
    for line in invoice_lines:
        hit = None
        method = ""
        if line.get("po_line_no"):
            found = [row for row in po_lines if int(row["line_no"]) == int(line["po_line_no"])]
            if len(found) == 1:
                hit, method = found[0], "po_line_no"
        if hit is None and _text(line.get("item_code")):
            found = [row for row in po_lines if _text(row.get("item_code")).casefold() == _text(line["item_code"]).casefold()
                     and int(row["line_no"]) not in used]
            if len(found) == 1:
                hit, method = found[0], "item_code"
            elif len(found) > 1:
                notes.append(f"Line {line['line_no']} matches more than one purchase-order line.")
                continue
        if hit is None and _norm(line.get("description")):
            found = [row for row in po_lines if _norm(row.get("description")) == _norm(line.get("description"))
                     and int(row["line_no"]) not in used]
            if len(found) == 1:
                hit, method = found[0], "description"
        if hit is None:
            notes.append(f"Line {line['line_no']} is not linked to a purchase-order line.")
            continue
        if int(hit["line_no"]) in used:
            notes.append(f"Line {line['line_no']} repeats a purchase-order line already used.")
            continue
        used.add(int(hit["line_no"]))
        pairs.append({"invoice": line, "po": hit, "method": method})
    return pairs, notes


def _supplier_problem(invoice, po_lines) -> str | None:
    if not po_lines:
        return None
    po_gstin = _text(po_lines[0].get("supplier_gstin")).upper()
    inv_gstin = _text((invoice.get("vendor") or {}).get("gstin")).upper()
    if po_gstin and inv_gstin and po_gstin != inv_gstin:
        return "supplier_mismatch"
    return None


def _invoice_lines(invoice: dict) -> list[dict]:
    rows = []
    for index, raw in enumerate(invoice.get("line_items") or [], start=1):
        if not isinstance(raw, dict):
            continue
        facts = raw.get("_facts") if isinstance(raw.get("_facts"), dict) else {}
        rows.append({
            "line_no": index,
            "description": raw.get("desc") or "",
            "item_code": facts.get("item_code") or raw.get("item_code") or "",
            "uom": facts.get("uom") or raw.get("uom") or "",
            "currency": facts.get("currency") or raw.get("currency") or invoice.get("currency") or "",
            "qty": raw.get("qty"),
            "rate": raw.get("rate"),
            "tax_rate": raw.get("tax_rate"),
            "po_line_no": facts.get("po_line_no") if facts.get("po_line_no") else raw.get("po_line_no"),
        })
    return rows


def _within(left, right, abs_tol, pct_tol):
    left_n, right_n = _dec(left), _dec(right)
    if left_n is None or right_n is None:
        return None
    return abs(left_n - right_n) <= max(_dec(abs_tol) or Decimal("0"), abs(right_n) * (_dec(pct_tol) or Decimal("0")))


def _limit(qty: Decimal, abs_tol, pct_tol) -> Decimal:
    return max(_dec(abs_tol) or Decimal("0"), abs(qty) * (_dec(pct_tol) or Decimal("0")))


def _sum_po_qty(lines):
    return sum((_dec(line.get("quantity")) or Decimal("0") for line in lines), Decimal("0")).quantize(_QTY)


def _sum_po_amount(lines):
    total = Decimal("0")
    for line in lines:
        qty, price = _dec(line.get("quantity")), _dec(line.get("unit_price"))
        if qty is None or price is None:
            continue
        total += qty * price
    return total.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _tolerance_view(tolerance: dict) -> dict:
    return {
        "version": int(tolerance.get("version") or 0),
        "qty_abs": _fmt_qty(_dec(tolerance.get("qty_abs")) or Decimal("0")),
        "qty_pct": _fmt_qty(_dec(tolerance.get("qty_pct")) or Decimal("0")),
        "price_abs": _fmt_money(_dec(tolerance.get("price_abs")) or Decimal("0")),
        "price_pct": _fmt_qty(_dec(tolerance.get("price_pct")) or Decimal("0")),
        "tax_abs": _fmt_qty(_dec(tolerance.get("tax_abs")) or Decimal("0")),
        "amount_abs": _fmt_money(_dec(tolerance.get("amount_abs")) or Decimal("0")),
        "note": tolerance.get("note") or "",
    }


def _jsonable_spec(spec: dict) -> dict:
    return {
        "receipt_line_id": spec["receipt_line_id"],
        "invoice_line_no": spec.get("invoice_line_no"),
        "quantity": _fmt_qty(_dec(spec["quantity"])),
        "kind": spec["kind"],
    }


def _uom(value) -> str:
    text = _text(value).casefold()
    if not text:
        return ""
    return _UOM.get(text, text)


def _currency(value) -> str:
    text = _text(value)
    if not text:
        return ""
    return _CCY.get(text.casefold(), text.upper() if len(text) == 3 else "")


def _norm(value) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _text(value).casefold()))


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _dec(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _fmt_qty(value) -> str | None:
    if value is None:
        return None
    text = format(_dec(value).quantize(_QTY, rounding=ROUND_HALF_UP), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _fmt_money(value) -> str | None:
    number = _dec(value)
    if number is None:
        return None
    return format(number.quantize(_MONEY, rounding=ROUND_HALF_UP), "f")
