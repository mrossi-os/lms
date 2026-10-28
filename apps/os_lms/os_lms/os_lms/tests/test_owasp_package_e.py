"""Regression tests for package E of docs/security/owasp-piano-residuo-2026-10-26.md
(the independent OWASP verification of 2026-10-28).

One class per point, named after its id. They patch Frappe's lookups instead of
writing records, so nothing is left in the database.
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase


class FakeSubmission(frappe._dict):
	"""Just enough of an LMS Quiz Submission for the validate hook."""

	def is_new(self):
		return self.get("new", True)


def _submission(*questions, percentage=50, new=True):
	rows = [frappe._dict(question_name=question) for question in questions]
	return FakeSubmission(quiz="quiz-1", result=rows, percentage=percentage, new=new)


class TestE1QuizRowsCountOnce(UnitTestCase):
	def _validate(self, doc, served=3):
		from os_lms.events import quiz_submission

		with patch.object(quiz_submission, "served_question_count", return_value=served):
			quiz_submission.validate_quiz_rows(doc)
		return doc

	def test_a_repeated_question_is_refused(self):
		for questions in (("q1", "q1"), ("q1", "q2", "q1")):
			with self.subTest(questions=questions), self.assertRaises(frappe.ValidationError):
				self._validate(_submission(*questions), served=10)

	def test_more_rows_than_served_questions_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._validate(_submission("q1", "q2", "q3", "q4"), served=3)

	def test_an_old_attempt_can_still_be_graded_after_the_quiz_shrinks(self):
		self._validate(_submission("q1", "q2", "q3", "q4", new=False), served=3)

	def test_a_normal_attempt_passes_untouched(self):
		doc = self._validate(_submission("q1", "q2", "q3", percentage=66.6))
		self.assertEqual(doc.percentage, 66.6)

	def test_the_percentage_never_passes_100(self):
		doc = self._validate(_submission("q1", percentage=300, new=False))
		self.assertEqual(doc.percentage, 100)

	def test_the_served_count_follows_the_question_limit(self):
		from os_lms.events.quiz_submission import served_question_count

		for limit, expected in ((0, 5), (2, 2), (8, 5)):
			with (
				self.subTest(limit=limit),
				patch.object(frappe.db, "count", return_value=5),
				patch.object(frappe.db, "get_value", return_value=limit),
			):
				self.assertEqual(served_question_count("quiz-1"), expected)

	def test_the_check_runs_when_a_submission_is_saved(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.doc_events["LMS Quiz Submission"]["validate"],
			"os_lms.events.quiz_submission.validate_quiz_rows",
		)

	def test_it_runs_after_the_upstream_score(self):
		"""The hook caps the percentage the controller just computed, so it must run
		after LMSQuizSubmission.validate, which is what doc_events do."""
		from lms.lms.doctype.lms_quiz_submission.lms_quiz_submission import LMSQuizSubmission

		doc = frappe.new_doc("LMS Quiz Submission")
		doc.update({"quiz": "quiz-1", "score_out_of": 2, "member": "Administrator"})
		doc.append("result", {"question_name": "q1", "marks": 2, "marks_out_of": 2})
		doc.append("result", {"question_name": "q2", "marks": 2, "marks_out_of": 2})
		with (
			patch.object(LMSQuizSubmission, "validate_if_max_attempts_exceeded"),
			patch("os_lms.events.quiz_submission.served_question_count", return_value=2),
		):
			doc.run_method("validate")
		self.assertEqual(doc.score, 4)
		self.assertEqual(doc.percentage, 100)


class TestE2InvitePageIsGone(UnitTestCase):
	def _redirect_location(self, query_string=None, path="new-sign-up"):
		from frappe.website.path_resolver import resolve_redirect

		frappe.cache.delete_value("website_redirects")
		frappe.flags.redirect_location = None
		with self.assertRaises(frappe.Redirect):
			resolve_redirect(path, query_string)
		return frappe.flags.redirect_location

	def test_the_page_redirects_to_login(self):
		for path in ("new-sign-up", "new-sign-up.html"):
			with self.subTest(path=path):
				self.assertEqual(self._redirect_location(path=path), "/login")

	def test_the_query_string_does_not_follow(self):
		self.assertEqual(self._redirect_location(b'invite_code="><b>probe</b>'), "/login")


class TestE3ExportPacksOnlyDownloadableFiles(UnitTestCase):
	def test_a_private_file_the_exporter_cannot_download_is_dropped(self):
		from os_lms.os_lms import course_export

		def find(url):
			return frappe._dict(name="ok") if url == "/private/files/mine.pdf" else None

		assets = [
			"/files/cover.png",
			"/private/files/mine.pdf",
			"/private/files/someone-else.pdf",
			"/private/../site_config.json",
		]
		with (
			patch.object(course_export, "find_file_by_url", side_effect=find),
			patch.object(course_export, "_references_vouched_by_owner", return_value=[]),
		):
			kept = course_export.downloadable_assets(assets, "course-1")
		self.assertEqual(kept, ["/files/cover.png", "/private/files/mine.pdf"])

	def _can_export(self, file_url="/private/files/lesson.pdf", downloadable=False, vouched=(), courses=()):
		"""vouched: lessons serve_resource accepts for the file; courses: those lessons' courses."""
		from os_lms.os_lms import course_export

		def exists(doctype, filters=None, *args, **kwargs):
			return doctype == "Course Lesson" and "course-1" in courses

		with (
			patch.object(course_export, "find_file_by_url", return_value=downloadable or None),
			patch.object(course_export, "_resolve_lesson_references", return_value=["ref"]),
			patch.object(
				course_export,
				"_references_vouched_by_owner",
				return_value=[(lesson, False) for lesson in vouched],
			),
			patch.object(frappe.db, "exists", side_effect=exists),
		):
			return course_export.can_export_private_file(file_url, "course-1")

	def test_a_lesson_upload_of_another_author_goes_in_when_the_lesson_serves_it(self):
		"""The staging case: unattached lesson files uploaded by a Gestore, exported by a Docente."""
		self.assertTrue(self._can_export(vouched=["lesson-1"], courses=["course-1"]))

	def test_a_file_served_only_by_another_course_stays_out(self):
		self.assertFalse(self._can_export(vouched=["lesson-9"], courses=["course-9"]))

	def test_a_file_no_lesson_vouches_for_stays_out(self):
		"""A student's file pasted into a lesson: serve_resource refuses it, so does the export."""
		self.assertFalse(self._can_export(vouched=[]))

	def test_a_file_the_exporter_can_download_goes_in(self):
		self.assertTrue(self._can_export(downloadable=frappe._dict(name="f")))

	def test_a_path_with_dot_dot_never_goes_in(self):
		self.assertFalse(
			self._can_export("/private/files/../../site_config.json", downloadable=frappe._dict(name="f"))
		)

	def test_the_export_writes_only_the_filtered_assets(self):
		from os_lms.os_lms import course_export

		zip_module = course_export.course_zip
		course = frappe._dict(name="course-1", chapters=[])
		with (
			patch.object(frappe, "get_doc", return_value=course),
			patch.object(zip_module, "get_chapters_for_export", return_value=[]),
			patch.object(zip_module, "get_lessons_for_export", return_value=[]),
			patch.object(zip_module, "get_course_instructors", return_value=[]),
			patch.object(zip_module, "get_course_evaluator", return_value=[]),
			patch.object(
				zip_module, "get_course_assets", return_value=["/files/a.png", "/private/files/b.pdf"]
			),
			patch.object(zip_module, "get_course_assessments", return_value=([], [], [])),
			patch.object(course_export, "find_file_by_url", return_value=None),
			patch.object(zip_module, "create_course_zip") as create,
		):
			course_export.export_course_zip("course-1")
		self.assertEqual(create.call_args.args[4], ["/files/a.png"])

	def test_only_who_can_modify_the_course_exports_it(self):
		from os_lms.os_lms import course_export

		with (
			patch.object(course_export, "can_modify_course", return_value=False),
			patch.object(course_export, "export_course_zip") as export,
			self.assertRaises(frappe.PermissionError),
		):
			course_export.export_course_as_zip("course-1")
		export.assert_not_called()

	def test_the_export_button_reaches_the_os_lms_method(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.override_whitelisted_methods["lms.lms.api.export_course_as_zip"],
			"os_lms.os_lms.course_export.export_course_as_zip",
		)

	def test_the_copy_makes_the_same_calls_as_upstream(self):
		"""export_course_zip copies upstream's: fail when upstream changes its steps."""
		from lms.lms import course_import_export
		from os_lms.os_lms import course_export

		self.assertEqual(
			_called_names(course_export.export_course_zip) - {"downloadable_assets"},
			_called_names(course_import_export.export_course_zip),
		)


def _called_names(function) -> set[str]:
	import ast
	import inspect
	import textwrap

	tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
	return {
		node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
		for node in ast.walk(tree)
		if isinstance(node, ast.Call)
	}
