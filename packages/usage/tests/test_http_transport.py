"""Fake-HTTP coverage for the Gemini transport. No socket and no provider account."""

import json

import pytest

from usage.kill_switch import KillSwitch
from usage.model_router import ModelRouter, Settings
from usage.provider_errors import ProviderTransientError
from usage.providers.gemini import GeminiProvider, GeminiSettings, gemini_output_allowance
from usage.providers.http_transport import HttpGeminiTransport, build_generate_url
from usage.providers.transport import TransportError

CREDENTIAL = "test-credential-do-not-log"
CANARY = "FINLEDGER_PII_CANARY_9f3c2a1b"
PROJECT = "finledger-test"
LOCATION = "asia-south1"
MODEL = "gemini-1.5-flash"


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


def _ok_body(text='{"invoice_no":"INV-1"}', tokens_in=3, tokens_out=4) -> bytes:
    return json.dumps({
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": tokens_in, "candidatesTokenCount": tokens_out},
    }).encode()


def _transport(http, **kwargs) -> HttpGeminiTransport:
    return HttpGeminiTransport(credential=CREDENTIAL, project=PROJECT, http_post=http, timeout_seconds=5, **kwargs)


def test_request_uses_explicit_location_and_model_and_hides_credential():
    http = FakeHttp([(200, _ok_body())])
    response = _transport(http).generate(
        model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": f"Total 1 {CANARY}"}
    )
    assert json.loads(response.text)["invoice_no"] == "INV-1"
    assert response.tokens_in == 3 and response.tokens_out == 4
    call = http.calls[0]
    assert call["url"] == build_generate_url(location=LOCATION, model=MODEL, project=PROJECT)
    assert call["url"].count(LOCATION) == 2
    assert "europe-west" not in call["url"] and "gemini-1.5-pro" not in call["url"]
    assert call["headers"]["Authorization"] == f"Bearer {CREDENTIAL}"
    assert CREDENTIAL not in call["url"] and CREDENTIAL.encode() not in call["body"]
    assert CANARY.encode() in call["body"]
    assert call["timeout"] == 5


def test_other_location_is_not_rewritten():
    http = FakeHttp([(200, _ok_body())])
    _transport(http).generate(model=MODEL, location="europe-west3", purpose="extract", payload={"markdown": "x"})
    assert "/locations/europe-west3/" in http.calls[0]["url"]
    assert LOCATION not in http.calls[0]["url"]


@pytest.mark.parametrize("status,code", [(401, "auth_rejected"), (403, "auth_rejected"), (400, "http_4xx"),
                                         (429, "http_429"), (503, "http_5xx"), (500, "http_5xx")])
def test_status_maps_to_fixed_category_without_response_body(status, code):
    secret = b"invoice-body-should-not-leak"
    http = FakeHttp([(status, secret)])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": CANARY})
    assert exc.value.code == code
    assert secret.decode() not in str(exc.value)
    assert CANARY not in str(exc.value)
    assert CREDENTIAL not in str(exc.value)


def test_timeout_and_transport_failure_hide_credential_and_payload():
    http = FakeHttp([TimeoutError(f"timed out {CREDENTIAL} {CANARY}")])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": CANARY})
    assert exc.value.code == "timeout"
    assert CREDENTIAL not in str(exc.value) and CANARY not in str(exc.value)

    http = FakeHttp([RuntimeError(f"connection reset {CREDENTIAL}")])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": CANARY})
    assert exc.value.code == "transport_unavailable"
    assert CREDENTIAL not in str(exc.value)


def test_oversized_request_is_rejected_before_http():
    http = FakeHttp([(200, _ok_body())])
    with pytest.raises(TransportError) as exc:
        _transport(http, max_request_bytes=32).generate(
            model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x" * 80}
        )
    assert exc.value.code == "payload_too_large"
    assert http.calls == []


def test_oversized_and_malformed_responses_are_fixed_categories():
    http = FakeHttp([(200, b"x" * 50)])
    with pytest.raises(TransportError) as exc:
        _transport(http, max_response_bytes=16).generate(
            model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
        )
    assert exc.value.code == "response_too_large"
    http = FakeHttp([(200, b'{"candidates":[]}')])
    with pytest.raises(TransportError) as exc:
        _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert exc.value.code == "invalid_response"
    assert "candidates" not in str(exc.value)


@pytest.mark.parametrize("location,model,project", [("", MODEL, PROJECT), (LOCATION, "", PROJECT),
                                                    (LOCATION, MODEL, "../other"), ("asia south1", MODEL, PROJECT)])
def test_missing_or_unsafe_target_does_not_call_http(location, model, project):
    http = FakeHttp([(200, _ok_body())])
    transport = HttpGeminiTransport(credential=CREDENTIAL, project=PROJECT, http_post=http)
    with pytest.raises(TransportError) as exc:
        if project != PROJECT:
            HttpGeminiTransport(credential=CREDENTIAL, project=project, http_post=http)
        else:
            transport.generate(model=model, location=location, purpose="extract", payload={"markdown": "x"})
    assert exc.value.code == "invalid_target"
    assert http.calls == []


def test_blank_credential_is_refused():
    with pytest.raises(ValueError, match="credential"):
        HttpGeminiTransport(credential=" ", project=PROJECT, http_post=FakeHttp([]))


def test_provider_retries_only_bounded_transient_http_and_keeps_auth_failure():
    http = FakeHttp([(429, b"slow down"), (200, _ok_body("{}", 2, 2))])
    provider = GeminiProvider(
        GeminiSettings(model=MODEL, location=LOCATION, max_retries=1),
        _transport(http),
        KillSwitch(limit=50_000, enabled=True),
        sleeper=lambda _delay: None,
    )
    response = provider.complete("extract", MODEL, "c1", "d1", {"markdown": "x"})
    assert response.text == "{}"
    assert len(http.calls) == 2

    http = FakeHttp([(401, b"denied"), (200, _ok_body())])
    provider = GeminiProvider(
        GeminiSettings(model=MODEL, location=LOCATION, max_retries=2),
        _transport(http),
        KillSwitch(limit=50_000, enabled=True),
        sleeper=lambda _delay: None,
    )
    with pytest.raises(TransportError) as exc:
        provider.complete("extract", MODEL, "c1", "d1", {"markdown": CANARY})
    assert exc.value.code == "auth_rejected"
    assert len(http.calls) == 1
    assert CANARY not in str(exc.value)

    http = FakeHttp([(503, b"down"), (503, b"down")])
    provider = GeminiProvider(
        GeminiSettings(model=MODEL, location=LOCATION, max_retries=1),
        _transport(http),
        KillSwitch(limit=50_000, enabled=True),
        sleeper=lambda _delay: None,
    )
    with pytest.raises(ProviderTransientError):
        provider.complete("extract", MODEL, "c1", "d1", {"markdown": "x"})
    assert len(http.calls) == 2


def test_hosted_guard_still_blocks_an_explicit_http_transport(monkeypatch):
    monkeypatch.setenv("FINLEDGER_ENV", "production")
    transport = _transport(FakeHttp([(200, _ok_body())]))
    with pytest.raises(RuntimeError, match="gemini LLM provider cannot run in a hosted environment"):
        ModelRouter(Settings(provider="gemini", gemini_location=LOCATION), gemini_transport=transport)


def _usage_body(text: str = "{}", **usage) -> bytes:
    payload: dict = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    if usage:
        payload["usageMetadata"] = usage
    return json.dumps(payload).encode()


# Vertex generateContent UsageMetadata, read 2026-10-22:
# https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1beta1/GenerateContentResponse
# totalTokenCount = promptTokenCount + candidatesTokenCount + toolUsePromptTokenCount + thoughtsTokenCount.
# thoughtsTokenCount is generated thoughts output, billed once, and is not inside candidatesTokenCount.
# cachedContentTokenCount is already inside promptTokenCount, so it is not added again.
# toolUsePromptTokenCount is outside promptTokenCount and inside totalTokenCount, so it counts as input once.
# generationConfig.maxOutputTokens (same day):
# https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference
_VERTEX_USAGE_DOC = "https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1beta1/GenerateContentResponse"


def test_thoughts_are_billed_output_once_and_match_total():
    assert _VERTEX_USAGE_DOC.startswith("https://cloud.google.com/")
    http = FakeHttp([(200, _usage_body(
        promptTokenCount=3, candidatesTokenCount=4, thoughtsTokenCount=1000, totalTokenCount=1007,
    ))])
    response = _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert getattr(response, "usage_known", False) is True
    assert response.tokens_in == 3
    assert response.tokens_out == 1004
    assert response.tokens_in + response.tokens_out == 1007


def test_thoughts_count_without_total_and_cached_tokens_are_not_added():
    http = FakeHttp([(200, _usage_body(promptTokenCount=3, candidatesTokenCount=4, thoughtsTokenCount=1000))])
    response = _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert getattr(response, "usage_known", False) is True
    assert response.tokens_out == 1004

    http = FakeHttp([(200, _usage_body(
        promptTokenCount=10, candidatesTokenCount=2, cachedContentTokenCount=4, totalTokenCount=12,
    ))])
    response = _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert getattr(response, "usage_known", False) is True
    assert response.tokens_in == 10
    assert response.tokens_out == 2


def test_tool_use_is_input_once_and_disagreement_is_unknown():
    http = FakeHttp([(200, _usage_body(
        promptTokenCount=3, candidatesTokenCount=4, thoughtsTokenCount=1, toolUsePromptTokenCount=9, totalTokenCount=17,
    ))])
    response = _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert getattr(response, "usage_known", False) is True
    assert response.tokens_in == 12
    assert response.tokens_out == 5
    assert response.tokens_in + response.tokens_out == 17

    http = FakeHttp([(200, _usage_body(
        promptTokenCount=3, candidatesTokenCount=4, thoughtsTokenCount=1000, totalTokenCount=7,
    ))])
    response = _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"})
    assert getattr(response, "usage_known", True) is False


@pytest.mark.parametrize("usage", [
    {},
    {"promptTokenCount": 3},
    {"promptTokenCount": True, "candidatesTokenCount": 4},
    {"promptTokenCount": -1, "candidatesTokenCount": 4},
    {"promptTokenCount": 1.5, "candidatesTokenCount": 4},
    {"promptTokenCount": "3", "candidatesTokenCount": 4},
    {"promptTokenCount": 3, "candidatesTokenCount": 4, "thoughtsTokenCount": True},
    {"promptTokenCount": 3, "candidatesTokenCount": 4, "thoughtsTokenCount": -5},
    {"promptTokenCount": 3, "candidatesTokenCount": 4, "thoughtsTokenCount": 1.0},
    {"promptTokenCount": 3, "candidatesTokenCount": False},
    {"promptTokenCount": 3, "candidatesTokenCount": 4, "cachedContentTokenCount": True, "totalTokenCount": 7},
    {"promptTokenCount": 3, "candidatesTokenCount": 4, "toolUsePromptTokenCount": "9", "totalTokenCount": 7},
])
def test_partial_or_malformed_usage_is_not_a_zero_success(usage):
    body = json.dumps({
        "candidates": [{"content": {"parts": [{"text": "kept"}]}}],
        "usageMetadata": usage,
    }).encode()
    response = _transport(FakeHttp([(200, body)])).generate(
        model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
    )
    assert response.text == "kept"
    assert getattr(response, "usage_known", True) is False


def test_missing_or_non_object_usage_is_unknown():
    missing = json.dumps({"candidates": [{"content": {"parts": [{"text": "kept"}]}}]}).encode()
    response = _transport(FakeHttp([(200, missing)])).generate(
        model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
    )
    assert getattr(response, "usage_known", True) is False
    weird = json.dumps({
        "candidates": [{"content": {"parts": [{"text": "kept"}]}}],
        "usageMetadata": ["nope"],
    }).encode()
    response = _transport(FakeHttp([(200, weird)])).generate(
        model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
    )
    assert getattr(response, "usage_known", True) is False


def test_request_sends_output_allowance_as_max_output_tokens():
    http = FakeHttp([(200, _ok_body())])
    blob = b"\x89PNG\r\n" + b"x" * 40
    _transport(http).generate(
        model=MODEL, location=LOCATION, purpose="extract_vision",
        payload={"markdown": "", "page_image_bytes": [blob]},
    )
    body = json.loads(http.calls[0]["body"])
    assert body["generationConfig"]["maxOutputTokens"] == gemini_output_allowance("extract_vision")
    parts = body["contents"][0]["parts"]
    assert parts[1]["inline_data"]["data"]
    assert b"page_image_bytes" not in http.calls[0]["body"]


def test_extract_allowance_fits_an_invoice_and_map_keeps_its_draft_allowance():
    from usage.providers.gemini import (
        GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE,
        GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE,
        GEMINI_OUTPUT_TOKEN_ALLOWANCE,
    )

    assert GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE > GEMINI_OUTPUT_TOKEN_ALLOWANCE
    assert gemini_output_allowance("extract") == GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE
    assert gemini_output_allowance("extract_vision") == GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE
    assert gemini_output_allowance("map") == GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE
    http = FakeHttp([(200, _ok_body()), (200, _ok_body())])
    _transport(http).generate(model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "Date: 2026-10-05"})
    body = json.loads(http.calls[0]["body"])
    assert body["generationConfig"]["maxOutputTokens"] == GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE
    _transport(http).generate(model=MODEL, location=LOCATION, purpose="map", payload={"invoice": {"total": 1}})
    mapped = json.loads(http.calls[1]["body"])
    assert mapped["generationConfig"]["maxOutputTokens"] == GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, False])
def test_transport_rejects_nonfinite_or_boolean_timeout(timeout):
    with pytest.raises(ValueError):
        HttpGeminiTransport(credential=CREDENTIAL, project=PROJECT, http_post=FakeHttp([]), timeout_seconds=timeout)


@pytest.mark.parametrize("bound", [0, -5, True, False])
def test_transport_rejects_non_positive_or_boolean_size_bounds(bound):
    with pytest.raises(ValueError):
        HttpGeminiTransport(
            credential=CREDENTIAL, project=PROJECT, http_post=FakeHttp([]), max_request_bytes=bound,
        )
    with pytest.raises(ValueError):
        HttpGeminiTransport(
            credential=CREDENTIAL, project=PROJECT, http_post=FakeHttp([]), max_response_bytes=bound,
        )


def test_status_error_marks_body_received_and_timeout_does_not():
    with pytest.raises(TransportError) as exc:
        _transport(FakeHttp([(429, b"slow")])).generate(
            model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
        )
    assert exc.value.code == "http_429"
    assert getattr(exc.value, "body_received", False) is True
    with pytest.raises(TransportError) as exc:
        _transport(FakeHttp([TimeoutError("timed out")])).generate(
            model=MODEL, location=LOCATION, purpose="extract", payload={"markdown": "x"}
        )
    assert exc.value.code == "timeout"
    assert getattr(exc.value, "body_received", True) is False
