import uuid

from contracts.schemas import CanonicalInvoice
from usage.provider import MockProvider

_MARKDOWN = "\n".join([
    "Vendor: Local Tech Solutions",
    "GSTIN: 29ABCDE1234F1Z5",
    "Inv No: INV-1001",
    "Date: 2026-09-01",
    "Total Taxable: 100",
    "Total: 118",
    "| item | hsn | qty | rate | taxable | cgst | sgst | igst |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    "| Steel | 7208 | 1 | 100 | 100 | 9 | 9 | 0 |",
])


def test_mock_extract_keeps_vendor_identity_for_a_positive_invoice():
    document_id = str(uuid.uuid4())
    raw = MockProvider()._extract(document_id, {"markdown": _MARKDOWN})
    payload = CanonicalInvoice.model_validate(raw).model_dump(mode="json")
    assert payload["total"] > 0
    assert len(payload["line_items"]) >= 1
    assert payload["invoice_no"] == "INV-1001"
    assert payload["vendor"]["pan"] == "ABCDE1234F"
    assert "state" in payload["vendor"]
    assert payload["cess"] == 0
    assert "raw_markdown_path" in payload
