"""Persist every LLM call routed through a wrapped provider to a JSONL file.

Used by ``AuthoringEvaluationRunner`` to capture the full prompt + response
chain of an evaluation run for offline inspection and debugging.

One file per ``session_id`` (typically the LMSA Quality Evaluation name) at
``{site}/private/files/llm_logs/{session_id}.jsonl``. Append-only JSONL so
concurrent writes from the same process serialize at line boundaries and a
crash mid-call still leaves the prior entries intact.

Debug-only — disabled by default. Flip ``ENABLED`` to ``True`` locally when
you need to inspect LLM calls (and remember to flip it back before commit).
The flag is also re-checked at every wrap site, so changing it from a REPL
or a debugger session takes effect on the next runner instance without a
worker restart.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frappe
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, LLMProvider

# Debug-only toggle. Set to True to enable JSONL logging of every LLM call
# routed through a ``LoggingProvider``. Do NOT commit True — this is meant
# for local debugging sessions, not for production audit.
ENABLED = True


def llm_log_path(session_id: str) -> Path:
	"""Return the absolute JSONL path for a given session id, scoped to the
	current Frappe site under ``private/files/llm_logs/``."""
	safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id)
	return Path(frappe.local.site_path) / "private" / "files" / "llm_logs" / f"{safe}.jsonl"


class LoggingProvider:
	"""Thin proxy over an ``LLMProvider`` that appends every ``chat()``
	call to a JSONL file. Non-overridden attributes (``health_check``, etc.)
	delegate transparently via ``__getattr__``.

	The wrapper is best-effort: write failures are swallowed (and logged via
	``frappe.log_error``) so the underlying LLM call flow never breaks
	because of a logging side effect.
	"""

	def __init__(self, inner: LLMProvider, log_path: Path):
		self._inner = inner
		self._log_path = log_path

	@property
	def name(self) -> str:
		return self._inner.name

	def __getattr__(self, attr: str):
		# Delegate any non-overridden attribute (health_check, _config, ...).
		return getattr(self._inner, attr)

	def chat(self, messages: list[ChatMessage], **kwargs: Any):
		request_blob = self._serialize_request(messages, kwargs)
		started_at = time.monotonic()
		try:
			response = self._inner.chat(messages, **kwargs)
		except Exception as e:
			self._write(
				{
					"timestamp": _now_iso(),
					"duration_ms": int((time.monotonic() - started_at) * 1000),
					"provider": self._inner.name,
					"request": request_blob,
					"response": None,
					"error": {"type": type(e).__name__, "message": str(e)},
				}
			)
			raise
		self._write(
			{
				"timestamp": _now_iso(),
				"duration_ms": int((time.monotonic() - started_at) * 1000),
				"provider": self._inner.name,
				"request": request_blob,
				"response": _serialize_response(response),
				"error": None,
			}
		)
		return response

	# ---- internals ----

	def _serialize_request(self, messages, kwargs) -> dict:
		return {
			"model": kwargs.get("model"),
			"system": kwargs.get("system"),
			"messages": [{"role": m.role, "content": m.content} for m in messages],
			"temperature": kwargs.get("temperature"),
			"max_tokens": kwargs.get("max_tokens"),
			"response_format": _serialize_response_format(kwargs.get("response_format")),
			"stream": kwargs.get("stream", False),
		}

	def _write(self, entry: dict) -> None:
		try:
			self._log_path.parent.mkdir(parents=True, exist_ok=True)
			with open(self._log_path, "a", encoding="utf-8") as f:
				f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
		except Exception:
			frappe.log_error(title="LoggingProvider write failed")


def _now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def _serialize_response_format(rf) -> dict | None:
	if rf is None:
		return None
	return {"name": getattr(rf, "name", None), "schema": getattr(rf, "schema", None)}


def _serialize_response(response) -> dict:
	# Streaming responses are iterators; skip detailed serialization.
	if not isinstance(response, ChatResponse):
		return {"streaming": True, "type": type(response).__name__}
	usage = getattr(response, "usage", None)
	return {
		"text": response.text,
		"finish_reason": response.finish_reason,
		"model": response.model,
		"provider": response.provider,
		"usage": {
			"prompt_tokens": getattr(usage, "prompt_tokens", 0),
			"completion_tokens": getattr(usage, "completion_tokens", 0),
			"total_tokens": getattr(usage, "total_tokens", 0),
		},
	}
