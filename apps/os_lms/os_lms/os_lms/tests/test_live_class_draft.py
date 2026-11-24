"""A live class is born as a draft and tells nobody until it is published.

Creating a class used to email the invitation and push the in-app notification to the
whole batch at once. Now every insert is a draft: the meeting and the calendar event are
created, but the students hear nothing (and see nothing) until a manager publishes it.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime

from os_lms.os_lms import api, live_class_draft, live_class_join, live_class_reminders
from os_lms.overrides import lms_live_class

NAME = "live-class-draft-test"


def _slot(days: int) -> dict:
	start = now_datetime() + timedelta(days=days)
	return {"date": start.date().isoformat(), "time": start.strftime("%H:%M:%S")}


def _slot_in(minutes: int) -> dict:
	start = now_datetime() + timedelta(minutes=minutes)
	return {"date": start.date().isoformat(), "time": start.strftime("%H:%M:%S")}


def make_doc(status="Draft", days=2, **values):
	return frappe.get_doc(
		{
			"doctype": "LMS Live Class",
			"name": NAME,
			"title": "Draft test",
			"batch_name": "draft-test-batch",
			"duration": 60,
			"timezone": "Europe/Rome",
			"status": status,
			"conferencing_provider": "Zoom",
			"zoom_account": "draft-test-zoom",
			**_slot(days),
			**values,
		}
	)


class TestDraftLifecycle(UnitTestCase):
	def test_is_draft_treats_empty_status_as_published(self):
		self.assertTrue(live_class_draft.is_draft("Draft"))
		self.assertTrue(live_class_draft.is_draft({"status": "Draft"}))
		for status in ("Published", "", None):
			self.assertFalse(live_class_draft.is_draft(status))

	def test_insert_forces_draft(self):
		doc = make_doc(status="Published")
		doc.before_insert()
		self.assertEqual(doc.status, "Draft")

	def test_creation_sends_nothing(self):
		doc = make_doc()
		with (
			patch.object(frappe.db, "get_value", return_value="draft-test-calendar"),
			patch.object(frappe.db, "set_value"),
			patch.object(frappe, "new_doc", return_value=MagicMock()),
			patch.object(doc, "_send_invitation_safe") as invitation,
			patch.object(doc, "_send_notification_safe") as notification,
		):
			doc.create_calendar_event()
		invitation.assert_not_called()
		notification.assert_not_called()

	def test_publish_sends_invitation_and_notification_once(self):
		doc = make_doc()
		published_at = now_datetime()
		with (
			patch.object(lms_live_class, "now_datetime", return_value=published_at),
			patch.object(doc, "db_set") as db_set,
			patch.object(doc, "_send_invitation_safe") as invitation,
			patch.object(doc, "_send_notification_safe") as notification,
		):
			doc.publish()
		# The publication instant is what the reminders are measured against.
		db_set.assert_called_once_with({"status": "Published", "published_at": published_at})
		invitation.assert_called_once_with()
		notification.assert_called_once_with()

	def test_draft_edit_sends_no_update(self):
		for status, expected_calls in (("Draft", 0), ("Published", 1)):
			with self.subTest(status=status):
				doc = make_doc(status=status)
				before = make_doc(status=status, title="Old title")
				with (
					patch.object(doc, "get_doc_before_save", return_value=before),
					patch.object(frappe, "enqueue") as enqueue,
				):
					doc._handle_class_update()
				self.assertEqual(enqueue.call_count, expected_calls)


class TestPublishEndpoint(UnitTestCase):
	def _publish(self, status, doc):
		with (
			patch.object(api, "_ensure_live_class_admin"),
			patch.object(frappe.db, "get_value", return_value=status) as lock,
			patch.object(frappe, "get_doc", return_value=doc),
			patch.object(doc, "check_permission"),
			patch.object(doc, "publish") as publish,
			patch.object(frappe.db, "commit"),
		):
			try:
				return api.publish_live_class(NAME), publish, lock
			except frappe.ValidationError:
				return None, publish, lock

	def test_publish_locks_the_row_and_publishes(self):
		result, publish, lock = self._publish("Draft", make_doc())
		self.assertEqual(result, {"name": NAME, "status": "Published"})
		publish.assert_called_once_with()
		lock.assert_called_once_with("LMS Live Class", NAME, "status", for_update=True)

	def test_publish_refuses_already_published(self):
		for status in ("Published", None):
			with self.subTest(status=status):
				result, publish, _lock = self._publish(status, make_doc(status=status or ""))
				self.assertIsNone(result)
				publish.assert_not_called()

	def test_publish_refuses_ended_class(self):
		result, publish, _lock = self._publish("Draft", make_doc(days=-1))
		self.assertIsNone(result)
		publish.assert_not_called()


class TestDraftGuards(UnitTestCase):
	def test_start_refuses_draft(self):
		doc = make_doc()
		with (
			patch.object(frappe, "get_doc", return_value=doc),
			patch.object(api, "_ensure_can_start_live_class"),
			patch.object(frappe.db, "set_value") as set_value,
		):
			with self.assertRaises(frappe.ValidationError):
				api.start_live_class(NAME)
		set_value.assert_not_called()

	def test_delete_draft_never_notifies(self):
		doc = frappe._dict(
			title="T",
			date="2026-12-01",
			time="10:00",
			batch_name="B",
			conferencing_provider=None,
			status="Draft",
		)
		with (
			patch.object(frappe.db, "exists", return_value=NAME),
			patch.object(api, "_ensure_live_class_admin"),
			patch.object(api, "_lock_live_class_for_delete"),
			patch.object(frappe, "get_doc", return_value=doc),
			patch.object(api, "_notify_students_class_cancelled") as notify,
			patch.object(frappe, "delete_doc") as delete_doc,
			patch.object(frappe.db, "commit"),
		):
			api.delete_live_class(NAME, notify_students=1)
		notify.assert_not_called()
		delete_doc.assert_called_once()


class TestDraftVisibility(UnitTestCase):
	def test_query_conditions_hide_drafts_from_students(self):
		with (
			patch.object(frappe, "get_roles", return_value=["LMS Student"]),
			patch.object(live_class_draft, "is_site_administrator", return_value=False),
		):
			condition = live_class_draft.query_conditions("student@example.com")
		self.assertIn("'Draft'", condition)
		self.assertIn("tabLMS Batch Valutatore", condition)
		self.assertIn("'student@example.com'", condition)

	def test_staff_query_conditions_unrestricted(self):
		for role in ("Moderator", "Docente", "Batch Evaluator"):
			with self.subTest(role=role):
				with (
					patch.object(frappe, "get_roles", return_value=[role]),
					patch.object(live_class_draft, "is_site_administrator", return_value=False),
				):
					self.assertEqual(live_class_draft.query_conditions("staff@example.com"), "")

	def test_has_permission_denies_student_read_of_draft(self):
		with patch.object(live_class_draft, "can_see_drafts", return_value=False) as can_see:
			self.assertFalse(live_class_draft.has_permission(make_doc(), "read", "s@example.com"))
			self.assertIs(
				live_class_draft.has_permission(make_doc(status="Published"), "read", "s@example.com"),
				True,
			)
		can_see.assert_called_once()

	def test_user_can_access_denies_student_on_draft(self):
		with (
			patch.object(frappe, "get_roles", return_value=["LMS Student"]),
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(live_class_draft, "can_see_drafts", return_value=False),
		):
			self.assertFalse(live_class_join.user_can_access(make_doc(), "s@example.com"))
			self.assertTrue(
				live_class_join.user_can_access(make_doc(status="Published"), "s@example.com")
			)

	def test_reminders_skip_drafts(self):
		with patch.object(frappe, "get_all", return_value=[]) as get_all:
			live_class_reminders.send_live_class_reminders()
		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters.get("status"), ["!=", "Draft"])

	def _run_reminders(self, doc):
		students = [frappe._dict(member="s@example.com", member_name="S")]
		with (
			patch.object(frappe, "get_doc", return_value=doc),
			patch.object(frappe, "get_all", return_value=students),
			patch.object(live_class_reminders, "_build_calendar_links", return_value={}),
			patch.object(live_class_reminders, "_send_reminder_mail") as mail,
			patch.object(doc, "save"),
			patch.object(frappe.db, "commit"),
		):
			live_class_reminders._process_class_reminders(
				frappe._dict(name=NAME), now_datetime(), MagicMock()
			)
		return mail

	def test_reminders_due_before_publication_are_skipped(self):
		# Class in 2 hours, published 30 minutes ago: the 3-hour reminder fell due
		# while it was a draft (skipped), the 2-hour one after the publication (sent),
		# the 1-hour one is still ahead (waits).
		doc = make_doc(
			status="Published",
			published_at=now_datetime() - timedelta(minutes=30),
			**_slot_in(minutes=120),
		)
		for hours in (3, 2, 1):
			doc.append("reminders", {"offset_value": hours, "offset_unit": "Hours"})
		mail = self._run_reminders(doc)
		self.assertEqual(mail.call_count, 1)
		self.assertEqual([bool(r.sent_at) for r in doc.reminders], [False, True, False])

	def test_reminders_of_a_class_without_publication_time_still_catch_up(self):
		# Created before drafts existed: no published_at, the old behaviour holds.
		doc = make_doc(status="", **_slot_in(minutes=120))
		doc.append("reminders", {"offset_value": 3, "offset_unit": "Hours"})
		mail = self._run_reminders(doc)
		self.assertEqual(mail.call_count, 1)

	def test_enrollment_skips_draft_events(self):
		enrollment = frappe.get_doc(
			{"doctype": "LMS Batch Enrollment", "batch": "draft-test-batch", "member": "s@example.com"}
		)
		with patch.object(frappe, "get_all", return_value=[]) as get_all:
			enrollment.add_member_to_live_class()
		filters = get_all.call_args.args[1]
		self.assertEqual(filters.get("status"), ["!=", "Draft"])


# Silence the unused-import linter: the override module must be importable here.
assert lms_live_class
