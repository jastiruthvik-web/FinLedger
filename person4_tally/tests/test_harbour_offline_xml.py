"""The approved Harbour GST bill cannot become an offline Tally voucher.

preview_purchase_xml refuses GST drafts before it writes XML and before any transport exists.
This test uses the HG-1103 draft shape. It does not post, and it does not claim a post.
"""
from decimal import Decimal

import pytest

from finledger_tally import DraftRejected, LedgerMasters, preview_purchase_xml
from test_voucher_xml import COMPANY

DOCUMENT = "3df15936-2a37-4135-8344-eae02e2e76de"
CLIENT = "3d6a2894-ca4a-4bd9-96c2-049ed15cbcdb"
PARTY = "Shree Ganesh Metals"
PURCHASE = "Purchases - Steel"
CGST = "Input CGST"
SGST = "Input SGST"


def test_approved_harbour_gst_bill_is_refused_without_writing_xml_or_posting():
    masters = LedgerMasters(COMPANY.guid, frozenset({PARTY, PURCHASE, CGST, SGST}))
    job = {
        "document_id": DOCUMENT,
        "client_id": CLIENT,
        "revision": 1,
        "idempotency_key": f"{DOCUMENT}:r1",
        "voucher_draft": {
            "document_id": DOCUMENT,
            "date": "2026-10-18",
            "voucher_type": "purchase",
            "party_ledger": PARTY,
            "party_create_proposal": False,
            "lines": [
                {"ledger": PURCHASE, "amount": "5000.00", "is_debit": True, "cost_centre": None},
                {"ledger": CGST, "amount": "450.00", "is_debit": True, "cost_centre": None},
                {"ledger": SGST, "amount": "450.00", "is_debit": True, "cost_centre": None},
            ],
            "gst": {"treatment": "intra", "input_ledgers": [CGST, SGST], "tax_breakup": {"CGST": 450.0, "SGST": 450.0}},
            "tds": {"applicable": False, "section": None, "ledger": None, "amount": "0"},
            "bill_wise": {"ref_type": "new_ref", "ref": "HG-1103", "due_date": "2026-10-18"},
            "narration": "Purchase of HR coil from Shree Ganesh Metals against invoice HG-1103 dated 2026-10-18.",
            "attachment_document_id": DOCUMENT,
            "reasons": ["mapped from Harbour books"],
            "map_trace_id": "c86d5788-2796-4f76-97a5-752f622c811b",
        },
    }
    with pytest.raises(DraftRejected) as caught:
        preview_purchase_xml(
            job, company=COMPANY, expected_company_name=COMPANY.name,
            masters=masters, expected_total=Decimal("5900.00"),
        )
    assert "unsupported_tax" in caught.value.codes
    assert not hasattr(caught.value, "xml")
