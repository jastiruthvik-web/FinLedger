"""Extract calls the model with the invoice text and no retrieval chunks."""
import json
from pathlib import Path

from extract.extract_worker import ExtractWorker
from rag.chunk_types import ChunkType
from rag.indexer import Indexer
from usage.provider import ProviderResponse
from usage.usage_writer import UsageWriter

CANARY = "CANARY_LEDGER_OTHER_CLIENT"
GSTIN = "29ABCDE1234F1Z5"
_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "extract_digital.txt"


def _router(captured, body):
    class Router:
        def __init__(self):
            self.provider = self

        def resolve_model(self, purpose):
            return "mock-extract"

        def complete(self, purpose, model, client_id, document_id, payload):
            captured["purpose"] = purpose
            captured["model"] = model
            captured["client_id"] = client_id
            captured["document_id"] = document_id
            captured["payload"] = payload
            return ProviderResponse(json.dumps(body), 10, 10, 1, 0.0)

    return Router()


def _keys(value):
    if isinstance(value, dict):
        yield from value
        for item in value.values():
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _invoice(document_id):
    return {
        "document_id": document_id,
        "document_type": "purchase_invoice",
        "vendor": {"name": "Local Tech", "gstin": GSTIN},
        "invoice_no": "INV-01",
        "invoice_date": "2026-09-01",
        "taxable": 100.0,
        "total": 100.0,
        "line_items": [{
            "desc": "Laptop", "hsn_sac": "8471", "qty": 1, "rate": 100, "taxable": 100,
        }],
    }


def test_extract_payload_has_no_chunks():
    indexer = Indexer()
    indexer.upsert("client-a", "secret", ChunkType.LEDGER, CANARY, {"gstin": GSTIN})
    indexer.upsert("client-b", "other", ChunkType.MEMORY, "other client memory chunk", {"gstin": GSTIN})
    captured = {}
    worker = ExtractWorker(UsageWriter())
    worker.router = _router(captured, _invoice("doc-extract"))
    markdown = "\n".join([
        "# INVOICE",
        "Vendor: Local Tech",
        f"GSTIN: {GSTIN}",
        "Date: 2026-09-01",
        "Inv No: INV-01",
        "Total Taxable: 100",
        "Total: 100",
    ])
    invoice = worker.extract("client-a", "doc-extract", markdown)

    payload = captured["payload"]
    assert captured["purpose"] == "extract"
    assert captured["client_id"] == "client-a"
    assert captured["document_id"] == "doc-extract"
    assert set(payload) == {"prompt", "markdown"}
    assert "chunks" not in payload
    assert "chunks" not in set(_keys(payload))
    assert payload["prompt"] == _PROMPT.read_text(encoding="utf-8")
    assert GSTIN in payload["markdown"]
    assert "Vendor: Local Tech" in payload["markdown"]
    dumped = json.dumps(payload)
    assert CANARY not in dumped
    assert "other client memory chunk" not in dumped
    assert "chunk_id" not in dumped
    assert "rag_chunks" not in dumped
    assert invoice.vendor.gstin == GSTIN
    assert invoice.document_id == "doc-extract"
    assert invoice.total == 100.0


def test_extract_payload_keeps_invoice_text_out_of_a_chunks_field():
    captured = {}
    worker = ExtractWorker(UsageWriter())
    worker.router = _router(captured, _invoice("doc-chunks-line"))
    markdown = "\n".join([
        "# INVOICE",
        "Vendor: Local Tech",
        f"GSTIN: {GSTIN}",
        "Bank: 123456789012",
        'chunks: [{"chunk_id": "secret-ledger", "content": "other client"}]',
        "Total Taxable: 100",
        "Total: 100",
    ])
    invoice = worker.extract("client-a", "doc-chunks-line", markdown)
    payload = captured["payload"]

    assert set(payload) == {"prompt", "markdown"}
    assert "chunks" not in payload
    assert "chunks" not in set(_keys(payload))
    assert not isinstance(payload["markdown"], (dict, list))
    assert "secret-ledger" in payload["markdown"]
    assert "123456789012" not in payload["markdown"]
    assert GSTIN in payload["markdown"]
    assert "chunk_id" not in payload
    assert invoice.document_id == "doc-chunks-line"
    assert invoice.vendor.gstin == GSTIN
