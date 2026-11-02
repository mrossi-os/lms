"""Send the LLM calls made by AI test runners to Arize Phoenix.

Used by the AI bias tests (ESG point 5): a runner wraps its provider with
``wrap_for_tracing`` so every ``chat()`` call becomes an OpenInference LLM
span in Phoenix (prompt, reply, model, token usage, test metadata).

Never applied in ``resolve_provider()``: live student traffic is not traced.
The full prompt and reply are stored in Phoenix, so runners must feed
synthetic data only.

Tracing stays off (``wrap_for_tracing`` returns the provider unchanged)
unless both hold:
- the optional ``tracing`` extra is installed
  (``pip install -e "apps/os_lms[tracing]"``);
- ``phoenix_collector_endpoint`` is set in site_config.json, e.g.
  ``http://phoenix:6006/v1/traces``, plus ``phoenix_api_key`` when Phoenix
  has authentication on.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, LLMProvider

# One OpenTelemetry TracerProvider per (endpoint, project), reused across
# runner instances so spans keep flowing through the same batch exporter.
_tracer_providers: dict[tuple[str, str], Any] = {}


def tracing_config() -> tuple[str | None, str | None]:
	"""Return (collector endpoint, API key) from site_config.json."""
	import frappe

	return frappe.conf.get("phoenix_collector_endpoint"), frappe.conf.get("phoenix_api_key")


def wrap_for_tracing(
	provider: LLMProvider, *, project: str, metadata: dict | None = None
) -> LLMProvider:
	"""Return ``provider`` wrapped in a ``TracingProvider`` writing to the
	Phoenix project ``project``, or ``provider`` itself when tracing is off.

	``metadata`` (e.g. test case id, variant) is attached to every span."""
	endpoint, api_key = tracing_config()
	if not endpoint:
		return provider
	tracer = _get_tracer(endpoint, api_key, project)
	if tracer is None:
		return provider
	return TracingProvider(provider, tracer, metadata=metadata)


def flush_traces(timeout_ms: int = 30000) -> None:
	"""Push the spans still queued in the batch exporters. Runners call it
	at the end of a run so a short-lived process does not drop them."""
	for tracer_provider in _tracer_providers.values():
		tracer_provider.force_flush(timeout_ms)


def _get_tracer(endpoint: str, api_key: str | None, project: str):
	key = (endpoint, project)
	if key not in _tracer_providers:
		try:
			from phoenix.otel import register
		except ImportError:
			_logger().warning(
				"phoenix_collector_endpoint is set but the os_lms 'tracing' extra "
				"is not installed: LLM calls are not traced."
			)
			return None
		_tracer_providers[key] = register(
			endpoint=endpoint,
			project_name=project,
			api_key=api_key,
			batch=True,
			set_global_tracer_provider=False,
			verbose=False,
		)
	return _tracer_providers[key].get_tracer(__name__)


class TracingProvider:
	"""Thin proxy over an ``LLMProvider`` that records every blocking
	``chat()`` call as an OpenInference LLM span. Streaming calls pass
	through untraced. Non-overridden attributes (``health_check``, ...)
	delegate transparently via ``__getattr__``, as in ``LoggingProvider``.

	Exceptions from the inner provider are recorded on the span and
	re-raised unchanged; a failure while building span attributes is
	logged and never breaks the LLM call."""

	def __init__(self, inner: LLMProvider, tracer, *, metadata: dict | None = None):
		self._inner = inner
		self._tracer = tracer
		self._metadata = dict(metadata or {})

	@property
	def name(self) -> str:
		return self._inner.name

	def __getattr__(self, attr: str):
		return getattr(self._inner, attr)

	def chat(self, messages: list[ChatMessage], **kwargs: Any):
		if kwargs.get("stream"):
			return self._inner.chat(messages, **kwargs)

		with self._tracer.start_as_current_span(f"{self._inner.name}.chat") as span:
			self._set_attributes(span, lambda: self._request_attributes(messages, kwargs))
			response = self._inner.chat(messages, **kwargs)
			self._set_attributes(span, lambda: _response_attributes(response, kwargs))
			return response

	# ---- internals ----

	def _request_attributes(self, messages: list[ChatMessage], kwargs: dict) -> dict:
		# Attribute names follow the OpenInference semantic conventions,
		# which Phoenix uses to render LLM spans.
		system = kwargs.get("system")
		all_messages = [("system", system)] if system else []
		all_messages += [(m.role, m.content) for m in messages]

		metadata = dict(self._metadata)
		if system:
			# The prompt can be edited from the desk while keeping its version
			# label, so the hash is what tells two prompt texts apart.
			metadata["system_prompt_sha256"] = hashlib.sha256(system.encode("utf-8")).hexdigest()

		response_format = kwargs.get("response_format")
		attributes = {
			"openinference.span.kind": "LLM",
			"llm.provider": self._inner.name,
			"llm.invocation_parameters": json.dumps(
				{
					"temperature": kwargs.get("temperature"),
					"top_p": kwargs.get("top_p"),
					"max_tokens": kwargs.get("max_tokens"),
					"response_format": getattr(response_format, "name", None),
				}
			),
			"metadata": json.dumps(metadata, ensure_ascii=False, default=str),
		}
		if kwargs.get("model"):
			attributes["llm.model_name"] = kwargs["model"]
		for i, (role, content) in enumerate(all_messages):
			attributes[f"llm.input_messages.{i}.message.role"] = role
			attributes[f"llm.input_messages.{i}.message.content"] = content or ""
		return attributes

	def _set_attributes(self, span, build) -> None:
		try:
			span.set_attributes(build())
		except Exception:
			_logger().exception("TracingProvider could not build span attributes")


def _response_attributes(response: ChatResponse, kwargs: dict) -> dict:
	return {
		"llm.model_name": response.model or kwargs.get("model") or "",
		"llm.output_messages.0.message.role": "assistant",
		"llm.output_messages.0.message.content": response.text or "",
		"output.value": response.text or "",
		"llm.token_count.prompt": response.usage.prompt_tokens,
		"llm.token_count.completion": response.usage.completion_tokens,
		"llm.token_count.total": response.usage.total_tokens,
	}


def _logger():
	import frappe

	return frappe.logger("os_lmsa", allow_site=True)
