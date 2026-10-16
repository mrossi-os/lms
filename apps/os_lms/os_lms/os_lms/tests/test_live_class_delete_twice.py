"""A second delete of the same live class stops before the cancellation emails.

A slow delete (emails, Zoom cleanup) invited a second click: both requests sent the
students a cancellation, then one failed on the row lock of delete_doc with "being
modified by another user" (elite, 2026-10-16). delete_live_class now refuses a class
that is gone or locked before notifying anyone.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import api

NAME = "live-class-delete-twice-test"


class TestLiveClassDeleteTwice(UnitTestCase):
	def test_a_class_already_deleted_is_reported_as_such(self):
		with (
			patch.object(frappe.db, "exists", return_value=None),
			patch.object(api, "_notify_students_class_cancelled") as notify,
		):
			with self.assertRaises(frappe.DoesNotExistError):
				api.delete_live_class(NAME, notify_students=1)
		notify.assert_not_called()

	def test_a_class_another_request_is_deleting_is_refused_before_the_emails(self):
		for lost_race in (frappe.QueryTimeoutError, frappe.QueryDeadlockError):
			with self.subTest(error=lost_race.__name__):
				with (
					patch.object(frappe.db, "exists", return_value=NAME),
					patch.object(api, "_ensure_live_class_admin"),
					patch.object(frappe.db, "get_value", side_effect=lost_race("locked")),
					patch.object(api, "_notify_students_class_cancelled") as notify,
					patch.object(frappe, "delete_doc") as delete_doc,
				):
					with self.assertRaises(frappe.ValidationError):
						api.delete_live_class(NAME, notify_students=1)
				notify.assert_not_called()
				delete_doc.assert_not_called()

	def test_the_row_is_locked_before_the_students_are_notified(self):
		calls = MagicMock()
		doc = frappe._dict(
			title="T", date="2026-10-16", time="10:00", batch_name="B", conferencing_provider=None
		)
		with (
			patch.object(frappe.db, "exists", return_value=NAME),
			patch.object(api, "_ensure_live_class_admin"),
			patch.object(frappe.db, "get_value", calls.lock),
			patch.object(frappe, "get_doc", return_value=doc),
			patch.object(api, "_notify_students_class_cancelled", calls.notify),
			patch.object(frappe, "delete_doc", calls.delete),
			patch.object(frappe.db, "commit"),
		):
			api.delete_live_class(NAME, notify_students=1)

		self.assertEqual([c[0] for c in calls.mock_calls], ["lock", "notify", "delete"])
		calls.lock.assert_called_once_with("LMS Live Class", NAME, "name", for_update=True, wait=False)
