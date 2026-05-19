# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _
from frappe.utils import get_request_site_address

from lms.lms.utils import get_lms_route


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
def google_callback(code=None):
	"""Override of frappe.integrations.doctype.google_calendar.google_calendar.google_callback.

	Replicates the token-exchange flow but, on success, redirects the user back
	to the LMS SPA Settings page instead of the Frappe desk, so the OAuth
	popup lands inside the application UI.
	"""
	from frappe.integrations.google_oauth import GoogleOAuth

	g_calendar_name = frappe.cache.hget("google_calendar", "google_calendar")
	if not g_calendar_name:
		frappe.throw(_("Sessione di autorizzazione Google non trovata. Riprova."))

	frappe.db.set_value("Google Calendar", g_calendar_name, "authorization_code", code)
	frappe.db.commit()

	google_calendar = frappe.get_doc("Google Calendar", g_calendar_name)
	google_settings = frappe.get_cached_doc("Google Settings")

	# Must match exactly the redirect_uri sent in the initial authorize_access
	# call, otherwise Google rejects the code exchange. We override the handler
	# via `override_whitelisted_methods` so this URL still routes to us.
	redirect_uri = (
		f"{get_request_site_address(full_address=True)}"
		f"?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
	)

	data = {
		"code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"redirect_uri": redirect_uri,
		"grant_type": "authorization_code",
	}

	try:
		r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()
	except Exception as exc:
		frappe.log_error(title="Google Calendar token exchange failed")
		frappe.throw(_("Errore nello scambio del token con Google: {0}").format(exc))

	if "refresh_token" in r:
		frappe.db.set_value(
			"Google Calendar", google_calendar.name, "refresh_token", r["refresh_token"]
		)
		frappe.db.commit()

	_render_popup_close(get_lms_route())


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
