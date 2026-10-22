import json
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.schemas import CanonicalInvoice
from finledger_control.boundary import CanonicalInvoiceBoundary, Vendor, validate_invoice
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


def test_mock_score_payload_validates_and_unknown_vendor_field_fails():
    document_id = str(uuid.uuid4())
    raw = MockProvider()._extract(document_id, {"markdown": _MARKDOWN})
    payload = CanonicalInvoice.model_validate(raw).model_dump(mode="json")
    validated, total = validate_invoice(payload, document_id)
    assert total > 0
    assert validated["line_items"]
    assert validated["vendor"]["pan"] == "ABCDE1234F"
    assert Vendor.model_config["extra"] == "forbid"
    assert CanonicalInvoiceBoundary.model_config["extra"] == "forbid"
    payload["vendor"]["nickname"] = "nope"
    with pytest.raises(ValidationError):
        validate_invoice(payload, document_id)


def test_person1_golden_invoice_validates_for_score():
    golden_path = Path(__file__).resolve().parents[2] / "packages" / "contracts" / "golden" / "intra_gst_18.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    document_id = str(uuid.uuid4())
    golden["document_id"] = document_id
    validated, total = validate_invoice(golden, document_id)
    assert total > 0
    assert validated["vendor"]["pan"] == "ABCDE1234F"
    assert validated["vendor"]["state"] == "Karnataka"
    assert validated["bank_upi"] == "localtech@upi"
    golden["vendor"]["nickname"] = "nope"
    with pytest.raises(ValidationError):
        validate_invoice(golden, document_id)
