import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.simulations.eval.permissions import (
	user_is_course_instructor,
	require_scenario_access,
)


class TestPermissions(IntegrationTestCase):
	def setUp(self):
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_scenario_with_instructor,
		)
		self.scenario, self.instructor, self.outsider = (
			make_scenario_with_instructor()
		)

	def test_instructor_is_recognised(self):
		self.assertTrue(
			user_is_course_instructor(self.instructor.name, self.scenario.lms_course)
		)

	def test_outsider_is_not_instructor(self):
		self.assertFalse(
			user_is_course_instructor(self.outsider.name, self.scenario.lms_course)
		)

	def test_require_access_passes_for_owner(self):
		frappe.set_user(self.scenario.owner)
		# Should not raise.
		require_scenario_access(self.scenario.name)

	def test_require_access_raises_for_outsider(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			require_scenario_access(self.scenario.name)
