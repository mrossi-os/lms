"""Redirect gate for joining an LMS Live Class.

Instead of handing students the raw Zoom/Meet link (which lets them enter before
the host has started the session), emails and calendar entries point to the
`join` endpoint here. When clicked it checks whether the host has started the
class (`started_at`, set by `start_live_class`):

  - started  -> HTTP redirect to the real `join_url`
  - not yet  -> a branded "waiting" page that auto-refreshes, so the student is
                forwarded automatically as soon as the host starts
  - ended    -> a "class ended" page

The gate URL is signed and guest-accessible (same pattern as the `.ics`
download), so the button works straight from the email/calendar without login.
The freshness check runs server-side at click time, so the URL stored in a
calendar entry stays valid and correct regardless of the class state.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import (
	cint,
	escape_html,
	format_date,
	format_time,
	get_datetime,
	now_datetime,
)
from frappe.utils.verified_command import get_signed_params, verify_request


def get_join_gate_url(name: str) -> str:
	"""Return a signed, guest-accessible URL to the join gate for a live class.

	The signature lets the `join` endpoint authorize the request without a
	logged-in session, so the button works from the email/calendar even for
	recipients who are not logged into the LMS. Pass the result wherever the raw
	`join_url` would otherwise be exposed to students (invitation email, `.ics`,
	"add to calendar" links).
	"""
	signed = get_signed_params({"name": name})
	return frappe.utils.get_url() + "/api/method/os_lms.os_lms.live_class_join.join?" + signed


def _can_access(doc) -> bool:
	# Reuse the batch-access check from the `.ics` download. Imported lazily to
	# avoid a circular import (live_class_ics imports get_join_gate_url).
	from os_lms.os_lms.live_class_ics import _user_can_access

	return _user_can_access(doc)


@frappe.whitelist(allow_guest=True)
def join(name: str) -> None:
	"""Redirect to the meeting if the host has started, otherwise show a page.

	Authorized either by a logged-in user with access to the batch, or by a
	valid signed link (see `get_join_gate_url`).
	"""
	if not name:
		frappe.throw(_("Live class non specificata."), frappe.PermissionError)

	doc = frappe.get_doc("LMS Live Class", name)

	if frappe.session.user != "Guest" and _can_access(doc):
		pass
	elif not verify_request():
		# verify_request has already rendered an "Invalid Link" web page.
		return

	start_dt = get_datetime(f"{doc.date} {doc.time}")
	end_dt = start_dt + timedelta(minutes=cint(doc.get("duration")) or 60)

	if now_datetime() > end_dt:
		_render_gate_page(doc, "ended")
		return

	if doc.get("started_at") and doc.get("join_url"):
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = doc.join_url
		return

	_render_gate_page(doc, "waiting")


def _render_gate_page(doc, state: str) -> None:
	html = _build_gate_html(doc, state)
	frappe.local.response.update(
		{
			# Frappe maps the "download" response type to `as_raw`, which streams
			# `filecontent` with the given `content_type`. "inline" display makes
			# the browser render the HTML instead of downloading it.
			"type": "download",
			"filename": "live-class.html",
			"filecontent": html.encode("utf-8"),
			"content_type": "text/html; charset=utf-8",
			"display_content_as": "inline",
		}
	)


def _build_gate_html(doc, state: str) -> str:
	site_url = frappe.utils.get_url()
	logo_url = site_url + "/files/logo%20salescience_bianco.png"
	batch_url = site_url + "/lms/batches/" + doc.batch_name if doc.get("batch_name") else site_url
	title = escape_html(doc.get("title") or "")

	if state == "ended":
		heading = _("La lezione è terminata")
		message = _("Questa sessione dal vivo si è già conclusa.")
		refresh_meta = ""
	else:
		heading = _("La lezione non è ancora iniziata")
		message = _(
			"Attendi che il relatore avvii la sessione: verrai reindirizzato "
			"automaticamente non appena la lezione sarà attiva."
		)
		refresh_meta = '<meta http-equiv="refresh" content="30" />'

	when_html = ""
	if doc.get("date") and doc.get("time"):
		when = _("{0} alle ore {1}").format(
			format_date(doc.date, "dd-MM-yyyy"), format_time(doc.time, "HH:mm")
		)
		when_html = (
			f'<p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#5b7aa5;">'
			f"{escape_html(when)}</p>"
		)

	return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
{refresh_meta}
<title>{escape_html(heading)}</title>
</head>
<body style="margin:0;padding:0;background:#D0EBF8;font-family:Helvetica,Arial,sans-serif;">
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px 16px;box-sizing:border-box;">
<div style="background:#FFFFFF;border:1px solid #A0D9F3;border-radius:12px;overflow:hidden;max-width:520px;width:100%;box-shadow:0 8px 24px rgba(14,55,104,0.14);">
<div style="background:#0e3768;padding:28px 32px;text-align:center;border-bottom:4px solid #FF8400;">
<img src="{logo_url}" alt="Salescience" style="height:40px;width:auto;display:inline-block;" />
</div>
<div style="padding:36px 32px;text-align:center;color:#14447c;">
<h1 style="margin:0 0 16px;font-size:20px;color:#0e3768;">{escape_html(heading)}</h1>
<p style="font-size:15px;line-height:1.7;margin:0 0 8px;color:#0e3768;font-weight:600;">{title}</p>
{when_html}
<p style="font-size:14px;line-height:1.7;margin:0 0 28px;color:#14447c;">{escape_html(message)}</p>
<a href="{batch_url}" style="display:inline-block;background:#0d65bb;color:#FFFFFF;padding:13px 30px;border-radius:6px;font-size:14px;font-weight:700;text-decoration:none;">{escape_html(_("Torna alla piattaforma"))}</a>
</div>
<div style="background:#D0EBF8;padding:16px 32px;text-align:center;font-size:11px;color:#14447c;border-top:1px solid #A0D9F3;">
<strong style="color:#0e3768;">Salescience</strong> · Academy
</div>
</div>
</div>
</body>
</html>"""
