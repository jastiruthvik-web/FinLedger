"""Opt-in live Gemini: hosted refusal stays, and the explicit client is the only way through."""
import socket

import pytest

from usage.live_gemini import build_explicit_transport, transport_is_explicit_live
from usage.model_router import ModelRouter, Settings
from usage.providers.gemini import GeminiProvider
from usage.providers.http_client import GeminiHttpClient
from usage.providers.http_transport import HttpGeminiTransport
from usage.providers.transport import FakeGeminiTransport


def _refuse_socket(*_args, **_kwargs):
    raise AssertionError("socket opened")


def _live_env(monkeypatch, **overrides):
    values = {
        "FINLEDGER_LLM_PROVIDER": "gemini",
        "FINLEDGER_GEMINI_LOCATION": "asia-south1",
        "FINLEDGER_MODEL_EXTRACT": "gemini-2.5-flash",
        "FINLEDGER_GEMINI_PROJECT": "finledger-local",
        "FINLEDGER_GEMINI_CREDENTIAL": "CANARYSECRET",
    }
    values.update(overrides)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def test_hosted_gemini_accepts_only_the_explicit_http_client(monkeypatch):
    monkeypatch.setenv("FINLEDGER_ENV", "production")
    monkeypatch.setattr(socket, "create_connection", _refuse_socket)
    settings = Settings(provider="gemini", gemini_location="asia-south1", model_extract="gemini-2.5-flash")
    with pytest.raises(RuntimeError, match="gemini LLM provider cannot run in a hosted environment"):
        ModelRouter(settings, gemini_transport=FakeGeminiTransport())
    posted = HttpGeminiTransport(
        credential="CANARYSECRET", project="finledger-local", http_post=lambda *_args: (200, b"{}"),
    )
    with pytest.raises(RuntimeError, match="gemini LLM provider cannot run in a hosted environment"):
        ModelRouter(settings, gemini_transport=posted)
    client = GeminiHttpClient(connect=_refuse_socket)
    transport = HttpGeminiTransport(credential="CANARYSECRET", project="finledger-local", http_client=client)
    router = ModelRouter(settings, gemini_transport=transport)
    assert isinstance(router.provider, GeminiProvider)
    assert router.provider.transport is transport
    assert router.resolve_model("extract") == "gemini-2.5-flash"
    with pytest.raises(RuntimeError, match="mock LLM provider cannot run in a hosted environment"):
        ModelRouter(Settings(provider="mock"), gemini_transport=transport)


def test_build_explicit_transport_does_not_open_a_socket_or_leak_the_credential(monkeypatch):
    _live_env(monkeypatch)
    monkeypatch.setenv("FINLEDGER_ENV", "staging")
    monkeypatch.setattr(socket, "create_connection", _refuse_socket)
    settings = Settings.from_env()
    transport = build_explicit_transport(settings)
    assert transport_is_explicit_live(transport)
    router = ModelRouter(settings, gemini_transport=transport)
    assert isinstance(router.provider, GeminiProvider)
    assert "CANARYSECRET" not in repr(transport)


@pytest.mark.parametrize("missing", [
    "FINLEDGER_GEMINI_LOCATION",
    "FINLEDGER_MODEL_EXTRACT",
    "FINLEDGER_GEMINI_PROJECT",
    "FINLEDGER_GEMINI_CREDENTIAL",
])
def test_missing_explicit_setting_fails_before_a_socket(monkeypatch, missing):
    _live_env(monkeypatch, **{missing: None})
    monkeypatch.setenv("FINLEDGER_GEMINI_FALLBACK_LOCATION", "us-central1")
    monkeypatch.setenv("FINLEDGER_MODEL_EXTRACT_VISION", "gemini-1.5-pro")
    monkeypatch.setattr(socket, "create_connection", _refuse_socket)
    settings = Settings.from_env()
    with pytest.raises(RuntimeError, match="explicit model, location, project, and credential") as exc:
        build_explicit_transport(settings)
    message = str(exc.value)
    assert "CANARYSECRET" not in message
    assert "us-central1" not in message
    assert "gemini-1.5" not in message


def test_live_switch_does_not_fall_back_to_mock(monkeypatch):
    _live_env(monkeypatch, FINLEDGER_LLM_PROVIDER="mock")
    monkeypatch.setattr(socket, "create_connection", _refuse_socket)
    settings = Settings.from_env()
    with pytest.raises(RuntimeError, match="does not fall back to another provider") as exc:
        build_explicit_transport(settings)
    assert "CANARYSECRET" not in str(exc.value)


def test_explicit_model_and_location_must_match_the_router_settings(monkeypatch):
    _live_env(monkeypatch)
    monkeypatch.setattr(socket, "create_connection", _refuse_socket)
    settings = Settings(
        provider="gemini", gemini_location="europe-west1", model_extract="gemini-2.5-flash",
    )
    with pytest.raises(RuntimeError, match="does not fall back to another model or location") as exc:
        build_explicit_transport(settings)
    assert "CANARYSECRET" not in str(exc.value)
    assert "europe-west1" not in str(exc.value)
