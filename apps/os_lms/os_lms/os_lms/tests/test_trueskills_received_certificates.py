"""Certificates TrueSkills issued straight to a user (profile "Certificates" tab).

TrueSkills is replaced by a fake that replays canned answers and records every
request, so nothing leaves the machine. Fixture users are written with
``db_insert`` under fixed ``ts-received-test-`` names and every test rolls back.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests import UnitTestCase

from os_lms.os_lms.trueskills import received
from os_lms.os_lms.trueskills.service import SEARCH_MAX_PAGES
from os_lms.os_lms.trueskills.settings import TrueSkillsSettings

P = "ts-received-test-"
API_KEY = "ts_test_SECRETKEY_0123456789"
# username: (email, roles)
OWNER, OTHER, GESTORE, SYSMAN, MODERATOR, DOCENTE = (
	f"{P}owner",
	f"{P}other",
	f"{P}gestore",
	f"{P}sysman",
	f"{P}moderator",
	f"{P}docente",
)
USERS = {
	OWNER: ["LMS Student"],
	OTHER: ["LMS Student"],
	GESTORE: ["Gestore"],
	SYSMAN: ["System Manager"],
	MODERATOR: ["Moderator"],
	DOCENTE: ["Docente", "Course Creator"],
}


def email_of(username: str) -> str:
	return f"{username}@example.com"


def insert_users():
	for username, roles in USERS.items():
		email = email_of(username)
		frappe.get_doc(
			{
				"doctype": "User",
				"name": email,
				"email": email,
				"username": username,
				"first_name": username,
				"full_name": username,
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
	for username in USERS:
		frappe.cache.hdel("roles", email_of(username))


def reply(status: int = 200, payload=None, *, body: bytes | None = None, content_type: str | None = None):
	response = requests.Response()
	response.status_code = status
	response.encoding = "utf-8"
	if payload is not None:
		response._content = json.dumps(payload).encode()
		response.headers["Content-Type"] = "application/json"
	else:
		response._content = body or b""
	if content_type:
		response.headers["Content-Type"] = content_type
	return response


def certificate(cert_id: int, formats=("image", "jsonp"), cert_type="Openbadge"):
	return {
		"id": cert_id,
		"uid": f"00000000-0000-0000-0000-{cert_id:012d}",
		"name": f"Certificate {cert_id}",
		"type": cert_type,
		"createdAt": "2026-04-03T10:30:00Z",
		"formats": list(formats),
	}


def page(rows, total=None, page_number=1, page_size=100):
	return reply(
		200,
		{
			"email": "echo",
			"page": page_number,
			"pageSize": page_size,
			"total": len(rows) if total is None else total,
			"certificates": rows,
		},
	)


class FakeTrueSkills:
	"""Replays queued answers per route and records the request of each call.

	An item is a ``requests.Response`` or an exception to raise. ``search`` and
	``download`` queues are consumed in order; an unexpected request fails the test.
	"""

	def __init__(self, search=(), download=()):
		self.queues = {"search-by-email": list(search), "download": list(download)}
		self.requests: list[dict] = []

	def __call__(self, **kwargs):
		self.requests.append(kwargs)
		route = "search-by-email" if kwargs["url"].endswith("/search-by-email") else "download"
		if not self.queues[route]:
			raise AssertionError(f"Unexpected TrueSkills request: {kwargs['method']} {kwargs['url']}")
		item = self.queues[route].pop(0)
		if isinstance(item, Exception):
			raise item
		return item

	def calls(self, route: str) -> list[dict]:
		marker = "/search-by-email" if route == "search-by-email" else "/download/"
		return [call for call in self.requests if marker in call["url"]]


class TestReceivedCertificates(UnitTestCase):
	def setUp(self):
		try:
			insert_users()
		except Exception:
			frappe.db.rollback()  # tearDown does not run when setUp fails
			raise
		forget_cached_roles()
		frappe.local.response = frappe._dict()
		for status, code in ((401, None), (400, None), (400, "invalid_email"), (None, "unexpected_response")):
			frappe.cache().delete_value(received.ERROR_LOG_CACHE_KEY.format(status=status, code=code))

		self.settings = TrueSkillsSettings(
			enabled=True, api_key=API_KEY, endpoint="https://trueskills.example.test"
		)
		self.logger = MagicMock()
		self.error_log = MagicMock()
		for target in (
			patch.object(TrueSkillsSettings, "load", side_effect=lambda: self.settings),
			patch("os_lms.os_lms.trueskills.client.time.sleep"),  # no real backoff
			patch("os_lms.os_lms.trueskills.client.get_logger", return_value=self.logger),
			patch("os_lms.os_lms.trueskills.service.get_logger", return_value=self.logger),
			patch.object(received.frappe, "log_error", self.error_log),
		):
			target.start()
			self.addCleanup(target.stop)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		forget_cached_roles()

	def fake(self, **queues) -> FakeTrueSkills:
		fake = FakeTrueSkills(**queues)
		patcher = patch.object(requests.Session, "request", side_effect=fake)
		patcher.start()
		self.addCleanup(patcher.stop)
		return fake

	def list_as(self, viewer: str, profile: str = OWNER) -> dict:
		frappe.set_user(email_of(viewer))
		return received.list_received_certificates(profile)

	def issue_log(self, trueskill_id: int, state: str = "issued"):
		frappe.get_doc(
			{
				"doctype": "TrueSkills Issue Log",
				"name": f"TSL-TEST-{trueskill_id}",
				"lms_certificate": "any",
				"state": state,
				"requested_at": "2026-04-03 10:00:00",
				"trueskill_id": trueskill_id,
			}
		).db_insert()

	# ---- list ---------------------------------------------------------

	def test_lists_certificates_with_only_the_downloadable_formats(self):
		fake = self.fake(
			search=[
				page(
					[
						certificate(456),
						certificate(455, formats=(), cert_type="Certificate"),
						certificate(454, formats=("jsonp", "unknown")),
					]
				)
			]
		)

		result = self.list_as(OWNER)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(
			[(c["id"], c["type"], c["formats"]) for c in result["certificates"]],
			[(456, "Openbadge", ["image", "jsonp"]), (455, "Certificate", []), (454, "Openbadge", ["jsonp"])],
		)
		self.assertEqual(result["certificates"][0]["created_at"], "2026-04-03T10:30:00Z")
		self.assertEqual(result["certificates"][0]["name"], "Certificate 456")

		(search,) = fake.calls("search-by-email")
		self.assertEqual(search["method"], "POST")
		self.assertEqual(search["json"], {"email": email_of(OWNER), "page": 1, "pageSize": 100})
		self.assertNotIn(OWNER, search["url"])  # the email never goes in the URL
		self.assertFalse(search.get("params"))

	def test_no_certificates_is_a_normal_empty_answer(self):
		self.fake(search=[page([])])
		self.assertEqual(self.list_as(OWNER), {"status": "ok", "certificates": []})

	def test_walks_every_page(self):
		fake = self.fake(
			search=[
				page([certificate(i) for i in range(900_200, 900_100, -1)], total=150, page_number=1),
				page([certificate(i) for i in range(900_100, 900_050, -1)], total=150, page_number=2),
			]
		)

		result = self.list_as(OWNER)

		self.assertEqual(len(result["certificates"]), 150)
		self.assertEqual([c["json"]["page"] for c in fake.calls("search-by-email")], [1, 2])

	def test_follows_the_page_size_the_server_really_applied(self):
		# Asked for 100, the server answers with pages of 50: 120 certificates = 3 pages.
		fake = self.fake(
			search=[
				page([certificate(i) for i in range(900_300, 900_250, -1)], total=120, page_size=50),
				page(
					[certificate(i) for i in range(900_250, 900_200, -1)],
					total=120,
					page_number=2,
					page_size=50,
				),
				page(
					[certificate(i) for i in range(900_200, 900_180, -1)],
					total=120,
					page_number=3,
					page_size=50,
				),
			]
		)

		self.assertEqual(len(self.list_as(OWNER)["certificates"]), 120)
		self.assertEqual(len(fake.calls("search-by-email")), 3)

	def test_pagination_cannot_loop_forever(self):
		# A server that keeps announcing more rows than it returns.
		empty_page = self.fake(search=[page([certificate(900_001)], total=10_000)] + [page([], total=10_000)])
		self.assertEqual(len(self.list_as(OWNER)["certificates"]), 1)
		self.assertEqual(len(empty_page.calls("search-by-email")), 2)  # stops on the empty page

		full = self.fake(
			search=[
				page([certificate(900_000 + i)], total=10_000, page_number=i)
				for i in range(1, SEARCH_MAX_PAGES + 5)
			]
		)
		self.assertEqual(len(self.list_as(OWNER)["certificates"]), SEARCH_MAX_PAGES)
		self.assertEqual(len(full.calls("search-by-email")), SEARCH_MAX_PAGES)

	def test_leaves_out_what_elite_itself_emitted(self):
		self.fake(search=[page([certificate(456), certificate(455), certificate(454)])])
		self.issue_log(455)

		result = self.list_as(OWNER)

		self.assertEqual([c["id"] for c in result["certificates"]], [456, 454])

	def test_integration_off_leaves_the_profile_untouched(self):
		self.settings.enabled = False
		fake = self.fake()

		self.assertEqual(self.list_as(OWNER), {"status": "disabled", "certificates": []})
		self.assertEqual(fake.requests, [])

	def test_endpoints_accept_the_http_methods_the_spa_uses(self):
		# frappe-ui's call() always POSTs; the files are fetched with a plain GET.
		allowed = frappe.allowed_http_methods_for_whitelisted_func
		self.assertEqual(set(allowed[received.list_received_certificates]), {"GET", "POST"})
		self.assertEqual(set(allowed[received.download_received_certificate]), {"GET"})

	# ---- who can see ---------------------------------------------------

	def test_owner_system_manager_gestore_and_administrator_can_see_a_profile(self):
		for viewer in (OWNER, SYSMAN, GESTORE):
			self.fake(search=[page([certificate(1)])])
			self.assertEqual(self.list_as(viewer, OWNER)["status"], "ok", viewer)

		self.fake(search=[page([certificate(1)])])
		frappe.set_user("Administrator")
		self.assertEqual(received.list_received_certificates(OWNER)["status"], "ok")

	def test_everybody_else_is_refused_without_calling_trueskills(self):
		fake = self.fake()
		for viewer in (OTHER, MODERATOR, DOCENTE):
			with self.assertRaises(frappe.PermissionError, msg=viewer):
				self.list_as(viewer, OWNER)
		self.assertEqual(fake.requests, [])

	def test_unknown_or_empty_username_never_reaches_trueskills(self):
		fake = self.fake()
		with self.assertRaises(frappe.DoesNotExistError):
			self.list_as(SYSMAN, f"{P}nobody")
		for empty in ("", "  "):
			with self.assertRaises(frappe.ValidationError):
				self.list_as(SYSMAN, empty)
		self.assertEqual(fake.requests, [])

	# ---- TrueSkills errors --------------------------------------------

	def test_transient_failure_is_retried_then_degrades_without_blocking(self):
		fake = self.fake(search=[reply(500, {"message": "internal_error"}), page([certificate(1)])])
		self.assertEqual(self.list_as(OWNER)["status"], "ok")
		self.assertEqual(len(fake.calls("search-by-email")), 2)

		fake = self.fake(search=[reply(500, {"message": "internal_error"})] * 2)
		self.assertEqual(self.list_as(OWNER), {"status": "unavailable", "certificates": []})
		self.assertEqual(len(fake.calls("search-by-email")), received.INTERACTIVE_ATTEMPTS)
		self.error_log.assert_not_called()  # a transient failure is not a bug to fix

		fake = self.fake(search=[requests.Timeout("slow")] * 2)
		self.assertEqual(self.list_as(OWNER)["status"], "unavailable")
		self.assertEqual(len(fake.calls("search-by-email")), received.INTERACTIVE_ATTEMPTS)

	def test_permanent_failures_are_not_retried_and_logged_once(self):
		# 401 is text/plain, a malformed request is the ASP.NET 400 without ``message``.
		cases = {
			"revoked key": reply(401, body=b"api_key_required", content_type="text/plain"),
			"malformed": reply(400, {"title": "One or more validation errors occurred.", "errors": {}}),
			"invalid email": reply(400, {"message": "invalid_email", "templateError": None}),
		}
		for label, answer in cases.items():
			self.error_log.reset_mock()
			fake = self.fake(search=[answer])

			self.assertEqual(self.list_as(OWNER), {"status": "unavailable", "certificates": []}, label)
			self.assertEqual(len(fake.calls("search-by-email")), 1, label)
			self.error_log.assert_called_once()

		# The same failure again within the window does not flood the Error Log.
		self.error_log.reset_mock()
		frappe.cache().delete_value(received.ERROR_LOG_CACHE_KEY.format(status=401, code=None))
		self.fake(search=[reply(401, body=b"api_key_required", content_type="text/plain")])
		self.list_as(OWNER)
		self.fake(search=[reply(401, body=b"api_key_required", content_type="text/plain")])
		self.list_as(OWNER)
		self.assertEqual(self.error_log.call_count, 1)

	def test_a_200_that_is_not_the_documented_answer_is_an_error(self):
		# A wrong endpoint can be answered with a 200 HTML page.
		self.fake(search=[reply(200, body=b"<html>app</html>", content_type="text/html")])
		self.assertEqual(self.list_as(OWNER)["status"], "unavailable")
		self.error_log.assert_called_once()

	# ---- download ------------------------------------------------------

	def download_as(self, viewer: str, cert_id: int, file_format: str, profile: str = OWNER):
		frappe.set_user(email_of(viewer))
		return received.download_received_certificate(profile, cert_id, file_format)

	def test_forwards_the_png_and_the_json_ld(self):
		fake = self.fake(
			search=[page([certificate(456)]), page([certificate(456)])],
			download=[
				reply(200, body=b"\x89PNG-bytes", content_type="image/png"),
				reply(200, body=b'{"@context": []}', content_type="application/ld+json"),
			],
		)

		self.download_as(OWNER, 456, "image")
		self.assertEqual(frappe.local.response.filename, "trueskill_456.png")
		self.assertEqual(frappe.local.response.filecontent, b"\x89PNG-bytes")
		self.assertEqual(frappe.local.response.content_type, "image/png")
		self.assertEqual(frappe.local.response.type, "download")

		self.download_as(OWNER, 456, "jsonp")
		self.assertEqual(frappe.local.response.filename, "trueskill_456.jsonld")
		self.assertEqual(frappe.local.response.content_type, "application/ld+json")

		first, second = fake.calls("download")
		self.assertTrue(first["url"].endswith("/download/456/image"))
		self.assertTrue(second["url"].endswith("/download/456/jsonp"))
		self.assertEqual(first["method"], "GET")

	def test_an_id_not_returned_by_the_search_is_refused_before_any_download(self):
		# Someone else's certificate id: the key could download it, we must not.
		fake = self.fake(search=[page([certificate(456)])])

		with self.assertRaises(frappe.DoesNotExistError):
			self.download_as(OWNER, 999, "image")

		self.assertEqual(fake.calls("download"), [])
		self.assertFalse(frappe.local.response.get("filecontent"))

	def test_the_membership_check_uses_the_profile_email_not_the_viewer(self):
		fake = self.fake(search=[page([])])

		with self.assertRaises(frappe.DoesNotExistError):
			self.download_as(SYSMAN, 456, "image", profile=OWNER)

		(search,) = fake.calls("search-by-email")
		self.assertEqual(search["json"]["email"], email_of(OWNER))

	def test_a_format_the_certificate_does_not_offer_is_refused(self):
		fake = self.fake(search=[page([certificate(454, formats=("jsonp",))])])

		with self.assertRaises(received.ReceivedCertificateFileError):
			self.download_as(OWNER, 454, "image")
		self.assertEqual(fake.calls("download"), [])

	def test_an_unknown_format_is_refused_without_calling_trueskills(self):
		fake = self.fake()
		for file_format in ("png", "json", "../x", ""):
			with self.assertRaises(received.ReceivedCertificateFileError):
				self.download_as(OWNER, 456, file_format)
		self.assertEqual(fake.requests, [])

	def test_a_stranger_cannot_download_and_trueskills_is_not_called(self):
		fake = self.fake()
		for viewer in (OTHER, MODERATOR):
			with self.assertRaises(frappe.PermissionError, msg=viewer):
				self.download_as(viewer, 456, "image")
		self.assertEqual(fake.requests, [])

	def test_a_file_that_cannot_be_generated_is_reported_distinctly(self):
		fake = self.fake(
			search=[page([certificate(456)])],
			download=[reply(400, {"message": "unable_to_generate_file", "templateError": None})],
		)

		with self.assertRaises(received.ReceivedCertificateFileError):
			self.download_as(OWNER, 456, "image")
		self.assertEqual(len(fake.calls("download")), 1)  # a 4xx is never retried

	def test_a_certificate_withdrawn_between_list_and_download_is_a_404(self):
		self.fake(
			search=[page([certificate(456)])],
			download=[reply(404, {"message": "certificate_not_found", "templateError": None})],
		)
		with self.assertRaises(frappe.DoesNotExistError):
			self.download_as(OWNER, 456, "image")

	def test_download_retries_transient_errors_then_reports_unavailable(self):
		fake = self.fake(
			search=[page([certificate(456)]), page([certificate(456)])],
			download=[
				reply(500, {"message": "internal_error"}),
				reply(200, body=b"png", content_type="image/png"),
				reply(500, {"message": "internal_error"}),
				reply(500, {"message": "internal_error"}),
			],
		)
		self.download_as(OWNER, 456, "image")
		self.assertEqual(frappe.local.response.filecontent, b"png")

		with self.assertRaises(received.TrueSkillsUnavailableError):
			self.download_as(OWNER, 456, "image")
		self.assertEqual(len(fake.calls("download")), 4)

	def test_the_search_failing_during_a_download_is_reported_unavailable(self):
		self.fake(search=[reply(500, {"message": "internal_error"})] * 2)
		with self.assertRaises(received.TrueSkillsUnavailableError):
			self.download_as(OWNER, 456, "image")

	# ---- secrets -------------------------------------------------------

	def test_the_api_key_and_the_email_never_leak(self):
		fake = self.fake(
			search=[
				page([certificate(456)]),  # list
				reply(401, body=b"api_key_required", content_type="text/plain"),  # failing list
				reply(500, {"message": "internal_error"}),  # failing search before a download
				reply(500, {"message": "internal_error"}),
				page([certificate(456)]),  # download
			],
			download=[reply(400, {"message": "unable_to_generate_file"})],
		)
		surfaced: list[str] = []

		surfaced.append(json.dumps(self.list_as(OWNER)))
		surfaced.append(json.dumps(self.list_as(OWNER)))
		for _ in range(2):
			try:
				self.download_as(OWNER, 456, "image")
			except Exception as exc:
				surfaced.append(f"{exc!r} {exc.__cause__!r} {exc.__context__!r}")
		surfaced.append(json.dumps({k: str(v) for k, v in frappe.local.response.items()}))

		logged = [str(call) for call in self.logger.method_calls] + [
			str(c) for c in self.error_log.call_args_list
		]
		sent = [f"{call['url']} {call.get('params')} {call.get('headers')}" for call in fake.requests]
		for text in surfaced + logged + sent:
			self.assertNotIn(API_KEY, text)
		for text in surfaced + logged:
			self.assertNotIn(email_of(OWNER), text)
		self.assertTrue(logged)  # the failures were actually logged
