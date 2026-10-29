"""Regression tests for H-1 of docs/security/owasp-top10-2025-correzioni-2026-10-29.md:
a lesson is completed only after the server handed it out to the same user and,
with enforce_video_completion on, only once the page recorded a watch time.

They patch Frappe's lookups instead of writing records; the cache keys written
by the round-trip test are deleted by exact name.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import lesson_progress


def _content(*blocks):
	return json.dumps({"blocks": list(blocks)})


class TestLessonCompletionNeedsTheLessonOpened(UnitTestCase):
	def _save(self, opened=True, enrolled=True, video_missing=False, scorm_details=None, scorm=False):
		with ExitStack() as stack:
			stack.enter_context(patch.object(lesson_progress, "get_lesson_course", return_value="course-1"))
			stack.enter_context(patch.object(frappe.db, "exists", return_value="enrollment-1" if enrolled else None))
			stack.enter_context(patch.object(lesson_progress, "was_lesson_opened", return_value=opened))
			missing = stack.enter_context(
				patch.object(lesson_progress, "is_video_watch_missing", return_value=video_missing)
			)
			stack.enter_context(patch.object(lesson_progress, "is_scorm_lesson", return_value=scorm))
			upstream = stack.enter_context(patch.object(lesson_progress, "lms_save_progress", return_value=42))
			try:
				result = lesson_progress.save_progress("lesson-1", "course-1", scorm_details)
			except (frappe.ValidationError, frappe.PermissionError) as error:
				result = error
		return result, upstream, missing

	def test_a_lesson_never_opened_is_not_completed(self):
		result, upstream, _ = self._save(opened=False)
		self.assertIsInstance(result, frappe.PermissionError)
		upstream.assert_not_called()

	def test_an_opened_lesson_takes_the_normal_path(self):
		result, upstream, _ = self._save()
		self.assertEqual(result, 42)
		upstream.assert_called_once_with("lesson-1", "course-1", None)

	def test_a_video_lesson_without_a_watch_time_is_not_completed(self):
		result, upstream, _ = self._save(video_missing=True)
		self.assertIsInstance(result, frappe.ValidationError)
		self.assertNotIsInstance(result, frappe.PermissionError)
		upstream.assert_not_called()

	def test_without_an_enrollment_upstream_answers_as_before(self):
		# Staff previewing a lesson: upstream records nothing and returns 0.
		result, upstream, _ = self._save(opened=False, enrolled=False)
		self.assertEqual(result, 42)
		upstream.assert_called_once()

	def test_a_scorm_lesson_must_be_opened_but_has_no_video_rule(self):
		details = {"is_complete": 1}
		result, _, _ = self._save(opened=False, scorm_details=details, scorm=True)
		self.assertIsInstance(result, frappe.PermissionError)

		result, upstream, missing = self._save(video_missing=True, scorm_details=details, scorm=True)
		self.assertEqual(result, 42)
		missing.assert_not_called()
		upstream.assert_called_once_with("lesson-1", "course-1", details)

	def test_the_quiz_and_assignment_path_goes_through_the_same_guard(self):
		lookups = {"Chapter Reference": "chapter-1", "Lesson Reference": "lesson-1"}
		with (
			patch.object(frappe, "get_value", side_effect=lambda doctype, *a, **k: lookups[doctype]),
			patch.object(lesson_progress, "save_progress") as guarded,
		):
			lesson_progress.mark_lesson_progress("course-1", 1, 2)
		guarded.assert_called_once_with("lesson-1", "course-1")

	def test_the_scorm_player_records_its_lesson_as_opened(self):
		with (
			patch.object(lesson_progress, "lms_get_scorm_playback", return_value={"lesson": "scorm-lesson"}),
			patch.object(lesson_progress, "record_lesson_open") as record,
		):
			self.assertEqual(lesson_progress.get_scorm_playback("chapter-1"), {"lesson": "scorm-lesson"})
		record.assert_called_once_with("scorm-lesson")

	def test_get_lesson_records_the_lesson_as_opened(self):
		from os_lms.os_lms import override_utils

		with (
			patch.object(override_utils, "_original_get_lesson", return_value={"name": "lesson-1"}),
			patch.object(override_utils, "_list_simulations_for_lesson", return_value=[]),
			patch.object(override_utils, "record_lesson_open") as record,
		):
			override_utils.get_lesson("course-1", 1, 1)
		record.assert_called_once_with("lesson-1")

	def test_the_completion_endpoints_reach_the_os_lms_methods(self):
		from os_lms import hooks

		overrides = hooks.override_whitelisted_methods
		self.assertEqual(
			overrides["lms.lms.api.mark_lesson_progress"], "os_lms.os_lms.lesson_progress.mark_lesson_progress"
		)
		self.assertEqual(
			overrides["lms.lms.doctype.course_chapter.course_chapter.get_scorm_playback"],
			"os_lms.os_lms.lesson_progress.get_scorm_playback",
		)


class TestLessonOpenRecord(UnitTestCase):
	LESSON = "owasp-h1-test-lesson"

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.cache.delete_value(lesson_progress._lesson_open_key(self.LESSON))

	def test_the_record_is_per_user(self):
		self.assertFalse(lesson_progress.was_lesson_opened(self.LESSON))
		lesson_progress.record_lesson_open(self.LESSON)
		self.assertTrue(lesson_progress.was_lesson_opened(self.LESSON))
		with patch.dict(frappe.local.session, {"user": "someone-else@example.com"}):
			self.assertFalse(lesson_progress.was_lesson_opened(self.LESSON))

	def test_a_guest_or_a_missing_lesson_records_nothing(self):
		with (
			patch.dict(frappe.local.session, {"user": "Guest"}),
			patch.object(frappe.cache, "set_value") as set_value,
		):
			lesson_progress.record_lesson_open(self.LESSON)
		set_value.assert_not_called()
		with patch.object(frappe.cache, "set_value") as set_value:
			lesson_progress.record_lesson_open(None)
		set_value.assert_not_called()


class TestVideoWatchRule(UnitTestCase):
	def _missing(self, enforce=1, completed=False, has_video=True, watched=False):
		def exists(doctype, *args, **kwargs):
			if doctype == "LMS Course Progress":
				return "progress-1" if completed else None
			if doctype == "LMS Video Watch Duration":
				return "watch-1" if watched else None
			raise AssertionError(doctype)

		with (
			patch.object(frappe, "get_cached_value", return_value=enforce),
			patch.object(frappe.db, "exists", side_effect=exists),
			patch.object(lesson_progress, "has_tracked_video", return_value=has_video),
		):
			return lesson_progress.is_video_watch_missing("lesson-1")

	def test_a_video_lesson_needs_a_recorded_watch_time(self):
		self.assertTrue(self._missing())
		self.assertFalse(self._missing(watched=True))

	def test_the_rule_applies_only_when_the_setting_is_on(self):
		self.assertFalse(self._missing(enforce=0))
		self.assertFalse(self._missing(enforce=None))

	def test_lessons_without_video_or_already_complete_are_left_alone(self):
		self.assertFalse(self._missing(has_video=False))
		self.assertFalse(self._missing(completed=True))


class TestTrackedVideoDetection(UnitTestCase):
	def _has_video(self, content=None, body=None, youtube=None):
		row = frappe._dict(content=content, body=body, youtube=youtube)
		with patch.object(frappe.db, "get_value", return_value=row):
			return lesson_progress.has_tracked_video("lesson-1")

	def test_editorjs_videos_the_page_tracks(self):
		self.assertTrue(self._has_video(_content({"type": "upload", "data": {"file_type": "MP4"}})))
		self.assertTrue(self._has_video(_content({"type": "embed", "data": {"service": "youtube"}})))
		self.assertTrue(self._has_video(_content({"type": "embed", "data": {"service": "vimeo"}})))

	def test_editorjs_content_the_page_does_not_track(self):
		# Cloudflare and Bunny render as bare iframes: the page never reports them.
		self.assertFalse(self._has_video(_content({"type": "embed", "data": {"service": "cloudflareStream"}})))
		self.assertFalse(self._has_video(_content({"type": "upload", "data": {"file_type": "pdf"}})))
		self.assertFalse(self._has_video(_content({"type": "paragraph", "data": {"text": "hi"}})))
		self.assertFalse(self._has_video("not editorjs"))

	def test_content_replaces_the_legacy_body(self):
		self.assertFalse(
			self._has_video(content=_content({"type": "paragraph", "data": {}}), body="x", youtube="abc")
		)

	def test_legacy_body_videos(self):
		self.assertTrue(self._has_video(body="Intro", youtube="https://youtu.be/abc"))
		self.assertTrue(self._has_video(body='{{ YouTubeVideo("abc") }}'))
		# <video><source></video>: video.src is empty, so the page cannot report it.
		self.assertFalse(self._has_video(body='{{ Video("/files/a.mp4") }}'))
		# The youtube field is rendered only alongside a body.
		self.assertFalse(self._has_video(youtube="abc"))

	def test_a_missing_lesson_has_no_video(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			self.assertFalse(lesson_progress.has_tracked_video("missing"))
