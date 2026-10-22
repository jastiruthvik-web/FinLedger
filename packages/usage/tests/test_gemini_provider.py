import json
from pathlib import Path

import pytest

from usage.kill_switch import KillSwitch
from usage.model_router import ModelRouter, Settings
from usage.provider import ProviderResponse, _tokens
from usage.provider_errors import ProviderTransientError
from usage.providers.gemini import GeminiProvider, GeminiSettings
from usage.providers.http_transport import HttpGeminiTransport
from usage.providers.transport import FakeGeminiTransport, TransportError, TransportResponse
from usage.usage_writer import UsageWriter

CANARY = "FINLEDGER_PII_CANARY_9f3c2a1b"


def _provider(transport: FakeGeminiTransport) -> GeminiProvider:
    return GeminiProvider(
        GeminiSettings(model="gemini-1.5-flash", location="asia-south1", max_request_bytes=128, max_retries=1),
        transport,
        KillSwitch(limit=50_000, enabled=True),
        sleeper=_noop_sleeper,
    )


def test_fake_transport_success_without_network():
    transport = FakeGeminiTransport([TransportResponse('{"ok":true}', 3, 4, 2)])
    response = _provider(transport).complete("extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "Invoice No: 1\nTotal: 1"})
    assert json.loads(response.text)["ok"] is True
    assert CANARY not in json.dumps(transport.calls)


@pytest.mark.parametrize("code", ["timeout", "http_429", "http_5xx", "transport_unavailable"])
def test_transient_errors_retry_then_provider_transient(code):
    transport = FakeGeminiTransport([TransportError(code), TransportError(code)])
    with pytest.raises(ProviderTransientError):
        _provider(transport).complete("extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"})
    assert len(transport.calls) == 2


def test_malformed_json_response_is_returned_as_text():
    transport = FakeGeminiTransport([TransportResponse("not-json", 1, 1)])
    response = _provider(transport).complete("extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"})
    assert response.text == "not-json"


def test_oversize_image_rejected():
    transport = FakeGeminiTransport([TransportResponse("{}", 1, 1)])
    with pytest.raises(TransportError, match="payload_too_large"):
        _provider(
            transport
        ).complete(
            "extract_vision",
            "gemini-1.5-pro",
            "c1",
            "d1",
            {"markdown": "", "page_image_bytes": [b"x" * 200]},
        )
    assert transport.calls == []


def test_router_rejects_gemini_without_transport():
    with pytest.raises(ValueError, match="explicit transport"):
        ModelRouter(Settings(provider="gemini", gemini_location="asia-south1"))


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_gemini_provider_blocked_in_hosted_environment(monkeypatch, environment):
    monkeypatch.setenv("FINLEDGER_ENV", environment)
    with pytest.raises(RuntimeError, match="gemini LLM provider"):
        ModelRouter(Settings(provider="gemini", gemini_location="asia-south1"), gemini_transport=FakeGeminiTransport())


def _noop_sleeper(_delay: float) -> None:
    return None


def _http_provider(http, kill: KillSwitch, **settings):
    from usage.providers import gemini as gemini_mod

    tariff_cls = getattr(gemini_mod, "GeminiTariff", None)
    kwargs = {"sleeper": _noop_sleeper}
    if settings.pop("priced", False):
        assert tariff_cls is not None
        kwargs["tariff"] = tariff_cls(input_usd_per_million=2, output_usd_per_million=4)
    provider_kwargs = {}
    if "sleeper" in GeminiProvider.__init__.__code__.co_varnames:
        provider_kwargs["sleeper"] = kwargs["sleeper"]
    if "tariff" in kwargs and "tariff" in GeminiProvider.__init__.__code__.co_varnames:
        provider_kwargs["tariff"] = kwargs["tariff"]
    return GeminiProvider(
        GeminiSettings(model="gemini-1.5-flash", location="asia-south1", max_retries=settings.get("max_retries", 1)),
        HttpGeminiTransport(credential="test-credential-do-not-log", project="finledger-test", http_post=http, timeout_seconds=5),
        kill,
        **provider_kwargs,
    )


def _body(text: str, usage: dict | None) -> bytes:
    payload: dict = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if usage is not None:
        payload["usageMetadata"] = usage
    return json.dumps(payload).encode()


class _ScriptedHttp:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(body)
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_reasoning_body_reconciles_full_chargeable_usage_and_fixture_cost():
    http = _ScriptedHttp([(200, _body("{}", {
        "promptTokenCount": 3, "candidatesTokenCount": 4, "thoughtsTokenCount": 1000, "totalTokenCount": 1007,
    }))])
    kill = KillSwitch(limit=50_000)
    response = _http_provider(http, kill, priced=True, max_retries=0).complete(
        "extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"}
    )
    assert response.tokens_in == 3
    assert response.tokens_out == 1004
    assert kill.usage("c1", "d1") == 1007
    assert getattr(response, "usage_known", False) is True
    assert getattr(response, "cost_computed", False) is True
    assert response.cost_usd == pytest.approx((3 * 2 + 1004 * 4) / 1_000_000)
    assert response.cost_usd > 0
    request = json.loads(http.calls[0])
    assert request["generationConfig"]["maxOutputTokens"] == 256


def test_missing_usage_reconciles_the_hold_instead_of_releasing_zero():
    http = _ScriptedHttp([(200, _body("kept", None))])
    kill = KillSwitch(limit=50_000)
    response = _http_provider(http, kill, max_retries=0).complete(
        "extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"}
    )
    assert response.text == "kept"
    assert getattr(response, "usage_known", True) is False
    assert response.tokens_out == 256
    assert response.tokens_in == _tokens(json.dumps({"markdown": "x"}, sort_keys=True))
    assert kill.usage("c1", "d1") == response.tokens_in + response.tokens_out
    assert kill.usage("c1", "d1") > 0
    assert kill.reserved("c1", "d1") == 0
    assert getattr(response, "cost_computed", True) is False
    assert response.cost_usd == 0.0


def test_output_over_the_allowance_is_reconciled_at_the_larger_actual():
    http = _ScriptedHttp([(200, _body("{}", {
        "promptTokenCount": 3, "candidatesTokenCount": 400, "totalTokenCount": 403,
    }))])
    kill = KillSwitch(limit=50_000)
    response = _http_provider(http, kill, max_retries=0).complete(
        "extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"}
    )
    assert response.tokens_out == 400
    assert kill.usage("c1", "d1") == 403
    assert json.loads(http.calls[0])["generationConfig"]["maxOutputTokens"] == 256


def test_image_reservation_uses_fixture_allowance_not_raw_bytes():
    from usage.providers import gemini as gemini_mod

    image_allowance = getattr(gemini_mod, "GEMINI_IMAGE_INPUT_TOKEN_ALLOWANCE", None)
    output_allowance = getattr(gemini_mod, "GEMINI_OUTPUT_TOKEN_ALLOWANCE", None)
    assert image_allowance == 1024
    assert output_allowance == 256

    def reserved_for(blob: bytes) -> int:
        kill = KillSwitch(limit=500_000)
        seen: dict[str, int] = {}

        class Capture(FakeGeminiTransport):
            def generate(self, **kwargs):
                seen["reserved"] = kill.reserved("c1", "d1")
                return TransportResponse("{}", 1, 1, 1)

        GeminiProvider(
            GeminiSettings(model="gemini-1.5-flash", location="asia-south1", max_retries=0),
            Capture(),
            kill,
            **({"sleeper": _noop_sleeper} if "sleeper" in GeminiProvider.__init__.__code__.co_varnames else {}),
        ).complete(
            "extract_vision", "gemini-1.5-pro", "c1", "d1",
            {"markdown": "x", "page_image_bytes": [blob]},
        )
        return seen["reserved"]

    small = reserved_for(b"a")
    large = reserved_for(b"a" * 80_000)
    assert small == large
    text_tokens = _tokens(json.dumps({"markdown": "x"}, sort_keys=True))
    assert small == text_tokens + image_allowance + output_allowance


def test_retry_with_a_body_settles_that_attempt_and_holds_the_next():
    http = _ScriptedHttp([
        (500, b"billed-attempt"),
        (200, _body("{}", {"promptTokenCount": 3, "candidatesTokenCount": 4, "totalTokenCount": 7})),
    ])
    kill = KillSwitch(limit=50_000)
    response = _http_provider(http, kill, max_retries=1).complete(
        "extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"}
    )
    hold = _tokens(json.dumps({"markdown": "x"}, sort_keys=True)) + 256
    assert response.tokens_in == 3 and response.tokens_out == 4
    assert kill.usage("c1", "d1") == hold + 7
    assert len(http.calls) == 2


def test_timeout_without_a_body_stays_uncounted():
    http = _ScriptedHttp([
        TimeoutError("no body"),
        (200, _body("{}", {"promptTokenCount": 3, "candidatesTokenCount": 4, "totalTokenCount": 7})),
    ])
    kill = KillSwitch(limit=50_000)
    response = _http_provider(http, kill, max_retries=1).complete(
        "extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"}
    )
    assert response.tokens_in + response.tokens_out == 7
    assert kill.usage("c1", "d1") == 7


def test_backoff_sleeper_is_bounded_by_max_retries():
    sleeps: list[float] = []
    transport = FakeGeminiTransport([TransportError("timeout"), TransportError("timeout"), TransportError("timeout")])
    kwargs = {}
    if "sleeper" in GeminiProvider.__init__.__code__.co_varnames:
        kwargs["sleeper"] = sleeps.append
    provider = GeminiProvider(
        GeminiSettings(model="gemini-1.5-flash", location="asia-south1", max_retries=2),
        transport,
        KillSwitch(limit=50_000),
        **kwargs,
    )
    with pytest.raises(ProviderTransientError):
        provider.complete("extract", "gemini-1.5-flash", "c1", "d1", {"markdown": "x"})
    assert len(transport.calls) == 3
    assert len(sleeps) == 2
    assert all(isinstance(delay, (int, float)) and delay > 0 and delay <= 1 for delay in sleeps)
    assert provider._sleeper is not None


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, False])
def test_gemini_settings_reject_bad_timeouts(timeout):
    with pytest.raises(ValueError):
        GeminiSettings(model="gemini-1.5-flash", location="asia-south1", timeout_seconds=timeout)


@pytest.mark.parametrize("bound", [0, -1, True, False])
def test_gemini_settings_reject_bad_size_bounds(bound):
    with pytest.raises(ValueError):
        GeminiSettings(model="gemini-1.5-flash", location="asia-south1", max_request_bytes=bound)


def test_mock_provider_still_logs_a_zero_cost_and_unpriced_gemini_does_not():
    from extract.extract_worker import ExtractWorker
    from extract.vision_fallback import ExtractionDispatcher
    from mapper.map_worker import MapWorker
    from rag.indexer import Indexer
    from rag.retriever import Retriever
    from safety.risk_worker import RiskWorker
    from summary.summary_worker import SummaryWorker
    from contracts.schemas import CanonicalInvoice, RiskScore, Vendor, VoucherDraft
    from usage.provider import MockProvider, persisted_cost_usd

    assert persisted_cost_usd(ProviderResponse("{}", 1, 1)) == 0.0
    assert persisted_cost_usd(None) == 0.0
    unpriced = ProviderResponse("{}", 3, 4, 1, 0.0, cost_computed=False)
    assert persisted_cost_usd(unpriced) is None
    assert persisted_cost_usd(ProviderResponse("{}", 3, 4, 1, 0.125, cost_computed=True)) == 0.125

    golden = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "golden" / "intra_gst_18.json").read_text())
    golden["document_id"] = "doc-cost"
    invoice_text = json.dumps(golden)

    class Router:
        def __init__(self, response):
            self.provider = self

            def complete(*_args, **_kwargs):
                return response

            self.complete = complete

        def resolve_model(self, _purpose):
            return "gemini-1.5-flash"

    usage = UsageWriter()
    worker = ExtractWorker(usage)
    worker.router = Router(ProviderResponse(invoice_text, 3, 4, 1, 0.0, cost_computed=False))
    worker.extract("client-a", "doc-cost", "Invoice No: INV-01\nTotal: 1")
    assert usage.logs[-1].cost_usd is None

    mock_usage = UsageWriter()
    mock_invoice = ExtractWorker(mock_usage).extract("client-a", "doc-mock", "Invoice No: INV-01\nTotal: 59000")
    assert mock_invoice.invoice_no
    assert mock_usage.logs[-1].cost_usd == 0.0

    vision_usage = UsageWriter()
    vision = ExtractionDispatcher(ExtractWorker(vision_usage))
    vision.worker.router = Router(ProviderResponse(invoice_text, 3, 4, 1, 0.0, cost_computed=False))
    vision.extract("client-a", "doc-cost", "  ", ["client-a/p.png"], [b"scan"])
    assert vision_usage.logs[-1].cost_usd is None

    invoice = CanonicalInvoice(
        document_id="doc-cost", document_type="purchase_invoice",
        vendor=Vendor(name="Vendor X", gstin="29XYZ", pan="XYZ", state="KA"),
        invoice_no="INV-123", invoice_date="2026-09-01", due_date="2026-10-01", total=100.0, taxable=100.0,
    )
    draft_json = json.dumps({
        "document_id": "doc-cost", "date": "2026-09-01", "voucher_type": "purchase",
        "party_ledger": "Vendor X Ledger", "party_create_proposal": False,
        "lines": [{"ledger": "Purchases", "amount": 100.0, "is_debit": True}],
        "gst": {"treatment": "intra", "input_ledgers": [], "tax_breakup": {}},
        "tds": {"applicable": False, "amount": 0.0},
        "bill_wise": {"ref_type": "new_ref", "ref": "INV-123", "due_date": "2026-10-01"},
        "narration": "Being purchase from Vendor X", "attachment_document_id": "doc-cost",
        "reasons": ["Mapped because of RAG match"],
    })
    map_usage = UsageWriter()
    mapper = MapWorker(map_usage, Retriever(Indexer()))
    mapper.router = Router(ProviderResponse(draft_json, 8, 9, 1, 0.0, cost_computed=False))
    result = mapper.map_invoice_result("client-a", invoice, "policy")
    assert map_usage.logs[-1].cost_usd is None
    assert result.trace.cost_usd is None

    draft = result.draft
    risk_json = json.dumps({
        "document_id": "doc-cost", "score": 0, "band": "low",
        "marks": [{"field": "narration", "check": "suspicious_language", "ok": True, "note": "ok"}],
    })
    risk_usage = UsageWriter()
    risk = RiskWorker(risk_usage)
    risk.router = Router(ProviderResponse(risk_json, 2, 2, 1, 0.0, cost_computed=False))
    score = risk.assess_risk("client-a", invoice, draft)
    assert score.band == "low"
    assert risk_usage.logs[-1].cost_usd is None

    summary_usage = UsageWriter()
    summary = SummaryWorker(summary_usage)
    summary.router = Router(ProviderResponse("ignored", 2, 2, 1, 0.0, cost_computed=False))
    text = summary.generate_summary("client-a", invoice, draft, RiskScore(**json.loads(risk_json)))
    assert "Vendor X" in text
    assert summary_usage.logs[-1].cost_usd is None
