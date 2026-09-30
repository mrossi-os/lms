"""Elite API catalogue: progress summaries and the list_courses / list_batches endpoints.

Test data and its exact cleanup live in ``elite_api_fixture``.
"""

from __future__ import annotations

from urllib.parse import urlencode

import frappe
from frappe.tests import UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils import get_test_client, get_url

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.progress import batch_summaries, course_summaries
from os_lms.os_lms.tests.elite_api_fixture import (
	ALPHA,
	BATCH_EMPTY,
	BATCH_MAIN,
	BETA,
	EXPECTED_ALPHA,
	EXPECTED_BETA,
	EXPECTED_EMPTY,
	EXPECTED_MAIN,
	SEARCH,
	P,
	delete_fixture,
	insert_fixture,
)

TEST_IP = "203.0.113.40"


class TestProgressSummaries(UnitTestCase):
	def setUp(self):
		try:
			insert_fixture()
		except Exception:
			frappe.db.rollback()  # tearDown does not run when setUp fails
			raise

	def tearDown(self):
		frappe.db.rollback()

	def test_course_summary_applies_every_rule(self):
		summaries = course_summaries([ALPHA, BETA])
		self.assertEqual(summaries[ALPHA], EXPECTED_ALPHA)
		self.assertEqual(summaries[BETA], EXPECTED_BETA)

	def test_course_without_students_has_an_empty_summary(self):
		summary = course_summaries([f"{P}gamma"])[f"{P}gamma"]
		self.assertEqual(summary, {"total": 0, "completed": 0, "in_progress": 0, "not_started": 0})

	def test_batch_summary_counts_courses_only_and_never_opened_as_zero(self):
		summaries = batch_summaries([BATCH_MAIN, BATCH_EMPTY])
		self.assertEqual(summaries[BATCH_MAIN], EXPECTED_MAIN)
		self.assertEqual(summaries[BATCH_EMPTY], EXPECTED_EMPTY)

	def test_empty_input(self):
		self.assertEqual(course_summaries([]), {})
		self.assertEqual(batch_summaries([]), {})


class TestCatalogEndpoints(FrappeAPITestCase):
	TEST_CLIENT = get_test_client(use_cookies=False)

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		try:
			cls.created = insert_fixture()
			key_doc, cls.raw_key = keys.generate_key("Catalog test")
		except Exception:
			# Never commit a half-built fixture: tearDownClass does not run when
			# setUpClass fails, and a later commit would persist it.
			frappe.db.rollback()
			raise
		cls.key_name = key_doc.name
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.db.delete("Elite API Access Log", {"api_key": cls.key_name})
		frappe.db.delete(keys.KEY_DOCTYPE, {"name": cls.key_name})
		frappe.cache.delete_value(f"elite_api:last_used:{cls.key_name}")
		delete_fixture(cls.created)
		frappe.db.commit()
		super().tearDownClass()

	def call(self, method, **params):
		url = f"{get_url()}/api/method/os_lms.os_lms.elite_api.v1.{method}"
		if params:
			url += "?" + urlencode(params)
		return self.get(url, headers={"X-Elite-Api-Key": self.raw_key, "X-Forwarded-For": TEST_IP})

	def test_list_courses_returns_every_course_with_its_summary(self):
		response = self.call("list_courses", search=SEARCH)

		self.assertEqual(response.status_code, 200)
		body = response.json["message"]
		self.assertEqual(body["total"], 4)
		self.assertEqual(
			[course["id"] for course in body["data"]],
			[f"{P}alpha", f"{P}beta", f"{P}delta", f"{P}gamma"],  # by title
		)
		alpha = body["data"][0]
		self.assertEqual(alpha["students"], EXPECTED_ALPHA)
		self.assertEqual(alpha["title"], f"{SEARCH} Alpha 50%")
		self.assertIs(alpha["published"], True)
		self.assertIs(body["data"][2]["published"], False)  # unpublished courses are listed too

	def test_search_matches_wildcards_literally(self):
		self.assertEqual(
			[c["id"] for c in self.call("list_courses", search="50%").json["message"]["data"]], [f"{P}alpha"]
		)
		self.assertEqual(
			[c["id"] for c in self.call("list_courses", search="a_b").json["message"]["data"]], [f"{P}delta"]
		)

	def test_pagination(self):
		body = self.call("list_courses", search=SEARCH, page=2, page_length=3).json["message"]
		self.assertEqual((body["total"], body["page"], body["page_length"]), (4, 2, 3))
		self.assertEqual([c["id"] for c in body["data"]], [f"{P}gamma"])

	def test_invalid_pagination_is_a_400(self):
		for params, parameter in (
			({"page": 0}, "page"),
			({"page": "abc"}, "page"),
			({"page_length": 501}, "page_length"),
			({"page_length": 0}, "page_length"),
		):
			response = self.call("list_courses", **params)
			self.assertEqual(response.status_code, 400, params)
			self.assertEqual(response.json["error"], "invalid_parameter", params)
			self.assertEqual(response.json["parameter"], parameter, params)

	def test_list_batches_returns_courses_and_summary(self):
		response = self.call("list_batches", search=SEARCH)

		self.assertEqual(response.status_code, 200)
		body = response.json["message"]
		self.assertEqual(body["total"], 2)
		empty, main = body["data"]  # most recent start date first
		self.assertEqual(empty["id"], BATCH_EMPTY)
		self.assertEqual(empty["courses"], [])
		self.assertEqual(empty["students"], EXPECTED_EMPTY)
		self.assertEqual(main["start_date"], "2026-01-10")
		self.assertEqual([c["id"] for c in main["courses"]], [ALPHA, BETA])
		self.assertEqual(main["students"], EXPECTED_MAIN)

	def test_rows_returned_reach_the_access_log(self):
		self.call("list_courses", search=SEARCH)
		rows = frappe.get_all(
			"Elite API Access Log",
			filters={"api_key": self.key_name, "method": "v1.list_courses"},
			fields=["rows_returned", "request_params"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(rows[0].rows_returned, 4)
		self.assertEqual(frappe.parse_json(rows[0].request_params), {"search": SEARCH})
