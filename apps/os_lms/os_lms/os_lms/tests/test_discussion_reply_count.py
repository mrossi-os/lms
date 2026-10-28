"""The reply count in get_discussion_topics runs on our Frappe release.

Upstream 6f299d0d2 counted the replies with fields=["topic", "count(name) as count"];
Frappe refuses SQL functions written as strings in fields, so listing a batch's
topics answered 417. The batch page asks for a single thread, which returns before
the count, so nothing on screen showed it.
"""

import pathlib
import re
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

# A get_all field written as a SQL call, e.g. "count(name) as count" or "sum(score)".
STRING_SQL_FUNCTION = re.compile(r"""["'](count|sum|avg|min|max)\([^"']*\)(\s+as\s+\w+)?["']""", re.I)
# Lines that may keep the string form: get_chart_details uses it only on Frappe 14/15,
# behind a version check, and the dict form on newer releases.
ALLOWED_LINES = {
	("lms/lms/utils.py", 'fields=[f"{datefield} as _unit", f"SUM({value_field})", "COUNT(*)"],'),
}


class TestDiscussionReplyCount(UnitTestCase):
	def test_listing_topics_runs_the_real_count_query(self):
		from lms.lms import utils

		topic = frappe._dict(name="topic-reply-count-test", title="t", owner="Administrator")
		real_get_all = frappe.get_all

		def get_all(doctype, *args, **kwargs):
			if doctype == "Discussion Topic":
				return [topic]
			return real_get_all(doctype, *args, **kwargs)

		with (
			patch.object(utils, "can_access_topic", return_value=True),
			patch.object(utils.frappe, "get_all", side_effect=get_all),
		):
			topics = utils.get_discussion_topics("LMS Batch", "batch-1")
		self.assertEqual(topics[0].reply_count, 0)

	def test_no_get_all_field_is_a_string_sql_function(self):
		offenders = []
		for app in ("lms", "os_lms"):
			root = pathlib.Path(frappe.get_app_path(app))
			for path in root.rglob("*.py"):
				if "tests" in path.parts or path.name.startswith("test_"):
					continue
				for number, line in enumerate(path.read_text().splitlines(), 1):
					relative = f"{app}/{path.relative_to(root)}"
					if STRING_SQL_FUNCTION.search(line) and (relative, line.strip()) not in ALLOWED_LINES:
						offenders.append(f"{relative}:{number}")
		self.assertEqual(offenders, [])
