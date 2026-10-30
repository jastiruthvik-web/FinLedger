"""Three-way quantity and amount comparison. No database and no Tally call."""
from decimal import Decimal

from finledger_control.three_way import (
    GST_BLOCK, GRN_MISSING, GRN_QTY, INTRA_BLOCK, INV_AMOUNT, INV_QTY, PO_AMOUNT, PO_MISSING, PO_QTY,
    assess_three_way, offline_xml_posting_block,
)


def _po(qty, amount):
    return {"po_number": "PO-HG-1103", "vendor_name": "Shree Ganesh Metals", "quantity": qty, "amount": amount}


def _grn(qty, number="GRN-HG-1103"):
    return {"grn_number": number, "po_number": "PO-HG-1103", "quantity_received": qty}


def _invoice(qty, amount, **overrides):
    body = {
        "po_number": "PO-HG-1103",
        "grn_number": "GRN-HG-1103",
        "total": amount,
        "line_items": [{"qty": qty, "desc": "HR coil"}],
    }
    body.update(overrides)
    return body


def test_matching_harbour_quantities_and_amounts_agree():
    result = assess_three_way(_invoice(10, "5900.00"), _po(Decimal("10.000"), Decimal("5900.00")), _grn(10), "three_way")
    assert result["matched"] is True
    assert result["holds_review"] is False
    assert result["differences"] == []
    assert result["purchase_order"] == {"po_number": "PO-HG-1103", "quantity": "10", "amount": "5900.00"}
    assert result["goods_receipt"]["quantity_received"] == "10"
    assert result["invoice"] == {"quantity": "10", "amount": "5900.00"}


def test_goods_receipt_quantity_is_the_side_that_differs():
    result = assess_three_way(_invoice(10, 5900), _po(10, 5900), _grn(8), "three_way")
    assert result["matched"] is False
    assert result["holds_review"] is True
    assert result["differences"] == [GRN_QTY]
    assert result["review_note"] == "Needs review. Goods receipt quantity differs."


def test_invoice_quantity_is_named_when_the_order_and_receipt_agree():
    result = assess_three_way(_invoice(8, 5900), _po(10, 5900), _grn(10), "three_way")
    assert result["differences"] == [INV_QTY]


def test_purchase_order_quantity_is_named_when_the_receipt_and_invoice_agree():
    result = assess_three_way(_invoice(10, 5900), _po(12, 5900), _grn(10), "three_way")
    assert result["differences"] == [PO_QTY]


def test_every_different_quantity_is_named():
    result = assess_three_way(_invoice(9, 5900), _po(10, 5900), _grn(8), "three_way")
    assert result["differences"] == [PO_QTY, GRN_QTY, INV_QTY]


def test_purchase_order_amount_is_named_when_quantities_agree():
    result = assess_three_way(_invoice(10, "6000.00"), _po(10, "5900.00"), _grn(10), "three_way")
    assert result["differences"] == [PO_AMOUNT]


def test_missing_order_or_receipt_names_that_side_and_holds_review():
    missing_order = assess_three_way(_invoice(10, 5900), None, _grn(10), "three_way")
    assert missing_order["differences"] == [PO_MISSING]
    assert missing_order["holds_review"] is True
    missing_receipt = assess_three_way(_invoice(10, 5900, grn_number=None), _po(10, 5900), None, "three_way")
    assert missing_receipt["differences"] == [GRN_MISSING]


def test_same_numbers_with_extra_scale_still_agree_and_a_half_up_paisa_does_not():
    agreed = assess_three_way(
        _invoice(Decimal("10.0004"), Decimal("5900.004")),
        _po(Decimal("10"), Decimal("5900.00")),
        _grn(Decimal("10.000")),
        "three_way",
    )
    assert agreed["matched"] is True
    drifted = assess_three_way(_invoice(10, Decimal("5900.005")), _po(10, "5900.00"), _grn(10), "three_way")
    assert drifted["differences"] == [PO_AMOUNT]


def test_invoice_only_does_not_hold_review_when_nothing_is_linked():
    result = assess_three_way({"total": 100, "line_items": [{"qty": 1}]}, None, None, "invoice_only")
    assert result["applicable"] is False
    assert result["holds_review"] is False
    assert result["differences"] == []


def test_invoice_without_a_total_names_the_invoice_amount():
    result = assess_three_way(
        {"po_number": "PO-1", "line_items": [{"qty": 1}]},
        _po(1, 10),
        _grn(1),
        "three_way",
    )
    assert INV_AMOUNT in result["differences"]


def test_offline_xml_refuses_intra_gst_and_leaves_posting_blocked():
    assert offline_xml_posting_block({"gst": {"treatment": "intra", "input_ledgers": [], "tax_breakup": {}}}) == INTRA_BLOCK
    assert "blocked" in INTRA_BLOCK.lower()
    assert offline_xml_posting_block({"gst": {"treatment": "exempt", "input_ledgers": [], "tax_breakup": {}}}) is None
    assert offline_xml_posting_block({"gst": {"treatment": "exempt", "input_ledgers": [], "tax_breakup": {"CGST": 1}}}) == GST_BLOCK
    assert offline_xml_posting_block({"gst": {"treatment": "inter", "input_ledgers": [], "tax_breakup": {}}}) == GST_BLOCK
    assert offline_xml_posting_block(None) is None
