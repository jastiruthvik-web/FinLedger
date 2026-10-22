"""One-shot stdlib POST for generateContent. Retries stay in GeminiProvider.

``exchange`` does not accept a URL. It builds one with ``build_generate_url`` and
opens that host. Tests may pass ``connect`` so the socket stays on 127.0.0.1.
There is no credential refresh and no key-file read on this branch.
"""

from __future__ import annotations

import http.client
from collections.abc import Callable, Mapping

from urllib.parse import urlsplit

from usage.providers.bounds import require_positive_finite, require_positive_int
from usage.providers.http_transport import build_generate_url
from usage.providers.transport import TransportError

_REDIRECTS = frozenset({301, 302, 303, 307, 308})
Connect = Callable[[str, int, float], http.client.HTTPConnection]


def open_vertex_https(host: str, port: int, timeout: float) -> http.client.HTTPConnection:
    if (
        not isinstance(host, str)
        or host != host.strip()
        or "/" in host
        or not host.endswith("-aiplatform.googleapis.com")
    ):
        raise TransportError("invalid_target")
    return http.client.HTTPSConnection(host, port, timeout=timeout)


class GeminiHttpClient:
    """One attempt. Does not follow redirects or forward the bearer to another host."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 1_048_576,
        connect: Connect | None = None,
    ):
        self.timeout_seconds = require_positive_finite(timeout_seconds)
        self.max_response_bytes = require_positive_int(max_response_bytes)
        self._connect = connect or open_vertex_https

    def exchange(
        self,
        *,
        location: str,
        model: str,
        project: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float | None = None,
    ) -> tuple[int, bytes]:
        url = build_generate_url(location=location, model=model, project=project)
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or host != f"{location}-aiplatform.googleapis.com":
            raise TransportError("invalid_target")
        deadline = self.timeout_seconds if timeout is None else require_positive_finite(timeout)
        try:
            conn = self._connect(host, parsed.port or 443, deadline)
        except TransportError:
            raise
        except TimeoutError:
            raise TransportError("timeout") from None
        except OSError:
            raise TransportError("transport_unavailable") from None
        try:
            return _exchange_on(conn, parsed.path, headers, body, self.max_response_bytes)
        finally:
            conn.close()


def _exchange_on(
    conn: http.client.HTTPConnection,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    max_bytes: int,
) -> tuple[int, bytes]:
    try:
        conn.request(
            "POST",
            path,
            body=body,
            headers={str(key): str(value) for key, value in headers.items()},
        )
        response = conn.getresponse()
        if response.status in _REDIRECTS:
            response.close()
            raise TransportError("invalid_target", body_received=True)
        return response.status, _read_bounded(response, max_bytes)
    except TransportError:
        raise
    except TimeoutError:
        raise TransportError("timeout") from None
    except OSError:
        raise TransportError("transport_unavailable") from None


def _read_bounded(response: http.client.HTTPResponse, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(8192, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            response.close()
            raise TransportError("response_too_large", body_received=True)
        chunks.append(chunk)
    return b"".join(chunks)
