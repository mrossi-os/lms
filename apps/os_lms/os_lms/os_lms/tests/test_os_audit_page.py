"""OS Audit phase 2: the page endpoints and the exports (docs/audit-studenti/PIANO.md §7-8).

Same rules as test_os_audit: everything inside the test transaction, rolled back.
The export job commits and writes a file, so its commit and file save are patched.
"""

import csv
import hashlib
import io
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from os_lms.os_lms import os_audit, os_audit_export, os_audit_page
from os_lms.os_lms.api import list_student_stats_exports
from os_lms.os_lms.tests.test_os_audit import (
	BUNDLES,
	COURSE,
	LESSON,
	OTHER_COURSE,
	OTHER_STUDENT,
	STUDENT,
	T0,
	P,
	OsAuditTestCase,
	configure,
	enroll,
	insert,
	make_user,
)

MENTOR = f"{P}mentor@example.com"
BATCH = f"{P}batch"
LIVE = f"{P}live"
HOST = f"{P}host@example.com"


def add_session(user, start, presence, active, course=COURSE, lesson=LESSON, closed=1):
	doc = frappe.get_doc(
		{
			"doctype": os_audit.SESSION,
			"user": user,
			"course": course,
			"lesson": lesson,
			"started_at": start,
			"last_seen_at": start + timedelta(seconds=presence),
			"presence_seconds": presence,
			"active_seconds": active,
			"closed": closed,
		}
	)
	doc.name = frappe.generate_hash(length=10)
	doc.db_insert()
	return doc.name


def set_course_rules(planned_hours=0, min_percent=0, **values):
	configure(**values)
	doc = frappe.get_single(os_audit.SETTINGS)
	for row in doc.courses:
		if row.course == COURSE:
			row.planned_hours = planned_hours
			row.min_attendance_percent = min_percent
	doc.save(ignore_permissions=True)
	frappe.clear_document_cache(os_audit.SETTINGS, os_audit.SETTINGS)
	os_audit.flush(commit=False)


class TestPageAccess(OsAuditTestCase):
	"""Only System Manager and Gestore, with the real role bundles (PIANO §8)."""

	ENDPOINTS = (
		(os_audit_page.get_page, {}),
		(os_audit_page.get_log, {}),
		(os_audit_page.get_attendance, {"course": COURSE}),
		(os_audit_page.get_student_summary, {"user": STUDENT}),
		(os_audit_page.get_seals, {}),
		(os_audit_page.retention_impact, {"retention_days": 10}),
		(os_audit_page.save_settings, {"values": {}}),
		(os_audit_export.list_audit_exports, {}),
		(os_audit_export.start_audit_export, {"report": "os_audit_events"}),
		(os_audit_export.delete_audit_export, {"name": "nope"}),
	)

	def setUp(self):
		super().setUp()
		configure()

	def _bundle_user(self, bundle):
		email = f"{P}{bundle}@example.com"
		make_user(email, BUNDLES[bundle])
		return email

	def test_gestore_and_system_manager_may_use_the_page(self):
		for bundle in ("gestore", "system_manager"):
			frappe.set_user(self._bundle_user(bundle))
			self.assertIn("settings", os_audit_page.get_page())
			self.assertTrue(os_audit.can_use_os_audit())

	def test_docente_valutatore_moderator_and_students_are_refused(self):
		users = [self._bundle_user(b) for b in ("docente", "valutatore", "moderator")] + [STUDENT]
		for user in users:
			frappe.set_user(user)
			for endpoint, kwargs in self.ENDPOINTS:
				with self.subTest(user=user, endpoint=endpoint.__name__):
					with self.assertRaises(frappe.PermissionError):
						endpoint(**kwargs)


class TestPageSettings(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def test_the_page_saves_settings_and_courses(self):
		page = os_audit_page.save_settings(
			{
				"inactivity_minutes": "5",
				"seal_email": "  ",
				"courses": [
					{"course": COURSE, "planned_hours": "12.5", "min_attendance_percent": 70},
					{"course": ""},
				],
			}
		)
		os_audit.flush(commit=False)
		settings = page["settings"]
		self.assertEqual(settings["inactivity_minutes"], 5)
		self.assertIsNone(settings["seal_email"])
		self.assertEqual(
			[(c["course"], c["planned_hours"], c["min_attendance_percent"]) for c in settings["courses"]],
			[(COURSE, 12.5, 70.0)],
		)
		change = frappe.get_all(
			os_audit.EVENT, filters={"event_type": "audit_settings_changed"}, pluck="data", order_by="seq desc"
		)[0]
		self.assertIn('"inactivity_minutes":[3,5]', change)
		logged = os_audit_page.get_log(event_type="audit_settings_changed")["events"][0]
		label = frappe.get_meta(os_audit.SETTINGS).get_label("inactivity_minutes")
		self.assertIn(label, logged["changed_labels"])
		self.assertNotIn("inactivity_minutes", logged["changed_labels"])

	def test_the_page_cannot_enable_the_audit_without_retention(self):
		with self.assertRaises(frappe.ValidationError):
			os_audit_page.save_settings({"retention_days": ""})

	def test_retention_impact_counts_what_the_night_would_delete(self):
		now = frappe.utils.now_datetime()
		add_session(STUDENT, now - timedelta(days=40), 60, 30)
		add_session(STUDENT, now - timedelta(days=5), 60, 30)
		os_audit.record("login", user=STUDENT)
		os_audit.flush(commit=False)
		frappe.db.sql(
			f"UPDATE `tab{os_audit.EVENT}` SET timestamp = %s WHERE event_type = 'login'",
			(now - timedelta(days=40),),
		)
		self.assertEqual(os_audit_page.retention_impact(30), {"events": 1, "sessions": 1})
		self.assertEqual(os_audit_page.retention_impact(0), {"events": 0, "sessions": 0})

	def test_page_payload_carries_status_and_translated_event_types(self):
		page = os_audit_page.get_page()
		self.assertTrue(page["status"]["active"])
		types = {row["value"]: row["label"] for row in page["event_types"]}
		self.assertEqual(types["session_closed"], "Lesson visit closed")
		self.assertEqual(set(types), set(os_audit_page.EVENT_LABELS))


class TestLogAndSummary(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def test_the_log_filters_and_pages(self):
		for _ in range(3):
			os_audit.record("login", user=STUDENT)
		os_audit.record("login", user=OTHER_STUDENT)
		os_audit.flush(commit=False)
		first = os_audit_page.get_log(user=STUDENT, page_length=2)
		self.assertEqual(len(first["events"]), 2)
		self.assertTrue(first["has_more"])
		rest = os_audit_page.get_log(user=STUDENT, start=2, page_length=2)
		self.assertEqual(len(rest["events"]), 1)
		self.assertFalse(rest["has_more"])
		self.assertEqual(rest["events"][0]["event_label"], "Logged in")
		self.assertEqual(
			len(os_audit_page.get_log(event_type="login", from_date=str(T0.date() + timedelta(days=9999)))["events"]),
			0,
		)

	def test_an_erased_event_is_shown_as_erased(self):
		os_audit.record("course_view", user=STUDENT, course=COURSE)
		os_audit.flush(commit=False)
		os_audit.erase_course_member(COURSE, STUDENT)
		os_audit.flush(commit=False)
		erased = [e for e in os_audit_page.get_log()["events"] if e["redacted"]]
		self.assertEqual(len(erased), 1)
		self.assertIsNone(erased[0]["user"])

	def test_the_summary_groups_time_per_lesson_and_per_day(self):
		add_session(STUDENT, T0, 600, 300)
		add_session(STUDENT, T0 + timedelta(hours=1), 120, 60)
		add_session(STUDENT, T0 + timedelta(days=1), 60, 60, course=OTHER_COURSE)
		add_session(OTHER_STUDENT, T0, 999, 999)
		summary = os_audit_page.get_student_summary(STUDENT)
		self.assertEqual(summary["totals"]["visits"], 3)
		self.assertEqual(summary["totals"]["presence_seconds"], 780)
		self.assertEqual(summary["totals"]["counted_seconds"], 780)
		by_course = {row["course"]: row for row in summary["lessons"]}
		self.assertEqual((by_course[COURSE]["visits"], by_course[COURSE]["active_seconds"]), (2, 360))
		self.assertEqual([d["date"] for d in summary["days"]], [str(T0.date() + timedelta(days=1)), str(T0.date())])
		self.assertEqual(summary["days"][1]["presence_seconds"], 720)

		only_course = os_audit_page.get_student_summary(STUDENT, course=COURSE, to_date=str(T0.date()))
		self.assertEqual(only_course["totals"]["visits"], 2)


class TestAttendance(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		make_user(MENTOR)
		insert({"doctype": "LMS Enrollment", "name": f"{P}mentor-enrollment", "course": COURSE, "member": MENTOR, "member_type": "Mentor"})
		set_course_rules(planned_hours=1, min_percent=50)

	def test_percent_of_the_planned_hours_and_the_threshold(self):
		add_session(STUDENT, T0, 1800, 600)  # 50% presence
		add_session(OTHER_STUDENT, T0, 900, 900)  # 25% presence
		data = os_audit_page.get_attendance(COURSE)
		by_user = {s["user"]: s for s in data["students"]}
		self.assertNotIn(MENTOR, by_user)
		self.assertEqual((by_user[STUDENT]["percent"], by_user[STUDENT]["below_threshold"]), (50.0, False))
		self.assertEqual((by_user[OTHER_STUDENT]["percent"], by_user[OTHER_STUDENT]["below_threshold"]), (25.0, True))

	def test_active_time_counts_when_the_settings_say_so(self):
		set_course_rules(planned_hours=1, min_percent=50, counted_time="Active Time")
		add_session(STUDENT, T0, 1800, 600)
		student = next(s for s in os_audit_page.get_attendance(COURSE)["students"] if s["user"] == STUDENT)
		self.assertEqual(student["counted_seconds"], 600)
		self.assertTrue(student["below_threshold"])

	def test_a_student_with_time_but_no_longer_enrolled_still_shows(self):
		left = f"{P}left@example.com"
		make_user(left)
		add_session(left, T0, 60, 60)
		student = next(s for s in os_audit_page.get_attendance(COURSE)["students"] if s["user"] == left)
		self.assertFalse(student["enrolled"])
		self.assertEqual(student["visits"], 1)

	def test_live_classes_bring_platform_joins_and_provider_attendance(self):
		make_user(HOST, ("Docente",))
		insert({"doctype": "LMS Batch", "name": BATCH, "title": BATCH, "start_date": T0.date(), "end_date": T0.date()})
		row = frappe.get_doc({"doctype": "Batch Course", "parent": BATCH, "parenttype": "LMS Batch", "parentfield": "courses", "course": COURSE})
		row.set_new_name()
		row.db_insert()
		insert({"doctype": "LMS Live Class", "name": LIVE, "title": "Live", "batch_name": BATCH, "host": HOST, "date": T0.date(), "time": "10:00:00", "duration": 60, "conferencing_provider": "Zoom"})
		participant = frappe.get_doc({"doctype": "LMS Live Class Participant", "live_class": LIVE, "member": HOST, "joined_at": T0, "left_at": T0 + timedelta(minutes=55), "duration": 3300})
		participant.name = f"{P}participant"
		participant.db_insert()
		os_audit.record("live_class_join", user=STUDENT, batch=BATCH, reference_doctype="LMS Live Class", reference_name=LIVE)
		os_audit.flush(commit=False)

		live = os_audit_page.get_attendance(COURSE)["live_classes"]
		self.assertEqual([l["name"] for l in live], [LIVE])
		people = {p["user"]: p for p in live[0]["participants"]}
		self.assertTrue(people[HOST]["is_host"])
		self.assertEqual(people[HOST]["duration_seconds"], 3300)
		self.assertIsNotNone(people[STUDENT]["joined_from_platform"])
		self.assertIsNone(people[STUDENT]["joined_at"])

		rows, count = os_audit_export.build_rows("os_audit_live", {"course": COURSE})
		self.assertEqual(count, 2)
		self.assertEqual(rows[1][5], "Teacher")
		self.assertEqual(rows[1][-1], "0:55")


class TestExports(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		set_course_rules(planned_hours=1, min_percent=50)

	def test_register_rows_list_each_visit_then_the_total(self):
		add_session(STUDENT, T0, 1800, 600)
		add_session(STUDENT, T0 + timedelta(hours=2), 900, 900)
		rows, count = os_audit_export.build_rows("os_audit_register", {"course": COURSE})
		header = rows.index(next(r for r in rows if r and r[0] == "Student"))
		body = [r for r in rows[header + 1 :] if r and r[1] == STUDENT]
		self.assertEqual([r[2] for r in body][-1], "Total")
		self.assertEqual(body[0][3:5], ["10:00", "10:30"])
		self.assertEqual(body[-1][6:], ["0:45", "0:25", 75.0])
		# Two visits + one total per student of the course (STUDENT, OTHER_STUDENT).
		self.assertEqual(count, 2 + 2)

	def test_every_file_ends_with_the_seal_and_the_chain_head(self):
		os_audit.record("daily_seal", user="Administrator", data={"date": "2026-11-10", "events": 3, "last_seq": 9, "last_hash": "abc"})
		os_audit.flush(commit=False)
		rows, _count = os_audit_export.build_rows("os_audit_events", {"to_date": "2026-11-10"})
		footer = rows[-3:]
		self.assertEqual(footer[1][1:], ["2026-11-10", "abc"])
		head_seq, head_hash = os_audit.chain_head()
		self.assertEqual(footer[2][1:], [head_seq, head_hash])

	def test_an_export_needs_a_course_when_the_report_does(self):
		with self.assertRaises(frappe.ValidationError):
			os_audit_export.start_audit_export("os_audit_register")
		with self.assertRaises(frappe.ValidationError):
			os_audit_export.start_audit_export("os_audit_events", from_date="2026-11-12", to_date="2026-11-01")

	def test_the_job_attaches_the_file_and_records_the_export_with_its_fingerprint(self):
		add_session(STUDENT, T0, 600, 300)
		with patch.object(frappe, "enqueue"):
			name = os_audit_export.start_audit_export("os_audit_sessions", file_format="csv", course=COURSE)["name"]
		saved = {}

		def fake_save_file(filename, content, *args, **kwargs):
			saved["content"] = content
			return SimpleNamespace(file_url=f"/private/files/{filename}")

		with patch.object(frappe.db, "commit"), patch("frappe.utils.file_manager.save_file", fake_save_file):
			os_audit_export.run_audit_export(name)
		os_audit.flush(commit=False)

		export = frappe.db.get_value("Student Stats Export", name, ["status", "row_count", "file"], as_dict=True)
		self.assertEqual((export.status, export.row_count), ("Ready", 1))
		lines = list(csv.reader(io.StringIO(saved["content"].decode("utf-8"))))
		self.assertEqual(lines[1][2], COURSE)

		event = frappe.get_all(os_audit.EVENT, filters={"event_type": "audit_export"}, fields=["user", "course", "data"])[0]
		self.assertEqual((event.user, event.course), ("Administrator", COURSE))
		self.assertIn(hashlib.sha256(saved["content"]).hexdigest(), event.data)

		# The statistics page does not list audit exports, the audit page lists only them.
		self.assertNotIn(name, [row.name for row in list_student_stats_exports()])
		self.assertIn(name, [row.name for row in os_audit_export.list_audit_exports()])
