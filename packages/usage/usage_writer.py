from dataclasses import dataclass
from typing import Optional
import datetime

@dataclass
class UsageRow:
    client_id: str
    doc_id: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float | None
    purpose: str
    timestamp: str

class UsageWriter:
    def __init__(self):
        self.logs = []

    def log_usage(
        self,
        client_id: str,
        doc_id: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        cost_usd: float | None,
        purpose: str,
        reservation_id: str | None = None,
    ) -> UsageRow:
        del reservation_id
        row = UsageRow(
            client_id=client_id,
            doc_id=doc_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            purpose=purpose,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        self.logs.append(row)
        return row


def log_provider_usage(
    writer: UsageWriter,
    response: object | None,
    *,
    client_id: str,
    doc_id: str,
    model: str,
    purpose: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
) -> UsageRow:
    """Record one call. Skip the writer when complete() already settled the durable row."""
    from usage.provider import persisted_cost_usd

    cost = persisted_cost_usd(response)
    if getattr(response, "usage_persisted", False):
        return UsageRow(
            client_id=client_id,
            doc_id=doc_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            purpose=purpose,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
    return writer.log_usage(
        client_id,
        doc_id,
        model,
        tokens_in,
        tokens_out,
        latency_ms,
        cost,
        purpose,
        reservation_id=getattr(response, "reservation_id", None),
    )
