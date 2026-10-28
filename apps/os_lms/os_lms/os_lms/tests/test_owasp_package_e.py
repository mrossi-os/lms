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


class CertificateDoc(frappe._dict):
	def is_new(self):
		return not self.get("name")


class TestE4CertificatesOnlyForTaughtCourses(UnitTestCase):
	def _allowed(self, doc, ptype="create", taught=(), stored=None, evaluator=False, staff=True):
		from os_lms.os_lms import certificate_permissions as perms

		def teaches(course, batch_name, user):
			return (course or batch_name) in taught

		with (
			patch.object(perms, "_is_scoped_staff", return_value=staff),
			patch.object(perms, "_teaches", side_effect=teaches),
			patch.object(perms.frappe.db, "get_value", return_value=stored),
			patch.object(perms, "is_assigned_evaluator", return_value=evaluator),
			patch.object(perms, "evaluates_certificate", return_value=evaluator),
		):
			return perms.has_permission(doc, ptype, "docente@example.com")

	def test_a_certificate_of_a_course_taught_is_allowed(self):
		self.assertTrue(self._allowed(CertificateDoc(course="c1", member="s@example.com"), taught=["c1"]))

	def test_a_certificate_of_another_course_is_refused(self):
		self.assertFalse(self._allowed(CertificateDoc(course="c2", member="s@example.com"), taught=["c1"]))

	def test_a_certificate_with_no_course_nor_batch_is_refused(self):
		self.assertFalse(self._allowed(CertificateDoc(member="s@example.com"), taught=["c1"]))

	def test_a_certificate_cannot_be_moved_from_another_course(self):
		stored = frappe._dict(course="c2", batch_name=None, member="s@example.com", published=0)
		doc = CertificateDoc(name="cert-1", course="c1", member="s@example.com", published=0)
		self.assertFalse(self._allowed(doc, "write", taught=["c1"], stored=stored))

	def test_the_assigned_evaluator_keeps_upstream_rights(self):
		self.assertTrue(self._allowed(CertificateDoc(course="c2", member="s@example.com"), evaluator=True))

	def test_published_certificates_stay_readable(self):
		stored = frappe._dict(course="c2", batch_name=None, member="s@example.com", published=1)
		doc = CertificateDoc(name="cert-1", course="c2", member="s@example.com", published=1)
		self.assertTrue(self._allowed(doc, "read", stored=stored))

	def test_moderator_and_learners_are_not_narrowed(self):
		self.assertTrue(self._allowed(CertificateDoc(member="s@example.com"), staff=False))

	def test_who_is_narrowed(self):
		from os_lms.os_lms import certificate_permissions as perms

		cases = (
			(["Course Creator", "Docente", "Batch Evaluator"], True),
			(["Batch Evaluator"], True),
			(["Moderator", "Course Creator"], False),
			(["System Manager", "Course Creator"], False),
			(["LMS Student"], False),
		)
		for user_roles, narrowed in cases:
			with self.subTest(roles=user_roles), patch.object(frappe, "get_roles", return_value=user_roles):
				self.assertEqual(perms._is_scoped_staff("someone@example.com"), narrowed)

	def test_teaches_means_listed_instructor(self):
		from os_lms.os_lms import certificate_permissions as perms

		with patch.object(perms.frappe.db, "exists", return_value="row") as exists:
			self.assertTrue(perms._teaches("c1", None, "d@example.com"))
			self.assertEqual(exists.call_args.args[1]["parenttype"], "LMS Course")
			self.assertTrue(perms._teaches(None, "b1", "d@example.com"))
			self.assertEqual(exists.call_args.args[1]["parenttype"], "LMS Batch")
		self.assertFalse(perms._teaches(None, None, "d@example.com"))

	def test_the_list_condition_is_valid_sql(self):
		from os_lms.os_lms import certificate_permissions as perms

		with patch.object(perms, "_is_scoped_staff", return_value=True):
			condition = perms.get_permission_query_conditions("nobody-e4@example.invalid")
		frappe.db.sql(f"select count(*) from `tabLMS Certificate` where {condition}")
		with patch.object(perms, "_is_scoped_staff", return_value=False):
			self.assertIsNone(perms.get_permission_query_conditions("admin@example.com"))

	def test_the_hooks_are_registered(self):
		from os_lms import hooks

		module = "os_lms.os_lms.certificate_permissions"
		self.assertEqual(hooks.has_permission["LMS Certificate"], f"{module}.has_permission")
		self.assertEqual(
			hooks.permission_query_conditions["LMS Certificate"], f"{module}.get_permission_query_conditions"
		)


class TestE5FrappeSignUpGoesThroughOurs(UnitTestCase):
	def test_frappe_sign_up_uses_the_os_lms_guard(self):
		from os_lms.os_lms import signup

		with patch.object(signup, "sign_up", return_value=(1, "ok")) as ours:
			self.assertEqual(signup.frappe_sign_up("a@example.com", "A", "/lms"), (1, "ok"))
		ours.assert_called_once_with("a@example.com", "A", verify_terms=False, user_category="")

	def test_the_override_is_registered(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.override_whitelisted_methods["frappe.core.doctype.user.user.sign_up"],
			"os_lms.os_lms.signup.frappe_sign_up",
		)


class TestE6HomeLiveClassesHaveNoHostLink(UnitTestCase):
	def test_the_host_link_is_dropped_and_the_join_link_is_gated(self):
		from os_lms.os_lms import override_api

		classes = [
			frappe._dict(name="lc-1", start_url="https://zoom.us/s/host", join_url="https://zoom.us/j/1"),
			frappe._dict(name="lc-2", start_url=None, join_url=None),
		]
		with patch.object(override_api, "_original_get_my_live_classes", return_value=classes):
			result = override_api.get_my_live_classes()
		self.assertNotIn("start_url", result[0])
		self.assertIn("os_lms.os_lms.api.join_live_class?name=lc-1", result[0].join_url)
		self.assertNotIn("zoom.us", frappe.as_json(result))
		self.assertFalse(result[1].join_url)


class BatchDoc(frappe._dict):
	def get_doc_before_save(self):
		return self.get("before")


class TestE7StudentsAreNotBatchEvaluators(UnitTestCase):
	def _validate(self, now, before=None, students=()):
		from os_lms.os_lms import valutatore

		rows = lambda users: [frappe._dict(valutatore=user) for user in users]  # noqa: E731
		doc = BatchDoc(
			valutatori=rows(now), before=BatchDoc(valutatori=rows(before)) if before is not None else None
		)

		def get_all(doctype, filters=None, pluck=None, **kwargs):
			return [user for user in filters["parent"][1] if user in students]

		with patch.object(valutatore.frappe, "get_all", side_effect=get_all):
			valutatore.validate_batch_valutatori(doc)

	def test_a_student_added_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self._validate(["staff@example.com", "student@example.com"], students=["student@example.com"])

	def test_a_student_already_listed_is_left_alone(self):
		self._validate(["student@example.com"], before=["student@example.com"], students=["student@example.com"])

	def test_staff_added_passes(self):
		self._validate(["staff@example.com"], before=[], students=["student@example.com"])

	def test_the_hook_is_registered(self):
		from os_lms import hooks

		self.assertEqual(
			hooks.doc_events["LMS Batch"]["validate"], "os_lms.os_lms.valutatore.validate_batch_valutatori"
		)


class TestE8ValutatoreSeesOnlyTheirBatchStudents(UnitTestCase):
	def test_the_os_lms_list_conditions_are_valid_sql_on_student_and_course(self):
		from os_lms.os_lms import valutatore

		for doctype, function in (
			("LMS Enrollment", valutatore.enrollment_query_conditions),
			("LMS Course Progress", valutatore.course_progress_query_conditions),
		):
			with (
				self.subTest(doctype=doctype),
				patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
				patch.object(valutatore, "get_valutatore_batches", return_value=["batch-e8"]),
			):
				condition = function("valutatore@example.com")
				self.assertIn(f"`tab{doctype}`.member", condition)
				frappe.db.sql(f"select count(*) from `tab{doctype}` where {condition}")

	def test_by_name_read_needs_the_student_in_the_batch(self):
		from os_lms.os_lms import valutatore

		doc = frappe._dict(course="c1", member="student@example.com")
		for in_batch in (True, False):
			with (
				self.subTest(in_batch=in_batch),
				patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
				patch.object(valutatore, "get_valutatore_batches", return_value=["batch-e8"]),
				patch.object(valutatore, "_batch_reaches_learner", return_value=in_batch) as reaches,
			):
				self.assertEqual(valutatore.course_scoped_has_permission(doc, "read"), in_batch)
				reaches.assert_called_once_with("c1", "student@example.com", ["batch-e8"])

	def test_the_upstream_graft_condition_is_valid_sql(self):
		from lms.lms import permissions

		with patch.object(frappe, "get_roles", return_value=["Valutatore", "LMS Student"]):
			condition = permissions.course_record_query_conditions(
				"valutatore-e8@example.invalid", "LMS Course Progress"
			)
		self.assertIn("LMS Batch Enrollment", condition)
		frappe.db.sql(f"select count(*) from `tabLMS Course Progress` where {condition}")

	def test_the_upstream_graft_single_row_check_runs(self):
		from lms.lms import permissions

		with patch.object(frappe, "get_roles", return_value=["Valutatore"]):
			self.assertFalse(
				permissions._valutatore_reaches_learner("no-course", "nobody@example.invalid", "v@example.invalid")
			)
		self.assertFalse(permissions._valutatore_reaches_learner("c1", None, "v@example.invalid"))


class TestE9ProgrammingExerciseDeletion(UnitTestCase):
	def _delete(self, author):
		from os_lms.os_lms import override_api

		with (
			patch.object(frappe, "only_for"),
			patch("lms.lms.permissions.can_author_assessment", return_value=author),
			patch.object(frappe, "get_all", return_value=["sub-1", "sub-2"]),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			override_api.delete_programming_exercise("ex-1")
		return delete_doc

	def test_someone_else_cannot_delete_it(self):
		with self.assertRaises(frappe.PermissionError):
			self._delete(author=False)

	def test_the_author_deletes_it_leaving_a_trace(self):
		delete_doc = self._delete(author=True)
		self.assertEqual(
			[call.args for call in delete_doc.call_args_list],
			[
				("LMS Programming Exercise Submission", "sub-1"),
				("LMS Programming Exercise Submission", "sub-2"),
				("LMS Programming Exercise", "ex-1"),
			],
		)

	def test_post_only_and_registered(self):
		from os_lms import hooks
		from os_lms.os_lms import override_api

		self.assertEqual(
			frappe.allowed_http_methods_for_whitelisted_func[override_api.delete_programming_exercise], ["POST"]
		)
		self.assertEqual(
			hooks.override_whitelisted_methods["lms.lms.api.delete_programming_exercise"],
			"os_lms.os_lms.override_api.delete_programming_exercise",
		)


class TestE10ProtectedAccountsDeletion(UnitTestCase):
	def _delete(self, caller_roles, target_roles):
		from os_lms.os_lms import override_api

		def get_roles(user=None):
			return target_roles if user else caller_roles

		with (
			patch.object(frappe, "only_for"),
			patch.object(frappe, "get_roles", side_effect=get_roles),
			patch.object(override_api, "_original_delete_member", return_value=True) as original,
		):
			override_api.delete_member("target@example.com")
		return original

	def test_a_gestore_cannot_delete_a_system_manager_or_a_gestore(self):
		for target in (["System Manager"], ["Gestore", "Moderator"]):
			with self.subTest(target=target), self.assertRaises(frappe.PermissionError):
				self._delete(["Gestore", "Moderator"], target)

	def test_a_system_manager_can(self):
		self._delete(["System Manager", "Moderator"], ["Gestore"]).assert_called_once()

	def test_a_plain_account_is_left_to_upstream(self):
		self._delete(["Gestore", "Moderator"], ["LMS Student"]).assert_called_once()


class TestE11ReviewsWithoutEmails(UnitTestCase):
	def _reviews(self, visible):
		from os_lms.os_lms import override_utils

		reviews = [frappe._dict(review="ok", rating=5, owner="s@example.com", owner_details={})]
		with (
			patch.object(override_utils, "guest_access_allowed", return_value=True),
			patch.object(override_utils, "_course_visible", return_value=visible),
			patch.object(override_utils, "_original_get_reviews", return_value=reviews),
		):
			return override_utils.get_reviews("c1")

	def test_no_email_in_the_reply(self):
		result = self._reviews(visible=True)
		self.assertEqual(len(result), 1)
		self.assertNotIn("owner", result[0])

	def test_a_course_the_caller_cannot_see_has_no_reviews(self):
		self.assertEqual(self._reviews(visible=False), [])


class TestE12DiscussionDoctypesSpelledExactly(UnitTestCase):
	def test_another_spelling_is_refused(self):
		from os_lms.os_lms import override_utils

		with patch.object(override_utils, "_original_get_discussion_topics") as original:
			for doctype in ("course lesson", "COURSE LESSON", "LMS Course"):
				with self.subTest(doctype=doctype), self.assertRaises(frappe.PermissionError):
					override_utils.get_discussion_topics(doctype, "lesson-1")
			original.assert_not_called()

	def test_the_exact_doctypes_go_through(self):
		from os_lms.os_lms import override_utils

		with patch.object(override_utils, "_original_get_discussion_topics", return_value=[]) as original:
			override_utils.get_discussion_topics("LMS Batch", "batch-1")
		original.assert_called_once_with("LMS Batch", "batch-1", False)

	def test_replies_follow_the_stored_doctype(self):
		from os_lms.os_lms import override_utils

		for stored, allowed in (("course lesson", False), ("Course Lesson", True), (None, False)):
			with (
				self.subTest(stored=stored),
				patch.object(override_utils.frappe.db, "get_value", return_value=stored),
				patch.object(override_utils, "_original_get_discussion_replies", return_value=[]),
			):
				if allowed:
					override_utils.get_discussion_replies("topic-1")
				else:
					with self.assertRaises(frappe.PermissionError):
						override_utils.get_discussion_replies("topic-1")


class TestE13IngestionOnlyForCourseEditors(UnitTestCase):
	def test_an_enrolled_student_cannot_start_it(self):
		from os_lms.os_lms.ai.ingestion import api

		with (
			patch.object(api.frappe.db, "get_value", return_value="c1"),
			patch.object(api, "can_modify_course", return_value=False),
			self.assertRaises(frappe.PermissionError),
		):
			api._load_lesson("lesson-1")

	def test_a_course_editor_can(self):
		from os_lms.os_lms.ai.ingestion import api

		with (
			patch.object(api.frappe.db, "get_value", return_value="c1"),
			patch.object(api, "can_modify_course", return_value=True),
			patch.object(api.frappe, "get_doc", return_value="lesson") as get_doc,
		):
			self.assertEqual(api._load_lesson("lesson-1"), "lesson")
		get_doc.assert_called_once_with("Course Lesson", "lesson-1")

	def test_post_only(self):
		from os_lms.os_lms.ai.ingestion import api

		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.start_lesson_ingestion], ["POST"])


class TestE17ExternalCallsHaveATimeout(UnitTestCase):
	FILES = (
		"os_lms/os_lms/google_calendar.py",
		"os_lms/os_lms/ai/utils/transcriber/vimeo.py",
		"lms/lms/utils.py",
		"lms/unsplash.py",
		"lms/lms/doctype/lms_batch/lms_batch.py",
		"lms/lms/doctype/lms_live_class/lms_live_class.py",
	)

	def test_every_requests_call_has_a_timeout(self):
		import ast

		missing = []
		for relative in self.FILES:
			app = "os_lms" if relative.startswith("os_lms/") else "lms"
			path = frappe.get_app_path(app, "..", relative)
			for node in ast.walk(ast.parse(open(path).read())):
				if (
					isinstance(node, ast.Call)
					and isinstance(node.func, ast.Attribute)
					and isinstance(node.func.value, ast.Name)
					and node.func.value.id == "requests"
					and node.func.attr in ("get", "post", "put", "patch", "delete", "request")
					and not any(keyword.arg == "timeout" for keyword in node.keywords)
				):
					missing.append(f"{relative}:{node.lineno}")
		self.assertEqual(missing, [])

	def test_the_country_lookup_never_fails_the_sign_up(self):
		import requests
		from lms.lms import utils

		with patch.object(utils.requests, "get", side_effect=requests.ConnectionError) as get:
			self.assertIsNone(utils.get_country_code())
		self.assertEqual(get.call_args.kwargs["timeout"], 3)


class TestE20RoleChangesLeaveATrace(UnitTestCase):
	def _save_role(self, value, has_role):
		from os_lms.os_lms import override_api

		with (
			patch.object(override_api, "assert_can_assign_role"),
			patch.object(override_api.frappe.db, "exists", return_value=has_role),
			patch.object(override_api.frappe, "new_doc"),
			patch.object(override_api.frappe.db, "delete"),
			patch.object(override_api.frappe, "clear_cache"),
			patch.object(override_api, "log_role_change") as log,
		):
			override_api.save_role("user@example.com", "Docente", value)
		return log

	def test_grant_and_revoke_are_logged(self):
		self._save_role(1, has_role=False).assert_called_once_with("user@example.com", "Docente", granted=True)
		self._save_role(0, has_role=True).assert_called_once_with("user@example.com", "Docente", granted=False)

	def test_no_change_no_row(self):
		self._save_role(1, has_role=True).assert_not_called()
		self._save_role(0, has_role=False).assert_not_called()

	def test_the_batch_sync_is_logged(self):
		from os_lms.os_lms import valutatore

		with (
			patch.object(valutatore.frappe.db, "exists", return_value=False),
			patch.object(valutatore.frappe, "new_doc"),
			patch.object(valutatore.frappe, "clear_cache"),
			patch.object(valutatore, "log_role_change") as log,
		):
			valutatore._ensure_role("user@example.com", "Valutatore")
		log.assert_called_once_with("user@example.com", "Valutatore", granted=True)

	def test_the_row_says_who_whom_and_which_role(self):
		from os_lms.os_lms import role_audit

		with patch.object(role_audit.frappe, "get_doc") as get_doc:
			role_audit.log_role_change("user@example.com", "Gestore", granted=True)
		row = get_doc.call_args.args[0]
		self.assertEqual(row["doctype"], "Activity Log")
		self.assertEqual(row["user"], frappe.session.user)
		self.assertEqual((row["reference_doctype"], row["reference_name"]), ("User", "user@example.com"))
		self.assertIn("Gestore", row["subject"])
		get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)
