# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""OS Audit page (phase 2 of docs/audit-studenti/PIANO.md §7): the endpoints behind
/lms/os-audit. Every endpoint is gated on os_audit.OS_AUDIT_ROLES (System Manager
and Gestore): the Gestore is usually a Website User, so the page lives in the SPA.

The page loads with one call (``get_page``); each tab then asks only for what the
user searched. Exports live in os_audit_export.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate

from os_lms.os_lms import os_audit
from os_lms.os_lms.os_audit import EVENT, SESSION, SETTINGS, assert_can_use_os_audit

# Settings the page edits (the chain anchor belongs to the retention job).
EDITABLE_FIELDS = (
	"enabled",
	"retention_days",
	"counted_time",
	"inactivity_minutes",
	"scope",
	"track_logins",
	"track_course_lesson",
	"track_lesson_time",
	"track_quizzes",
	"track_assignments",
	"track_live_classes",
	"track_scorm",
	"track_certificates",
	"track_videos",
	"track_files",
	"store_device",
	"store_ip",
	"on_account_deletion",
	"seal_email",
)
TOGGLE_FIELDS = {field for field in EDITABLE_FIELDS if field.startswith("track_")} | {"store_device"}

# Labels of the event types and devices: the page and the exports read them from
# here, so the codes never reach a reader untranslated.
EVENT_LABELS = {
	"login": "Logged in",
	"logout": "Logged out",
	"login_failed": "Failed login",
	"course_view": "Course opened",
	"lesson_open": "Lesson opened",
	"session_closed": "Lesson visit closed",
	"lesson_complete": "Lesson completed",
	"quiz_start": "Quiz started",
	"quiz_submit": "Quiz submitted",
	"assignment_submit": "Assignment submitted",
	"scorm_open": "SCORM package opened",
	"live_class_join": "Live class joined",
	"live_attendance": "Live class attendance",
	"certificate_issued": "Certificate issued",
	"audit_settings_changed": "Audit settings changed",
	"audit_data_erased": "Audit data erased",
	"audit_export": "Audit data exported",
	"daily_seal": "Daily seal",
	"video_play": "Video played",
	"video_pause": "Video paused",
	"video_seek": "Video skipped",
	"video_ended": "Video finished",
	"pdf_open": "PDF opened",
	"download": "File opened or downloaded",
}
DEVICE_LABELS = {"desktop": "Desktop", "tablet": "Tablet", "mobile": "Mobile"}

LOG_PAGE_LENGTH = 50
LOG_MAX_PAGE_LENGTH = 200
HISTORY_LIMIT = 20
SEAL_LIMIT = 30

EVENT_FIELDS = [
	"name",
	"seq",
	"event_type",
	"timestamp",
	"user",
	"course",
	"lesson",
	"batch",
	"reference_doctype",
	"reference_name",
	"session",
	"device",
	"ip_address",
	"data",
	"redacted",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def event_label(event_type: str | None) -> str:
	return _(EVENT_LABELS[event_type]) if event_type in EVENT_LABELS else (event_type or "")


def device_label(device: str | None) -> str:
	return _(DEVICE_LABELS[device]) if device in DEVICE_LABELS else (device or "")


def format_hm(seconds) -> str:
	"""Seconds as h:mm, the format attendance registers use."""
	minutes = max(cint(seconds), 0) // 60
	return f"{minutes // 60}:{minutes % 60:02d}"


def date_range(fieldname: str, from_date=None, to_date=None) -> list:
	"""Filters for a datetime field between two dates, both days included."""
	filters = []
	if from_date:
		filters.append([fieldname, ">=", get_datetime(getdate(from_date))])
	if to_date:
		filters.append([fieldname, "<", get_datetime(add_days(getdate(to_date), 1))])
	return filters


def parse_data(value) -> dict:
	if not value:
		return {}
	try:
		data = json.loads(value)
	except (TypeError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}


def names_of(doctype: str, names, field: str) -> dict:
	"""{name: title} for a set of links, in one query."""
	names = {name for name in names if name}
	if not names:
		return {}
	return dict(
		frappe.get_all(doctype, filters={"name": ["in", list(names)]}, fields=["name", field], as_list=True)
	)


def full_names(users) -> dict:
	return names_of("User", users, "full_name")


def counted_seconds(presence: int, active: int, settings=None) -> int:
	"""The time that counts (PIANO D12): presence unless the settings say active time."""
	settings = settings or os_audit.get_settings()
	return cint(active) if settings.get("counted_time") == "Active Time" else cint(presence)


def course_rules(course: str, settings=None) -> tuple[float, float]:
	"""(planned hours, minimum attendance %) of a course, 0 when not set."""
	settings = settings or os_audit.get_settings()
	for row in settings.get("courses") or []:
		if row.course == course:
			return flt(row.planned_hours), flt(row.min_attendance_percent)
	return 0.0, 0.0


def attendance_percent(counted: int, planned_hours: float) -> float | None:
	if planned_hours <= 0:
		return None
	return round(cint(counted) * 100 / (planned_hours * 3600), 1)


def last_seal(until=None) -> dict | None:
	"""The latest daily seal, or the latest one sealing a day up to ``until``."""
	filters = {"event_type": "daily_seal"}
	rows = frappe.get_all(EVENT, filters=filters, fields=["seq", "timestamp", "data"], order_by="seq desc", limit=400)
	limit_day = getdate(until) if until else None
	for row in rows:
		data = parse_data(row.data)
		if limit_day and data.get("date") and getdate(data["date"]) > limit_day:
			continue
		return {
			"date": data.get("date"),
			"events": data.get("events"),
			"last_seq": data.get("last_seq"),
			"last_hash": data.get("last_hash"),
			"sealed_at": row.timestamp,
			"seq": row.seq,
		}
	return None


# ---------------------------------------------------------------------------
# Page load: settings, history, status
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_page() -> dict:
	"""Everything the page shows on load, in one call."""
	assert_can_use_os_audit()
	settings = frappe.get_single(SETTINGS)
	return {
		"settings": settings_payload(settings),
		"history": settings_history(),
		"status": audit_status(settings),
		"event_types": [{"value": key, "label": event_label(key)} for key in EVENT_LABELS],
	}


def settings_payload(settings) -> dict:
	values = {}
	for field in EDITABLE_FIELDS:
		if field in TOGGLE_FIELDS:
			values[field] = os_audit._flag(settings, field)
		else:
			values[field] = settings.get(field)
	values["enabled"] = cint(values["enabled"])
	values["retention_days"] = cint(values["retention_days"]) or None
	values["inactivity_minutes"] = cint(values["inactivity_minutes"]) or 3
	values["counted_time"] = values["counted_time"] or "Presence"
	values["scope"] = values["scope"] or "Selected Courses"
	values["store_ip"] = values["store_ip"] or "Not Stored"
	values["on_account_deletion"] = values["on_account_deletion"] or "Delete Audit Data"
	titles = names_of("LMS Course", [row.course for row in settings.get("courses") or []], "title")
	values["courses"] = [
		{
			"course": row.course,
			"title": titles.get(row.course) or row.course,
			"planned_hours": flt(row.planned_hours),
			"min_attendance_percent": flt(row.min_attendance_percent),
		}
		for row in settings.get("courses") or []
	]
	return values


def settings_history() -> list:
	"""Who changed the settings, when and what (from the Versions of track_changes)."""
	meta = frappe.get_meta(SETTINGS)
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": SETTINGS, "docname": SETTINGS},
		fields=["owner", "creation", "data"],
		order_by="creation desc",
		limit=HISTORY_LIMIT,
	)
	names = full_names(version.owner for version in versions)
	history = []
	for version in versions:
		data = parse_data(version.data)
		changes = []
		for fieldname, old, new in data.get("changed") or []:
			if fieldname in EDITABLE_FIELDS:
				changes.append(
					{"field": fieldname, "label": _(meta.get_label(fieldname)), "old": old, "new": new}
				)
		if data.get("added") or data.get("removed") or data.get("row_changed"):
			changes.append({"field": "courses", "label": _(meta.get_label("courses")), "old": None, "new": None})
		if changes:
			history.append(
				{
					"user": version.owner,
					"full_name": names.get(version.owner) or version.owner,
					"at": version.creation,
					"changes": changes,
				}
			)
	return history


def audit_status(settings) -> dict:
	head_seq, head_hash = os_audit.chain_head()
	return {
		"active": os_audit.is_enabled(settings),
		"events": frappe.db.count(EVENT),
		"open_sessions": frappe.db.count(SESSION, {"closed": 0}),
		"chain_head_seq": head_seq or None,
		"chain_head_hash": head_hash or None,
		"anchor_seq": cint(settings.get("chain_anchor_seq")) or None,
		"last_seal": last_seal(),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(values: str | dict) -> dict:
	"""Save the settings from the page. OS Audit Settings.validate enforces the
	rules (retention mandatory, thresholds) and on_update writes the change event."""
	assert_can_use_os_audit()
	values = frappe.parse_json(values) or {}
	doc = frappe.get_single(SETTINGS)
	for field in EDITABLE_FIELDS:
		if field not in values:
			continue
		value = values[field]
		if field in ("retention_days", "inactivity_minutes"):
			value = cint(value) if value not in (None, "") else None
		elif field == "seal_email":
			value = (value or "").strip() or None
		doc.set(field, value)
	if "courses" in values:
		doc.set("courses", [])
		for row in values.get("courses") or []:
			if not row.get("course"):
				continue
			doc.append(
				"courses",
				{
					"course": row["course"],
					"planned_hours": flt(row.get("planned_hours")),
					"min_attendance_percent": flt(row.get("min_attendance_percent")),
				},
			)
	doc.save(ignore_permissions=True)
	return get_page()


@frappe.whitelist()
def retention_impact(retention_days: int | str) -> dict:
	"""How much data a shorter retention would delete the next night."""
	assert_can_use_os_audit()
	days = cint(retention_days)
	if days <= 0:
		return {"events": 0, "sessions": 0}
	cutoff = get_datetime(add_days(frappe.utils.now_datetime(), -days))
	return {
		"events": frappe.db.count(EVENT, {"timestamp": ["<", cutoff]}),
		"sessions": frappe.db.count(SESSION, {"last_seen_at": ["<", cutoff]}),
	}


# ---------------------------------------------------------------------------
# Log tab: event timeline and the per-student summary
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_log(
	user: str | None = None,
	course: str | None = None,
	event_type: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	start: int | str = 0,
	page_length: int | str = LOG_PAGE_LENGTH,
) -> dict:
	"""The event timeline, newest first, a page at a time."""
	assert_can_use_os_audit()
	length = min(max(cint(page_length) or LOG_PAGE_LENGTH, 1), LOG_MAX_PAGE_LENGTH)
	filters = date_range("timestamp", from_date, to_date)
	if user:
		filters.append(["user", "=", user])
	if course:
		filters.append(["course", "=", course])
	if event_type:
		filters.append(["event_type", "=", event_type])
	rows = frappe.get_all(
		EVENT,
		filters=filters,
		fields=EVENT_FIELDS,
		order_by="seq desc",
		offset=max(cint(start), 0),
		limit=length + 1,
	)
	has_more = len(rows) > length
	return {"events": decorate_events(rows[:length]), "has_more": has_more}


def decorate_events(rows) -> list:
	users = full_names(row.user for row in rows)
	courses = names_of("LMS Course", (row.course for row in rows), "title")
	lessons = names_of("Course Lesson", (row.lesson for row in rows), "title")
	batches = names_of("LMS Batch", (row.batch for row in rows), "title")
	settings_meta = frappe.get_meta(SETTINGS)
	events = []
	for row in rows:
		data = parse_data(row.data)
		# A settings change names the fields it touched: give their translated labels.
		changed_labels = [
			_(settings_meta.get_label(field)) for field in (data.get("changes") or {})
		] if row.event_type == "audit_settings_changed" else []
		events.append(
			{
				"name": row.name,
				"seq": row.seq,
				"event_type": row.event_type,
				"event_label": event_label(row.event_type),
				"timestamp": row.timestamp,
				"user": row.user,
				"full_name": users.get(row.user) or row.user,
				"course": row.course,
				"course_title": courses.get(row.course) or row.course,
				"lesson": row.lesson,
				"lesson_title": lessons.get(row.lesson) or row.lesson,
				"batch": row.batch,
				"batch_title": batches.get(row.batch) or row.batch,
				"reference_doctype": row.reference_doctype,
				"reference_name": row.reference_name,
				"device": row.device,
				"device_label": device_label(row.device),
				"ip_address": row.ip_address,
				"data": data,
				"changed_labels": changed_labels,
				"redacted": cint(row.redacted),
			}
		)
	return events


@frappe.whitelist()
def get_student_summary(
	user: str, course: str | None = None, from_date: str | None = None, to_date: str | None = None
) -> dict:
	"""Time per lesson and per day for one student, with the AI simulations and the
	tutor questions (already logged elsewhere: read here, never duplicated)."""
	assert_can_use_os_audit()
	if not user:
		frappe.throw(_("Choose a student."))
	settings = os_audit.get_settings()
	filters = [["user", "=", user], *date_range("started_at", from_date, to_date)]
	if course:
		filters.append(["course", "=", course])
	sessions = frappe.get_all(
		SESSION,
		filters=filters,
		fields=["course", "lesson", "started_at", "last_seen_at", "presence_seconds", "active_seconds", "video_seconds"],
		order_by="started_at asc",
	)
	courses = names_of("LMS Course", (s.course for s in sessions), "title")
	lessons = names_of("Course Lesson", (s.lesson for s in sessions), "title")

	by_lesson, by_day = {}, {}
	for s in sessions:
		lesson = by_lesson.setdefault(
			(s.course, s.lesson),
			{
				"course": s.course,
				"course_title": courses.get(s.course) or s.course,
				"lesson": s.lesson,
				"lesson_title": lessons.get(s.lesson) or s.lesson,
				"visits": 0,
				"presence_seconds": 0,
				"active_seconds": 0,
				"video_seconds": 0,
				"first_at": s.started_at,
				"last_at": s.last_seen_at,
			},
		)
		day_key = str(getdate(s.started_at))
		day = by_day.setdefault(
			day_key,
			{"date": day_key, "visits": 0, "presence_seconds": 0, "active_seconds": 0, "video_seconds": 0, "first_at": s.started_at, "last_at": s.last_seen_at, "_lessons": set()},
		)
		for bucket in (lesson, day):
			bucket["visits"] += 1
			bucket["presence_seconds"] += cint(s.presence_seconds)
			bucket["active_seconds"] += cint(s.active_seconds)
			bucket["video_seconds"] += cint(s.video_seconds)
			bucket["last_at"] = max(get_datetime(bucket["last_at"]), get_datetime(s.last_seen_at))
		day["_lessons"].add(s.lesson)

	days = []
	for day in sorted(by_day.values(), key=lambda d: d["date"], reverse=True):
		day["lessons"] = len(day.pop("_lessons"))
		days.append(day)

	presence = sum(cint(s.presence_seconds) for s in sessions)
	active = sum(cint(s.active_seconds) for s in sessions)
	video = sum(cint(s.video_seconds) for s in sessions)
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"counted_time": settings.get("counted_time") or "Presence",
		"totals": {
			"visits": len(sessions),
			"presence_seconds": presence,
			"active_seconds": active,
			"video_seconds": video,
			"counted_seconds": counted_seconds(presence, active, settings),
		},
		"lessons": sorted(by_lesson.values(), key=lambda row: (row["course_title"] or "", get_datetime(row["first_at"]))),
		"days": days,
		"simulations": student_simulations(user, course, from_date, to_date),
		"tutor_questions": student_tutor_questions(user, course, from_date, to_date),
	}


def student_simulations(user: str, course=None, from_date=None, to_date=None) -> list:
	filters = [["student", "=", user], *date_range("started_at", from_date, to_date)]
	if course:
		filters.append(["course", "=", course])
	rows = frappe.get_all(
		"LMSA Simulation Session",
		filters=filters,
		fields=["name", "scenario", "course", "modality", "status", "started_at", "ended_at", "session_seconds"],
		order_by="started_at desc",
		limit=200,
	)
	scenarios = names_of("LMSA Simulation Scenario", (r.scenario for r in rows), "scenario_name")
	courses = names_of("LMS Course", (r.course for r in rows), "title")
	for row in rows:
		row["scenario_title"] = scenarios.get(row.scenario) or row.scenario
		row["course_title"] = courses.get(row.course) or row.course
	return rows


def student_tutor_questions(user: str, course=None, from_date=None, to_date=None) -> list:
	"""When the student asked the AI tutor, and where. The question text stays in the
	tutor log: the audit only needs the activity."""
	filters = [["member", "=", user], *date_range("creation", from_date, to_date)]
	if course:
		filters.append(["course", "=", course])
	rows = frappe.get_all(
		"LMSA Query Log",
		filters=filters,
		fields=["creation", "course", "lesson", "status"],
		order_by="creation desc",
		limit=200,
	)
	courses = names_of("LMS Course", (r.course for r in rows), "title")
	lessons = names_of("Course Lesson", (r.lesson for r in rows), "title")
	for row in rows:
		row["course_title"] = courses.get(row.course) or row.course
		row["lesson_title"] = lessons.get(row.lesson) or row.lesson
	return rows


# ---------------------------------------------------------------------------
# Attendance tab
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_attendance(course: str, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Per student of a course: time spent against the planned hours, and the live
	classes of the classes that contain the course."""
	assert_can_use_os_audit()
	if not course:
		frappe.throw(_("Choose a course."))
	return {
		**course_attendance(course, from_date, to_date),
		"live_classes": live_attendance(course, from_date, to_date),
	}


def course_attendance(course: str, from_date=None, to_date=None) -> dict:
	settings = os_audit.get_settings()
	planned_hours, min_percent = course_rules(course, settings)
	conditions, values = ["course = %(course)s"], {"course": course}
	if from_date:
		conditions.append("started_at >= %(from)s")
		values["from"] = get_datetime(getdate(from_date))
	if to_date:
		conditions.append("started_at < %(to)s")
		values["to"] = get_datetime(add_days(getdate(to_date), 1))
	totals = frappe.db.sql(
		f"""SELECT user, COUNT(*) AS visits, SUM(presence_seconds) AS presence_seconds,
			SUM(active_seconds) AS active_seconds, MIN(started_at) AS first_at, MAX(last_seen_at) AS last_at
		FROM `tab{SESSION}` WHERE {" AND ".join(conditions)} GROUP BY user""",
		values,
		as_dict=True,
	)
	by_user = {row.user: row for row in totals}
	# Mentors and staff enrolled in the course are not students.
	enrolled = [
		row.member
		for row in frappe.get_all("LMS Enrollment", filters={"course": course}, fields=["member", "member_type"])
		if row.member_type not in ("Mentor", "Staff")
	]
	users = list(dict.fromkeys([*enrolled, *by_user]))
	names = full_names(users)
	students = []
	for user in users:
		row = by_user.get(user) or {}
		presence, active = cint(row.get("presence_seconds")), cint(row.get("active_seconds"))
		counted = counted_seconds(presence, active, settings)
		percent = attendance_percent(counted, planned_hours)
		students.append(
			{
				"user": user,
				"full_name": names.get(user) or user,
				"enrolled": user in enrolled,
				"visits": cint(row.get("visits")),
				"presence_seconds": presence,
				"active_seconds": active,
				"counted_seconds": counted,
				"percent": percent,
				"below_threshold": bool(min_percent and percent is not None and percent < min_percent),
				"first_at": row.get("first_at"),
				"last_at": row.get("last_at"),
			}
		)
	students.sort(key=lambda s: (s["full_name"] or "").lower())
	return {
		"course": course,
		"course_title": frappe.db.get_value("LMS Course", course, "title") or course,
		"in_scope": os_audit.course_in_scope(course, settings),
		"planned_hours": planned_hours,
		"min_attendance_percent": min_percent,
		"counted_time": settings.get("counted_time") or "Presence",
		"students": students,
	}


def live_attendance(course: str, from_date=None, to_date=None) -> list:
	"""Live classes of the classes containing the course: who joined from the
	platform (audit events) and, where the provider reported it, entry and exit
	(LMS Live Class Participant). Provider attendance arrives with phase 4."""
	batches = frappe.get_all("Batch Course", filters={"course": course, "parenttype": "LMS Batch"}, pluck="parent")
	if not batches:
		return []
	filters = [["batch_name", "in", list(set(batches))]]
	if from_date:
		filters.append(["date", ">=", getdate(from_date)])
	if to_date:
		filters.append(["date", "<=", getdate(to_date)])
	classes = frappe.get_all(
		"LMS Live Class",
		filters=filters,
		fields=["name", "title", "date", "time", "duration", "host", "batch_name", "conferencing_provider"],
		order_by="date desc, time desc",
		limit=500,
	)
	if not classes:
		return []
	names = [c.name for c in classes]
	joins = frappe.get_all(
		EVENT,
		filters={"event_type": "live_class_join", "reference_name": ["in", names], "redacted": 0},
		fields=["reference_name", "user", "timestamp"],
		order_by="timestamp asc",
	)
	participants = frappe.get_all(
		"LMS Live Class Participant",
		filters={"live_class": ["in", names]},
		fields=["live_class", "member", "member_name", "joined_at", "left_at", "duration"],
		order_by="joined_at asc",
	)
	people = full_names({j.user for j in joins} | {p.member for p in participants} | {c.host for c in classes})
	batch_titles = names_of("LMS Batch", (c.batch_name for c in classes), "title")
	result = []
	for live in classes:
		first_join = {}
		for join in joins:
			if join.reference_name == live.name and join.user not in first_join:
				first_join[join.user] = join.timestamp
		rows = []
		for p in participants:
			if p.live_class != live.name:
				continue
			rows.append(
				{
					"user": p.member,
					"full_name": people.get(p.member) or p.member_name or p.member,
					"is_host": bool(p.member and p.member == live.host),
					"joined_from_platform": first_join.get(p.member),
					"joined_at": p.joined_at,
					"left_at": p.left_at,
					"duration_seconds": cint(p.duration),
				}
			)
		reported = {row["user"] for row in rows}
		for user, joined in first_join.items():
			if user in reported:
				continue
			rows.append(
				{
					"user": user,
					"full_name": people.get(user) or user,
					"is_host": user == live.host,
					"joined_from_platform": joined,
					"joined_at": None,
					"left_at": None,
					"duration_seconds": None,
				}
			)
		rows.sort(key=lambda r: (not r["is_host"], (r["full_name"] or "").lower()))
		result.append(
			{
				"name": live.name,
				"title": live.title,
				"date": live.date,
				"time": live.time,
				"duration": cint(live.duration),
				"host": live.host,
				"host_name": people.get(live.host) or live.host,
				"batch": live.batch_name,
				"batch_title": batch_titles.get(live.batch_name) or live.batch_name,
				"provider": live.conferencing_provider,
				"provider_reported": any(row["joined_at"] for row in rows),
				"participants": rows,
			}
		)
	return result


# ---------------------------------------------------------------------------
# Integrity tab
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_seals(limit: int | str = SEAL_LIMIT) -> list:
	"""The latest daily seals, newest first."""
	assert_can_use_os_audit()
	rows = frappe.get_all(
		EVENT,
		filters={"event_type": "daily_seal"},
		fields=["seq", "timestamp", "data"],
		order_by="seq desc",
		limit=min(max(cint(limit) or SEAL_LIMIT, 1), 365),
	)
	seals = []
	for row in rows:
		data = parse_data(row.data)
		seals.append(
			{
				"seq": row.seq,
				"sealed_at": row.timestamp,
				"date": data.get("date"),
				"events": data.get("events"),
				"last_seq": data.get("last_seq"),
				"last_hash": data.get("last_hash"),
			}
		)
	return seals
