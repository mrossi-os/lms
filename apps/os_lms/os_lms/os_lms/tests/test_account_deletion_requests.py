"""Account deletion on request (LMS Settings review on) and privacy policy
acceptance.

Builds on the fixture of test_account_deletion (fixed ``acct-del-test-``
names, everything rolled back, commit patched out). The review flag and the
policy URL are patched, never written: a Single value written in a rolled-back
transaction would stay in the cache.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, getdate, now_datetime
from frappe.utils.password import update_password

from os_lms.os_lms import account_deletion, account_deletion_requests, privacy_consent, signup
from os_lms.os_lms.account_deletion import erase_user, find_traces
from os_lms.os_lms.tests.test_account_deletion import (
	PASSWORD,
	STUDENT,
	TEACHER,
	AccountDeletionCase,
	P,
	make_user,
)

GESTORE = f"{P}gestore@example.com"
MODERATOR = f"{P}moderator@example.com"
SYSTEM_MANAGER = f"{P}sysman@example.com"
DOCTYPE = account_deletion_requests.DOCTYPE
POLICY_URL = "https://example.com/privacy"


class ReviewCase(AccountDeletionCase):
	def setUp(self):
		super().setUp()
		review = patch.object(account_deletion_requests, "review_enabled", return_value=True)
		review.start()
		self.addCleanup(review.stop)
		make_user(GESTORE, "Gestore", roles=("Gestore", "Moderator", "Docente", "Course Creator"))
		make_user(MODERATOR, "Moderator", roles=("Moderator",))
		make_user(SYSTEM_MANAGER, "Sysman", roles=("System Manager",))
		sendmail = patch.object(frappe, "sendmail")
		self.sendmail = sendmail.start()
		self.addCleanup(sendmail.stop)

	def as_user(self, user: str):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def delete_my_account(self, user: str, secret: str):
		frappe.set_user(user)
		steps = MagicMock()
		with (
			patch.object(frappe.local, "login_manager", steps.login_manager, create=True),
			patch.object(frappe, "enqueue", steps.enqueue),
			patch("frappe.sessions.clear_sessions", steps.clear_sessions),
		):
			result = account_deletion.delete_my_account(secret)
		frappe.set_user("Administrator")
		return result, steps

	def file(self, user: str = STUDENT, due_in: int = 60) -> str:
		frappe.set_user("Administrator")
		name = account_deletion_requests.file_request(user)["name"]
		frappe.db.set_value(DOCTYPE, name, "due_on", add_days(getdate(), due_in))
		self.sendmail.reset_mock()
		return name


class TestFilingARequest(ReviewCase):
	def test_password_files_a_request_and_keeps_the_account(self):
		result, steps = self.delete_my_account(STUDENT, PASSWORD)

		self.assertTrue(result["requested"])
		request = frappe.get_doc(DOCTYPE, result["pending"]["name"])
		self.assertEqual((request.user, request.status), (STUDENT, "Pending"))
		self.assertEqual(getdate(request.due_on), add_days(getdate(), 60))
		self.assertEqual(frappe.db.get_value("User", STUDENT, "enabled"), 1)
		steps.login_manager.logout.assert_not_called()
		steps.enqueue.assert_not_called()

	def test_managers_are_told_without_who_asked(self):
		self.delete_my_account(STUDENT, PASSWORD)

		self.sendmail.assert_called_once()
		recipients = self.sendmail.call_args.kwargs["recipients"]
		self.assertIn(frappe.db.get_value("User", GESTORE, "email"), recipients)
		self.assertNotIn(STUDENT, self.sendmail.call_args.kwargs["message"])

	def test_wrong_password_files_nothing(self):
		with self.assertRaises(frappe.ValidationError):
			self.delete_my_account(STUDENT, "wrong")
		self.assertFalse(frappe.db.exists(DOCTYPE, {"user": STUDENT}))

	def test_a_second_request_is_the_first_one(self):
		first, _ = self.delete_my_account(STUDENT, PASSWORD)
		second, _ = self.delete_my_account(STUDENT, PASSWORD)

		self.assertEqual(first["pending"]["name"], second["pending"]["name"])
		self.assertEqual(frappe.db.count(DOCTYPE, {"user": STUDENT}), 1)

	def test_the_dialog_shows_the_pending_request_without_sending_a_code(self):
		self.file()
		self.as_user(STUDENT)

		result = account_deletion.start_account_deletion()

		self.assertEqual(result["mode"], "request")
		self.assertNotIn("method", result)
		self.sendmail.assert_not_called()

	def test_a_gestore_deletes_directly(self):
		update_password(GESTORE, PASSWORD)

		result, steps = self.delete_my_account(GESTORE, PASSWORD)

		self.assertEqual(result, {"queued": True})
		self.assertEqual(steps.enqueue.call_args.kwargs["user"], GESTORE)
		self.assertFalse(frappe.db.exists(DOCTYPE, {"user": GESTORE}))

	def test_the_user_withdraws(self):
		name = self.file()
		self.as_user(STUDENT)

		account_deletion_requests.withdraw_my_request()

		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "status"), "Withdrawn")
		with self.assertRaises(frappe.ValidationError):
			account_deletion_requests.withdraw_my_request()


class TestReview(ReviewCase):
	def test_only_managers_list_and_decide(self):
		name = self.file()
		for user in (MODERATOR, TEACHER, STUDENT):
			frappe.set_user(user)
			with self.subTest(user=user):
				with self.assertRaises(frappe.PermissionError):
					account_deletion_requests.get_requests()
				with self.assertRaises(frappe.PermissionError):
					account_deletion_requests.approve_request(name)
				with self.assertRaises(frappe.PermissionError):
					account_deletion_requests.reject_request(name, "no")
		frappe.set_user(GESTORE)
		pending = account_deletion_requests.get_requests()["pending"]
		frappe.set_user("Administrator")
		self.assertEqual([row.name for row in pending if row.user == STUDENT], [name])
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "status"), "Pending")

	def test_approval_queues_the_erasure(self):
		name = self.file()
		frappe.set_user(GESTORE)
		with (
			patch.object(frappe, "enqueue") as enqueue,
			patch("frappe.sessions.clear_sessions") as clear_sessions,
		):
			account_deletion_requests.approve_request(name)
		frappe.set_user("Administrator")

		request = frappe.db.get_value(DOCTYPE, name, ["status", "decided_by"], as_dict=True)
		self.assertEqual(request, {"status": "Approved", "decided_by": GESTORE})
		self.assertEqual(frappe.db.get_value("User", STUDENT, "enabled"), 0)
		clear_sessions.assert_called_once_with(user=STUDENT, force=True)
		self.assertEqual(enqueue.call_args.kwargs["user"], STUDENT)

	def test_a_decided_request_cannot_be_decided_again(self):
		name = self.file()
		frappe.set_user(GESTORE)
		account_deletion_requests.reject_request(name, "Open invoices")
		with self.assertRaises(frappe.ValidationError):
			account_deletion_requests.approve_request(name)

	def test_rejection_needs_a_reason_and_reaches_the_user(self):
		name = self.file()
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.ValidationError):
			account_deletion_requests.reject_request(name, "   ")

		account_deletion_requests.reject_request(name, "Open <b>invoices</b>")

		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "status"), "Rejected")
		self.assertEqual(self.sendmail.call_args.kwargs["recipients"], [STUDENT])
		self.assertIn("Open &lt;b&gt;invoices&lt;/b&gt;", self.sendmail.call_args.kwargs["message"])
		self.assertEqual(frappe.db.get_value("User", STUDENT, "enabled"), 1)

	def test_nobody_decides_their_own_request(self):
		name = self.file(GESTORE)
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.PermissionError):
			account_deletion_requests.approve_request(name)

	def test_a_gestore_cannot_approve_a_system_manager(self):
		name = self.file(SYSTEM_MANAGER)
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.PermissionError):
			account_deletion_requests.approve_request(name)

	def test_the_request_outlives_the_erased_account_without_the_user(self):
		name = self.file()
		frappe.db.set_value(
			DOCTYPE, name, {"status": "Approved", "decided_by": GESTORE, "decided_on": now_datetime()}
		)

		erase_user(STUDENT, notify=False)
		erase_user(GESTORE, notify=False)

		request = frappe.db.get_value(DOCTYPE, name, ["status", "user", "full_name", "decided_by"], as_dict=True)
		self.assertEqual(request, {"status": "Approved", "user": None, "full_name": None, "decided_by": None})
		self.assertEqual(find_traces(STUDENT), [])
		self.assertEqual(find_traces(GESTORE), [])


class TestReminders(ReviewCase):
	def remind(self):
		self.sendmail.reset_mock()
		account_deletion_requests.send_reminders()
		return self.sendmail.call_count

	def test_a_week_before_on_the_day_and_every_week_after(self):
		for due_in, reminded in ((10, False), (7, True), (3, False), (0, True), (-3, False), (-14, True)):
			with self.subTest(due_in=due_in):
				frappe.db.delete(DOCTYPE, {"user": STUDENT})
				self.file(due_in=due_in)
				self.assertEqual(self.remind(), int(reminded))

	def test_once_a_day(self):
		self.file(due_in=7)
		self.assertEqual(self.remind(), 1)
		self.assertEqual(self.remind(), 0)

	def test_decided_requests_are_not_reminded(self):
		name = self.file(due_in=0)
		frappe.db.set_value(DOCTYPE, name, "status", "Rejected")
		self.assertEqual(self.remind(), 0)


class TestDeleteMember(ReviewCase):
	def test_a_plain_moderator_no_longer_deletes_users(self):
		from os_lms.os_lms import override_api

		frappe.set_user(MODERATOR)
		with patch.object(override_api, "_original_delete_member") as original:
			with self.assertRaises(frappe.PermissionError):
				override_api.delete_member(STUDENT)
		original.assert_not_called()

	def test_a_gestore_deletes_a_student(self):
		from os_lms.os_lms import override_api

		frappe.set_user(GESTORE)
		with patch.object(override_api, "_original_delete_member", return_value=True) as original:
			override_api.delete_member(STUDENT)
		original.assert_called_once_with(STUDENT)


class TestPrivacyConsent(AccountDeletionCase):
	def setUp(self):
		super().setUp()
		for module in (privacy_consent, signup):
			url = patch.object(module, "get_privacy_policy_url", return_value=POLICY_URL)
			url.start()
			self.addCleanup(url.stop)

	def test_required_until_accepted(self):
		self.assertTrue(privacy_consent.is_consent_required(STUDENT))
		self.assertFalse(privacy_consent.is_consent_required("Administrator"))

		frappe.set_user(STUDENT)
		privacy_consent.accept_privacy_policy()
		frappe.set_user("Administrator")

		user = frappe.db.get_value(
			"User", STUDENT, ["privacy_accepted_url", "privacy_accepted_via", "privacy_accepted_on"], as_dict=True
		)
		self.assertEqual((user.privacy_accepted_url, user.privacy_accepted_via), (POLICY_URL, "Login"))
		self.assertIsNotNone(user.privacy_accepted_on)
		self.assertFalse(privacy_consent.is_consent_required(STUDENT))

	def test_not_required_without_a_policy(self):
		with patch.object(privacy_consent, "get_privacy_policy_url", return_value=""):
			self.assertFalse(privacy_consent.is_consent_required(STUDENT))

	def test_sign_up_refuses_without_the_box(self):
		with patch.object(signup, "lms_sign_up") as lms_sign_up:
			code, _message = signup.sign_up(f"{P}new@example.com", "New", 0, "")
		self.assertEqual(code, 0)
		lms_sign_up.assert_not_called()

	def test_sign_up_records_the_acceptance(self):
		def create(email, *args):
			make_user(email, "New")
			return 1, "ok"

		with (
			patch.object(signup, "lms_sign_up", side_effect=create),
			patch.object(signup, "_limit_message", return_value=None),
		):
			code, _message = signup.sign_up(f"{P}new@example.com", "New", 0, "", accept_privacy=1)

		self.assertEqual(code, 1)
		self.assertEqual(frappe.db.get_value("User", f"{P}new@example.com", "privacy_accepted_via"), "Signup")

	def test_frappe_s_form_gives_way_to_the_copy_with_the_box(self):
		with patch("lms.plugins.show_custom_signup", return_value=privacy_consent.FRAPPE_SIGNUP_TEMPLATE):
			template = privacy_consent.signup_form_template()
		self.assertEqual(template, privacy_consent.SIGNUP_WITH_PRIVACY_TEMPLATE)
		# The template reads the URL itself: login.py renders it without a context.
		# A plain function: Jinja's sandbox refuses to call a MagicMock.
		with patch.object(frappe.db, "get_single_value", new=lambda *args, **kwargs: POLICY_URL):
			html = frappe.render_template(template, {})
		self.assertIn('id="signup-privacy"', html)
		self.assertIn(f'href="{POLICY_URL}"', html)
		self.assertNotIn('class="form-signin form-signup"', html)

	def test_lms_s_form_stays_since_it_has_the_box(self):
		with patch("lms.plugins.show_custom_signup", return_value="lms/templates/signup-form.html"):
			self.assertEqual(privacy_consent.signup_form_template(), "lms/templates/signup-form.html")

	def test_upstream_s_choice_without_a_policy(self):
		with (
			patch.object(privacy_consent, "get_privacy_policy_url", return_value=""),
			patch("lms.plugins.show_custom_signup", return_value=privacy_consent.FRAPPE_SIGNUP_TEMPLATE),
		):
			self.assertEqual(privacy_consent.signup_form_template(), privacy_consent.FRAPPE_SIGNUP_TEMPLATE)
