import pytest
from usage.model_router import ModelRouter
from usage.usage_writer import UsageWriter

def test_router_resolves_model(monkeypatch):
    for name in (
        "FINLEDGER_MODEL_EXTRACT",
        "FINLEDGER_MODEL_EXTRACT_VISION",
        "FINLEDGER_MODEL_RISK",
        "FINLEDGER_MODEL_MAP",
        "FINLEDGER_MODEL_SUMMARY",
    ):
        monkeypatch.delenv(name, raising=False)
    router = ModelRouter()
    for purpose in ("extract", "extract_vision", "risk_llm", "map", "summary"):
        assert router.resolve_model(purpose) == "gemini-3.5-flash-lite"
    
    with pytest.raises(ValueError):
        router.resolve_model("invalid_purpose")

def test_usage_writer_logs_row():
    writer = UsageWriter()
    row = writer.log_usage(
        client_id="client-123",
        doc_id="doc-456",
        model="gemini-1.5-flash",
        tokens_in=1000,
        tokens_out=200,
        latency_ms=1500,
        cost_usd=0.001,
        purpose="extract"
    )
    
    assert len(writer.logs) == 1
    assert row.client_id == "client-123"
    assert row.doc_id == "doc-456"
    assert row.purpose == "extract"
    assert row.cost_usd == 0.001
    assert row.timestamp is not None
