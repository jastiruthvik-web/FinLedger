"""OpenRouter adapter. The live client is built only when the provider is openrouter."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from usage.kill_switch import KillSwitch
from usage.provider import ProviderResponse, _tokens, settle_provider_usage
from usage.provider_errors import ProviderTransientError
from usage.providers.bounds import require_positive_finite, require_positive_int
from usage.providers.gemini import GEMINI_IMAGE_INPUT_TOKEN_ALLOWANCE, gemini_output_allowance
from usage.providers.transport import OpenRouterTransport, TransportError, TransportResponse

OPENROUTER_DEFAULT_MODEL = "qwen/qwen3.7-flash"
_MISSING_KEY = "OPENROUTER_API_KEY is required when FINLEDGER_LLM_PROVIDER=openrouter"

# Fixed categories only. Auth and schema failures are not retried.
_RETRYABLE = frozenset({"timeout", "http_429", "http_5xx", "transport_unavailable"})


def require_openrouter_api_key() -> str:
    """Read the bearer token. The value is never included in the error."""
    if "OPENROUTER_API_KEY" not in os.environ:
        raise ValueError(_MISSING_KEY)
    value = os.environ["OPENROUTER_API_KEY"]
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError(_MISSING_KEY)
    return value


def build_openrouter_transport(credential: str):
    """Build the live transport. The client constructor does not open a socket."""
    from usage.providers.openrouter_http import OpenRouterHttpClient
    from usage.providers.openrouter_transport import HttpOpenRouterTransport

    return HttpOpenRouterTransport(credential=credential, http_client=OpenRouterHttpClient())


@dataclass(frozen=True)
class OpenRouterSettings:
    model: str
    max_request_bytes: int = 4_194_304
    timeout_seconds: float = 30.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        require_positive_finite(self.timeout_seconds)
        require_positive_int(self.max_request_bytes)
        if not self.model or not isinstance(self.model, str):
            raise ValueError("model is required for the openrouter provider")


class OpenRouterProvider:
    """Chat-completions adapter behind complete(...). CI passes a fake transport."""

    def __init__(
        self,
        settings: OpenRouterSettings,
        transport: OpenRouterTransport,
        kill_switch: KillSwitch | None = None,
        *,
        sleeper: Callable[[float], None] | None = None,
    ):
        if not settings.model:
            raise ValueError("model is required for the openrouter provider")
        self.settings = settings
        self.transport = transport
        self.kill_switch = kill_switch or KillSwitch()
        self._sleeper = sleeper or time.sleep

    def complete(
        self,
        purpose: str,
        model: str,
        client_id: str,
        document_id: str,
        payload: dict[str, Any],
    ) -> ProviderResponse:
        self._enforce_payload_bounds(payload)
        estimated_in = self._estimate_input_tokens(payload)
        allowance = gemini_output_allowance(purpose)
        hold = estimated_in + allowance
        model_name = model or self.settings.model
        attempts = 0
        while True:
            reservation = self.kill_switch.reserve(client_id, document_id, hold)
            attempts += 1
            try:
                started = time.perf_counter()
                transport_response = self.transport.generate(
                    model=model_name,
                    purpose=purpose,
                    payload=payload,
                )
            except TransportError as exc:
                self._settle_failed_attempt(reservation, exc, estimated_in, allowance, purpose, model_name)
                if exc.code not in _RETRYABLE or attempts > self.settings.max_retries:
                    if exc.code in _RETRYABLE:
                        raise ProviderTransientError() from None
                    raise
                self._sleeper(self._backoff_seconds(attempts))
                continue
            except Exception:
                self.kill_switch.release(reservation)
                raise
            latency_ms = transport_response.latency_ms or int((time.perf_counter() - started) * 1000)
            tokens_in, tokens_out = self._settled_tokens(transport_response, estimated_in, allowance)
            cost_usd, cost_computed = self._reported_cost(transport_response)
            persisted = settle_provider_usage(
                self.kill_switch,
                reservation,
                purpose=purpose,
                model=model_name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                cost_computed=cost_computed,
            )
            return ProviderResponse(
                transport_response.text,
                tokens_in,
                tokens_out,
                latency_ms,
                cost_usd,
                cost_computed=cost_computed,
                usage_known=transport_response.usage_known,
                reservation_id=reservation.reservation_id,
                usage_persisted=persisted,
            )

    def _settle_failed_attempt(
        self,
        reservation,
        exc: TransportError,
        estimated_in: int,
        allowance: int,
        purpose: str,
        model: str,
    ) -> None:
        # A timeout with no body can stay uncounted. A body, including an error body, is not released.
        # The error body is not priced, so the row stores no zero cost.
        if not exc.body_received:
            self.kill_switch.release(reservation)
            return
        settle_provider_usage(
            self.kill_switch,
            reservation,
            purpose=purpose,
            model=model,
            tokens_in=estimated_in,
            tokens_out=allowance,
            latency_ms=0,
            cost_usd=0.0,
            cost_computed=False,
        )

    @staticmethod
    def _settled_tokens(response: TransportResponse, estimated_in: int, allowance: int) -> tuple[int, int]:
        if response.usage_known:
            return response.tokens_in, response.tokens_out
        return estimated_in, allowance

    @staticmethod
    def _reported_cost(response: TransportResponse) -> tuple[float, bool]:
        # usage.cost is the charge. Absence is unpriced, not a free call stored as 0.
        if response.cost_known and response.cost_usd is not None:
            return response.cost_usd, True
        return 0.0, False

    def _backoff_seconds(self, failed_attempts: int) -> float:
        return min(0.05 * (2 ** (failed_attempts - 1)), 1.0)

    def _estimate_input_tokens(self, payload: dict[str, Any]) -> int:
        images = payload.get("page_image_bytes") or []
        if not isinstance(images, list):
            raise TransportError("payload_too_large", "payload_too_large")
        text_payload = {key: value for key, value in payload.items() if key != "page_image_bytes"}
        serialized = json.dumps(text_payload, sort_keys=True)
        image_count = 0
        for blob in images:
            if not isinstance(blob, (bytes, bytearray)):
                raise TransportError("payload_too_large", "payload_too_large")
            image_count += 1
        return _tokens(serialized) + image_count * GEMINI_IMAGE_INPUT_TOKEN_ALLOWANCE

    def _enforce_payload_bounds(self, payload: dict[str, Any]) -> None:
        text_payload = {key: value for key, value in payload.items() if key != "page_image_bytes"}
        size = len(json.dumps(text_payload, sort_keys=True).encode("utf-8"))
        if size > self.settings.max_request_bytes:
            raise TransportError("payload_too_large", "payload_too_large")
        for blob in payload.get("page_image_bytes", []) or []:
            if not isinstance(blob, (bytes, bytearray)) or len(blob) > self.settings.max_request_bytes:
                raise TransportError("payload_too_large", "payload_too_large")
