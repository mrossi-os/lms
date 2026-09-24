"""Turn the old <lms-inline-color> element in lesson content into a colour span.

Upstream v2.63.0 removed its inline colour tool; ours is rebuilt on the new
toolbar and emits <span class="lms-inline-color" style="...">, which both
sanitisers keep without an allowlist. Lessons saved with the old element still
render, but the new tool cannot find them to edit. This rewrites them once.
Only string values inside the EditorJS JSON are touched; unparseable content is
left alone. Idempotent: a converted lesson has no <lms-inline-color> left.
"""

import json
import re

import frappe

FIELDS = ("content", "instructor_content")
OPEN_TAG = re.compile(r"<lms-inline-color(\s[^>]*)?>", re.IGNORECASE)
CLOSE_TAG = re.compile(r"</lms-inline-color\s*>", re.IGNORECASE)
CLASS_ATTR = re.compile(r"""\bclass\s*=\s*(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)


def _open_span(match: re.Match) -> str:
	attrs = match.group(1) or ""
	if CLASS_ATTR.search(attrs):
		quote_and_merge = lambda m: f"class={m.group(1)}lms-inline-color {m.group(2)}{m.group(1)}"  # noqa: E731
		return f"<span{CLASS_ATTR.sub(quote_and_merge, attrs, count=1)}>"
	return f'<span class="lms-inline-color"{attrs}>'


def convert_markup(text: str) -> str:
	return CLOSE_TAG.sub("</span>", OPEN_TAG.sub(_open_span, text))


def convert_value(value):
	if isinstance(value, str):
		return convert_markup(value)
	if isinstance(value, list):
		return [convert_value(item) for item in value]
	if isinstance(value, dict):
		return {key: convert_value(item) for key, item in value.items()}
	return value


def convert_content(raw: str | None) -> str | None:
	"""The rewritten JSON, or None when there is nothing to change."""
	if not raw or "<lms-inline-color" not in raw.lower():
		return None
	try:
		data = json.loads(raw)
	except ValueError:
		return None
	return json.dumps(convert_value(data), ensure_ascii=False, separators=(",", ":"))


def execute():
	for field in FIELDS:
		lessons = frappe.get_all(
			"Course Lesson",
			filters={field: ["like", "%<lms-inline-color%"]},
			fields=["name", field],
		)
		for lesson in lessons:
			converted = convert_content(lesson.get(field))
			if converted is not None:
				frappe.db.set_value(
					"Course Lesson", lesson.name, field, converted, update_modified=False
				)
