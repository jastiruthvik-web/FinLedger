"""Authenticated import keeps the original bytes, and email dedupe is per company and attachment.

No mailbox is opened and no provider is called.
"""
from __future__ import annotations

import hashlib
from email.message import EmailMessage

from conftest import auth, invoice_pdf, photo_jpg
from finledger_platform.capture import capture_status
from finledger_platform.db import tenant
from finledger_platform.email_in import parse


def test_capture_status_does_not_claim_a_mailbox_or_portal():
    status = capture_status(
        inbound_webhook_secret=b"mock_inbound_webhook_secret_not_for_production",
        inbound_address="invoices.acme@inbound.localhost",
        upload_link="http://127.0.0.1/i/token",
    )
    assert status["email"]["mailbox_connected"] is False
    assert status["email"]["webhook"] == "configuration_required"
    assert status["vendor_portal"]["connected"] is False
    assert status["mail"]["mode"] == "authenticated_upload"
    assert "mock_" not in str(status)


def test_import_keeps_original_dedupes_per_company_and_rejects_disguised_type(world, client, conn, store):
    pdf = invoice_pdf("INV-SCAN-1")
    digest = hashlib.sha256(pdf).hexdigest()
    files = {"files": ("scan.pdf", pdf, "application/pdf")}
    first = client.post(
        f"/clients/{world.a['id']}/imports", data={"source": "mail_scan", "external_message_id": "paper-1"},
        files=files, headers=auth(world.token1),
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["mailbox_connected"] is False and body["vendor_portal_connected"] is False
    assert body["received"][0]["content_hash"] == digest
    again = client.post(
        f"/clients/{world.a['id']}/imports", data={"source": "mail_scan", "external_message_id": "paper-1"},
        files={"files": ("scan.pdf", pdf, "application/pdf")}, headers=auth(world.token1),
    )
    assert again.json()["received"][0]["replayed"] is True
    assert again.json()["received"][0]["document_id"] == body["received"][0]["document_id"]
    other = client.post(
        f"/clients/{world.c['id']}/imports", data={"source": "portal_download", "external_message_id": "paper-1"},
        files={"files": ("scan.pdf", pdf, "application/octet-stream")}, headers=auth(world.token1),
    )
    assert other.status_code == 201
    assert other.json()["received"][0]["document_id"] != body["received"][0]["document_id"]
    disguised = client.post(
        f"/clients/{world.a['id']}/imports", data={"source": "mail_scan"},
        files={"files": ("invoice.pdf", b"this is not a pdf", "application/pdf")}, headers=auth(world.token1),
    )
    assert disguised.status_code == 422
    assert "unsupported" in disguised.json()["rejected"][0]["reason"]
    photo = photo_jpg()
    scanned = client.post(
        f"/clients/{world.a['id']}/imports", data={"source": "mail_scan", "external_message_id": "photo-9"},
        files={"files": ("mail.jpg", photo, "image/jpeg")}, headers=auth(world.token1),
    )
    assert scanned.status_code == 201
    with tenant(conn, world.a["id"]):
        rows = conn.execute(
            "select id, channel, content_hash, object_path, source_meta from documents order by received_at"
        ).fetchall()
        assert {row["channel"] for row in rows} >= {"mail_scan"}
        kept = next(row for row in rows if row["content_hash"] == digest)
        assert store.get(kept["object_path"]) == pdf
        assert kept["source_meta"]["provenance"]["sha256"] == digest
        assert kept["source_meta"]["imported_by"] == str(world.admin1)
        assert kept["source_meta"]["tenant_linked_by"] == "authenticated_client"
    with tenant(conn, world.b["id"]):
        assert conn.execute("select count(*) as n from documents").fetchone()["n"] == 0
    stranger = client.post(
        f"/clients/{world.a['id']}/imports", data={"source": "mail_scan"},
        files={"files": ("x.pdf", pdf, "application/pdf")}, headers=auth(world.token2),
    )
    assert stranger.status_code == 404


def test_synthetic_mime_keeps_attachment_bytes_and_does_not_trust_the_sender():
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    message = EmailMessage()
    message["From"] = "Vendor <billing@evil.example>"
    message["To"] = "invoices.acme-steel@inbound.finledger.test"
    message["Message-ID"] = "<bill-42@vendor.example>"
    message["Authentication-Results"] = "mx.finledger.test; spf=pass smtp.mailfrom=vendor.example; dkim=pass header.d=vendor.example; dmarc=pass"
    message.set_content("invoice attached")
    message.add_attachment(pdf, maintype="application", subtype="pdf", filename="bill.pdf")
    parsed = parse(message.as_bytes(), "mx.finledger.test")
    assert parsed.attachments == [("bill.pdf", pdf)]
    assert parsed.sender == "billing@evil.example"
    assert parsed.intake_key.startswith("email:")
    assert "acme-steel" not in parsed.intake_key
