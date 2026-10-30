"""One Harbour client keeps its purchase order and goods receipt, and the bill page can match them.

Another client with the same order number cannot see those rows. A mismatch stays in
needs review and names the goods receipt. Offline XML still refuses the intra-GST draft,
so approval does not queue a post.
"""
import hashlib
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from finledger_control.api import create_app
from finledger_control.service import Conflict, ControlService
from finledger_control.three_way import INTRA_BLOCK
from finledger_platform.db import firm, tenant
from finledger_platform.purchase_documents import find_goods_receipt, find_purchase_order, save_goods_receipt, save_purchase_order
from finledger_platform.tenancy import add_member, create_client
from test_desk_api import SAME_ORIGIN
from test_service import canonical, draft

PO = "PO-HG-1103"
GRN_MATCH = "GRN-HG-1103"
GRN_SHORT = "GRN-HG-1104"
MATCHED = "33333333-3333-3333-3333-333333333333"
SHORT = "44444444-4444-4444-4444-444444444444"


def _document(conn, client_id, document_id, name):
    with tenant(conn, client_id):
        conn.execute(
            """insert into documents(id,client_id,channel,object_path,original_filename,content_hash,mime,size_bytes,status,virus_ok,source_meta)
               values (%s,%s,'link',%s,%s,%s,'application/pdf',100,'extracted',true,'{}')""",
            (document_id, client_id, f"{client_id}/2026/10/{document_id}/raw.pdf", name,
             hashlib.sha256(document_id.encode()).hexdigest()),
        )


def _invoice(document_id, number, grn):
    return canonical(
        document_id,
        invoice_no=number,
        po_number=PO,
        grn_number=grn,
        taxable=5000,
        cgst=450,
        sgst=450,
        igst=0,
        total=5900,
        line_items=[{
            "desc": "HR coil", "hsn_sac": "7208", "qty": 10, "rate": 500,
            "taxable": 5000, "tax_rate": 18, "tax_amount": 900,
        }],
    )


def test_harbour_bill_matches_its_own_order_and_receipt_and_blocks_intra_gst_posting(pool, conn, world):
    firm_id = world["client"]["firm_id"]
    with firm(conn, firm_id):
        harbour = create_client(
            conn, "Harbour Mills", inbound_slug="harbour-mills",
            policy={"match_mode": "three_way", "maker_checker": True, "auto_post_cap": 25000},
        )
        add_member(conn, harbour["id"], world["clerk"], "ap_clerk")
        add_member(conn, harbour["id"], world["approver"], "approver")
    harbour_id = harbour["id"]
    acme_id = world["client"]["id"]
    with tenant(conn, harbour_id):
        save_purchase_order(conn, po_number=PO, quantity=Decimal("10"), amount=Decimal("5900.00"),
                            vendor_name="Shree Ganesh Metals")
        save_goods_receipt(conn, grn_number=GRN_MATCH, po_number=PO, quantity_received=Decimal("10"))
        save_goods_receipt(conn, grn_number=GRN_SHORT, po_number=PO, quantity_received=Decimal("8"))
    with tenant(conn, acme_id):
        save_purchase_order(conn, po_number=PO, quantity=Decimal("99"), amount=Decimal("1.00"), vendor_name="Other mill")
        assert find_purchase_order(conn, PO)["quantity"] == Decimal("99.000")
        assert find_goods_receipt(conn, GRN_MATCH, PO) is None
        assert conn.execute("select count(*) as n from goods_receipts").fetchone()["n"] == 0
    with tenant(conn, harbour_id):
        assert find_purchase_order(conn, PO)["quantity"] == Decimal("10.000")
        assert find_goods_receipt(conn, GRN_MATCH, PO)["quantity_received"] == Decimal("10.000")
        assert conn.execute("select count(*) as n from purchase_orders").fetchone()["n"] == 1

    service = ControlService(conn)
    _document(conn, harbour_id, MATCHED, "hg-1103.pdf")
    _document(conn, harbour_id, SHORT, "hg-1104.pdf")
    service.score(harbour_id, MATCHED, _invoice(MATCHED, "HG-1103", GRN_MATCH), world["clerk"])
    service.submit_draft(harbour_id, MATCHED, draft(MATCHED, total=5900), world["clerk"])
    service.score(harbour_id, SHORT, _invoice(SHORT, "HG-1104", GRN_SHORT), world["clerk"])
    service.submit_draft(harbour_id, SHORT, draft(SHORT, total=5900), world["clerk"])

    approver = TestClient(create_app(pool, source_url=lambda path, name: "/files/signed"))
    headers = {"Authorization": f"Bearer {world['approver_token']}", **SAME_ORIGIN}
    matched = approver.get(f"/api/clients/{harbour_id}/invoices/{MATCHED}", headers=headers)
    assert matched.status_code == 200
    body = matched.json()
    assert body["client"]["name"] == "Harbour Mills"
    assert body["invoice"]["state_label"] == "Needs review"
    assert body["match"]["matched"] is True
    assert body["match"]["purchase_order"]["quantity"] == "10"
    assert body["match"]["purchase_order"]["amount"] == "5900.00"
    assert body["match"]["goods_receipt"]["quantity_received"] == "10"
    assert body["match"]["invoice"] == {"quantity": "10", "amount": "5900.00"}
    assert body["posting"]["blocked"] is True
    assert body["posting"]["reason"] == INTRA_BLOCK

    token = body["csrf_token"]
    approved = approver.post(
        f"/api/clients/{harbour_id}/invoices/{MATCHED}/approve",
        headers=headers,
        json={"csrf_token": token, "revision": body["invoice"]["revision"], "post": True},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["posting_blocked"] is True
    assert approved.json()["posting_reason"] == INTRA_BLOCK
    assert service.post_job_count(harbour_id, MATCHED) == 0
    again = approver.get(f"/api/clients/{harbour_id}/invoices/{MATCHED}", headers=headers).json()
    assert again["invoice"]["state_label"] == "Approved"
    assert again["posting"]["reason"] == INTRA_BLOCK

    short = approver.get(f"/api/clients/{harbour_id}/invoices/{SHORT}", headers=headers).json()
    assert short["match"]["matched"] is False
    assert short["match"]["holds_review"] is True
    assert short["match"]["differences"] == ["Goods receipt quantity differs."]
    assert short["match"]["goods_receipt"]["quantity_received"] == "8"
    assert short["invoice"]["state_label"] == "Needs review"
    refused = approver.post(
        f"/api/clients/{harbour_id}/invoices/{SHORT}/approve",
        headers=headers,
        json={"csrf_token": short["csrf_token"], "revision": short["invoice"]["revision"], "post": True},
    )
    assert refused.status_code == 409
    assert "Goods receipt quantity differs." in refused.json()["detail"]
    still = approver.get(f"/api/clients/{harbour_id}/queue?queue=needs_review", headers=headers).json()
    assert [item["invoice_no"] for item in still["items"]] == ["HG-1104"]
    assert still["items"][0]["state_label"] == "Needs review"
    assert service.post_job_count(harbour_id, SHORT) == 0
    with pytest.raises(Conflict, match="Goods receipt quantity differs"):
        service.approve(harbour_id, SHORT, world["approver"], post=True, expected_revision=short["invoice"]["revision"])
