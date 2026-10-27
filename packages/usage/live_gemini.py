"""Opt-in live Gemini transport.

Nothing here runs unless the caller asks. ``FINLEDGER_GEMINI_LIVE=1`` is the worker
switch. ``evals/run_evals.py --live-synthetic-eval`` is the eval switch. Both require
the provider, model, location, project, and credential to be set explicitly. A missing
value is a startup error. There is no mock, region, or model fallback, and the
credential is never put in an error, a URL, or a log line.
"""
from __future__ import annotations

import os

from usage.providers.http_client import GeminiHttpClient
from usage.providers.http_transport import HttpGeminiTransport

_MISSING = "live gemini requires an explicit model, location, project, and credential"
_NO_FALLBACK_PROVIDER = "live gemini does not fall back to another provider"
_NO_FALLBACK_TARGET = "live gemini does not fall back to another model or location"


def transport_is_explicit_live(transport: object) -> bool:
    """True only for the real HTTP client. A fake transport or an injected poster is not enough."""
    client = getattr(transport, "_http_client", None)
    return isinstance(transport, HttpGeminiTransport) and isinstance(client, GeminiHttpClient)


def build_explicit_transport(settings) -> HttpGeminiTransport:
    """Build the one live transport. Raises before any socket when configuration is incomplete."""
    provider = os.environ.get("FINLEDGER_LLM_PROVIDER", "").strip().lower()
    if provider != "gemini" or getattr(settings, "provider", None) != "gemini":
        raise RuntimeError(_NO_FALLBACK_PROVIDER)
    location = _explicit("FINLEDGER_GEMINI_LOCATION")
    model = _explicit("FINLEDGER_MODEL_EXTRACT")
    project = _explicit("FINLEDGER_GEMINI_PROJECT")
    credential = _credential()
    if settings.gemini_location != location or settings.model_extract != model:
        raise RuntimeError(_NO_FALLBACK_TARGET)
    # The client opens a socket only when exchange() is called.
    return HttpGeminiTransport(
        credential=credential,
        project=project,
        http_client=GeminiHttpClient(),
    )


def _explicit(name: str) -> str:
    if name not in os.environ:
        raise RuntimeError(_MISSING)
    value = os.environ[name]
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RuntimeError(_MISSING)
    return value


def _credential() -> str:
    if "FINLEDGER_GEMINI_CREDENTIAL" not in os.environ:
        raise RuntimeError(_MISSING)
    value = os.environ["FINLEDGER_GEMINI_CREDENTIAL"]
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise RuntimeError(_MISSING)
    return value
