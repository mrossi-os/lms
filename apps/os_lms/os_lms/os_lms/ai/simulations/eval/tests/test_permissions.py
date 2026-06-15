import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.simulations.eval.permissions import require_scenario_access


class TestPermissions(IntegrationTestCase):
	def setUp(self):
		# Reset to Administrator so fixture inserts always pass permission
		# checks regardless of which user the previous test ended with.
		frappe.set_user("Administrator")
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_scenario_with_instructor,
		)
		self.scenario, self.instructor, self.outsider = (
			make_scenario_with_instructor()
		)

	def test_require_access_passes_for_owner(self):
		frappe.set_user(self.scenario.owner)
		# Should not raise.
		require_scenario_access(self.scenario.name)

	def test_require_access_passes_for_instructor(self):
		frappe.set_user(self.instructor.name)
		# Should not raise — instructor of the linked LMS Course.
		require_scenario_access(self.scenario.name)

	def test_require_access_raises_for_outsider(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			require_scenario_access(self.scenario.name)
