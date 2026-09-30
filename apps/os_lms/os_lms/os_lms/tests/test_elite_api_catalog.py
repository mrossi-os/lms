"""Elite API catalogue: progress summaries and the list_courses / list_batches endpoints.

The fixture reproduces what production data actually contains (duplicated
enrollments, an enrollment of a deleted user, batch courses never opened) plus
the exclusion rules (disabled users, non-Student enrollments).

Rows are written with ``db_insert`` (no hooks, so no side documents such as
automatic enrollments or notifications) under fixed ``elite-api-test-`` names.
In-process tests roll back; the HTTP tests must commit, and delete exactly the
names they created.
"""

from __future__ import annotations

from urllib.parse import urlencode

import frappe
from frappe.tests import UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils import get_test_client, get_url

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.progress import batch_summaries, course_summaries

P = "elite-api-test-"
SEARCH = "EliteApiTest"
TEST_IP = "203.0.113.40"

COURSES = {
	f"{P}alpha": {"title": f"{SEARCH} Alpha 50%", "published": 1},
	f"{P}beta": {"title": f"{SEARCH} Beta", "published": 1},
	f"{P}gamma": {"title": f"{SEARCH} Gamma axb", "published": 1},
	f"{P}delta": {"title": f"{SEARCH} Delta a_b", "published": 0},
}
USERS = {
	f"{P}done@example.com": 1,
	f"{P}half@example.com": 1,
	f"{P}zero@example.com": 1,
	f"{P}dup@example.com": 1,
	f"{P}newbie@example.com": 1,
	f"{P}mentor@example.com": 1,
	f"{P}disabled@example.com": 0,
}
ORPHAN = f"{P}deleted@example.com"  # enrolled, but the User no longer exists
ALPHA, BETA = f"{P}alpha", f"{P}beta"
DONE, HALF, ZERO, DUP, NEWBIE, MENTOR, DISABLED = (
	f"{P}{n}@example.com" for n in ("done", "half", "zero", "dup", "newbie", "mentor", "disabled")
)
# (course, member, progress, member_type)
ENROLLMENTS = [
	(ALPHA, DONE, 100, "Student"),
	(ALPHA, HALF, 50, "Student"),
	(ALPHA, ZERO, 0, "Student"),
	(ALPHA, DUP, 0, "Student"),
	(ALPHA, DUP, 60, "Student"),  # duplicated row: the highest progress wins
	(ALPHA, DISABLED, 100, "Student"),  # disabled user: excluded
	(ALPHA, MENTOR, 100, "Mentor"),  # not a student: excluded
	(ALPHA, ORPHAN, 100, "Student"),  # deleted user: excluded
	(BETA, DONE, 100, "Student"),
	(BETA, HALF, 0, "Student"),
]
BATCH_MAIN, BATCH_EMPTY = f"{P}batch-main", f"{P}batch-empty"
BATCHES = {
	BATCH_MAIN: {"title": f"{SEARCH} Main batch", "start_date": "2026-01-10", "courses": [ALPHA, BETA]},
	BATCH_EMPTY: {"title": f"{SEARCH} Batch without courses", "start_date": "2026-02-01", "courses": []},
}
BATCH_ENROLLMENTS = [
	(BATCH_MAIN, DONE),  # 100 + 100 -> completed_all
	(BATCH_MAIN, HALF),  # 50 + 0 -> partial
	(BATCH_MAIN, ZERO),  # 0 + never opened -> not_started
	(BATCH_MAIN, DUP),  # 60 (duplicated row) + never opened -> partial
	(BATCH_MAIN, NEWBIE),  # never opened any course -> not_started
	(BATCH_MAIN, DISABLED),  # excluded
	(BATCH_EMPTY, DONE),  # batch without courses -> not_started
]

EXPECTED_ALPHA = {"total": 4, "completed": 1, "in_progress": 2, "not_started": 1}
EXPECTED_BETA = {"total": 2, "completed": 1, "in_progress": 0, "not_started": 1}
EXPECTED_MAIN = {"total": 5, "completed_all": 1, "partial": 2, "not_started": 2}
EXPECTED_EMPTY = {"total": 1, "completed_all": 0, "partial": 0, "not_started": 1}


def insert_fixture() -> dict[str, list[str]]:
	"""Insert the fixture and return ``{doctype: [names]}`` for an exact cleanup."""
	created: dict[str, list[str]] = {}

	def insert(values: dict):
		frappe.get_doc(values).db_insert()
		created.setdefault(values["doctype"], []).append(values["name"])

	for email, enabled in USERS.items():
		insert(
			{
				"doctype": "User",
				"name": email,
				"email": email,
				"first_name": "Elite API test",
				"enabled": enabled,
			}
		)
	for name, values in COURSES.items():
		insert({"doctype": "LMS Course", "name": name, **values})
	for n, (course, member, progress, member_type) in enumerate(ENROLLMENTS):
		insert(
			{
				"doctype": "LMS Enrollment",
				"name": f"{P}enrollment-{n}",
				"course": course,
				"member": member,
				"progress": progress,
				"member_type": member_type,
			}
		)
	for name, values in BATCHES.items():
		insert(
			{
				"doctype": "LMS Batch",
				"name": name,
				"title": values["title"],
				"start_date": values["start_date"],
				"end_date": values["start_date"],
				"published": 1,
			}
		)
		for idx, course in enumerate(values["courses"], start=1):
			# Batch Course is named by autoincrement: cleaned up by its parent.
			row = frappe.get_doc(
				{
					"doctype": "Batch Course",
					"parent": name,
					"parenttype": "LMS Batch",
					"parentfield": "courses",
					"idx": idx,
					"course": course,
				}
			)
			row.set_new_name()
			row.db_insert()
	for n, (batch, member) in enumerate(BATCH_ENROLLMENTS):
		insert(
			{
				"doctype": "LMS Batch Enrollment",
				"name": f"{P}batch-enrollment-{n}",
				"batch": batch,
				"member": member,
			}
		)
	return created


def delete_fixture(created: dict[str, list[str]]):
	for doctype, names in created.items():
		frappe.db.delete(doctype, {"name": ("in", names)})
	frappe.db.delete("Batch Course", {"parenttype": "LMS Batch", "parent": ("in", list(BATCHES))})


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
