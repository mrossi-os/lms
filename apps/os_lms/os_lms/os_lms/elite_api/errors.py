"""Errors of the Elite API and the parameter parsers that raise them.

Clients read ``error`` (a stable, untranslated code) and ``parameter`` from the
JSON body, never the prose. Parameters are parsed here instead of through
Frappe's type annotations: a type mismatch there answers 417 with internal
module names, before any code of ours runs.
"""

from __future__ import annotations

from collections.abc import Collection

import frappe


class EliteAPIBadRequest(frappe.ValidationError):
	http_status_code = 400


class EliteAPIUnauthorized(frappe.AuthenticationError):
	http_status_code = 401


class EliteAPIForbidden(frappe.PermissionError):
	http_status_code = 403


class EliteAPINotFound(frappe.DoesNotExistError):
	http_status_code = 404


class EliteAPITooManyRequests(frappe.TooManyRequestsError):
	http_status_code = 429


def api_error(exc_class: type[Exception], code: str, parameter: str | None = None):
	"""Raise ``exc_class`` with ``code`` exposed in the JSON response body."""
	frappe.local.response["error"] = code
	if parameter:
		frappe.local.response["parameter"] = parameter
	raise exc_class(code)


def require_param(name: str, value: str | None) -> str:
	value = (value or "").strip()
	if not value:
		api_error(EliteAPIBadRequest, "invalid_parameter", name)
	return value


def parse_int_param(
	name: str,
	value: str | int | None,
	default: int,
	minimum: int | None = None,
	maximum: int | None = None,
) -> int:
	if value is None or value == "":
		return default
	try:
		number = int(str(value).strip())
	except ValueError:
		api_error(EliteAPIBadRequest, "invalid_parameter", name)
	if (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
		api_error(EliteAPIBadRequest, "invalid_parameter", name)
	return number


def parse_choice_param(
	name: str, value: str | None, choices: Collection[str], default: str | None = None
) -> str | None:
	if value is None or value == "":
		return default
	if value not in choices:
		api_error(EliteAPIBadRequest, "invalid_parameter", name)
	return value
