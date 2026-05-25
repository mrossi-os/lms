"""Generate iCalendar (.ics) files for LMS Live Class events.

The email "Add to your calendar" button links to the `download` endpoint, which
returns the live class as an `.ics` attachment so the user's OS can open it
with whichever calendar app (Apple Calendar, Outlook, etc.) they use.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _
from frappe.utils import cint, get_datetime


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


@frappe.whitelist()
def download(name: str) -> None:
	"""Serve the live class as an `.ics` attachment for the calling user."""
	if not name:
		frappe.throw(_("Live class non specificata."), frappe.PermissionError)

	doc = frappe.get_doc("LMS Live Class", name)
	if not _user_can_access(doc):
		frappe.throw(
			_("Non sei autorizzato a scaricare questo evento."),
			frappe.PermissionError,
		)

	ics = build_ics(doc)
	frappe.local.response.update(
		{
			"type": "raw",
			"filename": f"live-class-{doc.name}.ics",
			"filecontent": ics.encode("utf-8"),
			"content_type": "text/calendar; charset=utf-8",
			"display_content_as": "attachment",
		}
	)
