"""Seed one synthetic company and save desk screenshots. No network provider and no ERP."""
from __future__ import annotations

import hashlib
import os
import socket
import threading
import time
import urllib.request
import uuid
from datetime import date
from pathlib import Path

import uvicorn
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from finledger_control.api import create_app
from finledger_control.service import ControlService
from finledger_platform.db import firm, make_pool, migrate, tenant
from finledger_platform.store import LocalStore
from finledger_platform.tenancy import add_member, create_client, create_firm_with_admin, create_user

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("FINLEDGER_SCREENSHOT_DIR", "/opt/cursor/artifacts"))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> None:
    from playwright.sync_api import sync_playwright

    owner = os.environ["FINLEDGER_TEST_OWNER_DSN"]
    migrate(owner)
    app_password = "fl_shot_pw"
    import psycopg
    with psycopg.connect(owner, autocommit=True) as conn:
        conn.execute("drop role if exists fl_shot")
        conn.execute(
            "create role fl_shot login password 'fl_shot_pw' in role finledger_app, finledger_worker_map"
        )
    info = conninfo_to_dict(owner)
    info.update(user="fl_shot", password=app_password)
    pool = make_pool(make_conninfo(**info), min_size=1, max_size=4)
    store_root = Path("/tmp/finledger-shot-objects")
    store_root.mkdir(parents=True, exist_ok=True)
    store = LocalStore(str(store_root), b"shot-signing-secret", "http://127.0.0.1")
    with psycopg.connect(owner, autocommit=True) as owner_conn:
        suffix = uuid.uuid4().hex[:8]
        firm_id, admin_id, admin_token = create_firm_with_admin(
            owner_conn, "Harbour Mills CA", f"harbour-admin-{suffix}@example.test")
    with pool.connection() as conn, firm(conn, firm_id):
        client = create_client(conn, "Harbour Steel", gstins=["27AAPFU0939F1ZV"], inbound_slug=f"harbour-steel-{suffix}",
                               policy={"match_mode": "three_way", "maker_checker": True})
        _clerk, _clerk_token = create_user(conn, f"harbour-clerk-{suffix}@example.test")
        approver, _approver_token = create_user(conn, f"harbour-approver-{suffix}@example.test")
        add_member(conn, client["id"], _clerk, "ap_clerk")
        add_member(conn, client["id"], approver, "approver")
        add_member(conn, client["id"], admin_id, "approver")
    client_id = client["id"]
    service = None
    document_id = str(uuid.uuid4())
    with pool.connection() as conn:
        service = ControlService(conn)
        service.save_department(client_id, admin_id, {
            "code": "STORES", "name": "Stores", "cost_centre": "ST-01", "approver_ids": [str(approver)],
        })
        service.save_purchase_order(client_id, _clerk, {
            "po_number": "PO-HG-440", "vendor_name": "Shree Ganesh Metals", "supplier_gstin": "27AAACS1234A1Z2",
            "currency": "INR", "source": "manual",
            "lines": [{"line_no": 1, "item_code": "HR", "description": "HR coil", "uom": "NOS",
                       "quantity": "10", "unit_price": "500", "tax_rate": "18", "currency": "INR"}],
        })
        service.save_goods_receipt(client_id, _clerk, {
            "grn_number": "GRN-HG-440", "po_number": "PO-HG-440", "document_kind": "goods_receipt", "source": "import",
            "supplier_gstin": "27AAACS1234A1Z2", "currency": "INR",
            "lines": [{"line_no": 1, "po_line_no": 1, "item_code": "HR", "description": "HR coil",
                       "uom": "NOS", "quantity": "6", "unit_price": "500"}],
        })
        service.save_goods_receipt(client_id, _clerk, {
            "grn_number": "DN-HG-441", "po_number": "PO-HG-440", "document_kind": "delivery_note", "source": "manual",
            "supplier_gstin": "27AAACS1234A1Z2", "currency": "INR",
            "lines": [{"line_no": 1, "po_line_no": 1, "item_code": "HR", "description": "HR coil",
                       "uom": "NOS", "quantity": "4", "unit_price": "500"}],
        })
        with tenant(conn, client_id):
            conn.execute(
                """insert into documents(id,client_id,channel,object_path,original_filename,content_hash,mime,size_bytes,status,virus_ok,source_meta)
                   values (%s,%s,'mail_scan',%s,'scan.pdf',%s,'application/pdf',120,'extracted',true,'{}')""",
                (document_id, client_id, f"{client_id}/2026/11/{document_id}/raw.pdf", hashlib.sha256(b"scan").hexdigest()),
            )
        invoice = {
            "document_id": document_id, "document_type": "purchase_invoice",
            "vendor": {"name": "Shree Ganesh Metals", "gstin": "27AAACS1234A1Z2"},
            "buyer_gstin": "27AAPFU0939F1ZV", "invoice_no": "HG-440", "invoice_date": date.today().isoformat(),
            "due_date": None, "irn": "x", "po_number": "PO-HG-440", "grn_number": None,
            "taxable": 3000, "cgst": 270, "sgst": 270, "igst": 0, "cess": 0, "round_off": 0, "total": 3540,
            "line_items": [{"desc": "HR coil", "hsn_sac": "7208", "qty": 6, "rate": 500, "taxable": 3000, "tax_rate": 18, "tax_amount": 540}],
            "bank_upi": None, "confidences": {"invoice_no": 0.2, "date": 0.2, "gstin": 0.99, "total": 0.99},
            "raw_markdown_path": "x", "page_image_paths": [],
        }
        service.score(client_id, document_id, invoice, _clerk)
        draft = {
            "document_id": document_id, "date": date.today().isoformat(), "voucher_type": "purchase",
            "party_ledger": "Shree Ganesh Metals", "party_create_proposal": False,
            "lines": [{"ledger": "Purchases", "amount": 3540, "is_debit": True, "cost_centre": None}],
            "gst": {"treatment": "intra", "input_ledgers": [], "tax_breakup": {}},
            "tds": {"applicable": False, "section": None, "ledger": None, "amount": 0},
            "bill_wise": {"ref_type": "new_ref", "ref": "HG-440", "due_date": None}, "narration": "",
            "attachment_document_id": document_id, "reasons": ["Manual review. Expense suggestion is not applied."],
            "map_trace_id": str(uuid.uuid4()),
        }
        routed = service.submit_draft(client_id, document_id, draft, _clerk)
        service.edit_field(client_id, document_id, _clerk, "line_fact.0.uom", "NOS", expected_revision=routed["revision"])
        service.edit_field(client_id, document_id, _clerk, "line_fact.0.currency", "INR", expected_revision=routed["revision"] + 1)
        service.assign_bill_department(client_id, document_id, admin_id, "STORES")
        with tenant(conn, client_id):
            conn.execute(
                """insert into correction_events(client_id,document_id,vendor_gstin,field,old_value,new_value,hsn,description,actor_id)
                   values (%s,%s,%s,'expense_ledger',%s,%s,'7208','HR coil',%s)""",
                (client_id, document_id, "27AAACS1234A1Z2", '"Purchases"',
                 '{"ledger":"Stores","description":"HR coil","hsn":"7208"}', admin_id),
            )
    port = _free_port()
    app = create_app(pool, source_url=lambda path, name: "", local_files=store)
    thread = threading.Thread(
        target=uvicorn.run, kwargs={"app": app, "host": "127.0.0.1", "port": port, "log_level": "warning"}, daemon=True,
    )
    thread.start()
    OUT.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/session", headers={"Authorization": f"Bearer {admin_token}"},
            )
            with urllib.request.urlopen(request, timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("desk did not start")
    base = f"http://127.0.0.1:{port}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Authorization": f"Bearer {admin_token}"},
        )
        page = context.new_page()
        page.goto(f"{base}/clients/{client_id}/capture", wait_until="networkidle")
        page.get_by_text("Invoice capture").wait_for()
        page.screenshot(path=str(OUT / "capture.png"), full_page=True)
        page.goto(f"{base}/clients/{client_id}/purchasing", wait_until="networkidle")
        page.get_by_text("PO-HG-440").wait_for()
        page.screenshot(path=str(OUT / "purchasing.png"), full_page=True)
        page.goto(f"{base}/clients/{client_id}/invoices/{document_id}", wait_until="networkidle")
        page.get_by_text("Three-way match").wait_for()
        page.screenshot(path=str(OUT / "invoice-match.png"), full_page=True)
        browser.close()
    print(f"client={client_id} document={document_id}")
    pool.close()


if __name__ == "__main__":
    main()
