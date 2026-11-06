"""Expense suggestions read saved corrections and do not invent a party ledger."""
from finledger_control.gl_suggest import suggest_expense_ledgers


def _correction(row_id, ledger, description, hsn="", gstin="27AAACS1234A1Z2"):
    return {
        "id": row_id, "field": "expense_ledger", "vendor_gstin": gstin, "description": description,
        "hsn": hsn, "created_at": f"2026-11-0{row_id}",
        "new_value": {"ledger": ledger, "description": description, "hsn": hsn},
    }


def test_one_vendor_can_have_two_expense_ledgers_and_a_conflict_abstains():
    corrections = [
        _correction(1, "Stores", "bearings", "8482"),
        _correction(2, "Professional fees", "consulting", "9983"),
        {"id": 3, "field": "party_ledger", "vendor_gstin": "27AAACS1234A1Z2", "description": "bearings",
         "hsn": "8482", "new_value": "Shree Ganesh Metals", "created_at": "2026-11-03"},
    ]
    lines = [
        {"description": "bearings", "hsn": "8482"},
        {"description": "consulting", "hsn": "9983"},
    ]
    suggestions = suggest_expense_ledgers(lines, corrections, vendor_gstin="27AAACS1234A1Z2")
    assert suggestions[0]["ledger"] == "Stores"
    assert suggestions[1]["ledger"] == "Professional fees"
    assert all(item["abstained"] is False for item in suggestions)
    conflict = suggest_expense_ledgers(
        [{"description": "bearings", "hsn": "8482"}],
        corrections + [_correction(4, "Inventory", "bearings", "8482")],
        vendor_gstin="27AAACS1234A1Z2",
    )
    assert conflict[0]["abstained"] is True
    assert conflict[0]["ledger"] is None
    other_company = suggest_expense_ledgers(lines, corrections, vendor_gstin="29ABCDE1234F1Z5")
    assert other_company[0]["abstained"] is True


def test_vendor_wide_expense_does_not_replace_a_line_rule():
    corrections = [
        _correction(1, "Purchases", ""),
        _correction(2, "Stores", "bearings", "8482"),
    ]
    line = suggest_expense_ledgers(
        [{"description": "bearings", "hsn": "8482"}], corrections, vendor_gstin="27AAACS1234A1Z2",
    )[0]
    assert line["ledger"] == "Stores"
    assert line["scope"] == "line"
    wide = suggest_expense_ledgers(
        [{"description": "something else", "hsn": "9999"}], corrections, vendor_gstin="27AAACS1234A1Z2",
    )[0]
    assert wide["ledger"] == "Purchases"
    assert wide["confidence"] == "low"
    assert wide["scope"] == "vendor"
