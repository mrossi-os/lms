# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""OS Audit exports (phase 2 of docs/audit-studenti/PIANO.md §7).

Exports reuse the queue of the student statistics export: a ``Student Stats Export``
record whose ``report_type`` starts with ``os_audit_`` (the statistics page hides
them), built on the ``long`` queue and attached as a private File, which the
Gestore can download through its read permission on the record.

Every finished export writes an ``audit_export`` event in the chain with who asked
for it, the filters, the row count and the SHA-256 of the file: what left the
platform stays on record, and a file handed to a third party can be matched to it.
"""

import csv
import hashlib
import io

import frappe
from frappe import _
from frappe.utils import cint, format_date, format_datetime, get_datetime, getdate, now_datetime

from os_lms.os_lms import os_audit
from os_lms.os_lms.os_audit import EVENT, SESSION, assert_can_use_os_audit
from os_lms.os_lms.os_audit_page import (
	EVENT_FIELDS,
	course_attendance,
	date_range,
	decorate_events,
	device_label,
	format_hm,
	full_names,
	last_seal,
	live_attendance,
	names_of,
)

EXPORT_DOCTYPE = "Student Stats Export"
REPORT_PREFIX = "os_audit_"
REPORTS = {
	"os_audit_register": {"label": "Attendance register", "needs_course": True},
	"os_audit_live": {"label": "Live class attendance", "needs_course": True},
	"os_audit_sessions": {"label": "Lesson visits", "needs_course": False},
	"os_audit_events": {"label": "Audit events", "needs_course": False},
}
FILE_FORMATS = ("xlsx", "csv")
MAX_ROWS = 200_000


def is_audit_export(report_type: str | None) -> bool:
	return bool(report_type) and report_type.startswith(REPORT_PREFIX)


@frappe.whitelist(methods=["POST"])
def start_audit_export(
	report: str,
	file_format: str = "xlsx",
	course: str | None = None,
	user: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
) -> dict:
	assert_can_use_os_audit()
	spec = REPORTS.get(report)
	if not spec:
		frappe.throw(_("Unknown report type."), frappe.ValidationError)
	if file_format not in FILE_FORMATS:
		frappe.throw(_("Invalid file format."), frappe.ValidationError)
	if spec["needs_course"] and not course:
		frappe.throw(_("Choose a course."), frappe.ValidationError)
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("The start date is after the end date."), frappe.ValidationError)

	filters = {
		key: value
		for key, value in {"course": course, "user": user, "from_date": from_date, "to_date": to_date}.items()
		if value
	}
	export = frappe.new_doc(EXPORT_DOCTYPE)
	export.report_type = report
	export.report_label = spec["label"]
	export.file_format = file_format
	export.columns = "[]"
	export.filters = frappe.as_json(filters)
	export.status = "Queued"
	export.insert(ignore_permissions=True)

	frappe.enqueue(
		"os_lms.os_lms.os_audit_export.run_audit_export",
		queue="long",
		timeout=1800,
		enqueue_after_commit=True,
		export_name=export.name,
	)
	return {"name": export.name}


def run_audit_export(export_name: str) -> None:
	"""Background job: build the file, attach it, then record the export in the chain."""
	export = frappe.get_doc(EXPORT_DOCTYPE, export_name)
	frappe.db.set_value(EXPORT_DOCTYPE, export_name, "status", "Processing")
	frappe.db.commit()
	try:
		filters = frappe.parse_json(export.filters or "{}") or {}
		rows, data_rows = build_rows(export.report_type, filters)
		label = _(REPORTS[export.report_type]["label"])
		filename, content = to_file(label, export.file_format, rows)

		from frappe.utils.file_manager import save_file

		file_doc = save_file(filename, content, EXPORT_DOCTYPE, export_name, is_private=1)
		frappe.db.set_value(
			EXPORT_DOCTYPE,
			export_name,
			{
				"file": file_doc.file_url,
				"row_count": data_rows,
				"file_size": len(content),
				"status": "Ready",
				"error": "",
			},
		)
		os_audit.record(
			"audit_export",
			user=export.owner,
			course=filters.get("course"),
			reference_doctype=EXPORT_DOCTYPE,
			reference_name=export_name,
			data={
				"report": export.report_type,
				"format": export.file_format,
				"filters": filters,
				"rows": data_rows,
				"file_sha256": hashlib.sha256(content).hexdigest(),
			},
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.db.set_value(
			EXPORT_DOCTYPE, export_name, {"status": "Failed", "error": frappe.get_traceback()[:2000]}
		)
		frappe.db.commit()
		frappe.log_error(title="OS Audit export failed", message=export_name)
		raise


@frappe.whitelist()
def list_audit_exports() -> list:
	assert_can_use_os_audit()
	return frappe.get_all(
		EXPORT_DOCTYPE,
		filters={"report_type": ["like", f"{REPORT_PREFIX}%"]},
		fields=["name", "report_type", "file_format", "status", "creation", "owner", "row_count", "file", "error", "filters"],
		order_by="creation desc",
		limit=200,
	)


@frappe.whitelist(methods=["POST"])
def delete_audit_export(name: str) -> dict:
	"""Delete an export file. The audit_export event stays: deleting the copy does
	not undo that the data left the platform."""
	assert_can_use_os_audit()
	if is_audit_export(frappe.db.get_value(EXPORT_DOCTYPE, name, "report_type")):
		frappe.delete_doc(EXPORT_DOCTYPE, name, ignore_permissions=True, delete_permanently=True)
	return {"name": name}


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


def build_rows(report: str, filters: dict) -> tuple[list[list], int]:
	"""(rows of the file, number of data rows) of a report."""
	builders = {
		"os_audit_register": register_rows,
		"os_audit_live": live_rows,
		"os_audit_sessions": session_rows,
		"os_audit_events": event_rows,
	}
	if report not in builders:
		frappe.throw(_("Unknown report type."))
	rows, data_rows = builders[report](filters)
	return rows + footer_rows(filters), data_rows


def _dt(value) -> str:
	return format_datetime(value, "dd/MM/yyyy HH:mm:ss") if value else ""


def _date(value) -> str:
	return format_date(value, "dd/MM/yyyy") if value else ""


def _time(value) -> str:
	return get_datetime(value).strftime("%H:%M") if value else ""


def register_rows(filters: dict) -> tuple[list[list], int]:
	"""One row per lesson visit of every student of the course, then the student's
	total in h:mm with the % of the planned hours (PIANO §7)."""
	course = filters["course"]
	attendance = course_attendance(course, filters.get("from_date"), filters.get("to_date"))
	counted_label = _("Presence") if attendance["counted_time"] != "Active Time" else _("Active Time")
	header = [
		_("Student"),
		_("Email"),
		_("Date"),
		_("Entry"),
		_("Exit"),
		_("Lesson"),
		_("Presence (h:mm)"),
		_("Active time (h:mm)"),
		_("Attendance % ({0})").format(counted_label),
	]
	sessions = frappe.get_all(
		SESSION,
		filters=[["course", "=", course], *date_range("started_at", filters.get("from_date"), filters.get("to_date"))],
		fields=["user", "lesson", "started_at", "last_seen_at", "presence_seconds", "active_seconds"],
		order_by="started_at asc",
		limit=MAX_ROWS,
	)
	lessons = names_of("Course Lesson", (s.lesson for s in sessions), "title")
	by_user = {}
	for s in sessions:
		by_user.setdefault(s.user, []).append(s)
	rows = [
		[_("Course"), attendance["course_title"]],
		[_("Planned hours"), attendance["planned_hours"] or ""],
		[_("Minimum attendance %"), attendance["min_attendance_percent"] or ""],
		[_("Period"), _period(filters)],
		[],
		header,
	]
	for student in attendance["students"]:
		for s in by_user.get(student["user"], []):
			rows.append(
				[
					student["full_name"],
					student["user"],
					_date(s.started_at),
					_time(s.started_at),
					_time(s.last_seen_at),
					lessons.get(s.lesson) or s.lesson or "",
					format_hm(s.presence_seconds),
					format_hm(s.active_seconds),
					"",
				]
			)
		rows.append(
			[
				student["full_name"],
				student["user"],
				_("Total"),
				"",
				"",
				"",
				format_hm(student["presence_seconds"]),
				format_hm(student["active_seconds"]),
				"" if student["percent"] is None else student["percent"],
			]
		)
	return rows, len(sessions) + len(attendance["students"])


def live_rows(filters: dict) -> tuple[list[list], int]:
	"""Per live class: date, time, teacher and every participant with entry, exit and
	duration (PIANO §7). Entry and exit come from the provider (phase 4)."""
	header = [
		_("Date"),
		_("Time"),
		_("Live class"),
		_("Class"),
		_("Provider"),
		_("Role"),
		_("Participant"),
		_("Email"),
		_("Joined from the platform"),
		_("Entry"),
		_("Exit"),
		_("Duration (h:mm)"),
	]
	rows = [header]
	for live in live_attendance(filters["course"], filters.get("from_date"), filters.get("to_date")):
		base = [_date(live["date"]), str(live["time"] or "")[:5], live["title"], live["batch_title"], live["provider"] or ""]
		people = live["participants"]
		if not any(p["is_host"] for p in people) and live["host"]:
			people = [
				{
					"user": live["host"],
					"full_name": live["host_name"],
					"is_host": True,
					"joined_from_platform": None,
					"joined_at": None,
					"left_at": None,
					"duration_seconds": None,
				},
				*people,
			]
		if not people:
			rows.append([*base, "", _("No attendance recorded"), "", "", "", "", ""])
		for p in people:
			rows.append(
				[
					*base,
					_("Teacher") if p["is_host"] else _("Participant"),
					p["full_name"],
					p["user"] or "",
					_dt(p["joined_from_platform"]),
					_dt(p["joined_at"]),
					_dt(p["left_at"]),
					"" if p["duration_seconds"] is None else format_hm(p["duration_seconds"]),
				]
			)
	return rows, len(rows) - 1


def session_rows(filters: dict) -> tuple[list[list], int]:
	conditions = date_range("started_at", filters.get("from_date"), filters.get("to_date"))
	if filters.get("course"):
		conditions.append(["course", "=", filters["course"]])
	if filters.get("user"):
		conditions.append(["user", "=", filters["user"]])
	sessions = frappe.get_all(
		SESSION,
		filters=conditions,
		fields=["name", "user", "course", "lesson", "started_at", "last_seen_at", "presence_seconds", "active_seconds", "closed", "device", "ip_address"],
		order_by="started_at asc",
		limit=MAX_ROWS,
	)
	users = full_names(s.user for s in sessions)
	courses = names_of("LMS Course", (s.course for s in sessions), "title")
	lessons = names_of("Course Lesson", (s.lesson for s in sessions), "title")
	rows = [
		[
			_("Student"),
			_("Email"),
			_("Course"),
			_("Lesson"),
			_("Started"),
			_("Last signal"),
			_("Presence (h:mm)"),
			_("Active time (h:mm)"),
			_("Closed"),
			_("Device"),
			_("IP Address"),
			_("Visit ID"),
		]
	]
	for s in sessions:
		rows.append(
			[
				users.get(s.user) or s.user,
				s.user,
				courses.get(s.course) or s.course or "",
				lessons.get(s.lesson) or s.lesson or "",
				_dt(s.started_at),
				_dt(s.last_seen_at),
				format_hm(s.presence_seconds),
				format_hm(s.active_seconds),
				_("Yes") if cint(s.closed) else _("No"),
				device_label(s.device),
				s.ip_address or "",
				s.name,
			]
		)
	return rows, len(sessions)


def event_rows(filters: dict) -> tuple[list[list], int]:
	conditions = date_range("timestamp", filters.get("from_date"), filters.get("to_date"))
	if filters.get("course"):
		conditions.append(["course", "=", filters["course"]])
	if filters.get("user"):
		conditions.append(["user", "=", filters["user"]])
	raw = frappe.get_all(EVENT, filters=conditions, fields=[*EVENT_FIELDS, "hash"], order_by="seq asc", limit=MAX_ROWS)
	hashes = {row.name: row.hash for row in raw}
	rows = [
		[
			_("Sequence"),
			_("Date and time"),
			_("Event"),
			_("Student"),
			_("Email"),
			_("Course"),
			_("Lesson"),
			_("Reference"),
			_("Device"),
			_("IP Address"),
			_("Details"),
			_("Hash"),
		]
	]
	for event in decorate_events(raw):
		reference = " ".join(filter(None, [event["reference_doctype"], event["reference_name"]]))
		rows.append(
			[
				event["seq"],
				_dt(event["timestamp"]),
				event["event_label"],
				_("Erased") if event["redacted"] else (event["full_name"] or ""),
				event["user"] or "",
				event["course_title"] or event["batch_title"] or "",
				event["lesson_title"] or "",
				reference,
				event["device_label"],
				event["ip_address"] or "",
				frappe.as_json(event["data"], indent=None) if event["data"] else "",
				hashes.get(event["name"]) or "",
			]
		)
	return rows, len(raw)


def footer_rows(filters: dict) -> list[list]:
	"""Under every export: when it was generated and the last seal it falls under,
	so the figures can be checked against the chain."""
	seal = last_seal(filters.get("to_date"))
	head_seq, head_hash = os_audit.chain_head()
	return [
		[],
		[_("Generated on"), _dt(now_datetime())],
		[_("Last daily seal included"), seal["date"] if seal else _("None yet"), (seal or {}).get("last_hash") or ""],
		[_("Chain at generation (sequence, hash)"), head_seq or "", head_hash or ""],
	]


def _period(filters: dict) -> str:
	start, end = filters.get("from_date"), filters.get("to_date")
	if not start and not end:
		return _("All data kept")
	return f"{_date(start) if start else '…'} – {_date(end) if end else '…'}"


# ---------------------------------------------------------------------------
# File
# ---------------------------------------------------------------------------


def to_file(label: str, file_format: str, rows: list[list]) -> tuple[str, bytes]:
	safe = frappe.scrub(label) or "os_audit"
	stamp = now_datetime().strftime("%Y%m%d-%H%M")
	if file_format == "csv":
		buffer = io.StringIO()
		csv.writer(buffer).writerows(rows)
		return f"{safe}-{stamp}.csv", buffer.getvalue().encode("utf-8")
	from frappe.utils.xlsxutils import make_xlsx

	return f"{safe}-{stamp}.xlsx", make_xlsx(rows, label[:31]).getvalue()
