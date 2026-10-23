"""Self-service account deletion (ESG point 3): nothing of the user survives,
nothing of anyone else is lost.

The acceptance check is ``find_traces``: after the erasure no text column of
any table contains the user's email. Every record is written under fixed
``acct-del-test-`` names and the whole test rolls back; ``erase_user`` commits,
so commit is patched out.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils.password import update_password

from os_lms.os_lms import account_deletion
from os_lms.os_lms.account_deletion import erase_user, find_traces

P = "acct-del-test-"
STUDENT = f"{P}student@example.com"
TEACHER = f"{P}teacher@example.com"
# Contains STUDENT as a substring: a LIKE match must never take it for STUDENT.
BYSTANDER = f"x{P}student@example.com"
PASSWORD = "Acct-Del-Test-9!q"
COURSE = f"{P}course"


def insert(values: dict) -> None:
	frappe.get_doc(values).db_insert()
	# db_insert stamps the session user as owner whatever the dict says.
	if "owner" in values:
		frappe.db.set_value(values["doctype"], values["name"], "owner", values["owner"], update_modified=False)


def make_user(email: str, first_name: str, roles=("LMS Student",)) -> None:
	# db_insert, not insert: User.insert commits on its way (a first run left
	# its user behind), which would defeat the rollback. The Contact Frappe
	# creates for a new user is written by hand instead.
	insert(
		{
			"doctype": "User",
			"name": email,
			"email": email,
			"first_name": first_name,
			"last_name": "Test",
			"full_name": f"{first_name} Test",
			"user_type": "Website User",
			"enabled": 1,
		}
	)
	for role in roles:
		row = frappe.get_doc(
			{"doctype": "Has Role", "parent": email, "parenttype": "User", "parentfield": "roles", "role": role}
		)
		row.set_new_name()
		row.db_insert()
	contact = f"{P}contact-{first_name.lower()}"
	insert({"doctype": "Contact", "name": contact, "first_name": first_name, "email_id": email, "user": email})
	row = frappe.get_doc(
		{
			"doctype": "Contact Email",
			"parent": contact,
			"parenttype": "Contact",
			"parentfield": "email_ids",
			"email_id": email,
		}
	)
	row.set_new_name()
	row.db_insert()


class AccountDeletionCase(UnitTestCase):
	def setUp(self):
		super().setUp()
		# A cleanup, not tearDown: it also runs when setUp itself fails, which
		# would otherwise leave the half-built fixture for the runner to commit.
		self.addCleanup(frappe.db.rollback)
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Administrator")
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)

		make_user(STUDENT, "Student")
		make_user(BYSTANDER, "Bystander")
		make_user(TEACHER, "Teacher", roles=("LMS Student", "Docente", "Course Creator", "Batch Evaluator"))
		update_password(STUDENT, PASSWORD)

		insert({"doctype": "Course Evaluator", "name": TEACHER, "evaluator": TEACHER, "full_name": "Teacher Test"})
		insert(
			{
				"doctype": "LMS Course",
				"name": COURSE,
				"title": "Account deletion test",
				"evaluator": TEACHER,
				"owner": TEACHER,
				"modified_by": TEACHER,
			}
		)
		row = frappe.get_doc(
			{
				"doctype": "Course Instructor",
				"parent": COURSE,
				"parenttype": "LMS Course",
				"parentfield": "instructors",
				"instructor": TEACHER,
			}
		)
		row.set_new_name()
		row.db_insert()


class TestStudentErasure(AccountDeletionCase):
	def setUp(self):
		super().setUp()
		for member, suffix in ((STUDENT, "s"), (BYSTANDER, "b")):
			insert(
				{
					"doctype": "LMS Enrollment",
					"name": f"{P}enrollment-{suffix}",
					"course": COURSE,
					"member": member,
					"member_name": "Name Test",
				}
			)
		insert({"doctype": "LMS Course Progress", "name": f"{P}progress", "course": COURSE, "member": STUDENT})
		insert({"doctype": "LMS Quiz Submission", "name": f"{P}quiz", "course": COURSE, "member": STUDENT})
		insert({"doctype": "LMS Lesson Note", "name": f"{P}note", "member": STUDENT, "note": "my note"})
		insert({"doctype": "LMSA Query Log", "name": f"{P}ai", "member": STUDENT, "course": COURSE})
		insert(
			{
				"doctype": "LMS Certificate",
				"name": f"{P}certificate",
				"course": COURSE,
				"member": STUDENT,
				"evaluator": TEACHER,
			}
		)
		insert(
			{
				"doctype": "TrueSkills Issue Log",
				"name": f"{P}issue",
				"lms_certificate": f"{P}certificate",
				"recipient_email": STUDENT,
				"recipient_name": "Student Test",
			}
		)
		# A topic someone else answered stays; a lone one goes with its author.
		insert({"doctype": "Discussion Topic", "name": f"{P}topic-shared", "title": "Shared", "owner": STUDENT})
		insert({"doctype": "Discussion Reply", "name": f"{P}reply-own", "topic": f"{P}topic-shared", "reply": "mine", "owner": STUDENT})
		insert({"doctype": "Discussion Reply", "name": f"{P}reply-other", "topic": f"{P}topic-shared", "reply": "theirs", "owner": TEACHER})
		insert({"doctype": "Discussion Topic", "name": f"{P}topic-lone", "title": "Lone", "owner": STUDENT})
		insert({"doctype": "Comment", "name": f"{P}comment", "comment_type": "Comment", "comment_email": STUDENT, "content": "hi"})
		insert({"doctype": "Activity Log", "name": f"{P}login", "user": STUDENT, "subject": "logged in", "owner": STUDENT})
		insert({"doctype": "Communication", "name": f"{P}mail-student", "recipients": f"Student <{STUDENT}>", "subject": "s"})
		insert({"doctype": "Communication", "name": f"{P}mail-bystander", "recipients": BYSTANDER, "subject": "b"})
		insert(
			{
				"doctype": "File",
				"name": f"{P}orphan-file",
				"file_name": "answer.png",
				"file_url": f"/private/files/{P}answer.png",
				"is_private": 1,
				"owner": STUDENT,
			}
		)
		# A restore copy about the student, and one the student only created.
		insert(
			{
				"doctype": "Deleted Document",
				"name": f"{P}deleted-about",
				"deleted_doctype": "LMS Enrollment",
				"deleted_name": f"{P}old-enrollment",
				"data": json.dumps({"member": STUDENT, "owner": STUDENT}),
			}
		)
		insert(
			{
				"doctype": "Deleted Document",
				"name": f"{P}deleted-by",
				"deleted_doctype": "LMS Enrollment",
				"deleted_name": f"{P}other-enrollment",
				"data": json.dumps({"member": BYSTANDER, "owner": STUDENT}),
			}
		)
		# Frappe stamps the session user into every Error Log it writes. Error Log
		# is a MyISAM table: no rollback, so the row is removed by name.
		self.addCleanup(frappe.db.delete, "Error Log", {"name": f"{P}error"})
		insert(
			{
				"doctype": "Error Log",
				"name": f"{P}error",
				"method": "Error in translation file",
				"error": f"Traceback: {STUDENT} and {BYSTANDER}",
				"metadata": json.dumps({"user": STUDENT}),
			}
		)

	def test_leaves_no_trace_of_the_student(self):
		# The sweep has to see the fixture first, or an empty result proves nothing.
		before = {table for table, _ in find_traces(STUDENT)}
		self.assertTrue({"tabUser", "tabLMS Enrollment", "tabTrueSkills Issue Log", "tabDeleted Document"} <= before)

		erase_user(STUDENT, notify=False)

		self.assertFalse(frappe.db.exists("User", STUDENT))
		self.assertEqual(find_traces(STUDENT), [])

	def test_keeps_what_belongs_to_others(self):
		erase_user(STUDENT, notify=False)

		self.assertTrue(frappe.db.exists("LMS Enrollment", f"{P}enrollment-b"))
		self.assertTrue(frappe.db.exists("Communication", f"{P}mail-bystander"))
		self.assertTrue(frappe.db.exists("Discussion Reply", f"{P}reply-other"))
		self.assertEqual(frappe.db.get_value("Discussion Topic", f"{P}topic-shared", "owner"), "Administrator")
		self.assertFalse(frappe.db.exists("Discussion Topic", f"{P}topic-lone"))
		kept = json.loads(frappe.db.get_value("Deleted Document", f"{P}deleted-by", "data"))
		self.assertEqual(kept, {"member": BYSTANDER, "owner": "Administrator"})
		self.assertFalse(frappe.db.exists("Deleted Document", f"{P}deleted-about"))
		self.assertTrue(frappe.db.exists("User", BYSTANDER))
		error = frappe.db.get_value("Error Log", f"{P}error", ["error", "metadata"], as_dict=True)
		self.assertEqual(error.error, f"Traceback: [deleted user] and {BYSTANDER}")
		self.assertEqual(json.loads(error.metadata), {"user": "[deleted user]"})


class TestTeacherErasure(AccountDeletionCase):
	def setUp(self):
		super().setUp()
		insert(
			{
				"doctype": "LMS Assignment Submission",
				"name": f"{P}graded",
				"member": BYSTANDER,
				"evaluator": TEACHER,
				"status": "Pass",
			}
		)
		insert(
			{
				"doctype": "LMS Certificate",
				"name": f"{P}bystander-certificate",
				"course": COURSE,
				"member": BYSTANDER,
				"evaluator": TEACHER,
				"evaluator_name": "Teacher Test",
			}
		)
		insert({"doctype": "LMS Live Class", "name": f"{P}live", "title": "Live", "host": TEACHER})
		insert(
			{
				"doctype": "LMSA Simulation Scenario",
				"name": f"{P}scenario",
				"title": "Scenario",
				"created_by_instructor": TEACHER,
			}
		)

	def test_keeps_the_records_of_others_without_the_teacher(self):
		erase_user(TEACHER, notify=False)

		self.assertIsNone(frappe.db.get_value("LMS Assignment Submission", f"{P}graded", "evaluator"))
		certificate = frappe.db.get_value(
			"LMS Certificate", f"{P}bystander-certificate", ["evaluator", "evaluator_name"], as_dict=True
		)
		self.assertEqual(certificate, {"evaluator": None, "evaluator_name": None})
		self.assertEqual(frappe.db.get_value("LMS Live Class", f"{P}live", "host"), "Administrator")
		self.assertIsNone(frappe.db.get_value("LMSA Simulation Scenario", f"{P}scenario", "created_by_instructor"))

		course = frappe.db.get_value("LMS Course", COURSE, ["evaluator", "owner", "modified_by"], as_dict=True)
		self.assertEqual(course, {"evaluator": None, "owner": "Administrator", "modified_by": "Administrator"})
		self.assertFalse(frappe.db.exists("Course Instructor", {"parent": COURSE, "instructor": TEACHER}))
		self.assertFalse(frappe.db.exists("Course Evaluator", TEACHER))

	def test_leaves_no_trace_of_the_teacher(self):
		erase_user(TEACHER, notify=False)

		self.assertEqual(find_traces(TEACHER), [])


class TestDeleteMyAccount(AccountDeletionCase):
	def call(self, user: str, secret: str):
		frappe.set_user(user)
		# One parent mock records the order of logout, session clearing and queueing.
		steps = MagicMock()
		with (
			patch.object(frappe.local, "login_manager", steps.login_manager, create=True),
			patch.object(account_deletion.frappe, "enqueue", steps.enqueue),
			patch("frappe.sessions.clear_sessions", steps.clear_sessions),
		):
			result = account_deletion.delete_my_account(secret)
		frappe.set_user("Administrator")
		return result, steps

	def test_administrator_cannot_delete_itself(self):
		with self.assertRaises(frappe.PermissionError):
			self.call("Administrator", "anything")

	def test_wrong_password_changes_nothing(self):
		with self.assertRaises(frappe.ValidationError):
			self.call(STUDENT, "wrong")
		self.assertEqual(frappe.db.get_value("User", STUDENT, "enabled"), 1)

	def test_right_password_disables_logs_out_and_queues(self):
		result, steps = self.call(STUDENT, PASSWORD)

		self.assertEqual(result, {"queued": True})
		self.assertEqual(frappe.db.get_value("User", STUDENT, "enabled"), 0)
		steps.login_manager.logout.assert_called_once_with(user=STUDENT)
		self.assertEqual(steps.enqueue.call_args.kwargs["user"], STUDENT)
		# Queued after the logout: logging out commits and writes Activity Logs,
		# which a job queued earlier would run ahead of and leave behind.
		self.assertEqual(
			[call[0] for call in steps.mock_calls],
			["login_manager.logout", "clear_sessions", "enqueue"],
		)

	def test_account_without_password_confirms_with_an_emailed_code(self):
		frappe.set_user(TEACHER)
		with patch.object(account_deletion.frappe, "sendmail") as sendmail:
			self.assertEqual(account_deletion.start_account_deletion(), {"method": "code"})
		code = next(word for word in sendmail.call_args.kwargs["message"].replace("<b>", " ").replace("</b>", " ").split() if word.isdigit())

		with self.assertRaises(frappe.ValidationError):
			self.call(TEACHER, "000000" if code != "000000" else "111111")
		result, _ = self.call(TEACHER, code)
		self.assertEqual(result, {"queued": True})
