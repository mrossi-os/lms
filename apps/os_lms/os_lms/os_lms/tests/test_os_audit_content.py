"""OS Audit phase 3: video, PDF and download events sent by the lesson page, and the
video time of a session (docs/audit-studenti/PIANO.md §4-5, §15).

Same rules as test_os_audit: everything inside the test transaction, rolled back.
"""

from datetime import timedelta

import frappe

from os_lms.os_lms import os_audit, os_audit_export, os_audit_page
from os_lms.os_lms.tests.test_os_audit import (
	COURSE,
	LESSON,
	OTHER_COURSE,
	STUDENT,
	T0,
	OsAuditTestCase,
	at,
	configure,
	events,
)

VIDEO = "/files/lesson-video.mp4"


def video(event_type, position, **extra):
	return {"type": event_type, "source": VIDEO, "position": position, "duration": 300, **extra}


class ContentTestCase(OsAuditTestCase):
	def setUp(self):
		super().setUp()
		configure()

	def send(self, session, seconds, sent=None, video_seconds=0, **flags):
		with at(T0 + timedelta(seconds=seconds)):
			return os_audit.heartbeat(session, active=True, events=sent, video_seconds=video_seconds, **flags)

	def recorded(self):
		os_audit.flush(commit=False)
		return [e for e in events() if e.event_type in os_audit.CLIENT_EVENTS]


class TestClientEvents(ContentTestCase):
	def test_lesson_open_tells_the_page_what_to_collect(self):
		frappe.set_user(STUDENT)
		with at(T0):
			answer = os_audit.on_lesson_open(COURSE, LESSON)
		self.assertEqual((answer["track_videos"], answer["track_files"]), (1, 1))

	def test_events_take_course_lesson_and_session_from_the_session(self):
		session = self.open_as(STUDENT)
		sent = [
			# A page cannot move an event to another course or lesson.
			video("video_play", 12.4, course=OTHER_COURSE, lesson="elsewhere"),
			video("video_seek", 90, **{"from": 12}),
			{"type": "pdf_open", "file": "/files/handout.pdf"},
			{"type": "download", "file": "/private/files/slides.zip"},
		]
		# Under 20 s: no time is credited, the events are recorded all the same.
		self.send(session, 10, sent)
		rows = self.recorded()
		self.assertEqual([e.event_type for e in rows], ["video_play", "video_seek", "pdf_open", "download"])
		for row in rows:
			self.assertEqual((row.course, row.lesson, row.session, row.user), (COURSE, LESSON, session, STUDENT))
		data = [frappe.parse_json(row.data) for row in rows]
		self.assertEqual(data[0], {"source": VIDEO, "position": 12, "duration": 300})
		self.assertEqual(data[1], {"source": VIDEO, "position": 90, "duration": 300, "from": 12})
		self.assertEqual(data[2], {"file": "/files/handout.pdf"})
		self.assertEqual(data[3], {"file": "/private/files/slides.zip"})
		self.assertTrue(os_audit.verify()["ok"])

	def test_only_known_types_and_valid_fields_are_kept(self):
		session = self.open_as(STUDENT)
		sent = [
			{"type": "lesson_complete"},
			{"type": "login"},
			"not an event",
			{"type": "video_play", "position": 3},
			{"type": "pdf_open", "file": "https://elsewhere.example.com/x.pdf"},
			{"type": "download", "file": "/api/method/frappe.auth.get_logged_user"},
			video("video_pause", "abc"),
			video("video_ended", float("inf")),
			{"type": "download", "file": "/files/" + "a" * 400},
		]
		self.send(session, 30, sent)
		rows = self.recorded()
		self.assertEqual([e.event_type for e in rows], ["video_pause", "video_ended", "download"])
		self.assertNotIn("position", frappe.parse_json(rows[0].data))
		self.assertNotIn("position", frappe.parse_json(rows[1].data))
		self.assertEqual(len(frappe.parse_json(rows[2].data)["file"]), os_audit.MAX_CLIENT_TEXT)

	def test_at_most_thirty_events_per_signal(self):
		session = self.open_as(STUDENT)
		self.send(session, 30, [video("video_play", n) for n in range(40)])
		self.assertEqual(len(self.recorded()), os_audit.MAX_CLIENT_EVENTS)

	def test_toggles_turn_videos_and_files_off(self):
		configure(track_videos=0)
		session = self.open_as(STUDENT)
		self.send(session, 30, [video("video_play", 1), {"type": "pdf_open", "file": "/files/a.pdf"}], video_seconds=20)
		self.assertEqual([e.event_type for e in self.recorded()], ["pdf_open"])
		self.assertEqual(self.session(session).video_seconds, 0)

		configure(track_videos=1, track_files=0)
		self.send(session, 60, [video("video_play", 1), {"type": "download", "file": "/files/a.zip"}])
		self.assertEqual([e.event_type for e in self.recorded()], ["pdf_open", "video_play"])

	def test_events_follow_the_course_scope(self):
		session = self.open_as(STUDENT)
		configure(courses=[OTHER_COURSE])
		self.send(session, 30, [video("video_play", 1)])
		self.assertEqual(self.recorded(), [])

	def test_a_session_of_another_user_is_refused(self):
		session = self.open_as(STUDENT)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			self.send(session, 30, [video("video_play", 1)])


class TestVideoTime(ContentTestCase):
	def test_video_time_grows_but_never_beyond_presence(self):
		session = self.open_as(STUDENT)
		self.send(session, 30, video_seconds=25)
		self.assertEqual(self.session(session).video_seconds, 25)
		# More than the 60 s of presence: capped.
		self.send(session, 60, video_seconds=100)
		self.assertEqual(self.session(session).video_seconds, 60)
		# A lower total (a page reloaded its counter) never takes time away.
		self.send(session, 90, video_seconds=10)
		self.assertEqual(self.session(session).video_seconds, 60)
		# An ignored signal (under 20 s) changes nothing.
		self.send(session, 95, video_seconds=95)
		self.assertEqual(self.session(session).video_seconds, 60)

		self.send(session, 120, video_seconds=110, close=True)
		os_audit.flush(commit=False)
		closed = events("session_closed")[-1]
		self.assertEqual(frappe.parse_json(closed.data)["video_seconds"], 110)

	def test_the_page_shows_and_exports_the_video_time(self):
		session = self.open_as(STUDENT)
		self.send(session, 30, video_seconds=30)
		self.send(session, 60, video_seconds=45, close=True)
		frappe.set_user("Administrator")
		summary = os_audit_page.get_student_summary(STUDENT)
		self.assertEqual(summary["totals"]["video_seconds"], 45)
		self.assertEqual(summary["lessons"][0]["video_seconds"], 45)
		self.assertEqual(summary["days"][0]["video_seconds"], 45)

		rows, count = os_audit_export.session_rows({"user": STUDENT})
		self.assertEqual(count, 1)
		column = rows[0].index(frappe._("Video time (h:mm)"))
		self.assertEqual(rows[1][column], "0:00")

	def test_the_page_saves_the_new_toggles(self):
		frappe.set_user("Administrator")
		values = os_audit_page.get_page()["settings"]
		self.assertEqual((values["track_videos"], values["track_files"]), (1, 1))
		values.update(track_videos=0, track_files=0)
		saved = os_audit_page.save_settings(values)["settings"]
		self.assertEqual((saved["track_videos"], saved["track_files"]), (0, 0))
