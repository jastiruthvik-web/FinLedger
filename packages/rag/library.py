"""Shared accounts-payable hints, copied into each client. There is no global row."""
from __future__ import annotations

import json
from pathlib import Path

from rag.chunk_types import ChunkType
from rag.indexer import Indexer

_SEED = Path(__file__).parent / "seeds" / "ap_starter.json"

STARTER_REFS = (
    "library:doc:purchase_invoice",
    "library:doc:debit_note",
    "library:doc:credit_note",
    "library:gst:intra",
    "library:gst:inter",
    "library:gst:rate:0",
    "library:gst:rate:5",
    "library:gst:rate:12",
    "library:gst:rate:18",
    "library:gst:rate:28",
    "library:sac:9982",
    "library:sac:9983",
    "library:sac:9987",
    "library:hsn:8471",
    "library:hsn:8528",
    "library:hsn:7208",
    "library:tds:194c",
    "library:tds:194i",
)


def load_starter() -> list[dict]:
    rows = json.loads(_SEED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("ap_starter.json must be a list")
    return rows


def seed_client_library(indexer: Indexer, client_id: str) -> int:
    """Upsert the starter into one client. Safe to re-run: the key is (client_id, ref)."""
    if not str(client_id).strip():
        raise ValueError("client_id is required")
    rows = load_starter()
    refs = [row["ref"] for row in rows]
    if len(refs) != len(set(refs)) or set(refs) != set(STARTER_REFS):
        raise ValueError("ap_starter.json does not match the starter set")
    for row in rows:
        if row.get("chunk_type") != "hard_rule":
            raise ValueError(f"{row['ref']} must be a hard_rule")
        metadata = dict(row.get("metadata") or {})
        if metadata.get("scope") != "library":
            raise ValueError(f"{row['ref']} must be scope library")
        indexer.upsert(str(client_id), row["ref"], ChunkType.HARD_RULE, row["content"], metadata)
    return len(rows)
