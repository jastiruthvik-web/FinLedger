"""Staff CSV → one client's masters and rag_chunks. Not the public vendor link."""
from __future__ import annotations

import csv
import io
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from rag.chunk_types import ChunkType
from rag.postgres_indexer import PostgresIndexer

from . import tenancy
from .store import object_key

# History is stored, not pasted into the prompt. The caps keep one file from becoming
# eight chunks large enough to spend the per-bill token budget on their own.
HISTORY_MAX_ROWS = 200
HISTORY_MAX_BYTES = 256 * 1024
MASTER_MAX_ROWS = 2000
MASTER_MAX_BYTES = 512 * 1024
FIELD_MAX = 240

_DOC_TYPES = frozenset({"purchase_invoice", "debit_note", "credit_note", "expense"})
_LEDGER_COLUMNS = ("name",)
_VENDOR_COLUMNS = ("name", "gstin")
_HISTORY_COLUMNS = (
    "doc_type", "invoice_no", "invoice_date", "vendor_gstin", "vendor_name",
    "description", "hsn_sac", "amount", "ledger",
)


def max_bytes(kind: str) -> int:
    return HISTORY_MAX_BYTES if kind == "posted_history" else MASTER_MAX_BYTES


def max_rows(kind: str) -> int:
    return HISTORY_MAX_ROWS if kind == "posted_history" else MASTER_MAX_ROWS


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV must be UTF-8") from None


def _rows(data: bytes, required: tuple[str, ...], limit: int) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(_decode(data)))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    fields = {(name or "").strip() for name in reader.fieldnames}
    missing = [name for name in required if name not in fields]
    if missing:
        raise ValueError("CSV is missing a required column")
    parsed: list[dict[str, str]] = []
    for raw in reader:
        row = {(key or "").strip(): (value or "").strip() for key, value in raw.items()}
        if not any(row.values()):
            continue
        for key, value in row.items():
            if len(value) > FIELD_MAX:
                raise ValueError("a CSV field is too long")
        parsed.append(row)
        if len(parsed) > limit:
            raise ValueError(f"CSV has more than {limit} rows")
    if not parsed:
        raise ValueError("CSV needs a header row and at least one data row")
    return parsed


def _require(row: dict[str, str], key: str) -> str:
    value = row.get(key, "").strip()
    if not value:
        raise ValueError("a required CSV value is blank")
    return value


def parse_ledgers(data: bytes) -> list[dict[str, str]]:
    items = []
    for row in _rows(data, _LEDGER_COLUMNS, MASTER_MAX_ROWS):
        item = {"name": _require(row, "name"), "parent_group": row.get("parent_group", "")}
        if row.get("gst_duty"):
            item["gst_duty"] = row["gst_duty"]
        items.append(item)
    return items


def parse_vendors(data: bytes) -> list[dict[str, str]]:
    items = []
    for row in _rows(data, _VENDOR_COLUMNS, MASTER_MAX_ROWS):
        gstin = _require(row, "gstin").upper()
        if not tenancy.gstin_valid(gstin):
            raise ValueError("a vendor GSTIN is invalid")
        item = {"name": _require(row, "name"), "gstin": gstin}
        if row.get("default_ledger"):
            item["default_ledger"] = row["default_ledger"]
        items.append(item)
    return items


def parse_history(data: bytes) -> list[dict[str, Any]]:
    items = []
    for row in _rows(data, _HISTORY_COLUMNS, HISTORY_MAX_ROWS):
        doc_type = _require(row, "doc_type")
        if doc_type not in _DOC_TYPES:
            raise ValueError("a history doc_type is not supported")
        gstin = _require(row, "vendor_gstin").upper()
        if not tenancy.gstin_valid(gstin):
            raise ValueError("a history GSTIN is invalid")
        try:
            amount = float(row.get("amount", "").replace(",", ""))
        except ValueError:
            raise ValueError("a history amount is not a number") from None
        if isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
            raise ValueError("a history amount is not a number")
        items.append({
            "doc_type": doc_type,
            "invoice_no": _require(row, "invoice_no"),
            "invoice_date": row.get("invoice_date", ""),
            "vendor_gstin": gstin,
            "vendor_name": _require(row, "vendor_name"),
            "description": _require(row, "description"),
            "hsn_sac": _require(row, "hsn_sac"),
            "amount": amount,
            "ledger": row.get("ledger", ""),
        })
    return items


def parse_csv(kind: str, data: bytes) -> list[dict[str, Any]]:
    if kind == "ledgers":
        return parse_ledgers(data)
    if kind == "vendors":
        return parse_vendors(data)
    if kind == "posted_history":
        return parse_history(data)
    raise ValueError("unknown retrieval file")


def store_and_index(conn, store, client_id: UUID | str, kind: str, data: bytes, rows: list[dict[str, Any]]) -> dict:
    """Call inside tenant(conn, client_id). The object key is under that client. Chunks use the same id."""
    key = object_key(client_id, uuid4(), datetime.now(UTC), f"{kind}.csv")
    store.put(key, data, "text/csv")
    indexer = PostgresIndexer(conn)
    client = str(client_id)
    if kind == "ledgers":
        tenancy.write_masters(conn, client_id, "ledger", rows, source="staff_upload")
        for item in rows:
            content = f"Ledger {item['name']}. Parent group {item.get('parent_group', '')}."
            metadata = {"name": item["name"], "parent_group": item.get("parent_group", "")}
            if item.get("gst_duty"):
                content += f" GST duty {item['gst_duty']}."
                metadata["gst_duty"] = item["gst_duty"]
            indexer.upsert(client, f"ledger:{item['name']}", ChunkType.LEDGER, content, metadata)
    elif kind == "vendors":
        tenancy.write_masters(conn, client_id, "vendor", rows, source="staff_upload")
        for item in rows:
            content = f"Vendor {item['name']} GSTIN {item['gstin']}."
            metadata = {"gstin": item["gstin"], "name": item["name"]}
            if item.get("default_ledger"):
                content += f" Default ledger {item['default_ledger']}."
                metadata["default_ledger"] = item["default_ledger"]
            indexer.upsert(client, f"vendor:{item['gstin']}", ChunkType.VENDOR, content, metadata)
    else:
        for item in rows:
            content = (
                f"Posted history {item['invoice_no']} {item['invoice_date']} vendor {item['vendor_name']} "
                f"{item['vendor_gstin']} {item['description']} HSN {item['hsn_sac']} amount {item['amount']} "
                f"{item['doc_type']} ledger {item['ledger']}"
            )
            indexer.upsert(
                client,
                f"history:{item['vendor_gstin']}:{item['invoice_no']}:{item['hsn_sac']}",
                ChunkType.POSTED_BILL,
                content,
                {
                    "gstin": item["vendor_gstin"],
                    "hsn": item["hsn_sac"],
                    "amount": item["amount"],
                    "doc_type": item["doc_type"],
                    "invoice_no": item["invoice_no"],
                    "vendor_name": item["vendor_name"],
                    "ledger": item["ledger"],
                },
            )
    return {"imported": len(rows), "kind": kind, "object_key": key}
