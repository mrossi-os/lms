"""Deleting a live class drops its calendar Event without re-checking Event permissions.

The site's Event Custom DocPerm grants delete to Tutor only, so the upstream after_delete
(which deletes the Event as the caller) refused every batch manager. The class deletion
itself already passed LMS Live Class permissions (live-class-delete-drops-event-unchecked).
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.overrides.lms_live_class import CustomLMSLiveClass


class TestLiveClassDeleteDropsEvent(UnitTestCase):
	def _after_delete(self, event):
		doc = frappe.get_doc({"doctype": "LMS Live Class", "event": event})
		with patch.object(frappe, "delete_doc") as delete_doc:
			CustomLMSLiveClass.after_delete(doc)
		return delete_doc

	def test_the_linked_event_goes_without_event_permissions(self):
		delete_doc = self._after_delete("EV-TEST-1")
		delete_doc.assert_called_once_with("Event", "EV-TEST-1", force=True, ignore_permissions=True)

	def test_a_class_without_event_deletes_nothing_else(self):
		self._after_delete(None).assert_not_called()

	def test_the_site_uses_the_override(self):
		self.assertIsInstance(frappe.get_doc({"doctype": "LMS Live Class"}), CustomLMSLiveClass)
