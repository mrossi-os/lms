"""Regression tests for package D of docs/security/owasp-piano-residuo-2026-10-26.md
(the external OWASP audit of 2026-10-27).

One class per point, named after its id. They patch Frappe's lookups instead of
writing records, so nothing is left in the database.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase


class FakeLesson(frappe._dict):
	"""Just enough of a Course Lesson for the validate hook."""


def _lesson_with(file_url, field="content"):
	content = {"blocks": [{"type": "upload", "data": {"file_url": file_url, "file_type": "txt"}}]}
	return FakeLesson({field: json.dumps(content)})


class TestD1LessonFilesStayInTheFilesFolders(UnitTestCase):
	def test_traversal_and_foreign_paths_resolve_to_nothing(self):
		from os_lms.os_lms.ai.utils.file_transcriber import resolve_site_file

		for file_url in (
			"/private/../site_config.json",
			"/private/files/../../site_config.json",
			"/files/../../site_config.json",
			"/files/../../../apps.txt",
			"/etc/passwd",
			"site_config.json",
			"/private/files/",
			None,
		):
			with self.subTest(file_url=file_url):
				self.assertIsNone(resolve_site_file(file_url))

	def test_uploaded_files_resolve_inside_their_folder(self):
		from os_lms.os_lms.ai.utils.file_transcriber import resolve_site_file

		private_root = Path(frappe.get_site_path("private", "files")).resolve()
		public_root = Path(frappe.get_site_path("public", "files")).resolve()
		self.assertEqual(resolve_site_file("/private/files/notes.pdf"), private_root / "notes.pdf")
		self.assertEqual(resolve_site_file("/files/slides.pptx"), public_root / "slides.pptx")

	def test_the_site_config_is_never_read(self):
		from os_lms.os_lms.ai.utils.file_transcriber import FileTranscriber

		# The file exists, so before the fix this returned its content.
		self.assertTrue(Path(frappe.get_site_path("site_config.json")).exists())
		with patch.object(Path, "read_text") as read_text:
			self.assertEqual(FileTranscriber().transcribe("/private/../site_config.json", "txt"), "")
		read_text.assert_not_called()

	def test_saving_a_lesson_that_points_outside_the_files_is_refused(self):
		from os_lms.events.lesson import validate_upload_blocks

		for field in ("content", "instructor_content"):
			with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
				validate_upload_blocks(_lesson_with("/private/../site_config.json", field))

	def test_uploaded_files_and_external_links_are_accepted(self):
		from os_lms.events.lesson import validate_upload_blocks

		for file_url in ("/files/a.pdf", "/private/files/b.docx", "https://example.com/c.pdf", ""):
			with self.subTest(file_url=file_url):
				validate_upload_blocks(_lesson_with(file_url))

	def test_other_blocks_and_non_editorjs_content_are_ignored(self):
		from os_lms.events.lesson import validate_upload_blocks

		paragraph = {"blocks": [{"type": "paragraph", "data": {"file_url": "/etc/passwd"}}]}
		validate_upload_blocks(FakeLesson(content=json.dumps(paragraph)))
		validate_upload_blocks(FakeLesson(content="plain text from the desk"))

	def test_the_check_runs_when_a_lesson_is_saved(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.doc_events["Course Lesson"]["validate"], "os_lms.events.lesson.validate_upload_blocks"
		)


class TestD2ScormDetailsOnlyOnScormLessons(UnitTestCase):
	def _save(self, is_scorm, scorm_details):
		from os_lms.os_lms import lesson_progress

		with (
			patch.object(lesson_progress, "is_scorm_lesson", return_value=is_scorm),
			patch.object(lesson_progress, "lms_save_progress", return_value=42) as upstream,
		):
			result = lesson_progress.save_progress("lesson-1", "course-1", scorm_details)
		return result, upstream

	def test_scorm_details_on_a_normal_lesson_are_dropped(self):
		result, upstream = self._save(False, {"is_complete": 1})
		upstream.assert_called_once_with("lesson-1", "course-1", None)
		self.assertEqual(result, 42)

	def test_scorm_details_on_a_scorm_lesson_pass_through(self):
		details = {"is_complete": 1}
		_, upstream = self._save(True, details)
		upstream.assert_called_once_with("lesson-1", "course-1", details)

	def test_a_normal_lesson_still_takes_the_normal_path(self):
		_, upstream = self._save(False, None)
		upstream.assert_called_once_with("lesson-1", "course-1", None)

	def test_a_lesson_is_scorm_only_in_a_scorm_chapter(self):
		from os_lms.os_lms.lesson_progress import is_scorm_lesson

		values = {
			("Course Lesson", "in-scorm", "chapter"): "scorm-chapter",
			("Course Lesson", "in-normal", "chapter"): "normal-chapter",
			("Course Chapter", "scorm-chapter", "is_scorm_package"): 1,
			("Course Chapter", "normal-chapter", "is_scorm_package"): 0,
		}
		lookup = lambda doctype, name, field: values.get((doctype, name, field))  # noqa: E731
		with patch.object(frappe.db, "get_value", side_effect=lookup):
			self.assertTrue(is_scorm_lesson("in-scorm"))
			self.assertFalse(is_scorm_lesson("in-normal"))
			self.assertFalse(is_scorm_lesson("missing"))
		self.assertFalse(is_scorm_lesson({"name": "in-scorm"}))

	def test_the_lesson_page_reaches_the_os_lms_method(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.override_whitelisted_methods["lms.lms.doctype.course_lesson.course_lesson.save_progress"],
			"os_lms.os_lms.lesson_progress.save_progress",
		)


class TestD6PasswordResetGivesOneAnswer(UnitTestCase):
	def _reset(self, user, enabled_name):
		from os_lms.www import login

		user_doc = MagicMock()
		messages = []
		get_value = frappe.db.get_value

		def user_lookup(doctype, *args, **kwargs):
			return enabled_name if doctype == "User" else get_value(doctype, *args, **kwargs)

		with (
			patch.object(frappe.db, "get_value", side_effect=user_lookup),
			patch.object(frappe, "get_doc", return_value=user_doc),
			patch.object(frappe, "msgprint", side_effect=lambda **kw: messages.append(kw)),
			patch.dict(frappe.local.response, {}, clear=False),
		):
			frappe.local.response.pop("http_status_code", None)
			result = login.reset_password(user)
			status = frappe.local.response.get("http_status_code")
		return result, user_doc, messages, status

	def test_every_address_gets_the_same_answer(self):
		answers = []
		for user, enabled_name in (
			("nobody@example.com", None),
			("disabled@example.com", None),
			("Administrator", "Administrator"),
			("student@example.com", "student@example.com"),
		):
			with self.subTest(user=user):
				result, _, messages, status = self._reset(user, enabled_name)
				self.assertIsNone(result)
				self.assertIsNone(status)
				answers.append(messages)
		self.assertTrue(all(answer == answers[0] for answer in answers))
		self.assertNotIn("student", json.dumps(answers[0]))

	def test_only_an_enabled_account_gets_the_email(self):
		_, user_doc, _, _ = self._reset("student@example.com", "student@example.com")
		user_doc.reset_password.assert_called_once_with(send_email=True)

		for user, enabled_name in (
			("nobody@example.com", None),
			("Administrator", "Administrator"),
		):
			with self.subTest(user=user):
				_, user_doc, _, _ = self._reset(user, enabled_name)
				user_doc.reset_password.assert_not_called()

	def test_the_login_page_reaches_the_os_lms_method(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.override_whitelisted_methods["frappe.core.doctype.user.user.reset_password"],
			"os_lms.www.login.reset_password",
		)
