"""Fake-HTTP coverage for the OpenRouter adapter. No socket and no provider account."""

import base64
import inspect
import json
import socket
from pathlib import Path

import pytest

from extract.extract_worker import ExtractWorker
from extract.failures import INVALID_MODEL_OUTPUT, ExtractFailure
from usage.kill_switch import KillSwitch
from usage.model_router import ModelRouter, Settings
from usage.provider import persisted_cost_usd
from usage.providers.gemini import GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE, GEMINI_OUTPUT_TOKEN_ALLOWANCE, gemini_output_allowance
from usage.providers.openrouter import OPENROUTER_DEFAULT_MODEL, OpenRouterProvider, OpenRouterSettings
from usage.providers.openrouter_transport import (
    OPENROUTER_CHAT_COMPLETIONS_URL,
    REASONING_OFF,
    HttpOpenRouterTransport,
)
from usage.providers.transport import TransportError
from usage.usage_writer import UsageWriter

FAKE_KEY = "test-openrouter-key"
CANARY = "FINLEDGER_PII_CANARY_9f3c2a1b"
MODEL = "qwen/qwen3.7-flash"
_MODEL_ENV = (
    "FINLEDGER_MODEL_EXTRACT",
    "FINLEDGER_MODEL_EXTRACT_VISION",
    "FINLEDGER_MODEL_RISK",
    "FINLEDGER_MODEL_MAP",
    "FINLEDGER_MODEL_SUMMARY",
    "FINLEDGER_OPENROUTER_MODEL",
)
_PURPOSES = ("extract", "extract_vision", "map", "risk_llm", "summary")


class FakeHttp:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        if not self._results:
            raise AssertionError("unexpected HTTP call")
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _chat(content: str, usage: dict | None = None) -> bytes:
    payload: dict = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    if usage is not None:
        payload["usage"] = usage
    return json.dumps(payload).encode()


def _usage(prompt_tokens: int, completion_tokens: int, cost: float | None = None, **extra) -> dict:
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        **extra,
    }
    if cost is not None:
        usage["cost"] = cost
    return usage


def _transport(http, **kwargs) -> HttpOpenRouterTransport:
    return HttpOpenRouterTransport(credential=FAKE_KEY, http_post=http, timeout_seconds=5, **kwargs)


def _settings(**overrides) -> Settings:
    values = {
        "provider": "openrouter",
        "model_extract": MODEL,
        "model_extract_vision": MODEL,
        "model_risk_llm": MODEL,
        "model_map": MODEL,
        "model_summary": MODEL,
    }
    values.update(overrides)
    return Settings(**values)


def _router(http, monkeypatch, **settings) -> ModelRouter:
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    return ModelRouter(_settings(**settings), openrouter_transport=_transport(http))


def _clear_model_env(monkeypatch) -> None:
    for name in _MODEL_ENV:
        monkeypatch.delenv(name, raising=False)


def _invoice_json() -> str:
    return json.dumps({
        "document_id": "d1",
        "document_type": "purchase_invoice",
        "vendor": {"name": "Vendor"},
        "invoice_no": "INV-1",
        "total": 10,
    })


def test_request_is_chat_completions_json_with_reasoning_off():
    assert OPENROUTER_CHAT_COMPLETIONS_URL == "https://openrouter.ai/api/v1/chat/completions"
    assert REASONING_OFF == {"effort": "none"}
    assert GEMINI_OUTPUT_TOKEN_ALLOWANCE == 256
    assert GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE == 4096
    http = FakeHttp([(200, _chat('{"invoice_no":"INV-1"}', _usage(3, 4, 0.01)))])
    response = _transport(http).generate(
        model=MODEL, purpose="extract", payload={"markdown": f"Total 1 {CANARY}"}
    )
    assert json.loads(response.text)["invoice_no"] == "INV-1"
    assert response.tokens_in == 3 and response.tokens_out == 4
    assert response.usage_known is True and response.cost_known is True
    assert response.cost_usd == pytest.approx(0.01)
    call = http.calls[0]
    assert call["url"] == OPENROUTER_CHAT_COMPLETIONS_URL
    assert call["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert FAKE_KEY.encode() not in call["body"]
    assert CANARY.encode() in call["body"]
    assert call["timeout"] == 5
    body = json.loads(call["body"])
    assert body["model"] == MODEL
    assert body["max_tokens"] == 256
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning"] == {"effort": "none"}
    assert "generationConfig" not in body and "inline_data" not in call["body"].decode()
    assert len(body["messages"]) == 1 and body["messages"][0]["role"] == "user"
    content = json.loads(body["messages"][0]["content"])
    assert content["purpose"] == "extract"
    assert "chunks" not in content["payload"]
    assert set(content["payload"]) == {"markdown"}


@pytest.mark.parametrize("purpose", ["extract", "extract_vision", "risk_llm", "summary", "map"])
def test_max_tokens_follows_the_purpose_allowance(purpose):
    expected = 4096 if purpose == "map" else 256
    assert gemini_output_allowance(purpose) == expected
    http = FakeHttp([(200, _chat("{}", _usage(1, 1)))])
    _transport(http).generate(model=MODEL, purpose=purpose, payload={"markdown": "x"})
    assert json.loads(http.calls[0]["body"])["max_tokens"] == expected


def test_images_are_image_url_data_urls_and_omitted_from_the_text_json():
    blob = b"\x89PNG\r\n" + b"x" * 40
    http = FakeHttp([(200, _chat("{}", _usage(2, 2)))])
    _transport(http).generate(
        model=MODEL,
        purpose="extract_vision",
        payload={"markdown": "", "page_image_bytes": [blob]},
    )
    body = json.loads(http.calls[0]["body"])
    assert body["max_tokens"] == 256
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "page_image_bytes" not in content[0]["text"]
    assert "chunks" not in content[0]["text"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.b64encode(blob).decode("ascii")},
    }
    assert b"inline_data" not in http.calls[0]["body"]
    assert b"page_image_bytes" not in http.calls[0]["body"]


def test_visible_content_is_kept_and_a_reasoning_trace_alone_is_rejected():
    http = FakeHttp([(200, json.dumps({
        "choices": [{"message": {"role": "assistant", "content": '{"ok":true}', "reasoning": "thinking"}}],
        "usage": _usage(1, 2),
    }).encode())])
    response = _transport(http).generate(model=MODEL, purpose="summary", payload={"text": "x"})
    assert response.text == '{"ok":true}'
    assert "thinking" not in response.text

    http = FakeHttp([(200, json.dumps({
        "choices": [{"message": {"role": "assistant", "content": None, "reasoning": '{"ok":true}'}}],
    }).encode())])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, purpose="summary", payload={"text": "x"})
    assert exc.value.code == "invalid_response"
    assert "thinking" not in str(exc.value) and FAKE_KEY not in str(exc.value)


def test_cost_is_known_only_when_usage_cost_is_a_number():
    priced = _transport(FakeHttp([(200, _chat("{}", _usage(4, 5, 0)))])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert priced.cost_known is True and priced.cost_usd == 0.0
    assert priced.tokens_in == 4 and priced.tokens_out == 5

    unpriced = _transport(FakeHttp([(200, _chat("{}", _usage(4, 5)))])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert unpriced.usage_known is True and unpriced.cost_known is False
    assert unpriced.cost_usd is None

    bogus = _transport(FakeHttp([(200, _chat("{}", {**_usage(4, 5), "cost": False}))])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert bogus.usage_known is True and bogus.cost_known is False

    # completion_tokens already includes reasoning tokens. Do not add them again.
    detailed = {
        "prompt_tokens": 3,
        "completion_tokens": 4,
        "total_tokens": 7,
        "completion_tokens_details": {"reasoning_tokens": 1000},
    }
    counted = _transport(FakeHttp([(200, _chat("{}", detailed))])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert counted.tokens_in == 3 and counted.tokens_out == 4 and counted.cost_known is False


def test_disagreement_or_malformed_tokens_are_unknown_without_erasing_a_real_cost():
    body = _chat("kept", {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 99, "cost": 0.2})
    response = _transport(FakeHttp([(200, body)])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert response.text == "kept"
    assert response.usage_known is False
    assert response.cost_known is True and response.cost_usd == pytest.approx(0.2)

    missing = _transport(FakeHttp([(200, _chat("kept"))])).generate(
        model=MODEL, purpose="extract", payload={"markdown": "x"}
    )
    assert missing.usage_known is False and missing.cost_known is False


def test_non_json_http_body_is_invalid_response_and_hides_the_key():
    http = FakeHttp([(200, b"not-json")])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, purpose="extract", payload={"markdown": CANARY})
    assert exc.value.code == "invalid_response"
    assert FAKE_KEY not in str(exc.value) and CANARY not in str(exc.value)


@pytest.mark.parametrize("status,code", [(401, "auth_rejected"), (403, "auth_rejected"), (402, "http_4xx"),
                                         (400, "http_4xx"), (429, "http_429"), (503, "http_5xx")])
def test_status_maps_to_a_fixed_category_without_the_response_body(status, code):
    secret = b"invoice-body-should-not-leak"
    http = FakeHttp([(status, secret)])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, purpose="extract", payload={"markdown": CANARY})
    assert exc.value.code == code
    assert secret.decode() not in str(exc.value)
    assert CANARY not in str(exc.value) and FAKE_KEY not in str(exc.value)


def test_blank_credential_and_unsafe_model_do_not_call_http():
    with pytest.raises(ValueError, match="credential"):
        HttpOpenRouterTransport(credential=" ", http_post=FakeHttp([]))
    http = FakeHttp([(200, _chat("{}"))])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model="qwen/bad model", purpose="extract", payload={"markdown": "x"})
    assert exc.value.code == "invalid_target"
    assert http.calls == []


def test_non_json_model_output_is_invalid_model_output(monkeypatch):
    http = FakeHttp([(200, _chat("not-json", _usage(3, 4, 0.01)))])
    worker = ExtractWorker(UsageWriter(), _router(http, monkeypatch))
    with pytest.raises(ExtractFailure) as exc:
        worker.extract("c1", "d1", "Invoice No: 1\nTotal: 10")
    assert exc.value.category == INVALID_MODEL_OUTPUT
    assert FAKE_KEY not in str(exc.value)
    assert "not-json" not in str(exc.value)
    assert CANARY not in str(exc.value)


def test_usage_row_stores_tokens_and_cost_only_when_usage_cost_is_present(monkeypatch):
    priced_http = FakeHttp([(200, _chat(_invoice_json(), _usage(11, 7, 0.00042)))])
    priced_usage = UsageWriter()
    invoice = ExtractWorker(priced_usage, _router(priced_http, monkeypatch)).extract(
        "c1", "d1", "Invoice No: INV-1\nTotal: 10"
    )
    assert invoice.invoice_no == "INV-1"
    row = priced_usage.logs[-1]
    assert row.tokens_in == 11 and row.tokens_out == 7
    assert row.cost_usd == pytest.approx(0.00042)
    assert row.model == MODEL and row.purpose == "extract"
    assert FAKE_KEY not in repr(row)
    sent = json.loads(priced_http.calls[0]["body"])
    payload = json.loads(sent["messages"][0]["content"])["payload"]
    assert "chunks" not in payload
    assert "chunks" not in priced_http.calls[0]["body"].decode()

    plain_http = FakeHttp([(200, _chat(_invoice_json(), _usage(8, 6)))])
    plain_usage = UsageWriter()
    ExtractWorker(plain_usage, _router(plain_http, monkeypatch)).extract(
        "c1", "d2", "Invoice No: INV-1\nTotal: 10"
    )
    assert plain_usage.logs[-1].tokens_in == 8
    assert plain_usage.logs[-1].tokens_out == 6
    assert plain_usage.logs[-1].cost_usd is None
    assert persisted_cost_usd(type("R", (), {"cost_computed": False, "cost_usd": 0.0})()) is None


def test_missing_usage_does_not_store_a_zero_cost_and_map_holds_4096(monkeypatch):
    http = FakeHttp([(200, _chat("{}", None))])
    kill = KillSwitch(limit=50_000)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    provider = OpenRouterProvider(
        OpenRouterSettings(model=MODEL, max_retries=0),
        _transport(http),
        kill,
        sleeper=lambda _delay: None,
    )
    response = provider.complete("map", MODEL, "c1", "d1", {"invoice": {"total": 1}})
    assert response.usage_known is False
    assert response.cost_computed is False
    assert response.tokens_out == 4096
    assert persisted_cost_usd(response) is None
    assert json.loads(http.calls[0]["body"])["max_tokens"] == 4096
    assert kill.usage("c1", "d1") == response.tokens_in + response.tokens_out
    assert kill.usage("c1", "d1") > 0


def test_explicit_zero_cost_is_stored_and_unpriced_success_is_not(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    kill = KillSwitch(limit=50_000)
    http = FakeHttp([(200, _chat("{}", _usage(3, 4, 0)))])
    response = OpenRouterProvider(
        OpenRouterSettings(model=MODEL, max_retries=0),
        _transport(http),
        kill,
        sleeper=lambda _delay: None,
    ).complete("extract", MODEL, "c1", "d1", {"markdown": "x"})
    assert response.cost_computed is True
    assert response.cost_usd == 0.0
    assert persisted_cost_usd(response) == 0.0
    assert response.tokens_out == 4


def test_transient_http_retries_and_auth_does_not(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    http = FakeHttp([(429, b"slow"), (200, _chat("{}", _usage(2, 2, 0.01)))])
    provider = OpenRouterProvider(
        OpenRouterSettings(model=MODEL, max_retries=1),
        _transport(http),
        KillSwitch(limit=50_000),
        sleeper=lambda _delay: None,
    )
    response = provider.complete("summary", MODEL, "c1", "d1", {"text": "x"})
    assert response.text == "{}"
    assert len(http.calls) == 2
    assert response.cost_computed is True

    http = FakeHttp([(401, b"denied"), (200, _chat("{}", _usage(1, 1)))])
    provider = OpenRouterProvider(
        OpenRouterSettings(model=MODEL, max_retries=2),
        _transport(http),
        KillSwitch(limit=50_000),
        sleeper=lambda _delay: None,
    )
    with pytest.raises(TransportError) as exc:
        provider.complete("summary", MODEL, "c1", "d1", {"text": CANARY})
    assert exc.value.code == "auth_rejected"
    assert len(http.calls) == 1
    assert FAKE_KEY not in str(exc.value) and CANARY not in str(exc.value)


def test_missing_key_fails_at_startup_and_the_value_is_not_in_the_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY") as exc:
        ModelRouter(_settings())
    assert FAKE_KEY not in str(exc.value)
    monkeypatch.setenv("OPENROUTER_API_KEY", "not a valid key")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY") as exc:
        ModelRouter(_settings())
    assert "not a valid key" not in str(exc.value)


def test_openrouter_defaults_every_purpose_to_qwen_unless_overridden(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("FINLEDGER_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    settings = Settings.from_env()
    router = ModelRouter(settings, openrouter_transport=_transport(FakeHttp([])))
    assert settings.model_extract == OPENROUTER_DEFAULT_MODEL
    assert all(router.resolve_model(purpose) == "qwen/qwen3.7-flash" for purpose in _PURPOSES)

    monkeypatch.setenv("FINLEDGER_OPENROUTER_MODEL", "qwen/shared-model")
    monkeypatch.setenv("FINLEDGER_MODEL_MAP", "qwen/map-only")
    monkeypatch.setenv("FINLEDGER_MODEL_RISK", "   ")
    overridden = Settings.from_env()
    assert overridden.model_extract == "qwen/shared-model"
    assert overridden.model_extract_vision == "qwen/shared-model"
    assert overridden.model_summary == "qwen/shared-model"
    assert overridden.model_risk_llm == "qwen/shared-model"
    assert overridden.model_map == "qwen/map-only"


def test_openrouter_model_env_does_not_change_mock_or_gemini_defaults(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("FINLEDGER_LLM_PROVIDER", "mock")
    monkeypatch.setenv("FINLEDGER_OPENROUTER_MODEL", "qwen/qwen3.7-flash")
    settings = Settings.from_env()
    assert settings.provider == "mock"
    assert settings.model_extract == "gemini-3.5-flash-lite"
    assert settings.model_extract_vision == "gemini-3.5-flash-lite"
    assert settings.model_map == "gemini-3.5-flash-lite"
    assert settings.model_summary == "gemini-3.5-flash-lite"
    router = ModelRouter(settings)
    assert router.resolve_model("extract") == "gemini-3.5-flash-lite"
    assert router.resolve_model("map") == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_hosted_openrouter_starts_only_when_the_key_is_present(monkeypatch, environment):
    monkeypatch.setenv("FINLEDGER_ENV", environment)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        ModelRouter(_settings())

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)

    def exploded(*_args, **_kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", exploded)
    monkeypatch.setattr("http.client.HTTPSConnection", exploded)
    router = ModelRouter(_settings())
    assert all(router.resolve_model(purpose) == MODEL for purpose in _PURPOSES)
    assert isinstance(router.provider, OpenRouterProvider)
    from usage.providers.openrouter_http import OpenRouterHttpClient

    assert isinstance(router.provider.transport._http_client, OpenRouterHttpClient)


def test_mock_and_injected_transport_do_not_construct_the_network_client(monkeypatch):
    import usage.model_router as model_router

    source = inspect.getsource(model_router)
    assert "GeminiHttpClient" not in source
    assert "OpenRouterHttpClient" not in source
    assert "http_client" not in source
    constructed = []
    monkeypatch.setattr(
        model_router,
        "build_openrouter_transport",
        lambda _credential: constructed.append("built"),
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ModelRouter(Settings(provider="mock"))
    assert constructed == []

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    ModelRouter(_settings(), openrouter_transport=_transport(FakeHttp([])))
    assert constructed == []


def test_extract_worker_does_not_call_openrouter_itself():
    text = Path(__file__).resolve().parents[3].joinpath(
        "person2_platform/src/finledger_platform/extract_worker.py"
    ).read_text(encoding="utf-8")
    assert "ModelRouter(" in text
    assert "openrouter.ai" not in text
    assert "OpenRouterHttpClient" not in text
    assert "OPENROUTER_API_KEY" not in text


def test_hosted_still_refuses_mock_and_gemini(monkeypatch):
    monkeypatch.setenv("FINLEDGER_ENV", "production")
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    with pytest.raises(RuntimeError, match="mock LLM provider"):
        ModelRouter(Settings(provider="mock"))
    with pytest.raises(RuntimeError, match="gemini LLM provider"):
        ModelRouter(Settings(provider="gemini", gemini_location="asia-south1"))
