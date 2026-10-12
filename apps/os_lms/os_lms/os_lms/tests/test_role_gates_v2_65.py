"""Our roles inside the permission gates upstream added in v2.65.0.

v2.65.0 routes quizzes, assignments, programming exercises and their submissions
through one "assessment" predicate, batch/live class/batch enrolment authoring through
can_author_batch, and lesson media through courses_authored_by_each. All of them only
know admins, Moderator, tagged instructors/evaluators, authors and enrolled members.
Client decisions at the v2.65.0 merge (the v2.64.0 rules confirmed):
- a "Docente" is a global instructor everywhere;
- a "Valutatore" reads the assessments of their batches and the submissions of their
  batches' students (os_lms.valutatore narrows further), never administers them;
- a Course Creator tagged on a batch manages it (upstream #2845 adopted).
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import permissions
from lms.lms.doctype.lms_batch_enrollment import lms_batch_enrollment
from lms.lms.doctype.lms_live_class import lms_live_class


class FakeDoc(frappe._dict):
	def is_new(self):
		return not self.get("name")


def roles(*names):
	return patch.object(frappe, "get_roles", return_value=list(names))


def no_moderator():
	return patch.object(permissions, "has_moderator_role", return_value=False)


class TestDocenteAuthorsEveryBatch(UnitTestCase):
	def test_docente_authors_an_untagged_batch(self):
		with roles("Docente"), no_moderator():
			self.assertTrue(permissions.can_author_batch("any-batch", user="docente@example.com"))

	def test_untagged_course_creator_does_not(self):
		with (
			roles("Course Creator"),
			no_moderator(),
			patch.object(permissions.frappe.db, "exists", side_effect=lambda doctype, *a, **k: doctype == "LMS Batch"),
		):
			self.assertFalse(permissions.can_author_batch("any-batch", user="cc@example.com"))

	def test_docente_writes_any_live_class(self):
		doc = FakeDoc(doctype="LMS Live Class", name="lc-1", batch_name="b1")
		with roles("Docente"):
			self.assertTrue(lms_live_class.has_permission(doc, "write", "docente@example.com"))

	def test_untagged_batch_evaluator_no_longer_writes_live_classes(self):
		doc = FakeDoc(doctype="LMS Live Class", name="lc-1", batch_name="b1")
		with roles("Batch Evaluator"), patch.object(lms_live_class, "can_author_batch", return_value=False):
			self.assertFalse(lms_live_class.has_permission(doc, "write", "be@example.com"))

	def test_docente_is_unscoped_on_batch_enrolments(self):
		self.assertIn("Docente", lms_batch_enrollment.UNSCOPED_ROLES)


class TestDocenteOnAssessments(UnitTestCase):
	def test_docente_is_unrestricted(self):
		with roles("Docente"), no_moderator():
			self.assertTrue(permissions._is_unrestricted("docente@example.com"))

	def test_course_creator_is_not(self):
		with roles("Course Creator"), no_moderator():
			self.assertFalse(permissions._is_unrestricted("cc@example.com"))

	def test_docente_administers_someone_elses_quiz(self):
		with (
			roles("Docente"),
			no_moderator(),
			patch.object(permissions.frappe.db, "exists", return_value=True),
			patch.object(permissions, "is_content_author", return_value=False),
			patch.object(permissions, "_reaches_through_a_course", return_value=False),
			patch.object(permissions, "_reaches_through_a_batch", return_value=False),
		):
			self.assertTrue(
				permissions.can_administer_assessment("LMS Quiz", "quiz-1", user="docente@example.com")
			)

	def test_docente_uploads_speak_for_every_lesson(self):
		with patch.object(permissions, "blanket_lesson_authors_among", return_value={"docente@example.com"}):
			self.assertEqual(
				permissions.courses_authored_by_each({"docente@example.com"}, ["c1", "c2"]),
				{"docente@example.com": {"c1", "c2"}},
			)

	def test_blanket_authority_is_moderator_or_docente(self):
		with patch.object(permissions.frappe.db, "get_all", return_value=[]) as get_all:
			permissions.blanket_lesson_authors_among({"someone@example.com"})
		self.assertEqual(get_all.call_args.kwargs["filters"]["role"], ("in", ["Moderator", "Docente"]))


class TestValutatoreOnAssessments(UnitTestCase):
	def _reaches(self, *, course_valutatore=False, batch_valutatore=False, role="Valutatore"):
		with (
			roles(role),
			patch.object(permissions, "_course_placements", return_value={"c1": {"l1"}}),
			patch.object(permissions, "_author_only_courses", return_value=set()),
			patch.object(permissions, "_running_batches", return_value=["b1"]),
			patch.object(permissions, "is_course_valutatore", return_value=course_valutatore),
			patch.object(permissions, "is_batch_valutatore", return_value=batch_valutatore),
		):
			return permissions._valutatore_reaches("LMS Quiz", "quiz-1", "valutatore@example.com")

	def test_reads_an_assessment_of_a_course_of_their_batch(self):
		self.assertTrue(self._reaches(course_valutatore=True))

	def test_reads_an_assessment_their_batch_runs(self):
		self.assertTrue(self._reaches(batch_valutatore=True))

	def test_outside_their_batches_does_not(self):
		self.assertFalse(self._reaches())

	def test_without_the_role_does_not(self):
		self.assertFalse(self._reaches(course_valutatore=True, role="LMS Student"))

	def _answer(self, include_members):
		with (
			roles("Valutatore"),
			no_moderator(),
			patch.object(permissions.frappe.db, "exists", return_value=True),
			patch.object(permissions, "is_content_author", return_value=False),
			patch.object(permissions, "_valutatore_reaches", return_value=True),
			patch.object(permissions, "_reaches_through_a_course", return_value=False),
			patch.object(permissions, "_reaches_through_a_batch", return_value=False),
		):
			return permissions._assessment_answer(
				"LMS Quiz", "quiz-1", "valutatore@example.com", include_members=include_members
			)

	def test_valutatore_reads(self):
		self.assertTrue(self._answer(include_members=True))

	def test_valutatore_never_administers(self):
		self.assertFalse(self._answer(include_members=False))

	def test_list_condition_includes_evaluated_batches(self):
		with roles("Valutatore"), no_moderator():
			sql = permissions._assessment_query_conditions("LMS Assignment", "valutatore@example.com")
		self.assertIn("LMS Batch Valutatore", sql)

	def test_student_list_condition_does_not(self):
		with roles("LMS Student"), no_moderator():
			sql = permissions._assessment_query_conditions("LMS Assignment", "student@example.com")
		self.assertNotIn("LMS Batch Valutatore", sql)


class TestValutatoreOnSubmissions(UnitTestCase):
	def test_list_condition_includes_their_students(self):
		with roles("Valutatore"), no_moderator():
			sql = permissions._assessment_submission_query_conditions(
				"LMS Assignment Submission", "valutatore@example.com"
			)
		self.assertIn("LMS Batch Valutatore", sql)

	def test_programming_exercise_submissions_keep_the_upstream_rule(self):
		with roles("Valutatore"), no_moderator():
			sql = permissions._assessment_submission_query_conditions(
				"LMS Programming Exercise Submission", "valutatore@example.com"
			)
		self.assertNotIn("LMS Batch Valutatore", sql)

	def _has_permission(self, doctype, field, of_student):
		doc = FakeDoc(doctype=doctype, name="sub-1", member="student@example.com", **{field: "a-1"})
		stored = frappe._dict(member="student@example.com", **{field: "a-1"})
		with (
			roles("Valutatore"),
			no_moderator(),
			patch.object(permissions.frappe.db, "get_value", return_value=stored),
			patch.object(permissions, "_is_valutatore_of_student", return_value=of_student),
			patch.object(permissions, "can_administer_assessment", return_value=False),
		):
			return permissions.assessment_submission_has_permission(doc, "write", "valutatore@example.com")

	def test_grades_a_submission_of_their_student(self):
		self.assertTrue(self._has_permission("LMS Assignment Submission", "assignment", True))

	def test_not_a_submission_of_someone_else(self):
		self.assertFalse(self._has_permission("LMS Assignment Submission", "assignment", False))

	def test_not_a_programming_exercise_submission(self):
		self.assertFalse(self._has_permission("LMS Programming Exercise Submission", "exercise", True))


class TestValutatoreOnBatchEnrolments(UnitTestCase):
	def _has_permission(self, ptype):
		doc = FakeDoc(doctype="LMS Batch Enrollment", name="enr-1", batch="b1", member="student@example.com")
		stored = frappe._dict(batch="b1", member="student@example.com")
		with (
			roles("Valutatore"),
			patch.object(lms_batch_enrollment.frappe.db, "get_value", return_value=stored),
			patch.object(lms_batch_enrollment, "is_batch_valutatore", return_value=True),
			patch.object(lms_batch_enrollment, "can_author_batch", return_value=False),
		):
			return lms_batch_enrollment.has_permission(doc, ptype, "valutatore@example.com")

	def test_reads_the_enrolments_of_their_batch(self):
		self.assertTrue(self._has_permission("read"))

	def test_never_writes_them(self):
		self.assertFalse(self._has_permission("write"))

	def test_list_condition_includes_their_batches(self):
		with roles("Valutatore"), patch.object(lms_batch_enrollment, "is_site_administrator", return_value=False):
			sql = lms_batch_enrollment.get_permission_query_conditions("valutatore@example.com")
		self.assertIn("LMS Batch Valutatore", sql)


class TestCourseCreatorBatchDocPerms(UnitTestCase):
	def test_rows_added_only_where_missing_on_customised_doctypes(self):
		from os_lms import setup

		def exists(doctype, filters=None, *args, **kwargs):
			if doctype in ("Role", "DocType"):
				return True
			if doctype == "Custom DocPerm":
				# Customised doctypes, with no Course Creator row yet.
				return "role" not in (filters or {})
			return False

		with (
			patch.object(setup.frappe.db, "exists", side_effect=exists),
			patch.object(setup.frappe.db, "commit"),
			patch("frappe.permissions.add_permission") as add_permission,
			patch("frappe.permissions.update_permission_property") as update,
		):
			setup.setup_course_creator_batch_permissions()

		self.assertEqual(
			{call.args[0] for call in add_permission.call_args_list},
			{"LMS Batch", "LMS Live Class", "LMS Batch Enrollment"},
		)
		batch_ptypes = {c.args[3] for c in update.call_args_list if c.args[0] == "LMS Batch"}
		self.assertNotIn("create", batch_ptypes)
		self.assertIn("write", batch_ptypes)


class TestBatchStatsEndpointsFollowCanAuthorBatch(UnitTestCase):
	"""The os_lms batch statistics endpoints admit whoever authors the batch
	(can_author_batch: a Course Creator tagged as a course evaluator included), and
	the batch's Valutatore; nobody else."""

	def _certified_count(self, author: bool, valutatore: bool):
		from os_lms.os_lms import api

		with (
			patch("lms.lms.permissions.can_author_batch", return_value=author),
			patch("lms.lms.utils.is_batch_valutatore", return_value=valutatore),
		):
			return api.get_batch_certified_count("no-such-batch")

	def test_batch_author_passes_the_gate(self):
		self.assertIn("certified_count", self._certified_count(author=True, valutatore=False))

	def test_valutatore_passes_the_gate(self):
		self.assertIn("certified_count", self._certified_count(author=False, valutatore=True))

	def test_anyone_else_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self._certified_count(author=False, valutatore=False)
