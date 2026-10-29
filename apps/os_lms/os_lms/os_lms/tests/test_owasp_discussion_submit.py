"""submit_discussion saves with the caller's permissions (OWASP M-06).

Frappe's website method, whitelisted for any logged-in user, rewrote a Discussion
Reply by name with ignore_permissions: a student of the batch could change what a
teacher or another student had written, still shown under their name. It also
opened topics on any document. Everything runs inside the test transaction and is
rolled back.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase
from lms.lms.api import give_discussions_permission

from os_lms import hooks
from os_lms.os_lms import override_utils

FRAPPE_METHOD = "frappe.website.doctype.discussion_topic.discussion_topic.submit_discussion"
AUTHOR = "discussion-author@example.com"
OTHER = "discussion-other@example.com"
OUTSIDER = "discussion-outsider@example.com"
BATCH = "discussion-submit-test-batch"
TOPIC = "discussion-submit-test-topic"
REPLY = "discussion-submit-test-reply"


def _student(email: str) -> None:
	if frappe.db.exists("User", email):
		return
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "Discussion", "send_welcome_email": 0}
	)
	user.append("roles", {"role": "LMS Student"})
	user.insert(ignore_permissions=True)


class TestSubmitDiscussionPermissions(UnitTestCase):
	def setUp(self):
		give_discussions_permission()
		for email in (AUTHOR, OTHER, OUTSIDER):
			_student(email)
		frappe.get_doc({"doctype": "LMS Batch", "name": BATCH, "title": "Discussion test"}).db_insert()
		for member in (AUTHOR, OTHER):
			enrollment = {"name": f"{BATCH}-{member}", "batch": BATCH, "member": member}
			frappe.get_doc({"doctype": "LMS Batch Enrollment", **enrollment}).db_insert()
		frappe.get_doc(
			{
				"doctype": "Discussion Topic",
				"name": TOPIC,
				"title": "Topic",
				"reference_doctype": "LMS Batch",
				"reference_docname": BATCH,
			}
		).db_insert()
		frappe.get_doc(
			{"doctype": "Discussion Reply", "name": REPLY, "topic": TOPIC, "reply": "<p>original</p>"}
		).db_insert()
		# db_insert stamps the session user as owner, and if_owner is what is under test.
		frappe.db.set_value("Discussion Topic", TOPIC, "owner", AUTHOR, update_modified=False)
		frappe.db.set_value("Discussion Reply", REPLY, "owner", AUTHOR, update_modified=False)
		frappe.clear_cache(doctype="Discussion Reply")
		frappe.clear_cache(doctype="Discussion Topic")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _submit(self, user: str, **kwargs):
		frappe.set_user(user)
		args = {"doctype": "LMS Batch", "docname": BATCH, "reply": "<p>new</p>", "title": "New topic"}
		args.update(kwargs)
		return override_utils.submit_discussion(**args)

	def test_frappe_method_is_overridden(self):
		self.assertEqual(
			hooks.override_whitelisted_methods.get(FRAPPE_METHOD),
			"os_lms.os_lms.override_utils.submit_discussion",
		)

	def test_frappe_original_lets_another_member_rewrite(self):
		# The hole the override closes: keeps this setup honest if Frappe ever fixes it.
		from frappe.website.doctype.discussion_topic.discussion_topic import submit_discussion

		frappe.set_user(OTHER)
		submit_discussion("LMS Batch", BATCH, "<p>rewritten</p>", "t", reply_name=REPLY)
		self.assertEqual(frappe.db.get_value("Discussion Reply", REPLY, "reply"), "<p>rewritten</p>")

	def test_another_member_cannot_rewrite_a_reply(self):
		with self.assertRaises(frappe.PermissionError):
			self._submit(OTHER, reply="<p>rewritten</p>", reply_name=REPLY)
		self.assertEqual(frappe.db.get_value("Discussion Reply", REPLY, "reply"), "<p>original</p>")

	def test_the_author_edits_their_own_reply(self):
		self._submit(AUTHOR, reply="<p>edited</p>", reply_name=REPLY)
		self.assertEqual(frappe.db.get_value("Discussion Reply", REPLY, "reply"), "<p>edited</p>")

	def test_a_member_replies_to_an_existing_topic(self):
		self.assertEqual(self._submit(OTHER, topic_name=TOPIC), TOPIC)
		owners = frappe.get_all("Discussion Reply", {"topic": TOPIC}, pluck="owner")
		self.assertCountEqual(owners, [AUTHOR, OTHER])

	def test_no_reply_to_a_batch_the_user_is_not_in(self):
		with self.assertRaises(frappe.ValidationError):
			self._submit(OUTSIDER, topic_name=TOPIC)
		self.assertEqual(frappe.db.count("Discussion Reply", {"topic": TOPIC}), 1)

	def test_no_topic_on_a_batch_the_user_is_not_in(self):
		with self.assertRaises(frappe.PermissionError):
			self._submit(OUTSIDER)
		self.assertEqual(frappe.db.count("Discussion Topic", {"reference_docname": BATCH}), 1)

	def test_no_topic_outside_the_discussion_doctypes(self):
		for doctype in ("User", "lms batch"):
			with self.subTest(doctype=doctype), self.assertRaises(frappe.PermissionError):
				self._submit(AUTHOR, doctype=doctype, docname=AUTHOR)
		self.assertFalse(frappe.db.exists("Discussion Topic", {"reference_docname": AUTHOR}))

	def test_a_member_opens_a_topic_on_their_batch(self):
		topic = self._submit(AUTHOR)
		self.assertEqual(frappe.db.get_value("Discussion Topic", topic, "owner"), AUTHOR)
		self.assertEqual(frappe.db.get_value("Discussion Reply", {"topic": topic}, "owner"), AUTHOR)
