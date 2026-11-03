"""Who manages and reviews simulations, with the role bundles used on the
platform (docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 5).

Rows are written with db_insert and deleted by exact name: the access rules
read only the child tables and the batch enrollments, never the parents."""
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations import access
from os_lms.os_lms.doctype.lmsa_simulation_debrief import lmsa_simulation_debrief as debrief_hooks
from os_lms.os_lms.doctype.lmsa_simulation_scenario import lmsa_simulation_scenario as scenario_hooks
from os_lms.os_lms.doctype.lmsa_simulation_session import lmsa_simulation_session as session_hooks

GESTORE = "acc-test-gestore@example.com"
DOCENTE = "acc-test-docente@example.com"
DOCENTE_WITHOUT_COURSES = "acc-test-docente-idle@example.com"
VALUTATORE = "acc-test-valutatore@example.com"
MODERATOR = "acc-test-moderator@example.com"
STUDENT_IN_BATCH = "acc-test-student-in@example.com"
STUDENT_OUTSIDE = "acc-test-student-out@example.com"

DOCENTE_COURSE = "acc-test-course-docente"
BATCH_COURSE = "acc-test-course-batch"
BATCH = "acc-test-batch"

ROLES = {
	GESTORE: ["Gestore", "Moderator", "Docente", "Course Creator", "Batch Evaluator"],
	DOCENTE: ["Docente", "Batch Evaluator"],
	DOCENTE_WITHOUT_COURSES: ["Docente", "Batch Evaluator"],
	VALUTATORE: ["Valutatore"],
	MODERATOR: ["Moderator"],
	STUDENT_IN_BATCH: ["LMS Student"],
	STUDENT_OUTSIDE: ["LMS Student"],
}

ROWS = [
	(
		"Course Instructor",
		{
			"name": "acc-test-instructor",
			"parent": DOCENTE_COURSE,
			"parenttype": "LMS Course",
			"parentfield": "instructors",
			"instructor": DOCENTE,
		},
	),
	(
		"LMS Batch Valutatore",
		{
			"name": "acc-test-valutatore",
			"parent": BATCH,
			"parenttype": "LMS Batch",
			"parentfield": "valutatori",
			"valutatore": VALUTATORE,
		},
	),
	(
		"Batch Course",
		{
			"parent": BATCH,
			"parenttype": "LMS Batch",
			"parentfield": "courses",
			"course": BATCH_COURSE,
		},
	),
	(
		"LMS Batch Enrollment",
		{"name": "acc-test-enrollment", "batch": BATCH, "member": STUDENT_IN_BATCH},
	),
]


def _roles():
	return patch.object(frappe, "get_roles", side_effect=lambda user=None: ROLES.get(user, []))


class TestSimulationAccess(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Batch Course is autonamed with an integer: keep what the insert gave.
		cls.inserted = []
		for doctype, values in ROWS:
			doc = frappe.get_doc({"doctype": doctype, **values})
			doc.db_insert()
			cls.inserted.append((doctype, doc.name))

	@classmethod
	def tearDownClass(cls):
		for doctype, name in cls.inserted:
			frappe.db.delete(doctype, {"name": name})
		super().tearDownClass()

	def test_gestore_bundle_reaches_everything(self):
		with _roles():
			self.assertTrue(access.has_full_access(GESTORE))
			self.assertIsNone(access.managed_courses(GESTORE))
			self.assertTrue(access.can_manage_course(BATCH_COURSE, GESTORE))
			self.assertTrue(access.can_review(DOCENTE_COURSE, STUDENT_OUTSIDE, GESTORE))

	def test_docente_manages_and_reviews_only_their_courses(self):
		with _roles():
			self.assertFalse(access.has_full_access(DOCENTE))
			self.assertEqual(access.managed_courses(DOCENTE), {DOCENTE_COURSE})
			self.assertTrue(access.may_author(DOCENTE))
			self.assertTrue(access.can_review(DOCENTE_COURSE, STUDENT_OUTSIDE, DOCENTE))
			self.assertFalse(access.can_manage_course(BATCH_COURSE, DOCENTE))
			self.assertFalse(access.can_review(BATCH_COURSE, STUDENT_IN_BATCH, DOCENTE))

	def test_docente_listed_on_no_course_gets_nothing(self):
		with _roles():
			self.assertEqual(access.managed_courses(DOCENTE_WITHOUT_COURSES), set())
			self.assertFalse(access.may_author(DOCENTE_WITHOUT_COURSES))

	def test_valutatore_manages_the_batch_courses_and_reviews_only_its_students(self):
		with _roles():
			self.assertEqual(access.managed_courses(VALUTATORE), {BATCH_COURSE})
			self.assertTrue(access.may_author(VALUTATORE))
			self.assertTrue(access.can_review(BATCH_COURSE, STUDENT_IN_BATCH, VALUTATORE))
			self.assertFalse(access.can_review(BATCH_COURSE, STUDENT_OUTSIDE, VALUTATORE))
			self.assertFalse(access.can_manage_course(DOCENTE_COURSE, VALUTATORE))

	def test_valutatore_who_also_teaches_the_course_reviews_every_student(self):
		ROLES_BOTH = {**ROLES, VALUTATORE: ["Valutatore", "Docente"]}
		row = frappe.get_doc(
			{
				"doctype": "Course Instructor",
				"name": "acc-test-instructor-2",
				"parent": BATCH_COURSE,
				"parenttype": "LMS Course",
				"parentfield": "instructors",
				"instructor": VALUTATORE,
			}
		)
		row.db_insert()
		try:
			with patch.object(frappe, "get_roles", side_effect=lambda user=None: ROLES_BOTH.get(user, [])):
				self.assertTrue(access.can_review(BATCH_COURSE, STUDENT_OUTSIDE, VALUTATORE))
		finally:
			frappe.db.delete("Course Instructor", {"name": row.name})

	def test_moderator_alone_and_students_get_nothing(self):
		for user in (MODERATOR, STUDENT_IN_BATCH):
			with self.subTest(user), _roles():
				self.assertFalse(access.has_full_access(user))
				self.assertFalse(access.may_author(user))
				self.assertFalse(access.can_manage_course(BATCH_COURSE, user))
				self.assertFalse(access.can_review(BATCH_COURSE, STUDENT_IN_BATCH, user))

	def test_reviewers_are_the_instructors_and_the_student_batch_valutatori(self):
		with _roles():
			self.assertEqual(access.reviewers_of(DOCENTE_COURSE, STUDENT_OUTSIDE), {DOCENTE})
			self.assertEqual(access.reviewers_of(BATCH_COURSE, STUDENT_IN_BATCH), {VALUTATORE})
			# Not in the batch: nobody reviews the session from a batch
			self.assertEqual(access.reviewers_of(BATCH_COURSE, STUDENT_OUTSIDE), set())
			self.assertEqual(access.reviewers_of(None, STUDENT_IN_BATCH), set())

	def test_reviewers_leave_out_gestori_and_the_student(self):
		ROLES_STUDENT_TEACHES = {**ROLES, STUDENT_IN_BATCH: ["LMS Student", "Docente"]}
		rows = [
			{"name": "acc-test-instructor-gestore", "instructor": GESTORE},
			{"name": "acc-test-instructor-student", "instructor": STUDENT_IN_BATCH},
			{"name": "acc-test-instructor-moderator", "instructor": MODERATOR},
		]
		for values in rows:
			frappe.get_doc(
				{
					"doctype": "Course Instructor",
					"parent": DOCENTE_COURSE,
					"parenttype": "LMS Course",
					"parentfield": "instructors",
					**values,
				}
			).db_insert()
		try:
			with patch.object(
				frappe, "get_roles", side_effect=lambda user=None: ROLES_STUDENT_TEACHES.get(user, [])
			):
				# The Gestore bundle holds Docente, so a Gestore listed as the
				# course instructor is asked like any teacher; a Moderator
				# alone is not, and nobody reviews their own session.
				self.assertEqual(
					access.reviewers_of(DOCENTE_COURSE, STUDENT_IN_BATCH), {DOCENTE, GESTORE}
				)
		finally:
			for values in rows:
				frappe.db.delete("Course Instructor", {"name": values["name"]})

	def test_session_hooks_follow_the_valutatore_batch(self):
		inside = frappe._dict(course=BATCH_COURSE, student=STUDENT_IN_BATCH)
		outside = frappe._dict(course=BATCH_COURSE, student=STUDENT_OUTSIDE)
		with _roles():
			self.assertTrue(session_hooks.has_permission(inside, "read", VALUTATORE))
			self.assertFalse(session_hooks.has_permission(inside, "write", VALUTATORE))
			self.assertFalse(session_hooks.has_permission(outside, "read", VALUTATORE))
			self.assertTrue(session_hooks.has_permission(outside, "read", STUDENT_OUTSIDE))
			self.assertFalse(session_hooks.has_permission(inside, "read", MODERATOR))

			condition = session_hooks.get_permission_query_conditions(VALUTATORE)
			self.assertIn(STUDENT_IN_BATCH, condition)
			self.assertNotIn(STUDENT_OUTSIDE, condition)
			self.assertEqual(session_hooks.get_permission_query_conditions(GESTORE), "")

	def test_debrief_hooks_follow_the_review_scope(self):
		inside = frappe._dict(course=BATCH_COURSE, student=STUDENT_IN_BATCH)
		with _roles():
			self.assertTrue(debrief_hooks.has_permission(inside, "write", VALUTATORE))
			self.assertTrue(debrief_hooks.has_permission(inside, "write", GESTORE))
			self.assertFalse(debrief_hooks.has_permission(inside, "read", MODERATOR))
			self.assertFalse(debrief_hooks.has_permission(inside, "read", STUDENT_IN_BATCH))
			self.assertEqual(debrief_hooks.get_permission_query_conditions(MODERATOR), "1=0")
			self.assertIn(DOCENTE_COURSE, debrief_hooks.get_permission_query_conditions(DOCENTE))

	def test_scenario_hooks_let_valutatore_and_docente_edit_their_courses(self):
		on_batch = frappe._dict(lms_course=BATCH_COURSE, status="Draft", owner=GESTORE)
		on_docente = frappe._dict(lms_course=DOCENTE_COURSE, status="Draft", owner=GESTORE)
		with _roles():
			self.assertTrue(scenario_hooks.has_permission(on_batch, "write", VALUTATORE))
			self.assertFalse(scenario_hooks.has_permission(on_docente, "write", VALUTATORE))
			self.assertTrue(scenario_hooks.has_permission(on_docente, "write", DOCENTE))
			self.assertFalse(scenario_hooks.has_permission(on_batch, "write", MODERATOR))
