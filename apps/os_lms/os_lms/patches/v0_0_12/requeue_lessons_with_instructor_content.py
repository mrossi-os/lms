"""Queue a re-index of the lessons whose RAG chunks hold instructor notes.

Until 2026-11 LessonContentParser indexed ``instructor_content`` next to the
lesson body, and the AI tutor answers learners from that same index: the
instructor-only notes could be repeated to students. The parser no longer reads
them, but the chunks already in Redis keep the old text until the lesson is
indexed again.

This patch only flags the affected lessons as ``pending``; the daily scheduler
job ``reindex_lesson_content`` re-ingests them, and ``RagDB.ingest_data``
deletes the lesson's old vectors before saving the new ones. Lessons without
instructor notes are left alone, so no embedding or transcription is paid for
them.

Safe to run again: lessons still pending are skipped. A lesson the scheduler
has already re-indexed would be queued once more (one extra paid ingestion,
same result), so run it by hand only once per site.

On a site where patches are bulk-marked as done before migrate, run it by hand:
    bench --site <site> execute os_lms.patches.v0_0_12.requeue_lessons_with_instructor_content.execute
"""

import json

import frappe

# Statuses whose lesson may have chunks in Redis built by the old parser.
# "failed" is included: a failed run can leave the previous vectors in place.
REQUEUE_FROM = ("indexed", "failed")


def has_instructor_blocks(raw) -> bool:
	"""True when instructor_content holds at least one EditorJS block."""
	if not raw:
		return False
	if isinstance(raw, list):
		return bool(raw)
	try:
		parsed = json.loads(raw)
	except (TypeError, ValueError):
		# Non-JSON text (legacy markdown) is still content.
		return bool(str(raw).strip())
	if isinstance(parsed, dict):
		return bool(parsed.get("blocks"))
	if isinstance(parsed, list):
		return bool(parsed)
	return False


def lessons_to_requeue() -> list[str]:
	rows = frappe.get_all(
		"Course Lesson",
		filters={
			"index_status": ["in", REQUEUE_FROM],
			"instructor_content": ["is", "set"],
		},
		fields=["name", "instructor_content"],
	)
	return [row.name for row in rows if has_instructor_blocks(row.instructor_content)]


def execute():
	names = lessons_to_requeue()
	if not names:
		return
	frappe.db.set_value(
		"Course Lesson",
		{"name": ["in", names]},
		"index_status",
		"pending",
		update_modified=False,
	)
