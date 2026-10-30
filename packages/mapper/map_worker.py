import json
import os
import re
from typing import Dict, Any, List
import uuid

from contracts.schemas import CanonicalInvoice, VoucherDraft, MapTrace, MapResult
from usage.model_router import ModelRouter
from usage.usage_writer import UsageWriter, log_provider_usage
from rag.retriever import Retriever

# "changed from {old} to {new}" — the last " to " is the separator so an old name may contain " to ".
_PARTY_LEDGER_CHANGE = re.compile(
    r"(?:^|;)\s*party_ledger\s+changed from\s+(?P<old>.*)\s+to\s+(?P<new>.+)\s*$",
    re.IGNORECASE | re.DOTALL,
)
# Retriever adds this to every memory row. It is not evidence the row is about this bill.
_MEMORY_TYPE_BONUS = 2


def _chunk_type(chunk: dict) -> str:
    raw = chunk.get("chunk_type")
    value = getattr(raw, "value", raw)
    return str(value or "").strip().casefold()


def _score(chunk: dict) -> float:
    try:
        return float(chunk.get("score"))
    except (TypeError, ValueError):
        return 0.0


def _matched_this_bill(chunk: dict) -> bool:
    """True when retrieval matched a bill field, not only the memory-type bonus."""
    reasons = chunk.get("ranking_reasons")
    if isinstance(reasons, list):
        return any(str(reason).strip() for reason in reasons)
    return _score(chunk) > _MEMORY_TYPE_BONUS


def _ledger_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _party_field(field: str) -> bool:
    return field.strip().casefold() == "party_ledger"


def named_party_ledger(chunk: dict) -> str | None:
    """Ledger named by a positive-score memory chunk that matched this bill's party ledger."""
    if _chunk_type(chunk) != "memory" or _score(chunk) <= 0 or not _matched_this_bill(chunk):
        return None
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    field = str(metadata.get("field") or "")
    if field and not _party_field(field):
        return None
    named = _ledger_name(metadata.get("new_ledger"))
    if _party_field(field) and named:
        return named
    match = _PARTY_LEDGER_CHANGE.search(str(chunk.get("content") or ""))
    if not match:
        return None
    return _ledger_name(match.group("new")) or None


def top_party_ledger_memory(chunks: List[dict]) -> tuple[str, str] | None:
    """Highest-ranked retrieved memory chunk that names a party ledger for this bill."""
    for chunk in chunks:
        ledger = named_party_ledger(chunk)
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if ledger and chunk_id:
            return chunk_id, ledger
    return None


def apply_party_ledger_memory(draft: dict, chunks: List[dict]) -> tuple[str, str] | None:
    """Overwrite party_ledger from the top matching memory chunk. The model cannot keep its own name."""
    found = top_party_ledger_memory(chunks)
    if not found or not isinstance(draft, dict):
        return None
    chunk_id, ledger = found
    draft["party_ledger"] = ledger
    return found


class MapWorker:
    def __init__(self, usage_writer: UsageWriter, retriever: Retriever, router: ModelRouter | None = None):
        self.usage_writer = usage_writer
        self.router = router or ModelRouter()
        self.retriever = retriever
        self.prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "map_prompt.txt")

    def _call_llm(self, model: str, prompt: str, invoice_data: str, context: str, policy: str) -> str:
        response = self.router.provider.complete("map", model, self._client_id, self._document_id, {
            "prompt": prompt, "invoice": json.loads(invoice_data), "chunks": json.loads(context), "policy": policy})
        self._provider_response = response
        return response.text

    def map_invoice(self, client_id: str, invoice: CanonicalInvoice, policy: str) -> VoucherDraft:
        return self.map_invoice_result(client_id, invoice, policy).draft

    def map_invoice_result(self, client_id: str, invoice: CanonicalInvoice, policy: str) -> MapResult:
        model = self.router.resolve_model("map")
        self._document_id = invoice.document_id
        self._client_id = client_id
        
        with open(self.prompt_path, "r") as f:
            prompt_template = f.read()

        # Gather fields to query retriever
        desc = [item.desc for item in invoice.line_items]
        hsn = invoice.line_items[0].hsn_sac if invoice.line_items else ""
        amount_band = str(invoice.total)
        
        chunks = self.retriever.retrieve(
            client_id=client_id,
            gstin=invoice.vendor.gstin,
            vendor_name=invoice.vendor.name,
            descriptions=desc,
            hsn=hsn,
            amount_band=amount_band,
            doc_type=invoice.document_type
        )
        
        chunk_context = json.dumps(chunks)
        invoice_json = invoice.model_dump_json()
        memory_ledger = top_party_ledger_memory(chunks)
        prompt = prompt_template
        if memory_ledger:
            chunk_id, ledger = memory_ledger
            prompt += (
                "\nRequired: set party_ledger to "
                f"{' '.join(ledger.split())} from memory chunk {chunk_id}. "
                "This party-ledger correction outranks every other party name.\n"
            )

        # LLM Call
        response_text = self._call_llm(model, prompt, invoice_json, chunk_context, policy)
        
        tokens_in = len(prompt + invoice_json + chunk_context + policy) // 4
        tokens_out = len(response_text) // 4
        response = getattr(self, "_provider_response", None)
        usage_row = log_provider_usage(
            self.usage_writer,
            response,
            client_id=client_id,
            doc_id=invoice.document_id,
            model=model,
            purpose="map",
            tokens_in=getattr(response, "tokens_in", max(1, tokens_in)),
            tokens_out=getattr(response, "tokens_out", max(1, tokens_out)),
            latency_ms=getattr(response, "latency_ms", 1200),
        )
        
        clean_json = re.sub(r'```json|```', '', response_text).strip()
        data = json.loads(clean_json)

        # Build MapTrace
        map_trace_id = str(uuid.uuid4())
        data["map_trace_id"] = map_trace_id
        # The model sees the correction in the prompt. Apply it again so a wrong party_ledger cannot stick.
        applied = apply_party_ledger_memory(data, chunks) if isinstance(data, dict) else None

        draft = VoucherDraft(**data)
        trace = MapTrace(map_trace_id=map_trace_id, document_id=invoice.document_id, client_id=client_id,
            retrieved_chunk_ids=[chunk["chunk_id"] for chunk in chunks], model_name=model,
            tokens_in=usage_row.tokens_in, tokens_out=usage_row.tokens_out, cost_usd=usage_row.cost_usd,
            party_ledger_chunk_id=applied[0] if applied else None,
            party_ledger_from_memory=applied[1] if applied else None)
        return MapResult(draft=draft, trace=trace)
