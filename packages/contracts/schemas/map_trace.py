from typing import List
from pydantic import BaseModel
from contracts.schemas.voucher_draft import VoucherDraft

class MapTrace(BaseModel):
    map_trace_id: str
    document_id: str
    client_id: str
    retrieved_chunk_ids: List[str]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None
    # Set when a retrieved party-ledger correction replaced the model's party ledger.
    party_ledger_chunk_id: str | None = None
    party_ledger_from_memory: str | None = None


class MapResult(BaseModel):
    draft: VoucherDraft
    trace: MapTrace
