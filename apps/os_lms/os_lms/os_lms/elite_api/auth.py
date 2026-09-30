"""Authentication, shared endpoint checks and access logging of the Elite API.

Request lifecycle (see docs/elite-api/fase-2-analisi.md):

1. ``authenticate_request`` (before_request) runs BEFORE Frappe's own
   ``validate_auth`` and the ``lms.auth`` hook, which would block os_lms paths
   under ``block_endpoints``. It only acts on Elite API paths carrying the
   ``X-Elite-Api-Key`` header, so the key is useless anywhere else.
2. ``elite_api_endpoint`` guards every endpoint: no verified key, no data,
   even for a logged-in browser session.
3. ``record_request`` (after_request) writes the access log and commits it:
   Frappe rolls back every GET and every failed request before this point.
"""

from __future__ import annotations

import json
import re
import time
from functools import wraps

import frappe
from frappe.utils import now_datetime

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.errors import (
	EliteAPIForbidden,
	EliteAPITooManyRequests,
	EliteAPIUnauthorized,
	api_error,
)

API_KEY_HEADER = "X-Elite-Api-Key"
API_METHOD_PREFIX = "os_lms.os_lms.elite_api."
# Keys only open the versioned public API (elite_api.v1, v2...), never the
# key-management endpoints in elite_api.admin used by the SPA.
API_PATH = re.compile(r"^/api/(?:v1/|v2/)?method/" + re.escape(API_METHOD_PREFIX) + r"v\d+\.")

# Failed attempts per IP before the IP is turned away (and no longer logged).
FAILED_ATTEMPTS_LIMIT = 20
FAILED_ATTEMPTS_WINDOW_SECONDS = 10 * 60
# last_used_on is written at most once per key in this window.
LAST_USED_THROTTLE_SECONDS = 60
# Only these request parameters reach the access log.
LOGGED_PARAMS = ("course", "batch", "page", "page_length", "status", "search")
MAX_LOGGED_PARAM_LENGTH = 140


def authenticate_request():
	"""before_request hook: verify the key and run the request as the API client user."""
	frappe.local.elite_api = None

	raw_key = frappe.get_request_header(API_KEY_HEADER)
	if not raw_key or not frappe.request or not API_PATH.match(frappe.request.path):
		return

	ip = frappe.local.request_ip
	context = frappe._dict(key=None, attempted_key=None, started=time.monotonic(), ip=ip, rows=None, log=True)
	frappe.local.elite_api = context
	# The client user is a System User: without this flag Frappe would send it
	# full tracebacks when System Settings allow them (the default).
	frappe.local.flags.disable_traceback = True

	if _failed_attempts(ip) >= FAILED_ATTEMPTS_LIMIT:
		context.log = False
		api_error(EliteAPITooManyRequests, "too_many_failed_attempts")

	key_name = keys.resolve_key(raw_key)
	if not key_name:
		_count_failed_attempt(ip)
		parsed = keys.parse_key(raw_key)
		if parsed and frappe.db.exists(keys.KEY_DOCTYPE, parsed[0]):
			context.attempted_key = parsed[0]
		api_error(EliteAPIUnauthorized, "invalid_api_key")

	context.key = key_name
	# set_user() wipes form_dict, i.e. the request parameters.
	form_dict = frappe.local.form_dict
	frappe.set_user(keys.CLIENT_USER)
	frappe.local.form_dict = form_dict


def get_current_key() -> str | None:
	context = getattr(frappe.local, "elite_api", None)
	return context.key if context else None


def elite_api_endpoint(fn):
	"""Guard an Elite API endpoint. Apply it below ``@frappe.whitelist(methods=["GET"])``."""

	@wraps(fn)
	def wrapper(*args, **kwargs):
		context = getattr(frappe.local, "elite_api", None)
		if not context or not context.key:
			api_error(EliteAPIUnauthorized, "invalid_api_key")
		if keys.CLIENT_ROLE not in frappe.get_roles():
			api_error(EliteAPIForbidden, "forbidden")

		result = fn(*args, **kwargs)
		if isinstance(result, dict) and isinstance(result.get("data"), list):
			context.rows = len(result["data"])
		return result

	return wrapper


def record_request(response=None, request=None):
	"""after_request hook: log the Elite API call, successful or not."""
	context = getattr(frappe.local, "elite_api", None)
	if not context or not context.log:
		return

	try:
		frappe.get_doc(
			{
				"doctype": "Elite API Access Log",
				"api_key": context.key or context.attempted_key,
				"method": _called_method(request),
				"status_code": getattr(response, "status_code", None) or 500,
				"rows_returned": context.rows or 0,
				"duration_ms": int((time.monotonic() - context.started) * 1000),
				"ip_address": context.ip,
				"request_params": _logged_params(),
			}
		).insert(ignore_permissions=True)
		_touch_last_used(context)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Elite API access log")


def _called_method(request) -> str:
	path = getattr(request, "path", "") or ""
	return path.rsplit("/", 1)[-1].removeprefix(API_METHOD_PREFIX)


def _logged_params() -> str | None:
	form_dict = frappe.local.form_dict or {}
	params = {
		name: str(form_dict[name])[:MAX_LOGGED_PARAM_LENGTH] for name in LOGGED_PARAMS if name in form_dict
	}
	return json.dumps(params, sort_keys=True) if params else None


def _touch_last_used(context):
	if not context.key:
		return
	cache_key = f"elite_api:last_used:{context.key}"
	if frappe.cache.get_value(cache_key):
		return
	# db.set_value skips the controller: last-use data is not part of the key's lifetime rules.
	frappe.db.set_value(
		keys.KEY_DOCTYPE,
		context.key,
		{"last_used_on": now_datetime(), "last_used_ip": context.ip},
		update_modified=False,
	)
	frappe.cache.set_value(cache_key, 1, expires_in_sec=LAST_USED_THROTTLE_SECONDS)


def _failed_attempts_cache_key(ip: str) -> str:
	return frappe.cache.make_key(f"elite_api:failed:{ip}")


def _failed_attempts(ip: str) -> int:
	return int(frappe.cache.get(_failed_attempts_cache_key(ip)) or 0)


def _count_failed_attempt(ip: str):
	cache_key = _failed_attempts_cache_key(ip)
	if not frappe.cache.get(cache_key):
		frappe.cache.setex(cache_key, FAILED_ATTEMPTS_WINDOW_SECONDS, 0)
	frappe.cache.incrby(cache_key, 1)
