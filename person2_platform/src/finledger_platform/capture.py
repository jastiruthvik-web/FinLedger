"""Authenticated import of scanned mail and portal downloads.

There is no mailbox login and no vendor-portal login here. The company is the
authenticated client. Sender text is never read from the request.
"""
from __future__ import annotations

from typing import Any

from . import intake

SOURCES = {
    "mail_scan": "mail_scan",
    "portal_download": "portal",
}

_PLACEHOLDER_MARKERS = ("mock_", "change-me", "not_for_production", "example")


def _secret_is_placeholder(secret: bytes) -> bool:
    try:
        text = secret.decode("utf-8")
    except UnicodeDecodeError:
        return False
    lowered = text.strip().lower()
    if len(lowered) < 16:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def capture_status(*, inbound_webhook_secret: bytes, inbound_address: str, upload_link: str) -> dict[str, Any]:
    """What this process can actually receive. Secrets are not copied into the result."""
    webhook = "configuration_required" if _secret_is_placeholder(inbound_webhook_secret) else "configured"
    return {
        "upload_link": upload_link,
        "mail": {
            "connected": True,
            "mode": "authenticated_upload",
            "detail": "Physical mail is a scan or photo uploaded by a signed-in person. There is no postal connector.",
        },
        "email": {
            "mailbox_connected": False,
            "webhook": webhook,
            "address": inbound_address,
            "detail": (
                "No mailbox is connected. A provider can POST a signed message to the inbound webhook "
                "after that webhook secret is configured. This screen does not create an inbox."
            ),
        },
        "vendor_portal": {
            "connected": False,
            "mode": "download_then_import",
            "detail": "FinLedger does not sign in to vendor portals. Download the bill and import the file.",
        },
    }


def import_uploads(conn, store, client_id, uploads: list[tuple[str, bytes]], *, source: str,
                   external_message_id: str, actor_id, max_bytes: int) -> intake.Receipt:
    if source not in SOURCES:
        raise ValueError("source must be mail_scan or portal_download")
    total = sum(len(data) for _, data in uploads)
    if total > max_bytes:
        raise ValueError("files exceed the upload limit")
    label = " ".join((external_message_id or "").split())[:200]
    meta = {
        "capture_source": source,
        "external_message_id": label,
        "imported_by": str(actor_id),
        "tenant_linked_by": "authenticated_client",
        "sender_untrusted": True,
    }
    base = f"import:{source}:{label or 'file'}"
    return intake.accept(
        conn, store, client_id, SOURCES[source], uploads, meta, intake_key=base,
    )
