import json
from unittest.mock import patch

from contracts.schemas import CanonicalInvoice, CorrectionEvent, LineItem, Vendor
from mapper.map_worker import MapWorker
from memory.memory_indexer import MemoryIndexer
from rag.chunk_types import ChunkType
from rag.indexer import Indexer
from rag.retriever import Retriever
from usage.usage_writer import UsageWriter

GSTIN = "29ABCDE1234F1Z5"
WRONG = "Purchases - Bearings"
CORRECTED = "SKF India - Sundry Creditors"


def _bill(document_id, *, gstin=GSTIN, name="SKF Bearings", desc="Bearings", hsn="8482"):
    return CanonicalInvoice(
        document_id=document_id,
        document_type="purchase_invoice",
        vendor=Vendor(name=name, gstin=gstin),
        invoice_no=f"INV-{document_id}",
        invoice_date="2026-10-02",
        due_date="2026-11-01",
        total=1180.0,
        taxable=1000.0,
        line_items=[LineItem(desc=desc, hsn_sac=hsn, qty=1, rate=1000, taxable=1000, tax_rate=18, tax_amount=180)],
    )


def _model_keeps_purchase_ledger(invoice_data):
    invoice = json.loads(invoice_data)
    document_id = invoice["document_id"]
    return json.dumps({
        "document_id": document_id,
        "date": "2026-10-02",
        "voucher_type": "purchase",
        "party_ledger": WRONG,
        "party_create_proposal": False,
        "lines": [{"ledger": "Purchases", "amount": 1180.0, "is_debit": True}],
        "gst": {"treatment": "intra", "input_ledgers": [], "tax_breakup": {}},
        "tds": {"applicable": False, "amount": 0.0},
        "bill_wise": {"ref_type": "new_ref", "ref": invoice["invoice_no"], "due_date": "2026-11-01"},
        "narration": "Being purchase",
        "attachment_document_id": document_id,
        "reasons": ["model kept the purchase ledger"],
    })


def test_party_ledger_correction_applies_to_client_a_only():
    """A matched party-ledger correction overrides the model. Client B never sees that ledger."""
    store = Indexer()
    memory = MemoryIndexer(store)
    correction = memory.index_correction(CorrectionEvent(
        client_id="client-a", document_id="doc-a-prev", vendor_gstin=GSTIN, field="party_ledger",
        hsn_sac="8482", description="Bearings", old_ledger=WRONG, new_ledger=CORRECTED,
    ))
    store.upsert(
        "client-a", "ledger:purchases-bearings", ChunkType.LEDGER,
        "Ledger Purchases - Bearings. Parent group Purchase Accounts.",
        {"name": WRONG, "parent_group": "Purchase Accounts"},
    )
    # Same vendor text as A's correction, but a narration edit. It must not become B's party ledger.
    memory.index_correction(CorrectionEvent(
        client_id="client-b", document_id="doc-b-prev", vendor_gstin=GSTIN, field="narration",
        hsn_sac="8482", description="Bearings", old_ledger="old note", new_ledger=CORRECTED,
    ))
    prompts = []

    def fake(_model, prompt, invoice_data, _context, _policy):
        prompts.append(prompt)
        return _model_keeps_purchase_ledger(invoice_data)

    worker = MapWorker(UsageWriter(), Retriever(store))
    with patch.object(MapWorker, "_call_llm", side_effect=fake):
        result_a = worker.map_invoice_result("client-a", _bill("doc-a-next"), "policy")
        result_b = worker.map_invoice_result("client-b", _bill("doc-b-next"), "policy")
        unrelated = worker.map_invoice_result(
            "client-a",
            _bill("doc-a-other", gstin="27ZZZZZ9999Z1Z9", name="Other Mills", desc="Stationery paper", hsn="4820"),
            "policy",
        )

    assert result_a.draft.party_ledger == CORRECTED
    assert result_a.draft.lines[0].ledger == "Purchases"
    assert result_a.trace.party_ledger_chunk_id == correction["chunk_id"]
    assert result_a.trace.party_ledger_from_memory == CORRECTED
    assert result_a.trace.retrieved_chunk_ids[0] == correction["chunk_id"]
    assert f"set party_ledger to {CORRECTED} from memory chunk {correction['chunk_id']}" in prompts[0]

    assert result_b.draft.party_ledger == WRONG
    assert result_b.trace.party_ledger_chunk_id is None
    assert result_b.trace.party_ledger_from_memory is None
    assert correction["chunk_id"] not in result_b.trace.retrieved_chunk_ids
    assert "Required: set party_ledger" not in prompts[1]

    assert unrelated.draft.party_ledger == WRONG
    assert unrelated.trace.party_ledger_from_memory is None
    assert "Required: set party_ledger" not in prompts[2]


def test_party_ledger_sentence_overrides_without_metadata_ledger():
    store = Indexer()
    content = (
        "Correction for 29ABCDE1234F1Z5: Bearings HSN 8482; "
        "party_ledger changed from Due to Vendor to SKF India - Sundry Creditors"
    )
    store.upsert("client-a", "correction:sentence", ChunkType.MEMORY, content, {
        "gstin": GSTIN, "hsn": "8482", "description": "Bearings", "field": "party_ledger",
    })
    worker = MapWorker(UsageWriter(), Retriever(store))
    with patch.object(MapWorker, "_call_llm", side_effect=lambda *_args: _model_keeps_purchase_ledger(_args[2])):
        result = worker.map_invoice_result("client-a", _bill("doc-sentence"), "policy")
    assert result.draft.party_ledger == CORRECTED
    assert result.trace.party_ledger_chunk_id == "correction:sentence"
    assert result.trace.party_ledger_from_memory == CORRECTED
