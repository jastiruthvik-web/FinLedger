"""OpenRouter chat-completions transport. Tests inject the HTTP call; nothing here opens a socket.

ModelRouter builds the live client only when the provider is openrouter. CI passes ``http_post``.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from usage.providers.bounds import require_positive_finite, require_positive_int
from usage.providers.gemini import gemini_output_allowance
from usage.providers.transport import TransportError, TransportResponse

# Model ids are JSON values, not URL path segments. A slash is a normal OpenRouter slug.
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")

OPENROUTER_HOST = "openrouter.ai"
OPENROUTER_PATH = "/api/v1/chat/completions"
OPENROUTER_CHAT_COMPLETIONS_URL = f"https://{OPENROUTER_HOST}{OPENROUTER_PATH}"

# `reasoning.effort` of "none" is the documented off switch. On qwen/qwen3.7-flash it
# leaves message.content as the JSON instead of a thinking trace.
# https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
REASONING_OFF = {"effort": "none"}

HttpPost = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]


class HttpOpenRouterTransport:
    """One attempt. Retries stay in OpenRouterProvider. Errors are fixed category codes only."""

    def __init__(
        self,
        *,
        credential: str,
        http_post: HttpPost | None = None,
        http_client: object | None = None,
        timeout_seconds: float = 30.0,
        max_request_bytes: int = 4_194_304,
        max_response_bytes: int = 1_048_576,
    ):
        if not isinstance(credential, str) or not credential or any(char.isspace() for char in credential):
            raise ValueError("provider credential is required")
        if (http_post is None) == (http_client is None):
            raise ValueError("pass http_post or http_client")
        self._credential = credential
        self._http_post = http_post
        self._http_client = http_client
        self.timeout_seconds = require_positive_finite(timeout_seconds)
        self.max_request_bytes = require_positive_int(max_request_bytes)
        self.max_response_bytes = require_positive_int(max_response_bytes)

    def generate(
        self,
        *,
        model: str,
        purpose: str,
        payload: dict[str, Any],
    ) -> TransportResponse:
        url = OPENROUTER_CHAT_COMPLETIONS_URL
        if self._credential in url:
            raise TransportError("auth_rejected")
        _require_model(model)
        body = _request_body(model, purpose, payload)
        if len(body) > self.max_request_bytes or self._credential.encode() in body:
            raise TransportError("payload_too_large")
        headers = {
            "Authorization": f"Bearer {self._credential}",
            "Content-Type": "application/json",
        }
        try:
            if self._http_client is not None:
                status, response_body = self._http_client.exchange(
                    headers=headers,
                    body=body,
                    timeout=self.timeout_seconds,
                )
            else:
                status, response_body = self._http_post(url, headers, body, self.timeout_seconds)
        except TimeoutError:
            raise TransportError("timeout") from None
        except OSError:
            raise TransportError("transport_unavailable") from None
        except TransportError:
            raise
        except Exception:
            raise TransportError("transport_unavailable") from None
        if not isinstance(status, int) or isinstance(status, bool) or not isinstance(response_body, (bytes, bytearray)):
            raise TransportError("invalid_response")
        response_body = bytes(response_body)
        if len(response_body) > self.max_response_bytes:
            raise TransportError("response_too_large", body_received=True)
        if status in {401, 403}:
            raise TransportError("auth_rejected", body_received=True)
        if status == 429:
            raise TransportError("http_429", body_received=True)
        if 500 <= status <= 599:
            raise TransportError("http_5xx", body_received=True)
        if status != 200:
            raise TransportError("http_4xx", body_received=True)
        return _parse_response(response_body)


def _require_model(model: object) -> str:
    if not isinstance(model, str) or not _MODEL.fullmatch(model):
        raise TransportError("invalid_target", "invalid_target")
    return model


def _request_body(model: str, purpose: str, payload: dict[str, Any]) -> bytes:
    if not isinstance(payload, dict):
        raise TransportError("payload_too_large")
    text_payload = {key: value for key, value in payload.items() if key != "page_image_bytes"}
    text = json.dumps({"purpose": purpose, "payload": text_payload}, sort_keys=True, default=str)
    images = payload.get("page_image_bytes") or []
    if not isinstance(images, list):
        raise TransportError("payload_too_large")
    content: str | list[dict[str, Any]]
    if images:
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for blob in images:
            if not isinstance(blob, (bytes, bytearray)):
                raise TransportError("payload_too_large")
            encoded = base64.b64encode(bytes(blob)).decode("ascii")
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            })
        content = parts
    else:
        content = text
    return json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": gemini_output_allowance(purpose),
            "response_format": {"type": "json_object"},
            "reasoning": REASONING_OFF,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _parse_response(body: bytes) -> TransportResponse:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise TransportError("invalid_response", body_received=True) from None
    if not isinstance(data, dict):
        raise TransportError("invalid_response", body_received=True)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise TransportError("invalid_response", body_received=True)
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise TransportError("invalid_response", body_received=True)
    text = _message_content(message)
    if not text:
        raise TransportError("invalid_response", body_received=True)
    tokens_in, tokens_out, usage_known, cost_usd, cost_known = _usage(data.get("usage"))
    return TransportResponse(
        text,
        tokens_in,
        tokens_out,
        0,
        usage_known=usage_known,
        cost_usd=cost_usd,
        cost_known=cost_known,
    )


def _message_content(message: dict[str, Any]) -> str:
    """Visible completion only. A reasoning trace is not the JSON object."""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
                and part["text"]
            ):
                texts.append(part["text"])
        joined = "".join(texts)
        if joined.strip():
            return joined
    return ""


def _counter(usage: dict[str, Any], name: str) -> int | None:
    value = usage[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usage(usage: object) -> tuple[int, int, bool, float | None, bool]:
    """Return tokens, whether those tokens are known, cost, and whether cost was present.

    OpenRouter usage (checked 2026-10-29):
    https://openrouter.ai/docs/cookbook/administration/usage-accounting
    prompt_tokens and completion_tokens are the native counts. completion_tokens already
    includes reasoning tokens. cost is the amount charged; a missing cost is not zero.
    """
    if not isinstance(usage, dict):
        return 0, 0, False, None, False
    tokens_known = False
    prompt = completion = 0
    if "prompt_tokens" in usage and "completion_tokens" in usage:
        prompt_value = _counter(usage, "prompt_tokens")
        completion_value = _counter(usage, "completion_tokens")
        if prompt_value is not None and completion_value is not None:
            if "total_tokens" in usage:
                total = _counter(usage, "total_tokens")
                if total is not None and total == prompt_value + completion_value:
                    prompt, completion, tokens_known = prompt_value, completion_value, True
            else:
                prompt, completion, tokens_known = prompt_value, completion_value, True
    cost_usd: float | None = None
    cost_known = False
    if "cost" in usage and usage["cost"] is not None:
        raw = usage["cost"]
        if not isinstance(raw, bool) and isinstance(raw, (int, float)) and math.isfinite(float(raw)) and float(raw) >= 0:
            cost_usd = float(raw)
            cost_known = True
    return prompt, completion, tokens_known, cost_usd, cost_known
