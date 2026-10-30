"""Socket tests for the OpenRouter client. Peers are 127.0.0.1 only."""

from __future__ import annotations

import http.client
import inspect
import json
import socket
import threading

import pytest

from usage.providers.openrouter_http import OpenRouterHttpClient, open_openrouter_https
from usage.providers.openrouter_transport import (
    OPENROUTER_CHAT_COMPLETIONS_URL,
    OPENROUTER_PATH,
    HttpOpenRouterTransport,
)
from usage.providers.transport import TransportError

SECRET = "test-openrouter-key"
MODEL = "qwen/qwen3.7-flash"


def _read_request(conn: socket.socket) -> bytes:
    conn.settimeout(2)
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    while len(rest) < length:
        chunk = conn.recv(4096)
        if not chunk:
            break
        rest += chunk
    return head + b"\r\n\r\n" + rest[:length]


def _serve(handler):
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    sock.settimeout(3)
    port = sock.getsockname()[1]
    box: dict = {"request": b""}

    def run():
        try:
            conn, _ = sock.accept()
        except OSError:
            return
        try:
            box["request"] = handler(conn)
        finally:
            conn.close()
            sock.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return port, thread, box


def _connect_loopback(port: int):
    def connect(host: str, _port: int, timeout: float):
        if host != "openrouter.ai":
            raise AssertionError(f"unexpected connect host {host}")
        return http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)

    return connect


def test_exchange_has_no_raw_url_argument():
    assert "url" not in inspect.signature(OpenRouterHttpClient.exchange).parameters


def test_default_connector_refuses_a_non_openrouter_host(monkeypatch):
    def exploded(*_args, **_kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(http.client, "HTTPSConnection", exploded)
    with pytest.raises(TransportError) as exc:
        open_openrouter_https("127.0.0.1", 443, 1.0)
    assert exc.value.code == "invalid_target"
    assert "127.0.0.1" not in str(exc.value)


def test_loopback_post_uses_chat_completions_and_one_authorization_header():
    def handler(conn):
        request = _read_request(conn)
        body = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "{}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7, "cost": 0.01},
        }).encode()
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
        )
        return request

    port, thread, box = _serve(handler)
    client = OpenRouterHttpClient(timeout_seconds=2, connect=_connect_loopback(port))
    transport = HttpOpenRouterTransport(credential=SECRET, http_client=client, timeout_seconds=2)
    response = transport.generate(model=MODEL, purpose="extract", payload={"markdown": "x"})
    thread.join(2)
    assert response.tokens_in == 3 and response.tokens_out == 4 and response.cost_usd == pytest.approx(0.01)
    request = box["request"]
    assert f"POST {OPENROUTER_PATH}".encode() in request
    assert b"openrouter.ai" not in request.split(b"\r\n\r\n", 1)[-1]
    assert SECRET.encode() in request
    assert request.count(b"Authorization:") == 1
    assert b'"reasoning":{"effort":"none"}' in request
    assert OPENROUTER_CHAT_COMPLETIONS_URL.encode() not in request


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_does_not_send_authorization_to_another_host(status):
    hits: list[bytes] = []

    def other(conn):
        hits.append(_read_request(conn))
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
        return hits[-1]

    other_port, other_thread, _other = _serve(other)

    def first(conn):
        _read_request(conn)
        location = f"http://127.0.0.1:{other_port}/steal".encode()
        conn.sendall(
            f"HTTP/1.1 {status} Found\r\nLocation: ".encode()
            + location
            + b"\r\nContent-Length: 0\r\n\r\n"
        )
        return b""

    port, thread, _box = _serve(first)
    client = OpenRouterHttpClient(timeout_seconds=1, connect=_connect_loopback(port))
    with pytest.raises(TransportError) as exc:
        client.exchange(
            headers={"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"},
            body=b"{}",
        )
    assert exc.value.code == "invalid_target"
    assert SECRET not in str(exc.value)
    assert "steal" not in str(exc.value)
    thread.join(1)
    other_thread.join(0.6)
    assert hits == []
