# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import json
import secrets

import frappe
import requests
from frappe import _
from frappe.integrations.doctype.google_calendar.google_calendar import get_authentication_url
from frappe.utils import get_request_site_address
from frappe.utils.password import set_encrypted_password

from lms.lms.utils import get_lms_route

# The redirect registered in the Google console names Frappe's method;
# override_whitelisted_methods routes it to google_callback below.
CALLBACK_METHOD = "frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
STATE_TTL_SECONDS = 10 * 60
TOKEN_FIELDS = ("authorization_code", "refresh_token")
MASK = "*****"


@frappe.whitelist()
def is_google_oauth_configured() -> bool:
	"""Return True if Google Settings has OAuth credentials set.

	Used by the frontend Settings page to decide whether to show the
	"Authorize" UI or a configuration warning. Doesn't expose the secret.
	"""
	settings = frappe.get_cached_doc("Google Settings")
	if not settings.enable or not settings.client_id:
		return False
	try:
		secret = settings.get_password("client_secret", raise_exception=False)
	except Exception:
		secret = None
	return bool(secret)


@frappe.whitelist()
def authorize_access(g_calendar: str, reauthorize: bool = False):
	"""Override of Frappe's authorize_access: start the Google consent for one calendar.

	Frappe keeps the calendar being linked in one site-wide cache slot, so its
	callback links whatever calendar was started last to whichever Google account
	the returning request carries, for any user who opens it. Each start here gets
	a one-time `state` bound to the user and the calendar instead, which Google
	sends back and google_callback checks.

	`reauthorize` stays for the callers: Frappe's other path re-exchanges the stored
	code, which Google already spent, so every start asks Google again.
	"""
	google_calendar = frappe.get_doc("Google Calendar", g_calendar)
	google_calendar.check_permission("write")
	google_settings = frappe.get_cached_doc("Google Settings")

	state = secrets.token_urlsafe(32)
	frappe.cache.set_value(
		_state_key(state),
		{"user": frappe.session.user, "calendar": google_calendar.name},
		expires_in_sec=STATE_TTL_SECONDS,
	)
	auth = get_authentication_url(client_id=google_settings.client_id, redirect_uri=_redirect_uri())
	auth["url"] += f"&state={state}"
	return auth


@frappe.whitelist()
def google_callback(code: str | None = None, state: str | None = None):
	"""Override of frappe.integrations.doctype.google_calendar.google_calendar.google_callback.

	Accepts only the return of a consent the same user started in the last ten
	minutes, stores the tokens encrypted and, on success, closes the OAuth popup
	inside the LMS SPA instead of landing on the Frappe desk.
	"""
	from frappe.integrations.google_oauth import GoogleOAuth

	pending = _pop_state(state)
	if not pending or pending.get("user") != frappe.session.user:
		frappe.throw(
			_("This Google authorization is not valid or has expired. Start the authorization again."),
			frappe.PermissionError,
		)
	if not code:
		frappe.throw(_("Google did not grant access to the calendar. Start the authorization again."))

	google_calendar = frappe.get_doc("Google Calendar", pending["calendar"])
	# Frappe's callback checked this through authorize_access; it may also have
	# changed since the start.
	google_calendar.check_permission("write")
	google_settings = frappe.get_cached_doc("Google Settings")

	data = {
		"code": code,
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		# Must match the redirect_uri of the consent, or Google rejects the exchange.
		"redirect_uri": _redirect_uri(),
		"grant_type": "authorization_code",
	}

	try:
		r = requests.post(GoogleOAuth.OAUTH_URL, data=data, timeout=15).json()
	except Exception as exc:
		frappe.log_error(title="Google Calendar token exchange failed")
		frappe.throw(_("Errore nello scambio del token con Google: {0}").format(exc))

	_store_token(google_calendar.name, "authorization_code", code)
	if "refresh_token" in r:
		_store_token(google_calendar.name, "refresh_token", r["refresh_token"])
	frappe.db.commit()

	_render_popup_close(get_lms_route())


def encrypt_plaintext_tokens() -> None:
	"""after_migrate: encrypt the tokens a former callback left in clear, and scrub Version.

	Not a patch: the staging deploy marks new patches done without running them.
	"""
	moved = 0
	for row in frappe.db.get_values("Google Calendar", {}, ["name", *TOKEN_FIELDS], as_dict=True):
		for fieldname in TOKEN_FIELDS:
			value = row.get(fieldname)
			if value and not _is_mask(value):
				_store_token(row.name, fieldname, value, update_modified=False)
				moved += 1
	scrubbed = _scrub_version_history()
	if moved or scrubbed:
		frappe.db.commit()
		print(f"Google Calendar: encrypted {moved} tokens, scrubbed {scrubbed} Version rows")


def _redirect_uri() -> str:
	return f"{get_request_site_address(full_address=True)}?cmd={CALLBACK_METHOD}"


def _state_key(state: str) -> str:
	return f"os_lms:google_calendar:oauth_state:{state}"


def _pop_state(state: str | None) -> dict | None:
	if not state:
		return None
	key = _state_key(state)
	pending = frappe.cache.get_value(key)
	# One use only, whoever brings it back.
	frappe.cache.delete_value(key)
	return pending


def _store_token(calendar: str, fieldname: str, value: str, update_modified: bool = True) -> None:
	# db.set_value writes a Password field as given, so the token would sit in clear
	# in the table: encrypt it and keep the placeholder Frappe writes on save.
	set_encrypted_password("Google Calendar", calendar, value, fieldname)
	frappe.db.set_value(
		"Google Calendar", calendar, fieldname, "*" * len(value), update_modified=update_modified
	)


def _scrub_version_history() -> int:
	"""Blank the token values the calendars' change history recorded while in clear.

	A save after the old callback logged the clear token as the field's old value.
	"""
	scrubbed = 0
	for row in frappe.get_all("Version", filters={"ref_doctype": "Google Calendar"}, fields=["name", "data"]):
		try:
			data = json.loads(row.data or "{}")
		except ValueError:
			continue
		touched = False
		for change in data.get("changed") or []:
			if len(change) == 3 and change[0] in TOKEN_FIELDS:
				for i in (1, 2):
					if change[i] and not _is_mask(str(change[i])):
						change[i] = MASK
						touched = True
		if touched:
			frappe.db.set_value("Version", row.name, "data", json.dumps(data, indent=1), update_modified=False)
			scrubbed += 1
	return scrubbed


def _is_mask(value: str) -> bool:
	return set(value) == {"*"}


def _render_popup_close(fallback_url: str):
	"""Serve a small HTML page that closes the OAuth popup and notifies the opener.

	If the browser blocks `window.close()` (e.g. the popup wasn't opened by JS in
	the same origin chain), the user is redirected to the LMS frontend root.
	"""
	html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Autorizzazione completata</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         display: flex; align-items: center; justify-content: center;
         min-height: 100vh; margin: 0; background: #f9fafb; color: #111827; }}
  .card {{ text-align: center; padding: 2rem 2.5rem; background: white;
          border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); max-width: 380px; }}
  h1 {{ font-size: 1.1rem; margin: 0 0 0.5rem; }}
  p  {{ font-size: 0.9rem; color: #4b5563; margin: 0; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Autorizzazione Google Calendar completata</h1>
    <p>Puoi chiudere questa finestra.</p>
  </div>
  <script>
    (function () {{
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage({{ type: 'google-calendar-authorized' }}, '*');
        }}
      }} catch (e) {{}}
      try {{ window.close(); }} catch (e) {{}}
      setTimeout(function () {{
        if (!window.closed) window.location.replace({fallback_url!r});
      }}, 800);
    }})();
  </script>
</body>
</html>"""

	frappe.local.response.update(
		{
			"type": "download",
			"filename": "google_calendar_callback.html",
			"filecontent": html,
			"content_type": "text/html; charset=utf-8",
			"display_content_as": "inline",
		}
	)
