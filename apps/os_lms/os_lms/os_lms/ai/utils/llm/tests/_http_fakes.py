"""Shared helpers for adapter unit tests.

Provides a minimal `requests.Response` stand-in so adapter tests can drive the
HTTP layer without touching the network. Use via `monkeypatch_requests_post`.
"""
from __future__ import annotations

import json
from typing import Any


class FakeResponse:
    """Subset of requests.Response used by the openai-compat and anthropic adapters."""

    def __init__(
        self,
        status_code: int = 200,
        *,
        json_body: dict | None = None,
        sse_lines: list[str] | None = None,
    ):
        self.status_code = status_code
        self._json_body = json_body
        self._sse_lines = sse_lines or []

    @property
    def text(self) -> str:
        if self._json_body is not None:
            return json.dumps(self._json_body)
        return ""

    def json(self) -> Any:
        if self._json_body is None:
            raise ValueError("FakeResponse has no JSON body")
        return self._json_body

    def iter_lines(self, decode_unicode: bool = False):
        for line in self._sse_lines:
            yield line if decode_unicode else line.encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RequestRecorder:
    """Captures the last requests.post call. Use as monkeypatch target."""

    def __init__(self, handler):
        self._handler = handler
        self.last_url: str | None = None
        self.last_payload: dict | None = None
        self.last_headers: dict | None = None
        self.last_stream: bool = False

    def __call__(self, url, **kwargs):
        self.last_url = url
        self.last_payload = kwargs.get("json")
        self.last_headers = kwargs.get("headers")
        self.last_stream = bool(kwargs.get("stream"))
        return self._handler(url, **kwargs)
