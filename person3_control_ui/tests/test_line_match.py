"""Line matching without a database. Unknowns are not treated as a match."""
from decimal import Decimal

from finledger_control.line_match import assess_lines

TOLERANCE = {
    "version": 0, "qty_abs": Decimal("0"), "qty_pct": Decimal("0"),
    "price_abs": Decimal("0.01"), "price_pct": Decimal("0"),
    "tax_abs": Decimal("0"), "amount_abs": Decimal("0.01"), "note": "built-in",
}


def _po_line(**overrides):
    line = {
        "line_no": 1, "item_code": "HR", "description": "HR coil", "uom": "NOS",
        "quantity": Decimal("10"), "unit_price": Decimal("500"), "tax_rate": Decimal("18"),
        "currency": "INR", "supplier_gstin": "27AAACS1234A1Z2", "po_number": "PO-1",
    }
    line.update(overrides)
    return line


def _receipt(qty, *, status="accepted", kind="goods_receipt", number="GRN-1", line_id="line-1"):
    return {
        "grn_number": number, "status": status, "document_kind": kind, "lines": [{
            "id": line_id, "line_no": 1, "po_line_no": 1, "item_code": "HR",
            "description": "HR coil", "uom": "NOS", "quantity": Decimal(str(qty)), "unit_price": Decimal("500"),
        }],
    }


def _invoice(qty, **overrides):
    body = {
        "document_type": "purchase_invoice",
        "po_number": "PO-1",
        "vendor": {"gstin": "27AAACS1234A1Z2", "name": "Shree Ganesh Metals"},
        "currency": "INR",
        "total": Decimal(qty) * Decimal("590"),
        "line_items": [{
            "desc": "HR coil", "item_code": "HR", "uom": "NOS", "currency": "INR",
            "qty": qty, "rate": "500", "tax_rate": "18",
        }],
    }
    body.update(overrides)
    return body


def test_partial_receipts_sum_and_a_delivery_note_does_not_count():
    result = assess_lines(
        invoice=_invoice(10), po_lines=[_po_line()],
        receipts=[_receipt(6, number="GRN-1", line_id="a"), _receipt(4, number="GRN-2", line_id="b"),
                  _receipt(10, status="pending_review", kind="delivery_note", number="DN-1", line_id="c")],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is True
    assert result["lines"][0]["received_qty"] == "10"
    assert result["reservation"][0]["quantity"] in {"6", "4"}
    assert sum(Decimal(row["quantity"]) for row in result["reservation"]) == Decimal("10")
    assert result["ignored_receipts"][0]["status"] == "pending_review"


def test_duplicate_receipt_is_not_available_quantity():
    result = assess_lines(
        invoice=_invoice(10), po_lines=[_po_line()],
        receipts=[_receipt(10, line_id="a"), _receipt(10, status="duplicate", number="GRN-COPY", line_id="b")],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is True
    assert result["lines"][0]["received_qty"] == "10"


def test_already_invoiced_quantity_blocks_a_second_full_bill():
    result = assess_lines(
        invoice=_invoice(8), po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[{"receipt_line_id": "line-1", "quantity": Decimal("6"), "document_id": "other"}],
        tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is False
    assert "quantity_over_received" in result["blocked"]
    assert result["reservation"] == []


def test_partial_invoice_leaves_the_rest_open():
    result = assess_lines(
        invoice=_invoice(4), po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is True
    assert result["reservation"] == [{
        "receipt_line_id": "line-1", "invoice_line_no": 1, "quantity": "4", "kind": "reserve",
    }]


def test_unknown_unit_currency_and_price_do_not_match():
    invoice = _invoice(10)
    invoice["line_items"][0]["uom"] = ""
    invoice["line_items"][0]["currency"] = ""
    invoice["currency"] = ""
    invoice["line_items"][0]["rate"] = None
    result = assess_lines(
        invoice=invoice, po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is False
    assert "uom_unknown" in result["overridable"]
    assert "currency_unknown" in result["overridable"]
    assert "price_unknown" in result["overridable"]


def test_currency_mismatch_and_supplier_mismatch_cannot_be_overridden_by_code():
    wrong_money = assess_lines(
        invoice=_invoice(10, currency="USD", line_items=[{
            "desc": "HR coil", "item_code": "HR", "uom": "NOS", "currency": "USD",
            "qty": 10, "rate": "500", "tax_rate": "18",
        }]),
        po_lines=[_po_line()], receipts=[_receipt(10)], allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert "currency_mismatch" in wrong_money["blocked"]
    wrong_supplier = assess_lines(
        invoice=_invoice(10, vendor={"gstin": "29ABCDE1234F1Z5", "name": "Other"}),
        po_lines=[_po_line()], receipts=[_receipt(10)], allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert "supplier_mismatch" in wrong_supplier["blocked"]


def test_credit_cannot_exceed_the_quantity_already_invoiced():
    credited = assess_lines(
        invoice=_invoice(4, document_type="credit_note"), po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[{"receipt_line_id": "line-1", "quantity": Decimal("4")}],
        tolerance=TOLERANCE, match_mode="three_way",
    )
    assert credited["matched"] is True
    assert credited["reservation"][0]["kind"] == "credit"
    assert credited["reservation"][0]["quantity"] == "-4"
    too_much = assess_lines(
        invoice=_invoice(5, document_type="credit_note"), po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[{"receipt_line_id": "line-1", "quantity": Decimal("4")}],
        tolerance=TOLERANCE, match_mode="three_way",
    )
    assert "credit_exceeds_invoiced" in too_much["blocked"]


def test_price_outside_the_tolerance_is_not_a_match():
    invoice = _invoice(10)
    invoice["line_items"][0]["rate"] = "510"
    result = assess_lines(
        invoice=invoice, po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is False
    assert "price_outside_tolerance" in result["admin_overridable"]


def test_unlinked_description_is_not_forced_onto_the_only_order_line():
    invoice = _invoice(10)
    invoice["line_items"][0]["desc"] = "Consulting"
    invoice["line_items"][0]["item_code"] = ""
    result = assess_lines(
        invoice=invoice, po_lines=[_po_line()], receipts=[_receipt(10)],
        allocations=[], tolerance=TOLERANCE, match_mode="three_way",
    )
    assert result["matched"] is False
    assert "unlinked_lines" in result["overridable"]
