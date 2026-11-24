"""The batch Valutatore observes live classes and never starts them.

Since 84571a094 the card gave the Valutatore Start/Open and start_live_class let them
start the class and open the Zoom host link. Decision of 2026-11-23: the Valutatore
only observes. start_live_class refuses them; join_live_class lets them in as an
observer, with the participant link (join_url), never the host link (start_url).
"""

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime

from os_lms.os_lms import api, os_audit

NAME = "live-class-valutatore-observer-test"
BATCH = "valutatore-observer-batch"
VALUTATORE = "valutatore-observer@example.com"
JOIN_URL = "https://zoom.us/j/111"
START_URL = "https://zoom.us/s/111?zak=host-token"


def _live_class(**values):
	start = now_datetime() - timedelta(minutes=10)
	doc = frappe._dict(
		doctype="LMS Live Class",
		name=NAME,
		batch_name=BATCH,
		date=start.date().isoformat(),
		time=start.strftime("%H:%M:%S"),
		duration=60,
		status="Published",
		started_at=None,
		join_url=JOIN_URL,
		start_url=START_URL,
	)
	doc.update(values)
	return doc


def _gates(*, roles, author=False, valutatore=False):
	"""Patch who the user is: their roles, whether they author the batch and whether
	they are its Valutatore. Nobody is enrolled in or tagged on the batch."""
	return (
		patch.object(frappe, "get_roles", return_value=roles),
		patch("lms.lms.permissions.can_author_batch", return_value=author),
		patch("lms.lms.utils.is_batch_valutatore", return_value=valutatore),
		patch("os_lms.os_lms.valutatore.is_batch_valutatore", return_value=valutatore),
	)


class TestValutatoreCannotStart(UnitTestCase):
	def test_start_live_class_refuses_the_batch_valutatore(self):
		roles, author, lms_valutatore, os_valutatore = _gates(
			roles=["Valutatore", "LMS Student"], valutatore=True
		)
		with (
			roles,
			author,
			lms_valutatore,
			os_valutatore,
			patch.dict(frappe.session, {"user": VALUTATORE}),
			patch.object(frappe, "get_doc", return_value=_live_class()),
			patch.object(frappe.db, "set_value") as set_value,
			patch.object(os_audit, "on_live_class_start") as audit_start,
		):
			with self.assertRaises(frappe.PermissionError):
				api.start_live_class(NAME)
		set_value.assert_not_called()
		audit_start.assert_not_called()

	def test_hosts_still_start(self):
		cases = {
			"Moderator": dict(roles=["Moderator"]),
			"Batch Evaluator": dict(roles=["Batch Evaluator"]),
			# Docente and tagged instructors pass through can_author_batch.
			"batch author": dict(roles=["Docente"], author=True),
			# A Valutatore who also authors the batch hosts it as its author.
			"author and Valutatore": dict(roles=["Docente", "Valutatore"], author=True, valutatore=True),
		}
		for label, case in cases.items():
			with self.subTest(user=label):
				roles, author, lms_valutatore, os_valutatore = _gates(**case)
				with roles, author, lms_valutatore, os_valutatore:
					api._ensure_can_start_live_class(_live_class())


class TestValutatoreJoinsAsObserver(UnitTestCase):
	def _exists(self, doctype, *args, **kwargs):
		# The class exists; the Valutatore is neither tagged on nor enrolled in its batch.
		return doctype == "LMS Live Class"

	def test_access_tier_is_observer(self):
		roles, author, lms_valutatore, os_valutatore = _gates(roles=["Valutatore"], valutatore=True)
		with roles, author, lms_valutatore, os_valutatore, patch.object(frappe.db, "exists", self._exists):
			self.assertEqual(api._live_class_access(_live_class(), VALUTATORE), "observer")

	def test_join_redirects_to_the_participant_link_before_the_host_starts(self):
		roles, author, lms_valutatore, os_valutatore = _gates(roles=["Valutatore"], valutatore=True)
		response = frappe.local.response
		saved = {key: response.get(key) for key in ("type", "location")}
		try:
			with (
				roles,
				author,
				lms_valutatore,
				os_valutatore,
				patch.dict(frappe.session, {"user": VALUTATORE}),
				patch.object(frappe.db, "exists", self._exists),
				patch.object(frappe, "get_doc", return_value=_live_class()),
				patch.object(os_audit, "on_live_class_join") as audit_join,
			):
				api.join_live_class(NAME)
			self.assertEqual(response.get("type"), "redirect")
			self.assertEqual(response.get("location"), JOIN_URL)
			audit_join.assert_called_once()
		finally:
			response.update(saved)
