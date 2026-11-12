"""OS Audit phase 4: live class attendance from Zoom and Google Meet
(docs/audit-studenti/fase-4-analisi.md §13).

Same rules as test_os_audit: everything inside the test transaction, rolled back.
The reader commits once per class, so frappe.db.commit is patched and the chain is
flushed by hand; the provider APIs are fakes behind requests.get / requests.post.
"""

import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import quote, unquote

import frappe

from os_lms.os_lms import os_audit, os_audit_export, os_audit_live, os_audit_page
from os_lms.os_lms.tests.test_os_audit import (
	BUNDLES,
	COURSE,
	OTHER_STUDENT,
	STUDENT,
	T0,
	P,
	OsAuditTestCase,
	configure,
	events,
	insert,
	make_user,
)

HOST = f"{P}host@example.com"
OUTSIDER = f"{P}outsider@example.com"
BATCH = f"{P}batch"
OTHER_BATCH = f"{P}other-batch"
LIVE = f"{P}live"
LIVE_2 = f"{P}live-2"
ZOOM_HOST_EMAIL = "zoom-owner@example.com"
AFTER = T0 + timedelta(hours=3)


class FakeResponse:
	def __init__(self, status_code=200, body=None):
		self.status_code = status_code
		self._body = body or {}
		self.text = str(body)

	def json(self):
		return self._body


def utc(moment) -> str:
	return os_audit_live.rfc3339(moment)


def zoom_participant(name, start_minute, end_minute, email="", user_id=""):
	return {
		"id": user_id,
		"name": name,
		"user_email": email,
		"join_time": utc(T0 + timedelta(minutes=start_minute)),
		"leave_time": utc(T0 + timedelta(minutes=end_minute)),
		"duration": (end_minute - start_minute) * 60,
	}


def fake_zoom(instances: dict, missing=(), error=None, page_size=None):
	"""requests.get for the Zoom API: instances {uuid: [participants]}."""

	def get(url, headers=None, params=None, timeout=None):
		if error:
			return FakeResponse(500, {"code": 500, "message": error})
		if url.endswith("/users/me"):
			return FakeResponse(200, {"email": ZOOM_HOST_EMAIL, "id": "zoom-owner"})
		if url.endswith("/instances"):
			return FakeResponse(200, {"meetings": [{"uuid": u} for u in instances]})
		match = re.search(r"/past_meetings/(.+)/participants$", url)
		uuid = unquote(unquote(match.group(1)))
		if uuid in missing or uuid not in instances:
			return FakeResponse(404, {"code": 3001, "message": "Meeting does not exist"})
		people = instances[uuid]
		if not page_size:
			return FakeResponse(200, {"participants": people})
		page = int((params or {}).get("next_page_token") or 0)
		chunk = people[page : page + page_size]
		token = str(page + page_size) if page + page_size < len(people) else ""
		return FakeResponse(200, {"participants": chunk, "next_page_token": token})

	return get


@contextmanager
def reading(get=None, now=AFTER):
	with (
		patch.object(os_audit_live, "now_datetime", return_value=now),
		patch.object(os_audit_live, "zoom_token", return_value="token"),
		patch.object(os_audit_live.requests, "get", side_effect=get or fake_zoom({})),
		patch.object(frappe.db, "commit"),
	):
		yield
	os_audit.flush(commit=False)


def set_full_name(user, full_name):
	frappe.db.set_value("User", user, "full_name", full_name, update_modified=False)


def add_live(name=LIVE, batch=BATCH, provider="Zoom", date=None, **values):
	insert(
		{
			"doctype": "LMS Live Class",
			"name": name,
			"title": name,
			"batch_name": batch,
			"host": HOST,
			"date": date or T0.date(),
			"time": "10:00:00",
			"duration": 60,
			"timezone": "Europe/Rome",
			"conferencing_provider": provider,
			"zoom_account": "zoom-test" if provider == "Zoom" else None,
			"google_meet_account": "meet-test" if provider == "Google Meet" else None,
			"meeting_id": "123" if provider == "Zoom" else None,
			"uuid": "base-uuid" if provider == "Zoom" else None,
			"join_url": "https://meet.google.com/abc-defg-hij" if provider == "Google Meet" else "https://zoom.us/j/123",
			**values,
		}
	)


def add_batch(name, courses=(COURSE,), members=()):
	insert({"doctype": "LMS Batch", "name": name, "title": name, "start_date": T0.date(), "end_date": T0.date()})
	for course in courses:
		row = frappe.get_doc({"doctype": "Batch Course", "parent": name, "parenttype": "LMS Batch", "parentfield": "courses", "course": course})
		row.set_new_name()
		row.db_insert()
	for member in members:
		insert({"doctype": "LMS Batch Enrollment", "name": f"{P}{name}-{member}", "batch": name, "member": member})


def rows_of(live=LIVE):
	return frappe.get_all(os_audit_live.ATTENDANCE, filters={"live_class": live}, fields=["*"], order_by="joined_at asc")


def read_status(live=LIVE):
	return frappe.db.get_value(os_audit_live.READ, live, ["status", "error", "rows", "matched", "unmatched"], as_dict=True)


class LiveTestCase(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()
		make_user(HOST, ("Docente",))
		make_user(OUTSIDER)
		set_full_name(STUDENT, "Mario Rossi")
		set_full_name(OTHER_STUDENT, "Anna Bianchi")
		set_full_name(HOST, "Laura Verdi")
		set_full_name(OUTSIDER, "Outside Person")
		add_batch(BATCH, members=(STUDENT, OTHER_STUDENT))
		add_live()

	def standard_meeting(self):
		"""Two instances: the teacher (Zoom account), the student by email in two
		segments, the other student by name in reverse order, an unknown guest."""
		return fake_zoom(
			{
				"inst/1": [
					zoom_participant("Laura (host)", 0, 60, email=ZOOM_HOST_EMAIL),
					zoom_participant("mario", 5, 30, email=STUDENT),
					zoom_participant("Bianchi Anna", 2, 58),
					zoom_participant("Zorro", 10, 20),
				],
				"inst//2": [zoom_participant("mario", 35, 55, email=STUDENT)],
			}
		)


class TestZoomRead(LiveTestCase):
	def test_every_instance_is_read_and_matched(self):
		with reading(self.standard_meeting()):
			self.assertEqual(os_audit_live.read_live_class(LIVE), "Read")

		rows = rows_of()
		self.assertEqual(len(rows), 5)
		by_user = {}
		for row in rows:
			by_user.setdefault(row.user, []).append(row)
		self.assertEqual({r.matched_by for r in by_user[HOST]}, {"host"})
		self.assertTrue(all(r.is_host for r in by_user[HOST]))
		self.assertEqual({r.matched_by for r in by_user[STUDENT]}, {"email"})
		self.assertEqual({r.matched_by for r in by_user[OTHER_STUDENT]}, {"name"})
		self.assertEqual([r.display_name for r in by_user[None]], ["Zorro"])
		status = read_status()
		self.assertEqual((status.status, status.rows, status.matched, status.unmatched), ("Read", 5, 4, 1))

		attendance = {e.user: frappe.parse_json(e.data) for e in events("live_attendance")}
		self.assertEqual(set(attendance), {HOST, STUDENT, OTHER_STUDENT})
		self.assertEqual(attendance[STUDENT]["seconds"], (25 + 20) * 60)
		self.assertEqual(attendance[STUDENT]["segment_count"], 2)
		self.assertEqual(attendance[HOST]["is_host"], 1)
		read = events("live_attendance_read")
		self.assertEqual(len(read), 1)
		data = frappe.parse_json(read[0].data)
		self.assertEqual((data["rows"], data["matched"], data["unmatched"]), (5, 4, 1))
		self.assertEqual(len(data["fingerprint"]), 64)
		self.assertNotIn("Zorro", read[0].data)
		self.assertTrue(os_audit.verify()["ok"])

		participants = frappe.get_all(
			"LMS Live Class Participant", filters={"live_class": LIVE}, fields=["member", "duration"]
		)
		self.assertEqual({p.member: p.duration for p in participants}[STUDENT], 45)
		self.assertEqual(frappe.db.get_value("LMS Live Class", LIVE, "attendees"), 3)

	def test_pages_of_participants_are_all_read(self):
		people = [zoom_participant(f"Guest {i}", 0, 10) for i in range(7)]
		with reading(fake_zoom({"inst/1": people}, page_size=3)):
			os_audit_live.read_live_class(LIVE)
		self.assertEqual(len(rows_of()), 7)

	def test_uuids_with_slashes_are_encoded_twice(self):
		self.assertEqual(os_audit_live.zoom_uuid_path("a/b=="), quote("a/b==", safe=""))
		self.assertEqual(os_audit_live.zoom_uuid_path("/ab=="), quote(quote("/ab==", safe=""), safe=""))
		self.assertEqual(os_audit_live.zoom_uuid_path("a//b"), quote(quote("a//b", safe=""), safe=""))

	def test_a_meeting_never_held_waits_then_is_not_held(self):
		missing = fake_zoom({})
		with reading(missing, now=AFTER):
			self.assertEqual(os_audit_live.read_live_class(LIVE), "Pending")
		with reading(missing, now=T0 + timedelta(days=3)):
			self.assertEqual(os_audit_live.read_live_class(LIVE), "Not Held")
		self.assertEqual(rows_of(), [])
		self.assertEqual(events("live_attendance_read"), [])

	def test_a_class_in_error_does_not_stop_the_others(self):
		add_live(LIVE_2)

		def get(url, **kwargs):
			if "zoom-test-broken" in str(kwargs.get("headers")):
				return FakeResponse(500, {"message": "boom"})
			return self.standard_meeting()(url, **kwargs)

		with (
			reading(get),
			patch.object(os_audit_live, "zoom_token", side_effect=lambda account: f"Bearer-{account}"),
		):
			frappe.db.set_value("LMS Live Class", LIVE, "zoom_account", "zoom-test-broken")
			self.assertEqual(os_audit_live.read_due_live_classes(), 1)
		self.assertEqual(read_status(LIVE).status, "Error")
		self.assertIn("boom", read_status(LIVE).error)
		self.assertEqual(read_status(LIVE_2).status, "Read")

	def test_rows_outside_the_class_window_are_ignored(self):
		late = zoom_participant("Tomorrow", 24 * 60, 24 * 60 + 30)
		with reading(fake_zoom({"inst/1": [late, zoom_participant("mario", 5, 30, email=STUDENT)]})):
			os_audit_live.read_live_class(LIVE)
		self.assertEqual([r.display_name for r in rows_of()], ["mario"])


class TestDueClasses(LiveTestCase):
	def test_scope_window_and_status(self):
		add_batch(OTHER_BATCH, courses=())
		add_live(f"{P}out-of-scope", batch=OTHER_BATCH)
		add_live(f"{P}too-old", date=(T0 - timedelta(days=40)).date())
		self.assertEqual(os_audit_live.due_live_classes(now=T0 + timedelta(minutes=70)), [])
		due = os_audit_live.due_live_classes(now=AFTER)
		self.assertEqual(due, [LIVE])

		os_audit_live._set_status(LIVE, "Zoom", "Read")
		self.assertEqual(os_audit_live.due_live_classes(now=AFTER), [])
		frappe.db.set_value(os_audit_live.READ, LIVE, {"status": "Error", "modified": AFTER}, update_modified=False)
		self.assertEqual(os_audit_live.due_live_classes(now=AFTER + timedelta(minutes=10)), [])
		self.assertEqual(os_audit_live.due_live_classes(now=AFTER + timedelta(hours=2)), [LIVE])

	def test_nothing_is_read_with_the_audit_or_the_toggle_off(self):
		for values in ({"enabled": 0}, {"track_live_classes": 0}):
			configure(**values)
			with self.subTest(values=values), reading(self.standard_meeting()):
				self.assertEqual(os_audit_live.read_due_live_classes(), 0)
				self.assertIsNone(os_audit_live.read_live_class(LIVE, force=True))
				with self.assertRaises(frappe.ValidationError):
					os_audit_live.reread_live_class(LIVE)
		self.assertEqual(rows_of(), [])

	def test_a_class_out_of_scope_is_never_read(self):
		add_batch(OTHER_BATCH, courses=())
		frappe.db.set_value("LMS Live Class", LIVE, "batch_name", OTHER_BATCH)
		with reading(self.standard_meeting()):
			self.assertIsNone(os_audit_live.read_live_class(LIVE))
		self.assertEqual(rows_of(), [])


class TestMatching(LiveTestCase):
	def test_an_ambiguous_name_or_an_outsider_email_stays_unmatched(self):
		make_user(f"{P}twin@example.com")
		set_full_name(f"{P}twin@example.com", "Mario Rossi")
		insert({"doctype": "LMS Batch Enrollment", "name": f"{P}twin", "batch": BATCH, "member": f"{P}twin@example.com"})
		meeting = fake_zoom(
			{"inst/1": [zoom_participant("Mario Rossi", 0, 30), zoom_participant("x", 0, 30, email=OUTSIDER)]}
		)
		with reading(meeting):
			os_audit_live.read_live_class(LIVE)
		self.assertEqual([r.user for r in rows_of()], [None, None])

	def test_names_match_without_accents_case_or_word_order(self):
		self.assertEqual(os_audit_live.normalize_name("Rossì  MARIO"), os_audit_live.normalize_name("mario rossi"))

	def test_the_teacher_is_who_started_the_class(self):
		doc = frappe.get_doc("LMS Live Class", LIVE)
		frappe.set_user(OTHER_STUDENT)
		os_audit.on_live_class_start(doc, OTHER_STUDENT)
		frappe.set_user("Administrator")
		os_audit.flush(commit=False)
		start = events("live_class_start")
		self.assertEqual([e.user for e in start], [OTHER_STUDENT])
		self.assertEqual(os_audit_live.teacher_of(frappe._dict(name=LIVE, host=HOST)), OTHER_STUDENT)
		with reading(fake_zoom({"inst/1": [zoom_participant("Owner", 0, 60, email=ZOOM_HOST_EMAIL)]})):
			os_audit_live.read_live_class(LIVE)
		self.assertEqual([(r.user, r.matched_by) for r in rows_of()], [(OTHER_STUDENT, "host")])


class TestManualMatch(LiveTestCase):
	def read(self):
		with reading(self.standard_meeting()):
			os_audit_live.read_live_class(LIVE)

	def zorro(self):
		return next(r for r in rows_of() if r.display_name == "Zorro")

	def test_the_gestore_matches_a_participant_and_the_chain_says_who(self):
		self.read()
		gestore = f"{P}gestore@example.com"
		make_user(gestore, BUNDLES["gestore"])
		frappe.set_user(gestore)
		live = os_audit_page.get_attendance(COURSE)["live_classes"][0]
		self.assertIn(STUDENT, [p["user"] for p in live["people"]])
		with patch.object(os_audit_live, "now_datetime", return_value=AFTER):
			result = os_audit_live.match_participant(self.zorro().name, user=OTHER_STUDENT)
		frappe.set_user("Administrator")
		os_audit.flush(commit=False)
		self.assertEqual(result["unmatched"], 0)
		zorro = self.zorro()
		self.assertEqual((zorro.user, zorro.matched_by, zorro.matched_by_user), (OTHER_STUDENT, "manual", gestore))
		last = events("live_attendance", user=OTHER_STUDENT)[-1]
		data = frappe.parse_json(last.data)
		self.assertEqual(data["manual_by"], gestore)
		# The name match (58 min) and Zorro (10 min) overlap: merged, not added.
		self.assertEqual(data["seconds"], 56 * 60)
		self.assertTrue(os_audit.verify()["ok"])

	def test_a_person_outside_the_class_is_refused(self):
		self.read()
		with self.assertRaises(frappe.ValidationError):
			os_audit_live.match_participant(self.zorro().name, user=OUTSIDER)

	def test_a_guest_leaves_the_unmatched_list(self):
		self.read()
		result = os_audit_live.match_participant(self.zorro().name, guest=1)
		self.assertEqual(result["unmatched"], 0)
		self.assertEqual(self.zorro().matched_by, "guest")
		live = os_audit_page.get_attendance(COURSE)["live_classes"][0]
		self.assertEqual(live["unmatched"], [])
		self.assertEqual([g["display_name"] for g in live["guests"]], ["Zorro"])

	def test_a_reread_keeps_manual_matches_and_guests(self):
		self.read()
		os_audit_live.match_participant(self.zorro().name, user=OTHER_STUDENT)
		with reading(self.standard_meeting()):
			self.assertEqual(os_audit_live.read_live_class(LIVE, force=True), "Read")
		self.assertEqual((self.zorro().user, self.zorro().matched_by), (OTHER_STUDENT, "manual"))

	def test_docente_valutatore_and_moderator_are_refused(self):
		self.read()
		row = self.zorro().name
		for bundle in ("docente", "valutatore", "moderator"):
			user = f"{P}{bundle}@example.com"
			make_user(user, BUNDLES[bundle])
			frappe.set_user(user)
			for call, kwargs in (
				(os_audit_live.match_participant, {"row": row, "user": STUDENT}),
				(os_audit_live.reread_live_class, {"live_class": LIVE}),
			):
				with self.subTest(bundle=bundle, call=call.__name__), self.assertRaises(frappe.PermissionError):
					call(**kwargs)
		frappe.set_user("Administrator")

	def test_reread_is_queued_only_after_the_end(self):
		with patch.object(os_audit_live, "now_datetime", return_value=T0 + timedelta(minutes=20)):
			with self.assertRaises(frappe.ValidationError):
				os_audit_live.reread_live_class(LIVE)
		with patch.object(frappe, "enqueue") as enqueue:
			self.assertEqual(os_audit_live.reread_live_class(LIVE), {"status": "Pending"})
		self.assertTrue(enqueue.call_args.kwargs["force"])
		self.assertEqual(read_status().status, "Pending")


def fake_meet(code="abc-defg-hij", participants=None, sessions=None):
	participants = participants or []
	sessions = sessions or {}

	def get(url, headers=None, params=None, timeout=None):
		if url.endswith("/conferenceRecords"):
			if code not in params["filter"]:
				return FakeResponse(200, {})
			return FakeResponse(200, {"conferenceRecords": [{"name": "conferenceRecords/rec1"}]})
		if url.endswith("/participants"):
			return FakeResponse(200, {"participants": participants})
		if url.endswith("/participantSessions"):
			participant = url.split("/v2/")[1].rsplit("/participantSessions", 1)[0]
			return FakeResponse(200, {"participantSessions": sessions.get(participant, [])})
		return FakeResponse(404, {})

	return get


def meet_session(start_minute, end_minute):
	return {
		"startTime": utc(T0 + timedelta(minutes=start_minute)),
		"endTime": utc(T0 + timedelta(minutes=end_minute)),
	}


class TestMeet(LiveTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_value("LMS Live Class", LIVE, {"conferencing_provider": "Google Meet", "zoom_account": None, "google_meet_account": "meet-test", "join_url": "https://meet.google.com/abc-defg-hij"})

	def meeting(self):
		return fake_meet(
			participants=[
				{"name": "conferenceRecords/rec1/participants/p1", "signedinUser": {"user": "users/42", "displayName": "Nick"}},
				{"name": "conferenceRecords/rec1/participants/p2", "anonymousUser": {"displayName": "Anna Bianchi"}},
			],
			sessions={
				"conferenceRecords/rec1/participants/p1": [meet_session(0, 20), meet_session(25, 50)],
				"conferenceRecords/rec1/participants/p2": [meet_session(1, 59)],
			},
		)

	def read(self, live=LIVE):
		with reading(self.meeting()), patch.object(os_audit_live, "meet_token", return_value="token"):
			return os_audit_live.read_live_class(live)

	def test_sessions_are_read_and_an_identity_is_remembered(self):
		self.assertEqual(self.read(), "Read")
		rows = rows_of()
		self.assertEqual(len(rows), 3)
		nick = [r for r in rows if r.external_id == "users/42"]
		self.assertEqual([r.user for r in nick], [None, None])
		anna = next(r for r in rows if r.display_name == "Anna Bianchi")
		self.assertEqual((anna.user, anna.matched_by, anna.external_id), (OTHER_STUDENT, "name", ""))

		os_audit_live.match_participant(nick[0].name, user=STUDENT)
		self.assertEqual({r.user for r in rows_of() if r.external_id == "users/42"}, {STUDENT})

		add_live(LIVE_2, provider="Google Meet")
		self.read(LIVE_2)
		nick_again = [r for r in rows_of(LIVE_2) if r.external_id == "users/42"]
		self.assertEqual({(r.user, r.matched_by) for r in nick_again}, {(STUDENT, "identity")})

	def test_a_calendar_without_the_meet_scope_is_an_error_with_its_name(self):
		error = os_audit_live.ProviderError("not authorized on the calendar cal-x")
		with reading(self.meeting()), patch.object(os_audit_live, "meet_token", side_effect=error):
			self.assertEqual(os_audit_live.read_live_class(LIVE), "Error")
		self.assertIn("cal-x", read_status().error)

	def test_meet_token_asks_for_the_meet_scope(self):
		insert({"doctype": "Google Calendar", "name": f"{P}cal", "calendar_name": f"{P}cal", "user": "Administrator", "enable": 1})
		insert({"doctype": "LMS Google Meet Settings", "name": "meet-test", "account_name": "meet-test", "member": "Administrator", "google_calendar": f"{P}cal", "enabled": 1})
		google = frappe._dict(client_id="cid", get_password=lambda **kw: "secret")
		refused = FakeResponse(400, {"error": "invalid_scope"})
		with (
			patch("frappe.model.document.Document.get_password", return_value="refresh"),
			patch.object(os_audit_live.frappe, "get_cached_doc", return_value=google),
			patch.object(os_audit_live.requests, "post", return_value=refused) as post,
		):
			with self.assertRaises(os_audit_live.ProviderError) as error:
				os_audit_live.meet_token(frappe._dict(google_meet_account="meet-test"))
		self.assertEqual(post.call_args.kwargs["data"]["scope"], os_audit_live.MEET_SCOPE)
		self.assertIn(f"{P}cal", str(error.exception))

	def test_the_meeting_code_comes_from_the_link(self):
		self.assertEqual(os_audit_live.meeting_code("https://meet.google.com/ABC-defg-hij?authuser=1"), "abc-defg-hij")
		self.assertIsNone(os_audit_live.meeting_code("https://zoom.us/j/1"))


class TestPageAndExport(LiveTestCase):
	def test_the_page_and_the_export_show_provider_attendance(self):
		os_audit.record("live_class_join", user=STUDENT, batch=BATCH, reference_doctype="LMS Live Class", reference_name=LIVE)
		os_audit.flush(commit=False)
		with reading(self.standard_meeting()):
			os_audit_live.read_live_class(LIVE)

		live = os_audit_page.get_attendance(COURSE)["live_classes"][0]
		self.assertEqual(live["read_status"], "Read")
		self.assertEqual(live["teacher"], HOST)
		people = {p["user"]: p for p in live["participants"]}
		self.assertTrue(people[HOST]["is_host"])
		self.assertEqual(people[STUDENT]["duration_seconds"], 45 * 60)
		self.assertEqual(people[STUDENT]["segments"], 2)
		self.assertEqual(people[STUDENT]["matched_by"], "email")
		self.assertIsNotNone(people[STUDENT]["joined_from_platform"])
		self.assertEqual([u["display_name"] for u in live["unmatched"]], ["Zorro"])

		rows, count = os_audit_export.build_rows("os_audit_live", {"course": COURSE})
		self.assertEqual(count, 4)
		header = rows[0]
		role = header.index("Role")
		self.assertEqual(rows[1][role], "Teacher")
		# Data rows are 1..count; the footer (seal, chain head) follows.
		self.assertEqual(rows[count][role], "Unmatched")
		self.assertEqual(rows[count][header.index("Name at the provider")], "Zorro")
		student = next(r for r in rows if r[header.index("Email")] == STUDENT)
		self.assertEqual(student[-1], "0:45")


class TestRetentionErasureAndUpstreamJob(LiveTestCase):
	def test_retention_and_account_deletion_cover_the_live_rows(self):
		with reading(self.standard_meeting()):
			os_audit_live.read_live_class(LIVE)
		self.assertEqual(os_audit_live.apply_retention(T0 + timedelta(minutes=3)), 2)
		self.assertEqual(len(rows_of()), 3)
		os_audit.erase_user_data(STUDENT)
		self.assertEqual([r for r in rows_of() if r.user == STUDENT], [])

	def test_the_upstream_reader_is_stopped(self):
		name = frappe.db.get_value("Scheduled Job Type", {"method": os_audit_live.UPSTREAM_ATTENDANCE_JOB}, "name")
		if not name:
			self.skipTest("upstream job not synced on this site")
		frappe.db.set_value("Scheduled Job Type", name, "stopped", 0, update_modified=False)
		with patch.object(frappe.db, "commit"):
			os_audit_live.stop_upstream_attendance_job()
		self.assertEqual(frappe.db.get_value("Scheduled Job Type", name, "stopped"), 1)
