"""The command-palette search judges a course by the course, not by the index row.

Collaudo v2.64 (test 11.2): the search offered a student courses that no longer
exist and courses that are unpublished, and each opened an empty page. The index
(learning.db) kept them flagged `published` from when they were last written.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import override_api

CAN_READ = "lms.lms.permissions.can_access_course"


def _row(name, *, row_id=None, **values):
	"""An index hit for course ``name``, as CustomLearningSearch returns it."""
	return {
		"id": row_id or f"LMS Course:{name}",
		"doctype": "LMS Course",
		"name": name,
		"owner": "a@example.com",
		**values,
	}


class TestSearchCourseVisibility(UnitTestCase):
	def test_deleted_course_is_not_offered(self):
		# Present in the index, absent from LMS Course.
		self.assertFalse(override_api.can_find_course("gone", {"live": 1}))

	def test_published_course_is_offered_to_everyone(self):
		with patch(CAN_READ) as can_read:
			self.assertTrue(override_api.can_find_course("live", {"live": 1}))
		can_read.assert_not_called()

	def test_draft_is_offered_only_to_who_may_open_it(self):
		with patch(CAN_READ, return_value=True):
			self.assertTrue(override_api.can_find_course("draft", {"draft": 0}))
		with patch(CAN_READ, return_value=False):
			self.assertFalse(override_api.can_find_course("draft", {"draft": 0}))

	def test_live_flags_come_from_the_courses_and_skip_deleted_ones(self):
		rows = [frappe._dict(name="live", published=1), frappe._dict(name="draft", published=0)]
		with patch.object(override_api.frappe, "get_all", return_value=rows) as get_all:
			flags = override_api.get_live_course_flags(["live", "draft", "gone", "live", ""])

		self.assertEqual(flags, {"live": 1, "draft": 0})
		# Each name once, no blank one, and no permission filter on the existence check.
		self.assertEqual(get_all.call_args.kwargs["filters"], {"name": ["in", ["live", "draft", "gone"]]})

	def test_no_course_results_means_no_query(self):
		with patch.object(override_api.frappe, "get_all") as get_all:
			self.assertEqual(override_api.get_live_course_flags([]), {})
		get_all.assert_not_called()

	def test_grouped_results_drop_a_stale_index_row(self):
		result = {
			"results": [
				_row("live", published=1),
				_row("gone", published=1),
				_row("draft", published=1),
			]
		}
		live = {"live": 1, "draft": 0}
		with (
			patch.object(override_api, "get_live_course_flags", return_value=live),
			patch(CAN_READ, return_value=False),
			patch.object(override_api, "get_instructor_info", return_value=[]),
		):
			groups = override_api.get_grouped_results_custom(result)

		self.assertEqual([r["name"] for r in groups.get("Courses", [])], ["live"])

	def test_stale_course_instructor_rows_are_dropped(self):
		# Collaudo v2.64: course "corso-0011", renamed "Public Speaking", was still found
		# and shown as "corso 0011" through a Course Instructor row of an old index.
		result = {
			"results": [
				_row("corso-0011", row_id="Course Instructor:2m0kov73j6", title="corso 0011", published=0),
				_row("corso-0011", title="Public Speaking", published=0),
			]
		}
		with (
			patch.object(override_api, "get_live_course_flags", return_value={"corso-0011": 0}),
			patch(CAN_READ, return_value=True),
			patch.object(override_api, "get_instructor_info", return_value=[]),
		):
			groups = override_api.get_grouped_results_custom(result)

		self.assertEqual([r["title"] for r in groups["Courses"]], ["Public Speaking"])
