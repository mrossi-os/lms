"""Our roles inside the permission gates upstream added in v2.64.0.

The new gates only know Administrator/System Manager/Moderator, Course Instructor
rows, content authors and enrolled members. Client decisions at the v2.64.0 merge:
- a "Docente" is a global instructor everywhere (like the can_modify_course graft);
- a "Valutatore" keeps reading the courses of the batches they evaluate, drafts too;
- program members read every course of their program;
- Moderator, Course Creator and Docente edit every program.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import permissions, utils
from lms.lms.doctype.lms_program import lms_program


class FakeDoc(frappe._dict):
	def is_new(self):
		return not self.get("name")


def roles(*names):
	return patch.object(frappe, "get_roles", return_value=list(names))


class TestDocenteIsGlobal(UnitTestCase):
	def test_docente_edits_content_authored_by_someone_else(self):
		doc = FakeDoc(doctype="LMS Quiz", name="quiz-1")
		with (
			roles("Docente"),
			patch.object(permissions, "has_moderator_role", return_value=False),
			patch.object(permissions, "is_content_author", return_value=False),
		):
			self.assertTrue(permissions.has_authored_content_permission(doc, "write", "docente@example.com"))

	def test_plain_course_creator_still_limited_to_own_content(self):
		doc = FakeDoc(doctype="LMS Quiz", name="quiz-1")
		with (
			roles("Course Creator"),
			patch.object(permissions, "has_moderator_role", return_value=False),
			patch.object(permissions, "is_content_author", return_value=False),
		):
			self.assertFalse(permissions.has_authored_content_permission(doc, "write", "cc@example.com"))

	def test_docente_authors_every_course_for_served_files(self):
		with roles("Docente"), patch.object(permissions, "has_moderator_role", return_value=False):
			self.assertEqual(
				permissions.courses_authored_by("docente@example.com", ["c1", "c2"]), {"c1", "c2"}
			)

	def test_docente_is_unscoped_in_course_lists(self):
		with roles("Docente"):
			self.assertIsNone(permissions._course_read_condition("docente@example.com"))

	def test_docente_lists_drafts(self):
		with roles("Docente"), patch.object(utils, "has_moderator_role", return_value=False):
			self.assertTrue(utils.can_list_unpublished("docente@example.com"))


class TestValutatoreReadsTheirCourses(UnitTestCase):
	def test_list_condition_includes_evaluated_batches(self):
		with roles("Valutatore"):
			condition = permissions._course_read_condition("valutatore@example.com")
		self.assertIn("LMS Batch Valutatore", permissions._render(condition))

	def test_student_list_condition_does_not(self):
		with roles("LMS Student"):
			condition = permissions._course_read_condition("student@example.com")
		self.assertNotIn("LMS Batch Valutatore", permissions._render(condition))

	def _can_access(self, valutatore=False, program_member=False):
		with (
			patch.object(permissions.frappe.db, "get_value", return_value=0),
			patch.object(permissions, "can_author_course", return_value=False),
			patch.object(permissions, "is_course_valutatore", return_value=valutatore),
			patch.object(permissions, "is_course_in_member_program", return_value=program_member),
			patch.object(permissions, "get_membership", return_value=None),
		):
			return permissions.can_access_course("draft-course", user="someone@example.com")

	def test_valutatore_reads_unpublished_course(self):
		self.assertTrue(self._can_access(valutatore=True))

	def test_program_member_reads_unpublished_course(self):
		self.assertTrue(self._can_access(program_member=True))

	def test_outsider_does_not(self):
		self.assertFalse(self._can_access())

	def _record_permission(self, ptype):
		doc = FakeDoc(doctype="LMS Course Progress", name="prog-1", member="student@example.com", course="c1")
		stored = frappe._dict(member="student@example.com", course="c1")
		with (
			patch.object(permissions, "_course_read_condition", return_value="narrowed"),
			patch.object(permissions.frappe.db, "get_value", return_value=stored),
			patch.object(permissions, "can_author_course", return_value=False),
			patch.object(permissions, "is_course_valutatore", return_value=True),
		):
			return permissions.course_record_has_permission(doc, ptype, "valutatore@example.com")

	def test_valutatore_reads_learner_progress(self):
		self.assertTrue(self._record_permission("read"))

	def test_valutatore_never_writes_learner_progress(self):
		self.assertFalse(self._record_permission("write"))

	def test_scoped_list_flag_keeps_drafts(self):
		filters = {}
		with (
			patch.object(utils, "can_list_unpublished", return_value=False),
			patch.dict(frappe.flags, {"oslms_valutatore_scoped_list": True}),
		):
			utils.restrict_to_published(filters, self_scoped=False)
		self.assertNotIn("published", filters)

	def test_without_flag_drafts_are_pinned_away(self):
		filters = {}
		with (
			patch.object(utils, "can_list_unpublished", return_value=False),
			patch.dict(frappe.flags, {"oslms_valutatore_scoped_list": False}),
		):
			utils.restrict_to_published(filters, self_scoped=False)
		self.assertEqual(filters["published"], 1)

	def test_os_lms_wrapper_raises_and_restores_the_flag(self):
		from os_lms.os_lms import override_utils

		with (
			patch.object(override_utils, "_only_scoped_valutatore", return_value=True),
			patch.dict(frappe.flags, {"oslms_valutatore_scoped_list": None}),
		):
			with override_utils._valutatore_scoped_list():
				self.assertTrue(frappe.flags.oslms_valutatore_scoped_list)
			self.assertIsNone(frappe.flags.oslms_valutatore_scoped_list)

	def test_valutatore_and_program_member_read_the_outline(self):
		for valutatore, member in ((True, False), (False, True)):
			with (
				patch.object(utils.frappe.db, "get_value", return_value=0),
				patch.object(utils.frappe, "session", frappe._dict(user="someone@example.com")),
				patch.object(utils, "can_modify_course", return_value=False),
				patch.object(utils, "get_membership", return_value=None),
				patch.object(utils, "is_course_valutatore", return_value=valutatore),
				patch.object(utils, "is_course_in_member_program", return_value=member),
			):
				self.assertTrue(utils.can_view_course("draft-course"))


class TestProgramsAreAPool(UnitTestCase):
	def test_authoring_roles_edit_every_program(self):
		doc = FakeDoc(doctype="LMS Program", name="program-1")
		for role in ("Course Creator", "Docente"):
			with roles(role):
				self.assertTrue(lms_program.has_program_authoring_permission(doc, "write", "x@example.com"))

	def test_student_does_not(self):
		doc = FakeDoc(doctype="LMS Program", name="program-1")
		with roles("LMS Student"):
			self.assertFalse(lms_program.has_program_authoring_permission(doc, "write", "s@example.com"))
