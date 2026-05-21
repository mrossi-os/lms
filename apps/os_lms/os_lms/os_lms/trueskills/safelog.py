"""PII-safe logging for the TrueSkills integration.

Defense-in-depth scrubber that masks anything matching:

- Italian ``codice fiscale`` (16-char alphanumeric pattern with the strict
  CF structure ``LLLLLL NN L NN L NNN L``).
- TrueSkills API keys (``ts_<opaque>``) — the value, not the header name.

All TrueSkills code paths SHOULD route through ``get_logger()`` instead of
``frappe.logger(...)`` directly so any accidental PII leak is caught at the
record boundary. For ``frappe.log_error`` calls (which bypass the logger)
wrap the message with ``scrub()`` first.

What you must NOT log even with the scrubber in place:
- Full request/response bodies of ``POST /issue``.
- ``fiscalIdHash`` values from TrueSkills responses (still PII-derived).
- The ``X-Api-Key`` header itself.

The scrubber is best-effort. Treat it as a safety net, not a license to log.
"""

import logging
import re

import frappe

# Italian codice fiscale: 6 letters + 2 digits + letter + 2 digits + letter
# + 3 digits + letter. Strict pattern keeps false-positives near zero.
_FISCAL_ID_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")

# TrueSkills API keys are documented as ``ts_<opaque>`` (brief §1).
_API_KEY_RE = re.compile(r"\bts_[A-Za-z0-9_\-]{8,}\b")

_REPLACEMENTS = (
	(_FISCAL_ID_RE, "[REDACTED-FISCAL-ID]"),
	(_API_KEY_RE, "ts_[REDACTED]"),
)


def scrub(text: str | None) -> str:
	"""Mask sensitive patterns in an arbitrary string."""
	if not text:
		return text or ""
	for pattern, replacement in _REPLACEMENTS:
		text = pattern.sub(replacement, text)
	return text


class _Scrubber(logging.Filter):
	"""Logging filter that scrubs PII from formatted messages."""

	def filter(self, record: logging.LogRecord) -> bool:
		if isinstance(record.msg, str):
			record.msg = scrub(record.msg)
		if record.args:
			record.args = tuple(
				scrub(a) if isinstance(a, str) else a for a in record.args
			)
		return True


def get_logger() -> logging.Logger:
	"""Return the ``trueskills`` Frappe logger with the PII scrubber installed.

	Idempotent: the filter is added at most once per logger instance.
	"""
	logger = frappe.logger("trueskills", allow_site=True)
	if not any(isinstance(f, _Scrubber) for f in logger.filters):
		logger.addFilter(_Scrubber())
	return logger
