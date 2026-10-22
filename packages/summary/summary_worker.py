import os
from contracts.schemas import CanonicalInvoice, VoucherDraft, RiskScore
from usage.model_router import ModelRouter
from usage.usage_writer import UsageWriter, log_provider_usage

class SummaryWorker:
    def __init__(self, usage_writer: UsageWriter, router: ModelRouter | None = None):
        self.usage_writer = usage_writer
        self.router = router or ModelRouter()

    def _call_llm(self, model: str, prompt: str) -> str:
        response = self.router.provider.complete("summary", model, self._client_id, self._document_id, {"text": prompt})
        self._provider_response = response
        return response.text

    def generate_summary(self, client_id: str, invoice: CanonicalInvoice, draft: VoucherDraft, risk: RiskScore) -> str:
        model = self.router.resolve_model("summary")
        self._document_id = invoice.document_id
        self._client_id = client_id
        
        prompt = f"""
        Summarize the following FinLedger processing for a human reviewer.
        Invoice: {invoice.model_dump_json()}
        Draft: {draft.model_dump_json()}
        Risk: {risk.model_dump_json()}
        """
        
        self._call_llm(model, prompt)
        rationale = "; ".join(draft.reasons[:2]) or f"mapped to ledger {draft.party_ledger}"
        response_text = "\n".join([
            f"Vendor: {invoice.vendor.name or 'Unknown vendor'}",
            f"Invoice amount: {invoice.total:.2f}",
            f"GST treatment: {draft.gst.treatment}",
            f"Risk band: {risk.band} ({risk.score}/100)",
            f"Mapping rationale: {rationale}; party ledger {draft.party_ledger}",
        ])
        
        tokens_in = len(prompt) // 4
        tokens_out = len(response_text) // 4
        response = getattr(self, "_provider_response", None)
        log_provider_usage(
            self.usage_writer,
            response,
            client_id=client_id,
            doc_id=invoice.document_id,
            model=model,
            purpose="summary",
            tokens_in=getattr(response, "tokens_in", max(1, tokens_in)),
            tokens_out=getattr(response, "tokens_out", max(1, tokens_out)),
            latency_ms=getattr(response, "latency_ms", 500),
        )
        
        return response_text.strip()
