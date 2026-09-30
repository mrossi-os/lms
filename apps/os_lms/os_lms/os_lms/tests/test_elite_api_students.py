"""Elite API student lists: get_course_students / get_batch_students.

Test data and its exact cleanup live in ``elite_api_fixture``; the expected
values below are worked out by hand from it.
"""

from __future__ import annotations

from urllib.parse import urlencode

import frappe
from frappe.tests import UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.utils import get_test_client, get_url

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.progress import (
	BATCH_STATUSES,
	COURSE_STATUSES,
	batch_students,
	batch_summaries,
	course_students,
	course_summaries,
)
from os_lms.os_lms.tests.elite_api_fixture import (
	ALPHA,
	BATCH_EMPTY,
	BATCH_MAIN,
	BETA,
	DONE,
	DUP,
	HALF,
	NEWBIE,
	ZERO,
	delete_fixture,
	insert_fixture,
)

TEST_IP = "203.0.113.50"

# Ordered by last name, first name, email ("" sorts first).
ALPHA_STUDENTS = [
	{
		"first_name": "Mario Verdi",
		"last_name": "",
		"fiscal_code": None,
		"email": ZERO,
		"enrolled_on": "2026-03-04T09:00:00",
		"progress": 0.0,
		"status": "not_started",
	},
	{
		"first_name": "Anna",
		"last_name": "Bianchi",
		"fiscal_code": "ELTBNC80A41H501A",
		"email": DONE,
		"enrolled_on": "2026-03-02T09:00:00",
		"progress": 100.0,
		"status": "completed",
	},
	{
		"first_name": "Dario",
		"last_name": "Neri",
		"fiscal_code": "ELTNRI80A01H501C",
		"email": DUP,
		"enrolled_on": "2026-03-01T09:00:00",  # first of its two enrollments
		"progress": 60.0,  # highest of its two enrollments
		"status": "in_progress",
	},
	{
		"first_name": "Carlo",
		"last_name": "Rossi",
		"fiscal_code": "ELTRSS80A01H501B",  # stored as " eltrss80a01h501b "
		"email": HALF,
		"enrolled_on": "2026-03-03T09:00:00",
		"progress": 50.0,
		"status": "in_progress",
	},
]


def batch_course(course, progress):
	status = "completed" if progress >= 100 else ("in_progress" if progress > 0 else "not_started")
	return {"id": course, "progress": float(progress), "status": status}


# (email, enrolled_on, courses_completed, status, alpha progress, beta progress)
MAIN_STUDENTS = [
	(ZERO, "2026-01-07T10:00:00", 0, "not_started", 0, 0),
	(DONE, "2026-01-05T10:00:00", 2, "completed_all", 100, 100),
	(NEWBIE, "2026-01-09T10:00:00", 0, "not_started", 0, 0),
	(DUP, "2026-01-08T10:00:00", 0, "partial", 60, 0),
	(HALF, "2026-01-06T10:00:00", 0, "partial", 50, 0),
]


class TestStudentLists(UnitTestCase):
	def setUp(self):
		try:
			insert_fixture()
		except Exception:
			frappe.db.rollback()  # tearDown does not run when setUp fails
			raise

	def tearDown(self):
		frappe.db.rollback()

	def test_course_students_identity_and_progress(self):
		students, total = course_students(ALPHA, None, limit=100, offset=0)
		self.assertEqual(students, ALPHA_STUDENTS)
		self.assertEqual(total, 4)

	def test_course_status_filter_counts_the_filtered_set(self):
		students, total = course_students(ALPHA, "in_progress", limit=100, offset=0)
		self.assertEqual([s["email"] for s in students], [DUP, HALF])
		self.assertEqual(total, 2)

	def test_course_pagination(self):
		students, total = course_students(ALPHA, None, limit=2, offset=2)
		self.assertEqual([s["email"] for s in students], [DUP, HALF])
		self.assertEqual(total, 4)

	def test_batch_students_with_per_course_detail(self):
		students, total = batch_students(BATCH_MAIN, [ALPHA, BETA], None, limit=100, offset=0)

		self.assertEqual(total, 5)
		self.assertEqual([s["email"] for s in students], [row[0] for row in MAIN_STUDENTS])
		for student, (_email, enrolled_on, completed, status, alpha, beta) in zip(
			students, MAIN_STUDENTS, strict=True
		):
			self.assertEqual(student["enrolled_on"], enrolled_on, student["email"])
			self.assertEqual(student["courses_completed"], completed, student["email"])
			self.assertEqual(student["courses_total"], 2, student["email"])
			self.assertEqual(student["status"], status, student["email"])
			self.assertEqual(
				student["courses"], [batch_course(ALPHA, alpha), batch_course(BETA, beta)], student["email"]
			)

	def test_batch_status_filter(self):
		students, total = batch_students(BATCH_MAIN, [ALPHA, BETA], "partial", limit=100, offset=0)
		self.assertEqual([s["email"] for s in students], [DUP, HALF])
		self.assertEqual(total, 2)

	def test_batch_without_courses(self):
		students, total = batch_students(BATCH_EMPTY, [], None, limit=100, offset=0)
		self.assertEqual(total, 1)
		self.assertEqual(
			(
				students[0]["email"],
				students[0]["courses_total"],
				students[0]["status"],
				students[0]["courses"],
			),
			(DONE, 0, "not_started", []),
		)

	def test_lists_agree_with_the_summaries(self):
		"""List and summary queries are written separately: they must count alike."""
		for course in (ALPHA, BETA):
			summary = course_summaries([course])[course]
			self.assertEqual(course_students(course, None, 500, 0)[1], summary["total"])
			for status in COURSE_STATUSES:
				self.assertEqual(
					course_students(course, status, 500, 0)[1], summary[status], (course, status)
				)
		for batch, courses in ((BATCH_MAIN, [ALPHA, BETA]), (BATCH_EMPTY, [])):
			summary = batch_summaries([batch])[batch]
			self.assertEqual(batch_students(batch, courses, None, 500, 0)[1], summary["total"])
			for status in BATCH_STATUSES:
				self.assertEqual(
					batch_students(batch, courses, status, 500, 0)[1], summary[status], (batch, status)
				)


class TestStudentEndpoints(FrappeAPITestCase):
	TEST_CLIENT = get_test_client(use_cookies=False)

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		try:
			cls.created = insert_fixture()
			key_doc, cls.raw_key = keys.generate_key("Students test")
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

	def test_get_course_students(self):
		response = self.call("get_course_students", course=ALPHA)

		self.assertEqual(response.status_code, 200)
		body = response.json["message"]
		self.assertEqual(body["course"], {"id": ALPHA, "title": "EliteApiTest Alpha 50%"})
		self.assertEqual(body["summary"], {"total": 4, "completed": 1, "in_progress": 2, "not_started": 1})
		self.assertEqual((body["total"], body["page"], body["page_length"]), (4, 1, 100))
		self.assertEqual(body["data"], ALPHA_STUDENTS)

	def test_summary_ignores_the_filter_and_total_does_not(self):
		body = self.call("get_course_students", course=ALPHA, status="completed").json["message"]
		self.assertEqual(body["summary"]["total"], 4)
		self.assertEqual(body["total"], 1)
		self.assertEqual([s["email"] for s in body["data"]], [DONE])

	def test_get_batch_students(self):
		response = self.call("get_batch_students", batch=BATCH_MAIN, page_length=2)

		self.assertEqual(response.status_code, 200)
		body = response.json["message"]
		self.assertEqual(body["batch"]["id"], BATCH_MAIN)
		self.assertEqual([c["id"] for c in body["batch"]["courses"]], [ALPHA, BETA])
		self.assertEqual(body["summary"], {"total": 5, "completed_all": 1, "partial": 2, "not_started": 2})
		self.assertEqual((body["total"], len(body["data"])), (5, 2))
		self.assertEqual(body["data"][1]["courses"], [batch_course(ALPHA, 100), batch_course(BETA, 100)])

	def test_errors(self):
		for method, params, status, parameter in (
			("get_course_students", {}, 400, "course"),
			("get_course_students", {"course": "elite-api-test-missing"}, 404, "course"),
			("get_course_students", {"course": ALPHA, "status": "partial"}, 400, "status"),
			("get_batch_students", {}, 400, "batch"),
			("get_batch_students", {"batch": "elite-api-test-missing"}, 404, "batch"),
			("get_batch_students", {"batch": BATCH_MAIN, "status": "completed"}, 400, "status"),
		):
			response = self.call(method, **params)
			self.assertEqual(response.status_code, status, (method, params))
			self.assertEqual(response.json["parameter"], parameter, (method, params))
			self.assertEqual(
				response.json["error"],
				"not_found" if status == 404 else "invalid_parameter",
				(method, params),
			)

	def test_fiscal_codes_never_reach_the_access_log(self):
		self.call("get_course_students", course=ALPHA, status="completed")
		row = frappe.get_all(
			"Elite API Access Log",
			filters={"api_key": self.key_name, "method": "v1.get_course_students"},
			fields=["*"],
			order_by="creation desc",
			limit=1,
		)[0]
		self.assertEqual(frappe.parse_json(row.request_params), {"course": ALPHA, "status": "completed"})
		self.assertEqual(row.rows_returned, 1)
		self.assertNotIn("ELTBNC80A41H501A", frappe.as_json(row))
