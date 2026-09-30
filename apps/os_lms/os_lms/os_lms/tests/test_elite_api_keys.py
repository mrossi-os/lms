"""Elite API keys: generation, verification, revocation, expiry and the client user.

Every test that creates rows undoes them with ``frappe.db.rollback()``: nothing
is ever deleted by filter.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe.core.doctype.log_settings.log_settings import _supports_log_clearing
from frappe.tests import UnitTestCase
from frappe.utils import add_days, now_datetime, today

from os_lms.os_lms.elite_api import keys
from os_lms.setup import setup_elite_api_client


class EliteAPIKeyTestCase(UnitTestCase):
	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()


class TestKeyFormat(EliteAPIKeyTestCase):
	def test_generated_key_has_the_documented_shape(self):
		doc, raw_key = keys.generate_key("Format test")

		prefix, secret = keys.parse_key(raw_key)
		self.assertTrue(raw_key.startswith("elite_"))
		self.assertEqual(prefix, doc.name)
		self.assertEqual(len(prefix), keys.PREFIX_LENGTH)
		self.assertEqual(len(secret), 43)

	def test_only_the_hash_of_the_secret_is_stored(self):
		doc, raw_key = keys.generate_key("Hash test")
		_prefix, secret = keys.parse_key(raw_key)

		stored = frappe.db.get_value(keys.KEY_DOCTYPE, doc.name, "secret_hash")
		self.assertEqual(stored, hashlib.sha256(secret.encode()).hexdigest())
		self.assertNotIn(secret, frappe.as_json(frappe.get_doc(keys.KEY_DOCTYPE, doc.name).as_dict()))

	def test_malformed_keys_are_not_parsed(self):
		for raw in (None, "", "elite_", "other_abcdefghijkl_" + "a" * 43, "elite_short_" + "a" * 43):
			self.assertIsNone(keys.parse_key(raw), raw)


class TestResolveKey(EliteAPIKeyTestCase):
	def test_valid_key_resolves_to_its_name(self):
		doc, raw_key = keys.generate_key("Valid")
		self.assertEqual(keys.resolve_key(raw_key), doc.name)

	def test_wrong_secret_is_rejected(self):
		doc, _raw_key = keys.generate_key("Wrong secret")
		self.assertIsNone(keys.resolve_key(keys.format_key(doc.name, "b" * 43)))

	def test_unknown_prefix_is_rejected(self):
		self.assertIsNone(keys.resolve_key(keys.format_key("A" * keys.PREFIX_LENGTH, "a" * 43)))

	def test_revoked_key_is_rejected(self):
		doc, raw_key = keys.generate_key("Revoked")
		keys.revoke_key(doc.name)

		self.assertIsNone(keys.resolve_key(raw_key))
		revoked = frappe.get_doc(keys.KEY_DOCTYPE, doc.name)
		self.assertEqual(revoked.revoked_by, frappe.session.user)
		self.assertIsNotNone(revoked.revoked_on)

	def test_revoking_twice_keeps_the_first_revocation(self):
		doc, _raw_key = keys.generate_key("Revoked twice")
		first = keys.revoke_key(doc.name).revoked_on
		self.assertEqual(keys.revoke_key(doc.name).revoked_on, first)

	def test_key_is_valid_through_its_expiry_day(self):
		_doc, raw_key = keys.generate_key("Expires today", expires_on=today())
		self.assertIsNotNone(keys.resolve_key(raw_key))

	def test_expired_key_is_rejected(self):
		doc, raw_key = keys.generate_key("Expired", expires_on=today())
		# Simulate the passing of time: the controller forbids changing the date.
		frappe.db.set_value(keys.KEY_DOCTYPE, doc.name, "expires_on", add_days(today(), -1))
		self.assertIsNone(keys.resolve_key(raw_key))


class TestKeyLifetimeIsFinal(EliteAPIKeyTestCase):
	def test_expiry_in_the_past_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			keys.generate_key("Past", expires_on=add_days(today(), -1))

	def test_revoked_key_cannot_be_re_enabled(self):
		doc, _raw_key = keys.generate_key("Re-enable")
		revoked = keys.revoke_key(doc.name)
		revoked.enabled = 1
		with self.assertRaises(frappe.ValidationError):
			revoked.save(ignore_permissions=True)

	def test_expiry_cannot_be_changed(self):
		doc, _raw_key = keys.generate_key("Extend", expires_on=today())
		doc.expires_on = add_days(today(), 30)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_secret_cannot_be_changed(self):
		doc, _raw_key = keys.generate_key("Rotate")
		doc.secret_hash = "0" * 64
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)


class TestAccessLogRetention(EliteAPIKeyTestCase):
	def test_log_settings_can_clear_the_access_log(self):
		self.assertTrue(_supports_log_clearing("Elite API Access Log"))

	def test_old_rows_are_cleared_and_recent_ones_kept(self):
		old = frappe.get_doc({"doctype": "Elite API Access Log", "method": "v1.ping"}).insert(
			ignore_permissions=True
		)
		recent = frappe.get_doc({"doctype": "Elite API Access Log", "method": "v1.ping"}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value(
			"Elite API Access Log",
			old.name,
			"creation",
			add_days(now_datetime(), -91),
			update_modified=False,
		)

		frappe.get_doc("Elite API Access Log", recent.name).clear_old_logs(days=90)

		self.assertFalse(frappe.db.exists("Elite API Access Log", old.name))
		self.assertTrue(frappe.db.exists("Elite API Access Log", recent.name))


class TestClientUserSetup(UnitTestCase):
	"""setup_elite_api_client commits (it runs in after_migrate), so these tests
	only leave behind the state a migrate would create anyway."""

	def test_setup_is_idempotent_and_leaves_a_locked_down_user(self):
		setup_elite_api_client()
		setup_elite_api_client()

		user = frappe.get_doc("User", keys.CLIENT_USER)
		self.assertEqual([row.role for row in user.roles], [keys.CLIENT_ROLE])
		self.assertEqual(user.enabled, 0)
		self.assertEqual(user.user_type, "System User")
		self.assertTrue(frappe.db.get_value("Role", keys.CLIENT_ROLE, "desk_access"))

	def test_roles_added_by_hand_are_removed(self):
		setup_elite_api_client()
		user = frappe.get_doc("User", keys.CLIENT_USER)
		user.append("roles", {"role": "System Manager"})
		user.save(ignore_permissions=True)

		setup_elite_api_client()

		roles = frappe.get_all("Has Role", {"parent": keys.CLIENT_USER, "parenttype": "User"}, pluck="role")
		self.assertEqual(roles, [keys.CLIENT_ROLE])

	def test_access_log_is_registered_in_log_settings(self):
		setup_elite_api_client()
		entries = {row.ref_doctype: row.days for row in frappe.get_single("Log Settings").logs_to_clear}
		self.assertIn("Elite API Access Log", entries)
