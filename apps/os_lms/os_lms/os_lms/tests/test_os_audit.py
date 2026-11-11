"""OS Audit phase 1 (docs/audit-studenti/PIANO.md §10).

Everything runs inside the test transaction and is rolled back: records are written
with db_insert (User.insert would commit), the chain is flushed with commit=False,
and the cached settings are dropped afterwards so the dev site never keeps them.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import os_audit

P = "os-audit-test-"
COURSE = f"{P}course"
OTHER_COURSE = f"{P}other-course"
LESSON = f"{P}lesson"
STUDENT = f"{P}student@example.com"
OTHER_STUDENT = f"{P}other@example.com"
T0 = datetime(2026, 11, 11, 10, 0, 0)

# Real platform bundles (memory: test_with_platform_role_bundles).
BUNDLES = {
	"gestore": ("Gestore", "Moderator", "Docente", "Course Creator", "Batch Evaluator"),
	"docente": ("Docente", "Batch Evaluator"),
	"valutatore": ("Valutatore",),
	"moderator": ("Moderator",),
	"system_manager": ("System Manager",),
}


def insert(values: dict) -> None:
	frappe.get_doc(values).db_insert()


def make_user(email: str, roles=("LMS Student",)) -> None:
	insert(
		{
			"doctype": "User",
			"name": email,
			"email": email,
			"first_name": "Audit",
			"user_type": "Website User",
			"enabled": 1,
		}
	)
	for role in roles:
		row = frappe.get_doc(
			{"doctype": "Has Role", "parent": email, "parenttype": "User", "parentfield": "roles", "role": role}
		)
		row.set_new_name()
		row.db_insert()


def enroll(member: str, course: str) -> None:
	insert({"doctype": "LMS Enrollment", "name": f"{P}{member}-{course}", "course": course, "member": member})


@contextmanager
def at(moment: datetime):
	with patch.object(os_audit, "now_datetime", return_value=moment):
		yield


def configure(**values) -> None:
	"""Save the settings through the doctype, so validate and on_update run."""
	doc = frappe.get_single(os_audit.SETTINGS)
	defaults = {
		"enabled": 1,
		"retention_days": 365,
		"scope": "Selected Courses",
		"inactivity_minutes": 3,
		"store_ip": "Not Stored",
		"on_account_deletion": "Delete Audit Data",
		**{field: 1 for field in os_audit.TOGGLE_DEFAULTS},
	}
	courses = values.pop("courses", [COURSE])
	defaults.update(values)
	doc.update(defaults)
	doc.set("courses", [{"course": course} for course in courses])
	doc.save(ignore_permissions=True)
	frappe.clear_document_cache(os_audit.SETTINGS, os_audit.SETTINGS)
	os_audit.flush(commit=False)


def events(event_type=None, **filters):
	"""The events of the test; the settings changes only when asked for."""
	filters["event_type"] = event_type or ["!=", "audit_settings_changed"]
	return frappe.get_all(os_audit.EVENT, filters=filters, fields=["*"], order_by="seq asc")


class OsAuditTestCase(UnitTestCase):
	def setUp(self):
		# addCleanup, not only tearDown: tearDown is skipped when setUp fails, and the
		# next module's commit would then keep this test's rows (it happened once).
		self.addCleanup(self._undo)
		frappe.set_user("Administrator")
		# Start every test from an empty chain inside the transaction.
		frappe.db.sql(f"DELETE FROM `tab{os_audit.EVENT}`")
		frappe.db.sql(f"DELETE FROM `tab{os_audit.SESSION}`")
		frappe.db.set_single_value(os_audit.SETTINGS, {"chain_anchor_seq": 0, "chain_anchor_hash": None})
		for course in (COURSE, OTHER_COURSE):
			insert({"doctype": "LMS Course", "name": course, "title": course})
		make_user(STUDENT)
		make_user(OTHER_STUDENT)
		enroll(STUDENT, COURSE)
		enroll(STUDENT, OTHER_COURSE)
		enroll(OTHER_STUDENT, COURSE)
		os_audit._discard_pending()

	def _undo(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		os_audit._discard_pending()
		frappe.clear_document_cache(os_audit.SETTINGS, os_audit.SETTINGS)

	def open_as(self, user: str, moment: datetime = T0, course: str = COURSE) -> str:
		frappe.set_user(user)
		with at(moment):
			answer = os_audit.on_lesson_open(course, LESSON)
		self.assertTrue(answer, "the lesson should be tracked")
		return answer["session"]

	def beat(self, session: str, moment: datetime, active=True, close=False) -> dict:
		with at(moment):
			return os_audit.heartbeat(session, active=active, close=close)

	def session(self, name: str):
		return frappe.db.get_value(os_audit.SESSION, name, ["*"], as_dict=True)


class TestSettings(OsAuditTestCase):
	def test_enabling_without_retention_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			configure(retention_days=0)

	def test_the_recorder_writes_nothing_without_retention(self):
		# Even if the value is wiped behind the doctype's back (D9).
		configure()
		frappe.db.set_single_value(os_audit.SETTINGS, "retention_days", 0)
		frappe.clear_document_cache(os_audit.SETTINGS, os_audit.SETTINGS)
		frappe.set_user(STUDENT)
		self.assertIsNone(os_audit.on_lesson_open(COURSE, LESSON))
		self.assertFalse(os_audit.record("login", user=STUDENT))
		os_audit.flush(commit=False)
		self.assertFalse(events())

	def test_audit_off_collects_nothing(self):
		configure(enabled=0)
		frappe.set_user(STUDENT)
		self.assertIsNone(os_audit.on_lesson_open(COURSE, LESSON))
		os_audit.on_course_view(COURSE)
		os_audit.flush(commit=False)
		self.assertFalse(events())
		self.assertFalse(frappe.get_all(os_audit.SESSION))

	def test_only_courses_in_scope_and_enrolled_students(self):
		configure()
		frappe.set_user(STUDENT)
		self.assertIsNone(os_audit.on_lesson_open(OTHER_COURSE, LESSON))
		frappe.set_user("Administrator")
		os_audit.on_course_view(COURSE)  # not enrolled
		frappe.set_user(STUDENT)
		os_audit.on_course_view(COURSE)
		os_audit.flush(commit=False)
		self.assertEqual([(e.event_type, e.user) for e in events()], [("course_view", STUDENT)])

		configure(scope="All Courses", courses=[])
		self.assertTrue(os_audit.on_lesson_open(OTHER_COURSE, LESSON))

	def test_a_toggle_turns_its_events_off(self):
		configure(track_course_lesson=0, track_lesson_time=0)
		frappe.set_user(STUDENT)
		self.assertIsNone(os_audit.on_lesson_open(COURSE, LESSON))
		os_audit.flush(commit=False)
		self.assertFalse(events("lesson_open"))

	def test_a_settings_change_is_an_event_with_who_and_what(self):
		configure()
		configure(inactivity_minutes=5)
		change = events("audit_settings_changed")[-1]
		self.assertEqual(change.user, "Administrator")
		self.assertIn('"inactivity_minutes":[3,5]', change.data)


class TestLessonTime(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def test_lesson_open_creates_a_session_and_an_event(self):
		session = self.open_as(STUDENT)
		os_audit.flush(commit=False)
		opened = events("lesson_open")
		self.assertEqual(len(opened), 1)
		self.assertEqual(opened[0].session, session)

	def test_credit_rules(self):
		session = self.open_as(STUDENT)
		# Under 20 s after the previous signal: ignored.
		self.beat(session, T0 + timedelta(seconds=10))
		self.assertEqual(self.session(session).presence_seconds, 0)
		# Active at 30 s: both measures.
		self.beat(session, T0 + timedelta(seconds=30), active=True)
		# Present at 70 s (gap 40 ≤ 45): presence only, in full.
		self.beat(session, T0 + timedelta(seconds=70), active=False)
		# Gap of 100 s: at most 30 s.
		self.beat(session, T0 + timedelta(seconds=170), active=True)
		row = self.session(session)
		self.assertEqual(row.presence_seconds, 30 + 40 + 30)
		self.assertEqual(row.active_seconds, 30 + 30)

	def test_a_long_pause_closes_the_session_and_opens_a_new_one(self):
		session = self.open_as(STUDENT)
		self.beat(session, T0 + timedelta(seconds=30))
		# Threshold 3 min + 2 min grace: 6 min later is a new visit.
		answer = self.beat(session, T0 + timedelta(minutes=6, seconds=30))
		self.assertNotEqual(answer["session"], session)
		self.assertTrue(self.session(session).closed)
		os_audit.flush(commit=False)
		closed = events("session_closed", session=session)
		self.assertEqual(len(closed), 1)
		self.assertIn('"presence_seconds":30', closed[0].data)

	def test_two_tabs_never_count_twice(self):
		tab_a = self.open_as(STUDENT)
		tab_b = self.open_as(STUDENT, T0 + timedelta(seconds=15))
		# Both tabs beat every 30 s, 15 s apart, for two minutes.
		for step in range(1, 5):
			self.beat(tab_a, T0 + timedelta(seconds=30 * step))
			self.beat(tab_b, T0 + timedelta(seconds=15 + 30 * step))
		total = self.session(tab_a).presence_seconds + self.session(tab_b).presence_seconds
		# Wall time from the first open to the last heartbeat (135 s), never 2x.
		self.assertEqual(total, 135)
		self.assertGreater(self.session(tab_a).presence_seconds, 0)
		self.assertGreater(self.session(tab_b).presence_seconds, 0)

	def test_a_session_of_another_user_is_refused(self):
		session = self.open_as(STUDENT)
		frappe.set_user(OTHER_STUDENT)
		with self.assertRaises(frappe.PermissionError):
			self.beat(session, T0 + timedelta(seconds=30))

	def test_closing_writes_the_totals(self):
		session = self.open_as(STUDENT)
		self.beat(session, T0 + timedelta(seconds=30))
		self.assertEqual(self.beat(session, T0 + timedelta(seconds=40), close=True), {"stop": 1})
		os_audit.flush(commit=False)
		closed = events("session_closed")
		self.assertEqual(len(closed), 1)
		self.assertIn('"presence_seconds":40', closed[0].data)
		self.assertIn('"reason":"page_closed"', closed[0].data)

	def test_the_job_closes_silent_sessions(self):
		session = self.open_as(STUDENT)
		with at(T0 + timedelta(minutes=10)):
			self.assertEqual(os_audit.close_stale_sessions(), 1)
		self.assertTrue(self.session(session).closed)

	def test_audit_turned_off_stops_the_page(self):
		session = self.open_as(STUDENT)
		frappe.set_user("Administrator")
		configure(enabled=0)
		frappe.set_user(STUDENT)
		self.assertEqual(self.beat(session, T0 + timedelta(seconds=30)), {"stop": 1})
		self.assertTrue(self.session(session).closed)


class TestChain(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def _three_events(self):
		for user in (STUDENT, OTHER_STUDENT, STUDENT):
			os_audit.record("login", user=user)
		os_audit.flush(commit=False)
		return events("login")

	def test_an_intact_chain_verifies(self):
		self._three_events()
		result = os_audit.verify()
		self.assertTrue(result["ok"], result)
		self.assertEqual(result["checked"], frappe.db.count(os_audit.EVENT))

	def test_an_altered_event_is_found(self):
		rows = self._three_events()
		frappe.db.sql(
			f"UPDATE `tab{os_audit.EVENT}` SET user = %s WHERE name = %s", ("someone@else.it", rows[1].name)
		)
		result = os_audit.verify()
		self.assertFalse(result["ok"])
		self.assertEqual((result["reason"], result["seq"]), ("altered", rows[1].seq))

	def test_a_deleted_event_is_found(self):
		rows = self._three_events()
		frappe.db.sql(f"DELETE FROM `tab{os_audit.EVENT}` WHERE name = %s", (rows[1].name,))
		result = os_audit.verify()
		self.assertFalse(result["ok"])
		self.assertEqual(result["reason"], "missing")
		self.assertEqual(result["expected_seq"], rows[1].seq)

	def test_a_fake_erasure_is_found(self):
		rows = self._three_events()
		frappe.db.sql(
			f"UPDATE `tab{os_audit.EVENT}` SET redacted = 1, salt = NULL WHERE name = %s", (rows[1].name,)
		)
		self.assertEqual(os_audit.verify()["reason"], "altered")

	def test_events_of_a_rolled_back_action_are_dropped(self):
		os_audit.record("login", user=STUDENT)
		frappe.db.rollback()
		os_audit.flush(commit=False)
		self.assertFalse(events("login"))

	def test_events_and_sessions_cannot_be_edited_or_deleted(self):
		row = self._three_events()[0]
		doc = frappe.get_doc(os_audit.EVENT, row.name)
		doc.user = "x@y.it"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(os_audit.EVENT, row.name, ignore_permissions=True)
		for role in ("System Manager", "Gestore"):
			for ptype in ("write", "create", "delete"):
				self.assertFalse(
					frappe.permissions.has_permission(os_audit.EVENT, ptype, user=self._user_with(role)),
					f"{role} must not {ptype} audit events",
				)

	def _user_with(self, role):
		email = f"{P}{role.lower().replace(' ', '-')}@example.com"
		if not frappe.db.exists("User", email):
			make_user(email, (role,))
		return email

	def test_a_get_request_is_made_to_commit(self):
		with patch.object(frappe.local, "request", SimpleNamespace(method="GET"), create=True):
			frappe.local.flags.commit = False
			os_audit.record("login", user=STUDENT)
			self.assertTrue(frappe.local.flags.commit)
		frappe.local.flags.commit = False


class TestSealAndRetention(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure(retention_days=30)

	def test_daily_seal_counts_the_day_once(self):
		yesterday = datetime.combine(frappe.utils.add_days(frappe.utils.getdate(), -1), datetime.min.time())
		with at(yesterday + timedelta(hours=9)):
			os_audit.record("login", user=STUDENT)
			os_audit.record("logout", user=STUDENT)
		os_audit.flush(commit=False)
		os_audit.daily_seal()
		os_audit.flush(commit=False)
		os_audit.daily_seal()
		os_audit.flush(commit=False)
		seals = events("daily_seal")
		self.assertEqual(len(seals), 1)
		self.assertIn('"events":2', seals[0].data)
		self.assertTrue(os_audit.verify()["ok"])

	def test_retention_deletes_the_old_prefix_and_the_chain_still_verifies(self):
		now = frappe.utils.now_datetime()
		# Retention removes a prefix of the chain: start from a chain in time order.
		frappe.db.sql(f"DELETE FROM `tab{os_audit.EVENT}`")
		with at(now - timedelta(days=40)):
			os_audit.record("login", user=STUDENT)
			os_audit.record("logout", user=STUDENT)
		with at(now - timedelta(days=1)):
			os_audit.record("login", user=OTHER_STUDENT)
		os_audit.flush(commit=False)
		before = len(events())
		with at(now):
			result = os_audit.apply_retention()
		self.assertEqual(result["events"], 2)
		self.assertEqual(len(events()), before - 2)
		self.assertTrue(os_audit.verify()["ok"])
		# New events keep chaining from the head.
		os_audit.record("logout", user=OTHER_STUDENT)
		os_audit.flush(commit=False)
		self.assertTrue(os_audit.verify()["ok"])

	def test_retention_of_everything_keeps_the_next_event_verifiable(self):
		now = frappe.utils.now_datetime()
		frappe.db.sql(f"DELETE FROM `tab{os_audit.EVENT}`")
		with at(now - timedelta(days=40)):
			os_audit.record("login", user=STUDENT)
		os_audit.flush(commit=False)
		with at(now):
			os_audit.apply_retention()
		self.assertFalse(events())
		os_audit.record("login", user=STUDENT)
		os_audit.flush(commit=False)
		self.assertEqual(events()[0].seq, 2)
		self.assertTrue(os_audit.verify()["ok"])

	def test_retention_deletes_old_sessions(self):
		now = frappe.utils.now_datetime()
		self.open_as(STUDENT, now - timedelta(days=40))
		recent = self.open_as(STUDENT, now)
		with at(now):
			self.assertEqual(os_audit.apply_retention()["sessions"], 1)
		self.assertEqual(frappe.get_all(os_audit.SESSION, pluck="name"), [recent])


class TestErasure(OsAuditTestCase):
	def _activity(self):
		session = self.open_as(STUDENT)
		self.open_as(STUDENT, course=OTHER_COURSE)
		self.open_as(OTHER_STUDENT)
		frappe.set_user("Administrator")
		os_audit.record("login", user=STUDENT)
		os_audit.flush(commit=False)
		return session

	def test_account_deletion_erases_but_the_chain_verifies(self):
		configure(courses=[COURSE, OTHER_COURSE])
		self._activity()
		self.assertEqual(os_audit.erase_user_data(STUDENT), 3)
		os_audit.flush(commit=False)
		self.assertFalse(events(user=STUDENT))
		self.assertFalse(frappe.get_all(os_audit.SESSION, filters={"user": STUDENT}))
		self.assertTrue(frappe.get_all(os_audit.SESSION, filters={"user": OTHER_STUDENT}))
		self.assertEqual(len(events("audit_data_erased")), 1)
		self.assertTrue(os_audit.verify()["ok"])

	def test_keep_until_expiry_leaves_everything(self):
		configure(courses=[COURSE, OTHER_COURSE], on_account_deletion="Keep Until Expiry")
		self._activity()
		self.assertEqual(os_audit.erase_user_data(STUDENT), 0)
		self.assertEqual(len(events(user=STUDENT)), 3)

	def test_course_purge_erases_only_that_course(self):
		configure(courses=[COURSE, OTHER_COURSE])
		self._activity()
		self.assertEqual(os_audit.erase_course_member(COURSE, STUDENT), 1)
		remaining = events(user=STUDENT)
		self.assertEqual(sorted(e.event_type for e in remaining), ["lesson_open", "login"])
		self.assertTrue(os_audit.verify()["ok"])

	def test_the_account_deletion_calls_the_erasure(self):
		from os_lms.os_lms import account_deletion

		with patch.object(os_audit, "erase_user_data") as erase, patch(
			"frappe.sessions.clear_sessions"
		), patch.object(account_deletion, "_delete_owned_records", side_effect=RuntimeError("stop")):
			with self.assertRaises(RuntimeError):
				account_deletion.erase_user(STUDENT, notify=False)
		erase.assert_called_once_with(STUDENT)


class TestServerEvents(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def test_quiz_duration_is_computed_on_the_server(self):
		insert({"doctype": "LMS Quiz", "name": f"{P}quiz", "title": "Q", "course": COURSE})
		frappe.set_user(STUDENT)
		with at(T0):
			os_audit.quiz_start(f"{P}quiz")
		os_audit.flush(commit=False)
		submission = frappe._dict(
			doctype="LMS Quiz Submission",
			name=f"{P}submission",
			quiz=f"{P}quiz",
			member=STUDENT,
			course=COURSE,
			creation=T0 + timedelta(seconds=95),
			score=4,
			score_out_of=5,
			percentage=80,
		)
		os_audit.on_quiz_submission_insert(submission)
		os_audit.flush(commit=False)
		submitted = events("quiz_submit")
		self.assertEqual(len(submitted), 1)
		self.assertIn('"duration_seconds":95', submitted[0].data)
		self.assertIn('"score":4', submitted[0].data)

	def test_lesson_completion_assignment_and_certificate(self):
		frappe.set_user("Administrator")
		os_audit.on_course_progress_insert(
			frappe._dict(doctype="LMS Course Progress", name="p1", status="Complete", member=STUDENT, course=COURSE, lesson=LESSON)
		)
		os_audit.on_course_progress_insert(
			frappe._dict(doctype="LMS Course Progress", name="p2", status="Partially Complete", member=STUDENT, course=COURSE, lesson=LESSON)
		)
		os_audit.on_assignment_submission_insert(
			frappe._dict(doctype="LMS Assignment Submission", name="a1", member=STUDENT, course=COURSE, lesson=LESSON, assignment="x")
		)
		os_audit.on_certificate_insert(
			frappe._dict(doctype="LMS Certificate", name="c1", member=STUDENT, course=COURSE)
		)
		os_audit.flush(commit=False)
		self.assertEqual(
			[e.event_type for e in events(user=STUDENT)],
			["lesson_complete", "assignment_submit", "certificate_issued"],
		)
		# Recorded for the student while the Administrator made the request: no device.
		self.assertFalse(any(e.device for e in events(user=STUDENT)))

	def test_logins_from_the_activity_log(self):
		for operation, status in (("Login", "Success"), ("Login", "Failed"), ("Logout", "Success")):
			os_audit.on_activity_log_insert(frappe._dict(operation=operation, status=status, user=STUDENT))
		os_audit.on_activity_log_insert(frappe._dict(operation="Login", status="Success", user="Administrator"))
		os_audit.on_activity_log_insert(frappe._dict(operation="Login", status="Failed", user="nobody@nowhere.it"))
		os_audit.flush(commit=False)
		self.assertEqual([e.event_type for e in events()][-3:], ["login", "login_failed", "logout"])
		self.assertFalse(events(user="Administrator", event_type="login"))

	def test_live_class_join_follows_the_batch_scope(self):
		insert({"doctype": "LMS Batch", "name": f"{P}batch", "title": "B"})
		row = frappe.get_doc(
			{"doctype": "Batch Course", "parent": f"{P}batch", "parenttype": "LMS Batch", "parentfield": "courses", "course": COURSE}
		)
		row.set_new_name()
		row.db_insert()
		live = frappe._dict(doctype="LMS Live Class", name=f"{P}live", batch_name=f"{P}batch", host="host@x.it")
		os_audit.on_live_class_join(live, STUDENT)
		os_audit.on_live_class_join(frappe._dict(live, batch_name="another-batch"), STUDENT)
		os_audit.flush(commit=False)
		joined = events("live_class_join")
		self.assertEqual(len(joined), 1)
		self.assertEqual(joined[0].batch, f"{P}batch")

	def test_device_and_ip_helpers(self):
		self.assertEqual(os_audit.classify_device("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile"), "mobile")
		self.assertEqual(os_audit.classify_device("Mozilla/5.0 (Linux; Android 14; SM-X200)"), "tablet")
		self.assertEqual(os_audit.classify_device("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"), "desktop")
		self.assertEqual(os_audit.format_ip("192.168.10.77", "Truncated"), "192.168.10.0")
		self.assertEqual(os_audit.format_ip("2001:db8:abcd:12::1", "Truncated"), "2001:db8:abcd::")
		self.assertEqual(os_audit.format_ip("192.168.10.77", "Full Address"), "192.168.10.77")
		self.assertIsNone(os_audit.format_ip("192.168.10.77", "Not Stored"))


class TestPermissions(OsAuditTestCase):
	def test_only_system_manager_and_gestore_bundles(self):
		configure()
		for bundle, roles in BUNDLES.items():
			email = f"{P}{bundle}@example.com"
			make_user(email, roles)
			frappe.set_user(email)
			allowed = bundle in ("gestore", "system_manager")
			self.assertEqual(os_audit.can_use_os_audit(), allowed, bundle)
			if allowed:
				self.assertTrue(os_audit.verify_chain()["ok"])
			else:
				with self.assertRaises(frappe.PermissionError, msg=bundle):
					os_audit.verify_chain()
			frappe.set_user("Administrator")
