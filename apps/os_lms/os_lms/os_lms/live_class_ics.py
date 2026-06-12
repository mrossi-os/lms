"""Generate iCalendar (.ics) files for LMS Live Class events.

The email "Add to your calendar" button links to the `download` endpoint, which
returns the live class as an `.ics` attachment so the user's OS can open it
with whichever calendar app (Apple Calendar, Outlook, etc.) they use.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _
from frappe.utils import cint, get_datetime
from frappe.utils.verified_command import get_signed_params, verify_request


def _escape(text: str | None) -> str:
	if not text:
		return ""
	return (
		str(text)
		.replace("\\", "\\\\")
		.replace(";", "\\;")
		.replace(",", "\\,")
		.replace("\r\n", "\\n")
		.replace("\n", "\\n")
	)


def _fold_line(line: str) -> str:
	# RFC 5545 line folding: max 75 octets per line, continuation lines start with a space.
	encoded = line.encode("utf-8")
	if len(encoded) <= 75:
		return line
	chunks = []
	while len(encoded) > 75:
		chunk = encoded[:75]
		# Avoid splitting a multi-byte UTF-8 character.
		while chunk and (chunk[-1] & 0xC0) == 0x80:
			chunk = chunk[:-1]
		chunks.append(chunk.decode("utf-8"))
		encoded = encoded[len(chunk):]
	chunks.append(encoded.decode("utf-8"))
	return "\r\n ".join(chunks)


def _to_utc(local_dt: datetime, tz_name: str | None) -> datetime:
	tz = None
	if tz_name:
		try:
			tz = ZoneInfo(tz_name)
		except ZoneInfoNotFoundError:
			tz = None
	if tz is None:
		# Fall back to the Frappe system timezone, then UTC.
		try:
			tz = ZoneInfo(frappe.utils.get_time_zone())
		except Exception:
			tz = timezone.utc
	return local_dt.replace(tzinfo=tz).astimezone(timezone.utc)


def build_ics(doc) -> str:
	"""Return an iCalendar VCALENDAR string for the given LMS Live Class doc."""
	local_dt = get_datetime(f"{doc.date} {doc.time}")
	start_utc = _to_utc(local_dt, doc.get("timezone"))
	duration_minutes = cint(doc.get("duration")) or 60
	end_utc = start_utc + timedelta(minutes=duration_minutes)
	now_utc = datetime.now(timezone.utc)

	site = getattr(frappe.local, "site", "") or "lms"
	uid = f"live-class-{doc.name}@{site}"

	description_parts = []
	if doc.get("description"):
		description_parts.append(doc.description)
	if doc.get("join_url"):
		description_parts.append(_("Partecipa: {0}").format(doc.join_url))
	description = "\n\n".join(description_parts)

	lines = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//OS LMS//Live Class//IT",
		"CALSCALE:GREGORIAN",
		"METHOD:PUBLISH",
		"BEGIN:VEVENT",
		f"UID:{uid}",
		f"DTSTAMP:{now_utc.strftime('%Y%m%dT%H%M%SZ')}",
		f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
		f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
		f"SUMMARY:{_escape(doc.get('title'))}",
	]
	if description:
		lines.append(f"DESCRIPTION:{_escape(description)}")
	if doc.get("join_url"):
		lines.append(f"LOCATION:{_escape(doc.join_url)}")
		lines.append(f"URL:{_escape(doc.join_url)}")
	lines.extend([
		"STATUS:CONFIRMED",
		"END:VEVENT",
		"END:VCALENDAR",
	])

	return "\r\n".join(_fold_line(line) for line in lines) + "\r\n"


def get_ics_url(name: str) -> str:
	"""Return a signed, guest-accessible URL to download the live class `.ics`.

	The signature lets the `download` endpoint authorize the request without a
	logged-in session, so the "Add to calendar" button works straight from the
	email (any calendar app), even for recipients who are not logged into the LMS.
	Pass the result into email `args` as `ics_url` so any template — including the
	per-client desk-managed Email Templates — can render `{{ ics_url }}`.
	"""
	signed = get_signed_params({"name": name})
	return frappe.utils.get_url() + "/api/method/os_lms.os_lms.live_class_ics.download?" + signed


def get_calendar_links(doc) -> dict:
	"""Return "add to calendar" URLs for the given LMS Live Class doc.

	  - ``google_url`` / ``outlook_url``: prefilled web "add event" deep links for
	    Google Calendar and Outlook.com.
	  - ``ics_url``: the signed ``.ics`` download (Apple Calendar, Thunderbird,
	    desktop Outlook and any other client that handles ``.ics``).

	Built here, not in Jinja, so timezone conversion and URL-encoding stay correct
	and consistent with the ``.ics`` the download endpoint serves. Pass the result
	into email ``args`` so any template — file-based or per-client desk Email
	Template — can render ``{{ google_url }}``, ``{{ outlook_url }}``, ``{{ ics_url }}``.
	"""
	local_dt = get_datetime(f"{doc.date} {doc.time}")
	start_utc = _to_utc(local_dt, doc.get("timezone"))
	duration_minutes = cint(doc.get("duration")) or 60
	end_utc = start_utc + timedelta(minutes=duration_minutes)

	title = doc.get("title") or _("Lezione dal vivo")
	location = doc.get("join_url") or ""
	details_parts = []
	if doc.get("description"):
		details_parts.append(doc.description)
	if doc.get("join_url"):
		details_parts.append(_("Partecipa: {0}").format(doc.join_url))
	details = "\n\n".join(details_parts)

	# UTC with a trailing "Z" is unambiguous; each provider renders it in the
	# recipient's own timezone.
	google_url = "https://calendar.google.com/calendar/render?" + urlencode(
		{
			"action": "TEMPLATE",
			"text": title,
			"dates": f"{start_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
			"details": details,
			"location": location,
		}
	)
	outlook_url = "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(
		{
			"path": "/calendar/action/compose",
			"rru": "addevent",
			"subject": title,
			"startdt": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"enddt": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"body": details,
			"location": location,
		}
	)
	return {
		"google_url": google_url,
		"outlook_url": outlook_url,
		"ics_url": get_ics_url(doc.name),
	}


def _user_can_access(doc) -> bool:
	user = frappe.session.user
	if user in ("Administrator",):
		return True
	roles = set(frappe.get_roles(user))
	if {"System Manager", "Moderator", "Course Creator", "Batch Evaluator"} & roles:
		return True
	if doc.get("batch_name"):
		if frappe.db.exists(
			"LMS Batch Enrollment",
			{"batch": doc.batch_name, "member": user},
		):
			return True
		# Instructors of the batch are also allowed.
		if frappe.db.exists(
			"Course Instructor",
			{"parenttype": "LMS Batch", "parent": doc.batch_name, "instructor": user},
		):
			return True
	return False


@frappe.whitelist(allow_guest=True)
def download(name: str) -> None:
	"""Serve the live class as an `.ics` attachment.

	Authorized in either of two ways:
	  1. A logged-in user with access to the batch (covers in-app use and any
	     older, unsigned links).
	  2. A valid signed link (see `get_ics_url`) — this lets the "Add to calendar"
	     button work from the email without requiring the recipient to log in.
	"""
	if not name:
		frappe.throw(_("Live class non specificata."), frappe.PermissionError)

	doc = frappe.get_doc("LMS Live Class", name)

	if frappe.session.user != "Guest" and _user_can_access(doc):
		pass
	elif not verify_request():
		# `verify_request` has already rendered an "Invalid Link" web page.
		return

	ics = build_ics(doc)
	frappe.local.response.update(
		{
			# Frappe maps the "download" response type to `as_raw`, which streams
			# `filecontent` with the given `content_type` and Content-Disposition.
			"type": "download",
			"filename": f"live-class-{doc.name}.ics",
			"filecontent": ics.encode("utf-8"),
			# Werkzeug appends "; charset=utf-8" to text/* mimetypes itself.
			"content_type": "text/calendar",
			"display_content_as": "attachment",
		}
	)
