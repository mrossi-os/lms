"""Elite API authentication, shared checks and access log, exercised over HTTP.

Requests run in another thread with their own DB connection, so the keys are
committed. Cleanup deletes only what this module created: the keys by exact
name, the access log rows by those key names or by this module's TEST-NET IPs
(RFC 5737, never a real client).
"""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import urlencode

import frappe
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils import add_days, get_test_client, get_url, today

from os_lms.os_lms.elite_api import auth, errors, keys

PING = "os_lms.os_lms.elite_api.v1.ping"
TEST_IPS = [f"203.0.113.{n}" for n in range(1, 30)]


class TestEliteAPIAuth(FrappeAPITestCase):
	# The shared client keeps cookies, which would carry a session from one test
	# into the next; an API client like TrueSkill sends none.
	TEST_CLIENT = get_test_client(use_cookies=False)
	created_keys: list[str]

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.created_keys = []

		cls.valid_name, cls.valid_key = cls._make_key("Auth test valid")
		revoked_name, cls.revoked_key = cls._make_key("Auth test revoked")
		keys.revoke_key(revoked_name)
		expired_name, cls.expired_key = cls._make_key("Auth test expired", expires_on=today())
		frappe.db.set_value(keys.KEY_DOCTYPE, expired_name, "expires_on", add_days(today(), -1))
		frappe.db.commit()

	@classmethod
	def _make_key(cls, key_name, expires_on=None):
		doc, raw_key = keys.generate_key(key_name, expires_on=expires_on)
		cls.created_keys.append(doc.name)
		return doc.name, raw_key

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		log = frappe.qb.DocType("Elite API Access Log")
		frappe.db.delete(log, filters=log.api_key.isin(cls.created_keys))
		frappe.db.delete(log, filters=log.ip_address.isin(TEST_IPS))
		for name in cls.created_keys:
			frappe.delete_doc(keys.KEY_DOCTYPE, name, ignore_permissions=True, force=True)
			frappe.cache.delete_value(f"elite_api:last_used:{name}")
		for ip in TEST_IPS:
			frappe.cache.delete(auth._failed_attempts_cache_key(ip))
		frappe.db.commit()
		super().tearDownClass()

	def call(
		self,
		method=PING,
		raw_key=None,
		ip=TEST_IPS[0],
		version="",
		params=None,
		http="get",
		extra_headers=None,
	):
		prefix = f"api/{version}/method" if version else "api/method"
		url = f"{get_url()}/{prefix}/{method}"
		if params:
			url += "?" + urlencode(params)
		headers = {"X-Forwarded-For": ip}
		if raw_key is not None:
			headers["X-Elite-Api-Key"] = raw_key
		headers.update(extra_headers or {})
		if http == "post":
			return self.post(url, {}, headers=headers)
		return self.get(url, headers=headers)

	# -- authentication ------------------------------------------------------

	def test_valid_key_runs_as_the_disabled_client_user(self):
		response = self.call(raw_key=self.valid_key)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"]["status"], "ok")
		self.assertEqual(response.json["message"]["key_name"], "Auth test valid")
		self.assertEqual(frappe.db.get_value("User", keys.CLIENT_USER, "enabled"), 0)

	def test_every_api_url_form_is_authenticated(self):
		for version, envelope in (("", "message"), ("v1", "message"), ("v2", "data")):
			response = self.call(raw_key=self.valid_key, version=version)
			self.assertEqual(response.status_code, 200, version)
			self.assertEqual(response.json[envelope]["status"], "ok", version)

	def test_unusable_keys_get_the_same_answer(self):
		wrong_secret = keys.format_key(self.valid_name, "x" * 43)
		bodies = []
		for n, raw_key in enumerate((wrong_secret, self.revoked_key, self.expired_key, "garbage"), start=2):
			response = self.call(raw_key=raw_key, ip=TEST_IPS[n])
			self.assertEqual(response.status_code, 401, raw_key)
			bodies.append((response.json["error"], response.json["exc_type"]))
		self.assertEqual(len(set(bodies)), 1)
		self.assertEqual(bodies[0], ("invalid_api_key", "EliteAPIUnauthorized"))

	def test_missing_header_is_refused_by_frappe(self):
		response = self.call()
		self.assertEqual(response.status_code, 403)

	def test_logged_in_session_without_key_gets_no_data(self):
		response = self.call(params={"sid": self.sid}, ip=TEST_IPS[14])
		self.assertEqual(response.status_code, 401)
		self.assertEqual(response.json["error"], "invalid_api_key")

	def test_key_is_ignored_outside_the_elite_api(self):
		response = self.call(method="frappe.auth.get_logged_user", raw_key=self.valid_key)
		self.assertNotEqual(response.json.get("message"), keys.CLIENT_USER)

	def test_non_get_requests_are_refused(self):
		response = self.call(raw_key=self.valid_key, http="post", ip=TEST_IPS[7])
		self.assertEqual(response.status_code, 403)

	def test_errors_never_carry_a_traceback(self):
		# POST fails after authentication, when the request already runs as the
		# client user (a System User, to whom Frappe would send tracebacks).
		response = self.call(raw_key=self.valid_key, http="post", ip=TEST_IPS[8])
		self.assertNotIn("exc", response.json)
		self.assertNotIn("exception", response.json)

	def test_too_many_failed_attempts_never_lock_out_a_valid_key(self):
		ip = TEST_IPS[9]
		for _ in range(auth.FAILED_ATTEMPTS_LIMIT):
			self.assertEqual(self.call(raw_key="garbage", ip=ip).status_code, 401)

		response = self.call(raw_key="garbage", ip=ip)
		self.assertEqual(response.status_code, 429)
		self.assertEqual(response.json["error"], "too_many_failed_attempts")
		# Spoofing the client's IP (X-Forwarded-For) must not lock the client out.
		self.assertEqual(self.call(raw_key=self.valid_key, ip=ip).status_code, 200)

	def test_the_cmd_parameter_cannot_run_another_method(self):
		"""Frappe runs form_dict.cmd before routing /api/ paths (security review, finding 1)."""
		cmd = {"cmd": "frappe.auth.get_logged_user"}
		headers = {"X-Elite-Api-Key": self.valid_key, "X-Forwarded-For": TEST_IPS[15]}
		url = f"{get_url()}/api/method/{PING}"
		for label, response in (
			("GET query", self.get(f"{url}?{urlencode(cmd)}", headers=headers)),
			("POST body", self.post(url, cmd, headers=headers)),
		):
			self.assertEqual(response.status_code, 400, label)
			self.assertEqual(response.json["error"], "invalid_request", label)
			self.assertNotIn(keys.CLIENT_USER, response.get_data(as_text=True), label)
		# The refusals are logged against the key that was misused.
		self.assertEqual(
			frappe.get_all(
				"Elite API Access Log", {"ip_address": TEST_IPS[15], "status_code": 400}, pluck="api_key"
			),
			[self.valid_name, self.valid_name],
		)
		# With a JSON body Frappe ignores the query string: `cmd` there is not even read.
		response = self.post(f"{url}?{urlencode(cmd)}", {}, headers=headers)
		self.assertNotIn(keys.CLIENT_USER, response.get_data(as_text=True))

	def test_a_key_is_refused_inside_a_logged_in_session(self):
		response = self.call(raw_key=self.valid_key, ip=TEST_IPS[16], params={"sid": self.sid})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"], "invalid_request")

	def test_a_key_is_refused_with_an_authorization_header(self):
		response = self.call(
			raw_key=self.valid_key, ip=TEST_IPS[17], extra_headers={"Authorization": "Bearer x"}
		)
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"], "invalid_request")

	# -- access log ----------------------------------------------------------

	def test_successful_and_failed_calls_are_logged(self):
		ip = TEST_IPS[11]
		self.call(raw_key=self.valid_key, ip=ip, params={"page": "2", "codice_fiscale": "RSSMRA80A01H501U"})
		self.call(raw_key=self.revoked_key, ip=ip)

		rows = frappe.get_all(
			"Elite API Access Log",
			filters={"ip_address": ip},
			fields=["api_key", "method", "status_code", "request_params"],
			order_by="creation asc",
		)
		self.assertEqual([row.status_code for row in rows], [200, 401])
		self.assertEqual(rows[0].api_key, self.valid_name)
		self.assertEqual(rows[0].method, "v1.ping")
		self.assertEqual(frappe.parse_json(rows[0].request_params), {"page": "2"})
		self.assertIsNotNone(rows[1].api_key)

	def test_invalid_keys_past_the_limit_are_not_logged(self):
		ip = TEST_IPS[12]
		frappe.cache.setex(auth._failed_attempts_cache_key(ip), 60, auth.FAILED_ATTEMPTS_LIMIT)
		self.assertEqual(self.call(raw_key="garbage", ip=ip).status_code, 429)
		self.assertFalse(frappe.db.exists("Elite API Access Log", {"ip_address": ip}))

	def test_last_use_is_recorded(self):
		ip = TEST_IPS[13]
		frappe.cache.delete_value(f"elite_api:last_used:{self.valid_name}")
		self.call(raw_key=self.valid_key, ip=ip)
		self.assertEqual(frappe.db.get_value(keys.KEY_DOCTYPE, self.valid_name, "last_used_ip"), ip)


class TestAuthenticateRequestDirectly(FrappeAPITestCase):
	"""Checks that are easier without an HTTP round trip."""

	def test_request_parameters_survive_the_user_switch(self):
		frappe.set_user("Administrator")
		_doc, raw_key = keys.generate_key("Form dict test")
		frappe.utils.set_request(
			method="GET", path=f"/api/method/{PING}", headers={"X-Elite-Api-Key": raw_key}
		)
		frappe.local.request_ip = TEST_IPS[20]
		frappe.set_user("Guest")  # an API call arrives without a logged-in session
		frappe.local.form_dict = frappe._dict(page="2", course="corso-x")
		try:
			auth.authenticate_request()
			self.assertEqual(frappe.session.user, keys.CLIENT_USER)
			self.assertEqual(frappe.form_dict, {"page": "2", "course": "corso-x"})
			self.assertTrue(frappe.local.flags.disable_traceback)
		finally:
			frappe.local.flags.disable_traceback = False
			frappe.set_user("Administrator")
			frappe.db.rollback()

	def test_a_client_user_with_extra_roles_is_refused(self):
		"""A role added by hand between migrates must not reach any key (review, finding 6)."""
		frappe.set_user("Administrator")
		_doc, raw_key = keys.generate_key("Extra roles test")
		frappe.utils.set_request(
			method="GET", path=f"/api/method/{PING}", headers={"X-Elite-Api-Key": raw_key}
		)
		frappe.local.request_ip = TEST_IPS[21]
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict()
		extra = [keys.CLIENT_ROLE, "All", "Guest", "Desk User", "System Manager"]
		try:
			with (
				patch.object(auth.frappe, "get_roles", return_value=extra),
				patch.object(auth.frappe, "log_error"),
				self.assertRaises(errors.EliteAPIForbidden),
			):
				auth.authenticate_request()
			self.assertEqual(frappe.session.user, "Guest")  # never switched to the client user
		finally:
			frappe.local.flags.disable_traceback = False
			frappe.set_user("Administrator")
			frappe.db.rollback()

	def test_requests_without_the_header_are_untouched(self):
		frappe.set_user("Administrator")
		frappe.utils.set_request(method="GET", path=f"/api/method/{PING}")
		try:
			auth.authenticate_request()
			self.assertEqual(frappe.session.user, "Administrator")
			self.assertIsNone(frappe.local.elite_api)
		finally:
			frappe.db.rollback()
