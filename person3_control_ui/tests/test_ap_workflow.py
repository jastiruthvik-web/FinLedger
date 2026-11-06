"""Purchase-order allocation, department routing, and expense-ledger history.

The database is the throwaway cluster from conftest. No production data and no ERP post.
"""
from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import date

import pytest

from finledger_control.service import Conflict, ControlService, Forbidden
from finledger_platform.db import firm, tenant
from finledger_platform.purchase_documents import OverAllocated, reserve_allocations
from finledger_platform.tenancy import add_member, create_client, create_user
from test_service import canonical, draft


def _document(conn, client_id, document_id):
    with tenant(conn, client_id):
        conn.execute(
            """insert into documents(id,client_id,channel,object_path,original_filename,content_hash,mime,size_bytes,status,virus_ok,source_meta)
               values (%s,%s,'mail_scan',%s,'scan.pdf',%s,'application/pdf',120,'extracted',true,'{}')""",
            (document_id, client_id, f"{client_id}/2026/11/{document_id}/raw.pdf",
             hashlib.sha256(str(document_id).encode()).hexdigest()),
        )


def _order(service, client_id, actor, qty="10"):
    return service.save_purchase_order(client_id, actor, {
        "po_number": "PO-LINE-1", "vendor_name": "Shree Ganesh Metals", "supplier_gstin": "27AAACS1234A1Z2",
        "currency": "INR", "source": "manual",
        "lines": [{
            "line_no": 1, "item_code": "HR", "description": "HR coil", "uom": "NOS",
            "quantity": qty, "unit_price": "500", "tax_rate": "18", "currency": "INR",
        }],
    })


def _receipt(service, client_id, actor, grn, qty, kind="goods_receipt"):
    return service.save_goods_receipt(client_id, actor, {
        "grn_number": grn, "po_number": "PO-LINE-1", "document_kind": kind, "source": "import",
        "supplier_gstin": "27AAACS1234A1Z2", "currency": "INR",
        "lines": [{
            "line_no": 1, "po_line_no": 1, "item_code": "HR", "description": "HR coil",
            "uom": "NOS", "quantity": qty, "unit_price": "500",
        }],
    })


def _bill(conn, world, document_id, qty, number):
    client_id = world["client"]["id"]
    _document(conn, client_id, document_id)
    service = ControlService(conn)
    invoice = canonical(
        document_id, invoice_no=number, po_number="PO-LINE-1", total=int(qty) * 590,
        taxable=int(qty) * 500, cgst=int(qty) * 45, sgst=int(qty) * 45,
        line_items=[{
            "desc": "HR coil", "hsn_sac": "7208", "qty": qty, "rate": 500,
            "taxable": int(qty) * 500, "tax_rate": 18, "tax_amount": int(qty) * 90,
        }],
    )
    service.score(client_id, document_id, invoice, world["clerk"])
    routed = service.submit_draft(client_id, document_id, draft(document_id, total=int(qty) * 590), world["clerk"])
    service.edit_field(client_id, document_id, world["clerk"], "line_fact.0.uom", "NOS", expected_revision=routed["revision"])
    edited = service.edit_field(client_id, document_id, world["clerk"], "line_fact.0.currency", "INR",
                                expected_revision=routed["revision"] + 1)
    return service, edited["revision"]


def test_line_allocation_is_company_scoped_and_a_delivery_note_is_not_received(conn, world):
    client_id = world["client"]["id"]
    with tenant(conn, client_id):
        conn.execute("update clients set match_mode='three_way' where id=%s", (client_id,))
    service = ControlService(conn)
    _order(service, client_id, world["clerk"])
    note = _receipt(service, client_id, world["clerk"], "DN-1", "10", "delivery_note")
    assert note["status"] == "pending_review"
    assert note["counts_as_received"] is False
    _receipt(service, client_id, world["clerk"], "GRN-1", "6")
    _receipt(service, client_id, world["clerk"], "GRN-2", "4")
    copied = _receipt(service, client_id, world["clerk"], "GRN-COPY", "6")
    assert copied["status"] == "duplicate"
    with firm(conn, world["client"]["firm_id"]):
        other = create_client(conn, "Other Mill", inbound_slug="other-mill")
    with tenant(conn, other["id"]):
        assert conn.execute("select count(*) as n from purchase_orders").fetchone()["n"] == 0
        assert conn.execute("select count(*) as n from goods_receipts").fetchone()["n"] == 0
    document_id = str(uuid.uuid4())
    service, revision = _bill(conn, world, document_id, 10, "INV-LINE-1")
    match = service.bill_match(client_id, document_id)["match"]
    assert match["basis"] == "lines"
    assert match["matched"] is True
    assert match["source_label"].startswith("Manual or file import")
    approved = service.approve(client_id, document_id, world["approver"], post=False, expected_revision=revision)
    assert approved["status"] == "approved"
    with tenant(conn, client_id):
        taken = conn.execute(
            "select quantity from receipt_allocations where document_id=%s and released_at is null", (document_id,)
        ).fetchall()
    assert sum(row["quantity"] for row in taken) == 10
    second = str(uuid.uuid4())
    service, second_revision = _bill(conn, world, second, 1, "INV-LINE-2")
    refused = service.bill_match(client_id, second)["match"]
    assert "quantity_over_received" in refused["blocked"]
    with pytest.raises(Conflict, match="accepted receipt"):
        service.approve(client_id, second, world["approver"], post=False, expected_revision=second_revision)


def test_edit_after_approval_releases_the_reserved_quantity(conn, world):
    client_id = world["client"]["id"]
    with tenant(conn, client_id):
        conn.execute("update clients set match_mode='three_way' where id=%s", (client_id,))
    service = ControlService(conn)
    _order(service, client_id, world["clerk"], "10")
    _receipt(service, client_id, world["clerk"], "GRN-REL", "10")
    document_id = str(uuid.uuid4())
    service, revision = _bill(conn, world, document_id, 4, "INV-PART")
    service.approve(client_id, document_id, world["approver"], post=False, expected_revision=revision)
    edited = service.edit_field(client_id, document_id, world["approver"], "party_ledger", "Ganesh Metals - AP",
                                expected_revision=revision)
    detail = service.review_detail(client_id, document_id)
    assert detail["status"] == "in_review"
    assert detail["draft"]["party_ledger"] == "Ganesh Metals - AP"
    with tenant(conn, client_id):
        open_qty = conn.execute(
            "select count(*) as n from receipt_allocations where document_id=%s and released_at is null", (document_id,)
        ).fetchone()["n"]
    assert open_qty == 0
    with pytest.raises(Forbidden, match="editor"):
        service.approve(client_id, document_id, world["approver"], post=False, expected_revision=edited["revision"])


def test_non_po_bill_can_be_reviewed_without_inventing_an_order(conn, world, document):
    client_id = world["client"]["id"]
    with tenant(conn, client_id):
        conn.execute("update clients set match_mode='three_way' where id=%s", (client_id,))
    service = ControlService(conn)
    invoice = canonical(document, po_number=None)
    service.score(client_id, document, invoice, world["clerk"])
    routed = service.submit_draft(client_id, document, draft(document), world["clerk"])
    match = service.bill_match(client_id, document)["match"]
    assert match["path"] == "non_po"
    assert match["holds_review"] is False
    approved = service.approve(client_id, document, world["approver"], post=False, expected_revision=routed["revision"])
    assert approved["status"] == "approved"


def test_concurrent_reservations_cannot_consume_the_same_receipt(conn, pool, world):
    client_id = world["client"]["id"]
    service = ControlService(conn)
    _order(service, client_id, world["clerk"], "10")
    saved = _receipt(service, client_id, world["clerk"], "GRN-RACE", "10")
    line_id = saved["lines"][0]["id"]
    barrier = threading.Barrier(2)
    results = []

    def once(document_id):
        with pool.connection() as other:
            with tenant(other, client_id):
                barrier.wait()
                try:
                    reserve_allocations(other, document_id=document_id, specs=[{
                        "receipt_line_id": line_id, "invoice_line_no": 1, "quantity": 8, "kind": "reserve",
                    }])
                    results.append("ok")
                except OverAllocated:
                    results.append("over")
                except Exception as exc:
                    results.append(f"err:{exc}")

    left, right = str(uuid.uuid4()), str(uuid.uuid4())
    for document_id in (left, right):
        _document(conn, client_id, document_id)
    threads = [threading.Thread(target=once, args=(document_id,)) for document_id in (left, right)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["ok", "over"]


def test_department_routing_blocks_the_wrong_approver_and_flags_a_missing_one(conn, world, document):
    client_id = world["client"]["id"]
    firm_id = world["client"]["firm_id"]
    with firm(conn, firm_id):
        outsider, _token = create_user(conn, "other-approver@sharma.test")
        add_member(conn, client_id, outsider, "approver")
    service = ControlService(conn)
    service.score(client_id, document, canonical(document), world["clerk"])
    service.submit_draft(client_id, document, draft(document), world["clerk"])
    service.save_department(client_id, world["admin"], {
        "code": "STORES", "name": "Stores", "cost_centre": "ST", "approver_ids": [str(world["approver"])],
    })
    routed = service.assign_bill_department(client_id, document, world["clerk"], "STORES")
    assert routed["status"] == "pending"
    with pytest.raises(Forbidden):
        service.decide_department(client_id, document, outsider, decision="approve", expected_revision=routed["revision"], note="")
    with pytest.raises(Forbidden):
        service.decide_department(client_id, document, world["payer"], decision="approve", expected_revision=routed["revision"], note="")
    signed = service.decide_department(client_id, document, world["approver"], decision="approve",
                                      expected_revision=routed["revision"], note="")
    assert signed["status"] == "approved"
    assert service.review_detail(client_id, document)["status"] == "in_review"
    service.save_department(client_id, world["admin"], {"code": "QA", "name": "Quality", "cost_centre": "QA", "approver_ids": []})
    missing = service.assign_bill_department(client_id, document, world["clerk"], "QA")
    assert missing["status"] == "no_approver"
    with pytest.raises(Forbidden):
        service.decide_department(client_id, document, world["clerk"], decision="admin_fallback",
                                 expected_revision=missing["revision"], note="no approver")
    fallback = service.decide_department(client_id, document, world["admin"], decision="admin_fallback",
                                        expected_revision=missing["revision"], note="no approver on the department")
    assert fallback["status"] == "admin_fallback"
    assert service.review_detail(client_id, document)["status"] == "in_review"


def test_expense_corrections_stay_separate_from_the_party_ledger_and_from_extraction(conn, world, document):
    client_id = world["client"]["id"]
    service = ControlService(conn)
    invoice = canonical(document)
    service.score(client_id, document, invoice, world["clerk"])
    routed = service.submit_draft(client_id, document, draft(document), world["clerk"])
    before = service.review_detail(client_id, document)["invoice"]
    service.edit_field(client_id, document, world["clerk"], "party_ledger", "Ganesh Metals - AP",
                      expected_revision=routed["revision"])
    service.edit_field(client_id, document, world["clerk"], "lines.0.ledger", "Stores",
                      expected_revision=routed["revision"] + 1)
    service.edit_field(client_id, document, world["clerk"], "lines.0.ledger", "Inventory",
                      expected_revision=routed["revision"] + 2)
    detail = service.review_detail(client_id, document)
    assert detail["invoice"]["line_items"] == before["line_items"]
    assert detail["invoice"]["vendor"] == before["vendor"]
    assert detail["draft"]["party_ledger"] == "Ganesh Metals - AP"
    assert detail["draft"]["lines"][0]["ledger"] == "Inventory"
    fields = [row["field"] for row in service.corrections(client_id, document)]
    assert fields.count("expense_ledger") == 2
    assert "party_ledger" in fields
    stores = detail["suggestions"][0]
    assert stores["abstained"] is True
    assert "Stores" in stores["explanation"] and "Inventory" in stores["explanation"]
    with firm(conn, world["client"]["firm_id"]):
        other = create_client(conn, "Second Books", inbound_slug="second-books")
    with tenant(conn, other["id"]):
        assert conn.execute("select count(*) as n from correction_events").fetchone()["n"] == 0


def test_editor_department_signoff_is_refused_and_a_later_edit_clears_it(conn, world, document):
    client_id = world["client"]["id"]
    firm_id = world["client"]["firm_id"]
    with firm(conn, firm_id):
        second, _token = create_user(conn, "second-approver@sharma.test")
        add_member(conn, client_id, second, "approver")
    service = ControlService(conn)
    service.score(client_id, document, canonical(document), world["clerk"])
    routed = service.submit_draft(client_id, document, draft(document), world["clerk"])
    service.save_department(client_id, world["admin"], {
        "code": "MILL", "name": "Mill", "cost_centre": "ML",
        "approver_ids": [str(world["approver"]), str(second)],
    })
    assigned = service.assign_bill_department(client_id, document, world["admin"], "MILL")
    service.edit_field(client_id, document, world["approver"], "narration", "Checked the rate",
                      expected_revision=routed["revision"])
    with pytest.raises(Forbidden, match="editor"):
        service.decide_department(client_id, document, world["approver"], decision="approve",
                                 expected_revision=assigned["revision"], note="")
    signed = service.decide_department(client_id, document, second, decision="approve",
                                      expected_revision=assigned["revision"], note="second approver did not edit")
    assert signed["status"] == "approved"
    service.edit_field(client_id, document, world["clerk"], "narration", "Changed after sign-off",
                      expected_revision=routed["revision"] + 1)
    cleared = service.review_detail(client_id, document)["department"]
    assert cleared["status"] == "pending"
    assert cleared["revision"] > signed["revision"]
