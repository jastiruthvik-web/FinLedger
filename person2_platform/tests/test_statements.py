"""Bank lines match an open bill only when the invoice number and the amount both agree."""
from finledger_platform.statements import lines_from_table, match_payments


def test_payment_matching_invoice_number_and_amount_marks_the_bill():
    lines = lines_from_table([
        ["Date", "Narration", "Debit", "Credit"],
        ["2026-10-18", "NEFT HG-1103 Shree Ganesh Metals", "5900", ""],
        ["2026-10-05", "NEFT salary", "", "250000"],
        ["2026-10-19", "NEFT HG-1103 short", "100", ""],
        ["2026-10-20", "NEFT HG-11030", "5900", ""],
    ])
    result = match_payments(lines, [
        {"document_id": "3df15936-2a37-4135-8344-eae02e2e76de", "invoice_no": "HG-1103",
         "amount": "5900.00", "vendor_name": "Shree Ganesh Metals", "status": "approved"},
        {"document_id": "11111111-1111-1111-1111-111111111111", "invoice_no": "HG-1101",
         "amount": "11800", "vendor_name": "Shree Ganesh Metals", "status": "in_review"},
    ])
    by_narration = {line["narration"]: line for line in result["lines"]}
    assert by_narration["NEFT HG-1103 Shree Ganesh Metals"]["status"] == "matched"
    assert by_narration["NEFT HG-1103 Shree Ganesh Metals"]["invoice_no"] == "HG-1103"
    assert by_narration["NEFT salary"]["status"] == "unmatched"
    assert by_narration["NEFT salary"]["document_id"] is None
    assert by_narration["NEFT HG-1103 short"]["status"] == "unmatched"
    assert by_narration["NEFT HG-11030"]["status"] == "unmatched"
    bills = {bill["invoice_no"]: bill["status"] for bill in result["bills"]}
    assert bills == {"HG-1103": "matched", "HG-1101": "unmatched"}


def test_a_second_payment_for_the_same_bill_stays_unmatched():
    lines = lines_from_table([
        ["Date", "Reference", "Debit"],
        ["2026-10-01", "INV-42", "11800"],
        ["2026-10-02", "INV-42", "11800"],
    ])
    result = match_payments(lines, [{
        "document_id": "doc-1", "invoice_no": "INV-42", "amount": 11800, "vendor_name": "Ganesh", "status": "in_review",
    }])
    assert [line["status"] for line in result["lines"]] == ["matched", "unmatched"]
    assert result["bills"][0]["status"] == "matched"
