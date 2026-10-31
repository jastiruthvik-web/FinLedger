"""Serve the built desk to browsers without replacing the API or the HTML tests."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse

QUEUES = ("new", "needs_review", "approved", "exception", "posted")


def desk_dist() -> Path:
    override = os.environ.get("FINLEDGER_DESK_DIST", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "desk" / "dist"


def desk_document(request: Request) -> FileResponse | None:
    """Browser navigations ask for text/html. API tests send */* and keep the existing pages."""
    accept = request.headers.get("accept") or ""
    index = desk_dist() / "index.html"
    if "text/html" not in accept or not index.is_file():
        return None
    return FileResponse(index, headers={"Cache-Control": "no-store"})


def queue_name(value: str | None) -> str:
    if value in QUEUES:
        return value
    return "needs_review"


def mfa_blocks(who) -> bool:
    """Password sign-in is enough when the account has no verified TOTP factor."""
    if not isinstance(who, dict) or who.get("mfa_required", True) is False:
        return False
    return "aal" in who and who["aal"] != "aal2"
