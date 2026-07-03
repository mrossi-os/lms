# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt
"""
Firebase Cloud Messaging (FCM) push delivery for the Elite mobile app.

Uses the FCM HTTP v1 API. The service-account credentials are read from the
site config (site_config.json), so each Frappe site/instance can point at the
SAME Firebase project (the one that owns the mobile app):

    # site_config.json
    {
        "fcm_service_account_path": "/path/to/eliteapp-service-account.json"
    }

or, inline:

    {
        "fcm_service_account": { ...service account JSON... }
    }

If no credentials are configured, push delivery is silently skipped (the
in-app Notification Log is unaffected). Device tokens are stored in the
"Push Device Token" doctype, registered by the mobile app via
``os_lms.os_lms.api.register_push_token``.
"""

import json

import frappe
from frappe.utils import now_datetime, strip_html

FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_ACCESS_TOKEN_CACHE_KEY = "fcm_access_token"
_ACCESS_TOKEN_TTL = 3000  # seconds (~50 min; tokens last 60 min)


# ──────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────
def _service_account_info() -> dict | None:
	"""Returns the parsed service-account dict from site config, or None."""
	inline = frappe.conf.get("fcm_service_account")
	if inline:
		if isinstance(inline, str):
			try:
				return json.loads(inline)
			except json.JSONDecodeError:
				frappe.log_error("Invalid fcm_service_account JSON", "Push Notifications")
				return None
		return inline

	path = frappe.conf.get("fcm_service_account_path")
	if path:
		try:
			with open(path) as fh:
				return json.load(fh)
		except (OSError, json.JSONDecodeError) as exc:
			frappe.log_error(f"Cannot read fcm_service_account_path: {exc}", "Push Notifications")
			return None

	return None


def is_configured() -> bool:
	return _service_account_info() is not None


# ──────────────────────────────────────────────────────────────────────────
# OAuth2 access token (cached)
# ──────────────────────────────────────────────────────────────────────────
def _get_access_token(info: dict) -> str | None:
	cached = frappe.cache().get_value(_ACCESS_TOKEN_CACHE_KEY)
	if cached:
		return cached

	try:
		from google.auth.transport.requests import Request
		from google.oauth2 import service_account
	except ImportError:
		frappe.log_error(
			"google-auth not installed. Run: pip install google-auth",
			"Push Notifications",
		)
		return None

	try:
		credentials = service_account.Credentials.from_service_account_info(
			info, scopes=[FCM_SCOPE]
		)
		credentials.refresh(Request())
	except Exception as exc:  # noqa: BLE001
		frappe.log_error(f"FCM credential refresh failed: {exc}", "Push Notifications")
		return None

	token = credentials.token
	if token:
		frappe.cache().set_value(_ACCESS_TOKEN_CACHE_KEY, token, expires_in_sec=_ACCESS_TOKEN_TTL)
	return token


# ──────────────────────────────────────────────────────────────────────────
# Low-level send
# ──────────────────────────────────────────────────────────────────────────
def _send_one(access_token: str, project_id: str, token_doc: dict, title: str, body: str, data: dict) -> bool:
	"""Sends to a single device. Returns True on success; deletes the token on
	a permanent UNREGISTERED/NOT_FOUND error."""
	import requests

	# FCM data payload must be a flat string→string map.
	str_data = {k: str(v) for k, v in (data or {}).items() if v is not None}

	message = {
		"message": {
			"token": token_doc["token"],
			"notification": {"title": title, "body": body},
			"data": str_data,
			"android": {"priority": "high", "notification": {"sound": "default"}},
			"apns": {"payload": {"aps": {"sound": "default"}}},
		}
	}

	try:
		resp = requests.post(
			FCM_SEND_URL.format(project_id=project_id),
			headers={
				"Authorization": f"Bearer {access_token}",
				"Content-Type": "application/json",
			},
			data=json.dumps(message),
			timeout=10,
		)
	except requests.RequestException as exc:
		frappe.log_error(f"FCM request failed: {exc}", "Push Notifications")
		return False

	if resp.status_code == 200:
		return True

	# 404 UNREGISTERED / 400 invalid token → drop the stale token.
	if resp.status_code in (400, 403, 404):
		error_text = resp.text or ""
		if any(s in error_text for s in ("UNREGISTERED", "NOT_FOUND", "InvalidRegistration")):
			frappe.delete_doc(
				"Push Device Token", token_doc["name"], ignore_permissions=True, force=True
			)
			return False

	frappe.log_error(
		f"FCM send error {resp.status_code}: {resp.text}", "Push Notifications"
	)
	return False


# ──────────────────────────────────────────────────────────────────────────
# Public send helpers
# ──────────────────────────────────────────────────────────────────────────
def send_to_user(user: str, title: str, body: str, data: dict | None = None) -> int:
	"""Sends a push to every enabled device of ``user``. Returns count sent."""
	info = _service_account_info()
	if not info:
		return 0

	project_id = info.get("project_id")
	if not project_id:
		frappe.log_error("Service account missing project_id", "Push Notifications")
		return 0

	tokens = frappe.get_all(
		"Push Device Token",
		filters={"user": user, "enabled": 1},
		fields=["name", "token"],
	)
	if not tokens:
		return 0

	access_token = _get_access_token(info)
	if not access_token:
		return 0

	sent = 0
	for token_doc in tokens:
		if _send_one(access_token, project_id, token_doc, title, body, data or {}):
			sent += 1

	if sent:
		frappe.db.commit()
	return sent


# ──────────────────────────────────────────────────────────────────────────
# Notification Log hook
# ──────────────────────────────────────────────────────────────────────────
def on_notification_log_insert(doc, method=None):
	"""``after_insert`` hook on Notification Log: fan the notification out to
	the user's devices as a push, asynchronously. Never blocks (or fails) the
	creation of the in-app notification."""
	if not is_configured():
		return
	try:
		frappe.enqueue(
			"os_lms.os_lms.push_notifications.send_for_notification_log",
			queue="short",
			enqueue_after_commit=True,
			notification_name=doc.name,
		)
	except Exception:  # noqa: BLE001
		frappe.log_error(frappe.get_traceback(), "Push enqueue failed")


def send_for_notification_log(notification_name: str):
	"""Background job: build a push payload from a Notification Log and send it."""
	doc = frappe.get_doc("Notification Log", notification_name)

	user = doc.for_user
	if not user or user in ("Administrator", "Guest"):
		return

	title = doc.subject or frappe._("New notification")
	body = strip_html(doc.email_content or "").strip()
	if len(body) > 240:
		body = body[:237] + "…"

	data = {
		"notification_id": doc.name,
		"link": doc.link or "",
		"document_type": doc.document_type or "",
		"document_name": doc.document_name or "",
		"type": doc.type or "",
	}

	send_to_user(user, title, body, data)