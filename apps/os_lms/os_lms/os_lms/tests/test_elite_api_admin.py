"""Elite API key management (the SPA "Elite API" settings tab).

Users are written with ``db_insert`` under fixed ``elite-api-test-`` names and
every in-process test rolls back; the HTTP test deletes exactly what it made.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils import add_days, get_test_client, get_url, today

from os_lms.os_lms.elite_api import admin, keys

P = "elite-api-test-"
# email: (full name, roles). The Gestore bundle is never assigned alone in
# production, but the gate must accept the Gestore role on its own.
USERS = {
	f"{P}sysman@example.com": ("Sara Sistema", ["System Manager"]),
	f"{P}gestore@example.com": ("Giulio Gestore", ["Gestore"]),
	f"{P}moderator@example.com": ("Mara Moderatrice", ["Moderator"]),
	f"{P}docente@example.com": ("Dino Docente", ["Docente", "Course Creator"]),
	f"{P}student@example.com": ("Stella Studente", ["LMS Student"]),
}
SYSMAN, GESTORE, MODERATOR, DOCENTE, STUDENT = USERS


def insert_users():
	for email, (full_name, roles) in USERS.items():
		first_name, last_name = full_name.split(" ")
		frappe.get_doc(
			{
				"doctype": "User",
				"name": email,
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"full_name": full_name,
				"enabled": 1,
				"user_type": "System User",
			}
		).db_insert()
		for role in roles:
			frappe.get_doc(
				{
					"doctype": "Has Role",
					"name": frappe.generate_hash(length=10),
					"parent": email,
					"parenttype": "User",
					"parentfield": "roles",
					"role": role,
				}
			).db_insert()


def forget_cached_roles():
	for email in USERS:
		frappe.cache.hdel("roles", email)


class TestKeyManagement(UnitTestCase):
	def setUp(self):
		try:
			insert_users()
		except Exception:
			frappe.db.rollback()  # tearDown does not run when setUp fails
			raise
		forget_cached_roles()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		forget_cached_roles()

	def test_system_manager_and_gestore_manage_every_key(self):
		frappe.set_user(SYSMAN)
		created = admin.create_key("Made by the system manager")

		frappe.set_user(GESTORE)
		listed = {key["name"]: key for key in admin.list_keys()}
		self.assertIn(created["name"], listed)  # D9: every manager sees every key
		self.assertEqual(listed[created["name"]]["created_by"], "Sara Sistema")

		revoked = admin.revoke_key(created["name"])  # ...and may revoke it
		self.assertEqual((revoked["state"], revoked["revoked_by"]), ("revoked", "Giulio Gestore"))

	def test_everybody_else_is_refused(self):
		frappe.set_user(SYSMAN)
		name = admin.create_key("Someone else's key")["name"]

		for user in (MODERATOR, DOCENTE, STUDENT, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError, msg=user):
				admin.list_keys()
			with self.assertRaises(frappe.PermissionError, msg=user):
				admin.create_key("Not allowed")
			with self.assertRaises(frappe.PermissionError, msg=user):
				admin.revoke_key(name)

	def test_the_full_key_leaves_only_once_and_the_hash_never(self):
		frappe.set_user(GESTORE)
		created = admin.create_key("Shown once")
		secret = keys.parse_key(created["key"])[1]
		stored_hash = frappe.db.get_value(keys.KEY_DOCTYPE, created["name"], "secret_hash")

		self.assertEqual(keys.resolve_key(created["key"]), created["name"])
		self.assertNotIn(stored_hash, frappe.as_json(created))
		listing = frappe.as_json(admin.list_keys())
		for value in (created["key"], secret, stored_hash):
			self.assertNotIn(value, listing)

	def test_states_and_order(self):
		frappe.set_user(GESTORE)
		revoked = admin.create_key("Revoked")["name"]
		admin.revoke_key(revoked)
		expired = admin.create_key("Expired", expires_on=today())["name"]
		frappe.db.set_value(keys.KEY_DOCTYPE, expired, "expires_on", add_days(today(), -1))
		active = admin.create_key("Active", expires_on=add_days(today(), 30))["name"]

		states = {key["name"]: key["state"] for key in admin.list_keys()}
		self.assertEqual((states[active], states[expired], states[revoked]), ("active", "expired", "revoked"))
		self.assertEqual(admin.list_keys()[0]["state"], "active")  # active keys come first

	def test_validation(self):
		frappe.set_user(GESTORE)
		for key_name, expires_on in (
			("", None),
			("   ", None),
			("x" * (admin.MAX_KEY_NAME_LENGTH + 1), None),
			("Past expiry", add_days(today(), -1)),
		):
			with self.assertRaises(frappe.ValidationError, msg=(key_name[:10], expires_on)):
				admin.create_key(key_name, expires_on)
		with self.assertRaises(frappe.DoesNotExistError):
			admin.revoke_key(f"{P}missing")

	def test_can_manage_matches_the_roles(self):
		expected = {SYSMAN: True, GESTORE: True, MODERATOR: False, DOCENTE: False, STUDENT: False}
		for user, allowed in expected.items():
			frappe.set_user(user)
			self.assertEqual(admin.can_manage_elite_api(), allowed, user)


class TestKeysDoNotOpenKeyManagement(FrappeAPITestCase):
	TEST_CLIENT = get_test_client(use_cookies=False)

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		doc, cls.raw_key = keys.generate_key("Admin endpoints test")
		cls.key_name = doc.name
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.db.delete("Elite API Access Log", {"api_key": cls.key_name})
		frappe.db.delete(keys.KEY_DOCTYPE, {"name": cls.key_name})
		frappe.cache.delete_value(f"elite_api:last_used:{cls.key_name}")
		frappe.db.commit()
		super().tearDownClass()

	def test_an_api_key_is_ignored_on_the_management_endpoints(self):
		response = self.get(
			f"{get_url()}/api/method/os_lms.os_lms.elite_api.admin.list_keys",
			headers={"X-Elite-Api-Key": self.raw_key, "X-Forwarded-For": "203.0.113.60"},
		)
		# The key is not even looked at: the request stays anonymous.
		self.assertEqual(response.status_code, 403)
		self.assertFalse(frappe.db.exists("Elite API Access Log", {"api_key": self.key_name}))
