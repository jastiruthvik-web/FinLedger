from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from usage.kill_switch import KillSwitch
from usage.provider import ProviderResponse, _tokens, settle_provider_usage
from usage.provider_errors import ProviderTransientError
from usage.providers.bounds import require_positive_finite, require_positive_int
from usage.providers.transport import GeminiTransport, TransportError, TransportResponse

# Fixed categories only. Auth and schema failures are not retried.
_RETRYABLE = frozenset({"timeout", "http_429", "http_5xx", "transport_unavailable"})

# The output half of a reservation. The HTTP body sends the same number.
# Risk and summary stay short. Extract emits a CanonicalInvoice; 256 cuts that JSON off.
# Map emits a voucher draft and keeps its own allowance.
GEMINI_OUTPUT_TOKEN_ALLOWANCE = 256
GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE = 8192
GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE = 4096


def gemini_output_allowance(purpose: str) -> int:
    if purpose == "map":
        return GEMINI_MAP_OUTPUT_TOKEN_ALLOWANCE
    if purpose in {"extract", "extract_vision"}:
        return GEMINI_EXTRACT_OUTPUT_TOKEN_ALLOWANCE
    return GEMINI_OUTPUT_TOKEN_ALLOWANCE

# Per-image stand-in added to the text estimate. Not Google's live image-token formula.
GEMINI_IMAGE_INPUT_TOKEN_ALLOWANCE = 1024


@dataclass(frozen=True)
class GeminiTariff:
    """Positive per-million USD rates supplied by the caller. Not a spending approval."""

    input_usd_per_million: float
    output_usd_per_million: float

    def __post_init__(self) -> None:
        for value in (self.input_usd_per_million, self.output_usd_per_million):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("tariff rates must be positive and finite")


@dataclass(frozen=True)
class GeminiSettings:
    model: str
    location: str
    max_request_bytes: int = 4_194_304
    timeout_seconds: float = 30.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        require_positive_finite(self.timeout_seconds)
        require_positive_int(self.max_request_bytes)


class GeminiProvider:
    """Approved-provider adapter behind complete(...). Requires an explicit transport (fake in CI)."""

    def __init__(
        self,
        settings: GeminiSettings,
        transport: GeminiTransport,
        kill_switch: KillSwitch | None = None,
        *,
        tariff: GeminiTariff | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        if not settings.model or not settings.location:
            raise ValueError("model and location are required for the gemini provider")
        self.settings = settings
        self.transport = transport
        self.kill_switch = kill_switch or KillSwitch()
        self._tariff = tariff
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
                    location=self.settings.location,
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
            cost_usd, cost_computed = self._priced_cost(tokens_in, tokens_out)
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
        if not exc.body_received:
            self.kill_switch.release(reservation)
            return
        tokens_in, tokens_out = estimated_in, allowance
        cost_usd, cost_computed = self._priced_cost(tokens_in, tokens_out)
        settle_provider_usage(
            self.kill_switch,
            reservation,
            purpose=purpose,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=0,
            cost_usd=cost_usd,
            cost_computed=cost_computed,
        )

    @staticmethod
    def _settled_tokens(response: TransportResponse, estimated_in: int, allowance: int) -> tuple[int, int]:
        if response.usage_known:
            return response.tokens_in, response.tokens_out
        return estimated_in, allowance

    def _priced_cost(self, tokens_in: int, tokens_out: int) -> tuple[float, bool]:
        if self._tariff is None:
            return 0.0, False
        cost = (
            tokens_in * float(self._tariff.input_usd_per_million)
            + tokens_out * float(self._tariff.output_usd_per_million)
        ) / 1_000_000
        return cost, True

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
