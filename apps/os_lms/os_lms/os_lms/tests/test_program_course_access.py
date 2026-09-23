"""Program members see and take every course of their program.

The regression these cover: a course added to a program but left unpublished
vanished from the program page for its students (get_course_details returned
{}) and could not be enrolled in ("You cannot enroll in an unpublished course").
A program is published as a whole, so the course's own flag must not matter.
"""

from __future__ import annotations

import frappe

from lms.lms.test_helpers import BaseTestUtils
from lms.lms.utils import get_course_details, is_course_in_member_program

STUDENT = "program-access-student@example.com"
OUTSIDER = "program-access-outsider@example.com"
INSTRUCTOR = "program-access-instructor@example.com"


class TestProgramCourseAccess(BaseTestUtils):
	def setUp(self):
		super().setUp()
		self._create_user(STUDENT, "Program", "Student", ["LMS Student"])
		self._create_user(OUTSIDER, "Program", "Outsider", ["LMS Student"])
		self._create_user(INSTRUCTOR, "Program", "Instructor", ["Course Creator"])
		self.course = self._create_course("Program Access Unpublished Course", instructor=INSTRUCTOR)
		frappe.db.set_value("LMS Course", self.course.name, "published", 0)

		program = frappe.new_doc("LMS Program")
		program.update(
			{
				"title": "Program Access Test Program",
				"published": 0,
				"program_courses": [{"course": self.course.name}],
				"program_members": [{"member": STUDENT}],
			}
		)
		program.insert(ignore_permissions=True)
		self.cleanup_items.append(("LMS Program", program.name))

	def tearDown(self):
		frappe.set_user("Administrator")
		for member in (STUDENT, OUTSIDER):
			enrollment = frappe.db.exists("LMS Enrollment", {"course": self.course.name, "member": member})
			if enrollment:
				frappe.delete_doc("LMS Enrollment", enrollment, force=True)
		super().tearDown()

	def test_member_is_recognised(self):
		self.assertTrue(is_course_in_member_program(self.course.name, STUDENT))
		self.assertFalse(is_course_in_member_program(self.course.name, OUTSIDER))
		self.assertFalse(is_course_in_member_program(self.course.name, "Guest"))

	def test_member_sees_unpublished_course(self):
		frappe.set_user(STUDENT)
		self.assertEqual(get_course_details(self.course.name).name, self.course.name)

	def test_outsider_still_does_not_see_it(self):
		frappe.set_user(OUTSIDER)
		self.assertEqual(get_course_details(self.course.name), {})

	def test_member_can_enroll_in_unpublished_course(self):
		frappe.set_user(STUDENT)
		enrollment = frappe.new_doc("LMS Enrollment")
		enrollment.update({"course": self.course.name, "member": STUDENT})
		enrollment.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("LMS Enrollment", enrollment.name))

	def test_outsider_cannot_enroll_in_unpublished_course(self):
		frappe.set_user(OUTSIDER)
		enrollment = frappe.new_doc("LMS Enrollment")
		enrollment.update({"course": self.course.name, "member": OUTSIDER})
		with self.assertRaises(frappe.ValidationError):
			enrollment.insert(ignore_permissions=True)
