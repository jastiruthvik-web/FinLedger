"""Gemini HTTP transport. Tests inject the HTTP call; nothing here opens a network socket.

The router still refuses to construct this transport, and staging/production still refuse
the gemini provider. Wiring a live credential is a separate owner-approved step.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from usage.providers.bounds import require_positive_finite, require_positive_int
from usage.providers.gemini import GEMINI_OUTPUT_TOKEN_ALLOWANCE
from usage.providers.transport import TransportError, TransportResponse

# Location, model and project are path segments. Reject anything that could change the host or path.
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

HttpPost = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]]


def build_generate_url(*, location: str, model: str, project: str) -> str:
    location_token = _require_token(location, "location")
    model_token = _require_token(model, "model")
    project_token = _require_token(project, "project")
    return (
        f"https://{location_token}-aiplatform.googleapis.com/v1/projects/{project_token}"
        f"/locations/{location_token}/publishers/google/models/{model_token}:generateContent"
    )


class HttpGeminiTransport:
    """One attempt. Retries stay in GeminiProvider. Errors are fixed category codes only."""

    def __init__(
        self,
        *,
        credential: str,
        project: str,
        http_post: HttpPost,
        timeout_seconds: float = 30.0,
        max_request_bytes: int = 4_194_304,
        max_response_bytes: int = 1_048_576,
    ):
        if not isinstance(credential, str) or not credential or any(char.isspace() for char in credential):
            raise ValueError("provider credential is required")
        self._credential = credential
        self._project = _require_token(project, "project")
        self._http_post = http_post
        self.timeout_seconds = require_positive_finite(timeout_seconds)
        self.max_request_bytes = require_positive_int(max_request_bytes)
        self.max_response_bytes = require_positive_int(max_response_bytes)

    def generate(
        self,
        *,
        model: str,
        location: str,
        purpose: str,
        payload: dict[str, Any],
    ) -> TransportResponse:
        url = build_generate_url(location=location, model=model, project=self._project)
        if self._credential in url:
            raise TransportError("auth_rejected")
        body = _request_body(purpose, payload)
        if len(body) > self.max_request_bytes or self._credential.encode() in body:
            raise TransportError("payload_too_large")
        headers = {
            "Authorization": f"Bearer {self._credential}",
            "Content-Type": "application/json",
        }
        try:
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


def _require_token(value: object, label: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise TransportError("invalid_target", "invalid_target")
    return value


def _request_body(purpose: str, payload: dict[str, Any]) -> bytes:
    if not isinstance(payload, dict):
        raise TransportError("payload_too_large")
    text_payload = {key: value for key, value in payload.items() if key != "page_image_bytes"}
    parts: list[dict[str, Any]] = [
        {"text": json.dumps({"purpose": purpose, "payload": text_payload}, sort_keys=True, default=str)}
    ]
    images = payload.get("page_image_bytes") or []
    if not isinstance(images, list):
        raise TransportError("payload_too_large")
    for blob in images:
        if not isinstance(blob, (bytes, bytearray)):
            raise TransportError("payload_too_large")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(bytes(blob)).decode("ascii"),
            }
        })
    return json.dumps(
        {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": GEMINI_OUTPUT_TOKEN_ALLOWANCE},
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
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise TransportError("invalid_response", body_received=True)
    parts = (candidates[0].get("content") or {}).get("parts") if isinstance(candidates[0].get("content"), dict) else None
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"]:
                texts.append(part["text"])
    if not texts:
        raise TransportError("invalid_response", body_received=True)
    tokens_in, tokens_out, usage_known = _chargeable_usage(data.get("usageMetadata"))
    return TransportResponse("".join(texts), tokens_in, tokens_out, 0, usage_known=usage_known)


def _counter(usage: dict[str, Any], name: str) -> int | None:
    value = usage[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _chargeable_usage(usage: object) -> tuple[int, int, bool]:
    """Return chargeable input, chargeable output, and whether the metadata is known.

    Vertex UsageMetadata (checked 2026-10-22):
    https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1beta1/GenerateContentResponse
    totalTokenCount is prompt + candidates + toolUsePrompt + thoughts.
    thoughtsTokenCount is generated thoughts output and is added once, not also via totalTokenCount.
    cachedContentTokenCount is already inside promptTokenCount.
    toolUsePromptTokenCount is outside promptTokenCount and inside totalTokenCount, so it is input once.
    """
    if not isinstance(usage, dict) or not usage:
        return 0, 0, False
    required = ("promptTokenCount", "candidatesTokenCount")
    if any(name not in usage for name in required):
        return 0, 0, False
    prompt = _counter(usage, "promptTokenCount")
    candidates = _counter(usage, "candidatesTokenCount")
    thoughts = _counter(usage, "thoughtsTokenCount") if "thoughtsTokenCount" in usage else 0
    tool = _counter(usage, "toolUsePromptTokenCount") if "toolUsePromptTokenCount" in usage else 0
    cached = _counter(usage, "cachedContentTokenCount") if "cachedContentTokenCount" in usage else 0
    if None in {prompt, candidates, thoughts, tool, cached}:
        return 0, 0, False
    assert prompt is not None and candidates is not None and thoughts is not None and tool is not None
    component_sum = prompt + candidates + thoughts + tool
    if "totalTokenCount" in usage:
        total = _counter(usage, "totalTokenCount")
        if total is None or total != component_sum:
            return 0, 0, False
    return prompt + tool, candidates + thoughts, True
