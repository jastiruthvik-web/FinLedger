"""Tenant prefix check for object keys. Raises before any storage read or model call."""

from __future__ import annotations

from extract.failures import ExtractFailure, OBJECT_KEY_REJECTED


def require_tenant_object_key(client_id: str, object_key: str) -> None:
    """Refuse keys that are not strictly under ``{client_id}/``. The error carries no key text."""
    if not _tenant_id(client_id) or not _key_under_tenant(client_id, object_key):
        raise ExtractFailure(OBJECT_KEY_REJECTED)


def require_tenant_object_keys(client_id: str, object_keys: list[str]) -> None:
    for object_key in object_keys:
        require_tenant_object_key(client_id, object_key)


def _tenant_id(client_id: object) -> bool:
    if not isinstance(client_id, str) or not client_id or client_id != client_id.strip():
        return False
    if "/" in client_id or "\\" in client_id:
        return False
    return all(ord(char) >= 32 for char in client_id)


def _key_under_tenant(client_id: str, object_key: object) -> bool:
    if not isinstance(object_key, str):
        return False
    prefix = f"{client_id}/"
    if not object_key.startswith(prefix) or "\\" in object_key:
        return False
    if any(ord(char) < 32 for char in object_key):
        return False
    remainder = object_key[len(prefix):]
    if not remainder:
        return False
    return all(part not in {"", ".", ".."} for part in remainder.split("/"))
