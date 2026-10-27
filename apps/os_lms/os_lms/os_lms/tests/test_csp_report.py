"""CSP violation reports (OWASP B3): parsing, anonymisation and the counters.

The rows are real. Every report here uses pages under ``/__csp_test__/``, and
cleanup deletes the rows by the exact names those reports produce.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import csp_report

PAGE = "/__csp_test__/lesson"
OTHER_PAGE = "/__csp_test__/other"


def _report_uri(blocked="https://cdn.example.org/lib.js?token=abc", page=PAGE, directive="script-src-elem"):
	return json.dumps(
		{
			"csp-report": {
				"document-uri": f"https://elite.example.org{page}?email=student@example.org#top",
				"effective-directive": directive,
				"violated-directive": directive,
				"blocked-uri": blocked,
				"disposition": "report",
				"script-sample": "alert(document.cookie)",
				"source-file": "https://elite.example.org/assets/app.js",
			}
		}
	)


def _expected(blocked, page=PAGE, directive="script-src-elem"):
	return {"directive": directive, "blocked_source": blocked, "page": page, "disposition": "report"}


TEST_VIOLATIONS = [
	_expected("https://cdn.example.org"),
	_expected("https://cdn.example.org", page=OTHER_PAGE),
	_expected("https://media.example.org:8443", page=OTHER_PAGE, directive="media-src"),
	_expected("inline", directive="script-src-attr"),
	_expected("chrome-extension:", directive="img-src"),
	_expected("(other)", directive="img-src"),
	_expected("https://new-kind.example.org"),
]
TEST_KEYS = [csp_report.violation_key(v) for v in TEST_VIOLATIONS]


def _cleanup():
	frappe.db.rollback()
	for key in TEST_KEYS:
		frappe.db.delete(csp_report.DOCTYPE, {"name": key})
	frappe.db.commit()


def _row(violation):
	return frappe.db.get_value(
		csp_report.DOCTYPE,
		csp_report.violation_key(violation),
		["directive", "blocked_source", "page", "disposition", "hits"],
		as_dict=True,
	)


class TestCSPReport(UnitTestCase):
	def setUp(self):
		_cleanup()

	def tearDown(self):
		_cleanup()

	def test_report_uri_format_counts_one_row_per_kind(self):
		self.assertEqual(csp_report.record_reports(_report_uri()), 1)
		self.assertEqual(csp_report.record_reports(_report_uri()), 1)

		row = _row(TEST_VIOLATIONS[0])
		self.assertEqual(row.hits, 2)
		self.assertEqual(row.directive, "script-src-elem")
		self.assertEqual(row.disposition, "report")

	def test_only_origin_and_path_are_kept(self):
		csp_report.record_reports(_report_uri())

		row = frappe.db.get_value(
			csp_report.DOCTYPE, TEST_KEYS[0], ["blocked_source", "page"], as_dict=True
		)
		self.assertEqual(row.blocked_source, "https://cdn.example.org")
		self.assertEqual(row.page, PAGE)
		stored = json.dumps(frappe.db.get_value(csp_report.DOCTYPE, TEST_KEYS[0], "*", as_dict=True), default=str)
		for personal in ("token=abc", "student@example.org", "alert(", "#top"):
			self.assertNotIn(personal, stored)

	def test_reporting_api_format(self):
		body = json.dumps(
			[
				{
					"type": "csp-violation",
					"body": {
						"documentURL": f"https://elite.example.org{OTHER_PAGE}",
						"effectiveDirective": "script-src-elem",
						"blockedURL": "https://cdn.example.org/x.js",
						"disposition": "report",
					},
				},
				{
					"type": "csp-violation",
					"body": {
						"documentURL": f"https://elite.example.org{OTHER_PAGE}",
						"effectiveDirective": "media-src",
						"blockedURL": "https://media.example.org:8443/v.mp4",
						"disposition": "report",
					},
				},
				{"type": "deprecation", "body": {"id": "x"}},
			]
		)

		self.assertEqual(csp_report.record_reports(body), 2)
		self.assertEqual(_row(TEST_VIOLATIONS[1]).hits, 1)
		self.assertEqual(_row(TEST_VIOLATIONS[2]).hits, 1)

	def test_keywords_schemes_and_unknown_sources(self):
		csp_report.record_reports(_report_uri(blocked="inline", directive="script-src-attr"))
		csp_report.record_reports(_report_uri(blocked="chrome-extension://abcdef/icon.png", directive="img-src"))
		csp_report.record_reports(_report_uri(blocked="::not a url::", directive="img-src"))

		self.assertEqual(_row(TEST_VIOLATIONS[3]).hits, 1)
		self.assertEqual(_row(TEST_VIOLATIONS[4]).hits, 1)
		self.assertEqual(_row(TEST_VIOLATIONS[5]).hits, 1)

	def test_garbage_is_ignored(self):
		for body in (
			"",
			"not json",
			json.dumps({"other": {}}),
			json.dumps([1, "x", {"type": "csp-violation", "body": "x"}]),
			_report_uri(directive="script-src; drop table"),
			"x" * (csp_report.MAX_BODY_CHARS + 1),
		):
			with self.subTest(body=body[:40]):
				self.assertEqual(csp_report.record_reports(body), 0)

	def test_reports_per_request_are_capped(self):
		item = json.loads(_report_uri())["csp-report"]
		body = json.dumps(
			[
				{
					"type": "csp-violation",
					"body": {
						"documentURL": item["document-uri"],
						"effectiveDirective": item["effective-directive"],
						"blockedURL": item["blocked-uri"],
						"disposition": "report",
					},
				}
			]
			* (csp_report.MAX_REPORTS_PER_REQUEST + 5)
		)

		self.assertEqual(csp_report.record_reports(body), csp_report.MAX_REPORTS_PER_REQUEST)
		self.assertEqual(_row(TEST_VIOLATIONS[0]).hits, csp_report.MAX_REPORTS_PER_REQUEST)

	def test_new_kinds_stop_at_the_row_limit_existing_ones_keep_counting(self):
		csp_report.record_reports(_report_uri())
		with patch.object(csp_report, "MAX_ROWS", frappe.db.count(csp_report.DOCTYPE)):
			self.assertEqual(csp_report.record_reports(_report_uri(blocked="https://new-kind.example.org/a.js")), 0)
			self.assertEqual(csp_report.record_reports(_report_uri()), 1)

		self.assertFalse(frappe.db.exists(csp_report.DOCTYPE, TEST_KEYS[6]))
		self.assertEqual(_row(TEST_VIOLATIONS[0]).hits, 2)

	def test_endpoint_is_open_to_guests_post_only(self):
		fn = frappe.get_attr("os_lms.os_lms.csp_report.collect")
		self.assertIn(fn, frappe.guest_methods)
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[fn], ["POST"])

	def test_rows_are_readable_by_system_manager_only(self):
		perms = frappe.get_meta(csp_report.DOCTYPE).permissions
		self.assertEqual([p.role for p in perms], ["System Manager"])
		self.assertIn(csp_report.DOCTYPE, frappe.get_hooks("default_log_clearing_doctypes"))
