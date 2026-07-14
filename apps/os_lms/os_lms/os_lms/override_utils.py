import json

import frappe
from frappe.rate_limiter import rate_limit

from lms.lms.utils import get_batch_details as _original_get_batch_details
from lms.lms.utils import get_batches as _original_get_batches
from lms.lms.utils import get_course_details as _original_get_course_details
from lms.lms.utils import get_course_outline as _original_get_course_outline
from lms.lms.utils import get_courses as _orginal_get_courses
from lms.lms.utils import get_lesson as _original_get_lesson
from lms.lms.utils import get_lesson_details as _original_get_lesson_details
from lms.lms.utils import get_lesson_icon, get_progress, is_course_valutatore
from os_lms.os_lms.api import (
	_find_adjacent_video_lessons,
	evaluate_lesson_access,
	evaluate_quiz_access,
	get_batch_tab_unread_counts,
)
from os_lms.os_lms.utils import get_course_feature_sections, get_courses_total_minutes
from os_lms.os_lms.valutatore import (
	_only_scoped_valutatore,
	get_valutatore_batches,
	get_valutatore_course_names,
)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_course_details(course: str):
	course_detail = _original_get_course_details(course)
	course_detail.feature_sections = get_course_feature_sections(course)

	hero = (
		frappe.db.get_value(
			"LMS Course",
			course,
			[
				"hero_enabled",
				"hero_media_type",
				"hero_media_url",
				"trueskills_certificate_enabled",
			],
			as_dict=True,
		)
		or {}
	)
	course_detail.hero = {
		"enabled": bool(hero.get("hero_enabled")),
		"media_type": hero.get("hero_media_type") or "Video",
		"media_url": hero.get("hero_media_url") or "",
	}

	# Exposed so the SPA "Get Certificate" gate works for TrueSkills-only courses
	# (where the internal completion certificate is off — the two are exclusive).
	course_detail.trueskills_certificate_enabled = (
		1 if hero.get("trueskills_certificate_enabled") else 0
	)

	# Read-only access flag for a "Valutatore" of a batch containing this course:
	# the SPA uses it to skip the "unpublished → redirect to Courses" guard.
	course_detail.is_valutatore = is_course_valutatore(course)

	return course_detail


@frappe.whitelist(allow_guest=True)
def get_course_outline(course: str, progress: bool = False) -> list:
	detail = _original_get_course_outline(course, progress)
	if detail.count == 0:
		return detail

	lessons = frappe.get_all(
		"Course Lesson",
		filters={
			"course": course,
		},
		fields=["name", "index_status", "indexed_at", "tags"],
	)
	lesson_index = {lesson.name: lesson for lesson in lessons}
	for item in detail:
		for lesson in item.get("lessons", []):
			lesson_info = lesson_index.get(lesson["name"])
			if lesson_info:
				lesson["index_status"] = lesson_info.index_status
				lesson["indexed_at"] = lesson_info.indexed_at
				lesson["tags"] = lesson_info.tags
	return detail


@frappe.whitelist(allow_guest=True)
def get_lesson(course: str, chapter: int, lesson: int) -> dict:
	lesson_details = _original_get_lesson(course, chapter, lesson)
	if isinstance(lesson_details, dict) and lesson_details.get("name"):
		lesson_name = lesson_details["name"]
		lesson_details["tags"] = frappe.db.get_value("Course Lesson", lesson_name, "tags")

		user = frappe.session.user
		is_guest = not user or user == "Guest"
		roles = set(frappe.get_roles(user)) if not is_guest else set()
		instructors = lesson_details.get("instructors") or []
		is_admin = (
			bool(roles & {"Moderator", "Course Creator", "LMS Instructor"})
			or user in instructors
			# A valutatore of a batch containing this course reviews it read-only,
			# so it should reach every lesson regardless of enrolment / order.
			or is_course_valutatore(course)
		)

		if is_guest or is_admin:
			lesson_details["lesson_access"] = {"allowed": True}
			lesson_details["quiz_access"] = {"allowed": True}
		else:
			lesson_details["lesson_access"] = evaluate_lesson_access(course, lesson_name)
			lesson_details["quiz_access"] = evaluate_quiz_access(course, lesson_name)

		# Published simulation scenarios visible from this lesson. Returns the
		# lesson-specific ones first (course_lesson == lesson_name) and falls
		# back to course-level scenarios if none are bound to the lesson.
		# The frontend (Lesson.vue / SimulationLauncher) uses this list to
		# decide whether to render the "Avvia simulazione" button.
		lesson_details["simulations"] = _list_simulations_for_lesson(course, lesson_name)
	return lesson_details


def _list_simulations_for_lesson(course: str, lesson_name: str) -> list[dict]:
	"""List Published scenarios available from a given lesson.

	Lesson-bound scenarios come first; course-level (no lesson) scenarios
	fill the remaining slots so the launcher has something to offer even on
	lessons without a dedicated scenario.
	"""
	fields = ["name", "scenario_name", "difficulty", "modality", "course_lesson", "time_limit_minutes"]
	bound = frappe.get_all(
		"LMSA Simulation Scenario",
		filters={"lms_course": course, "course_lesson": lesson_name, "status": "Published"},
		fields=fields,
		order_by="modified desc",
	)
	course_level = frappe.get_all(
		"LMSA Simulation Scenario",
		filters={"lms_course": course, "course_lesson": ["in", [None, ""]], "status": "Published"},
		fields=fields,
		order_by="modified desc",
	)
	return bound + course_level


@frappe.whitelist()
def get_lesson_creation_details(course: str, chapter: int, lesson: int) -> dict:
	frappe.only_for(["Moderator", "Course Creator"])
	chapter_name = frappe.db.get_value("Chapter Reference", {"parent": course, "idx": chapter}, "chapter")
	lesson_name = frappe.db.get_value("Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson")

	if lesson_name:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			lesson_name,
			[
				"name",
				"title",
				"include_in_preview",
				"body",
				"content",
				"instructor_notes",
				"instructor_content",
				"youtube",
				"quiz_id",
				"duration",
				"index_status",
				"indexed_at",
				"tags",
			],
			as_dict=1,
		)
	lesson_count = frappe.db.count("Lesson Reference", {"parent": chapter_name})

	return {
		"course_title": frappe.db.get_value("LMS Course", course, "title"),
		"chapter": frappe.db.get_value("Course Chapter", chapter_name, ["title", "name"], as_dict=True),
		"lesson": lesson_details if lesson_name else None,
		"lesson_count": lesson_count,
	}


def custom_get_lesson_details(chapter: dict, progress: bool = False):
	lessons = []
	lesson_list = frappe.get_all(
		"Lesson Reference", {"parent": chapter.name}, ["lesson", "idx"], order_by="idx"
	)
	for row in lesson_list:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			row.lesson,
			[
				"name",
				"title",
				"include_in_preview",
				"body",
				"creation",
				"youtube",
				"quiz_id",
				"question",
				"file_type",
				"instructor_notes",
				"course",
				"chapter",
				"content",
				"index_status",
				"indexed_at",
				"tags",
			],
			as_dict=True,
		)
		lesson_details.number = f"{chapter.idx}-{row.idx}"
		lesson_details.icon = get_lesson_icon(lesson_details.body, lesson_details.content)

		if progress:
			lesson_details.is_complete = get_progress(lesson_details.course, lesson_details.name)

		lessons.append(lesson_details)
	return lessons


# ---------------------------------------------------------------------------
# Valutatore visibility scoping for the Courses / Batches list views.
#
# A scoped "Valutatore" must only see the records they are assigned to plus the
# public (published) ones — for both batches ("classi") and the courses linked to
# those batches. The base list methods use ``frappe.get_all`` (which ignores user
# permissions), so the scoping is enforced here, regardless of the filters the
# frontend tabs send.
# ---------------------------------------------------------------------------
def _scope_filters_for_valutatore(filters: dict, doctype: str, get_own_names) -> dict:
	"""Narrow the ``name`` filter to "published OR assigned to the valutatore"."""
	if not _only_scoped_valutatore(frappe.session.user):
		return filters

	filters = dict(filters or {})
	published = set(frappe.get_all(doctype, {"published": 1}, pluck="name"))
	allowed = published | set(get_own_names())

	# The union already encodes "published OR mine"; a published filter coming
	# from the frontend tabs would otherwise hide the valutatore's own drafts.
	filters.pop("published", None)

	existing = filters.get("name")
	if isinstance(existing, (list, tuple)) and len(existing) == 2 and str(existing[0]).lower() == "in":
		allowed &= set(existing[1])

	filters["name"] = ["in", list(allowed) or [""]]
	return filters


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_courses(filters: dict = None, start: int = 0) -> list:
	filters = _scope_filters_for_valutatore(filters, "LMS Course", get_valutatore_course_names)
	courses = _orginal_get_courses(filters, start)

	if courses:
		course_names = [course.name for course in courses]
		duration_map = get_courses_total_minutes(course_names)
		for course in courses:
			course.total_minutes = duration_map.get(course.name, 0)

	return courses


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_batches(filters: dict = None, start: int = 0, order_by: str = "start_date") -> list:
	filters = _scope_filters_for_valutatore(filters, "LMS Batch", get_valutatore_batches)
	return _original_get_batches(filters, start, order_by)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_batch_details(batch: str):
	# Stale notifications / deep links can point at a batch that no longer exists.
	# The upstream helper then crashes setting attributes on a None result (for a
	# batch admin the permission guard passes but the row fetch returns None).
	# Return None so the SPA's "no data" guard redirects to the batch list.
	if not frappe.db.exists("LMS Batch", batch):
		return None

	batch_detail = _original_get_batch_details(batch)

	# Upstream returns {} when the user can't access the batch — don't try to set
	# custom attributes on a falsy result.
	if not batch_detail:
		return batch_detail

	raw = frappe.db.get_value("LMS Batch", batch, "custom_feature_sections")
	try:
		if raw:
			unescaped = raw.replace("&quot;", '"').replace("&amp;", "&")
			batch_detail.custom_feature_sections = json.loads(unescaped)
		else:
			batch_detail.custom_feature_sections = []
	except (json.JSONDecodeError, TypeError):
		batch_detail.custom_feature_sections = []

	batch_detail.tab_notifications = get_batch_tab_unread_counts(batch)

	return batch_detail


def _has_role(member: str, role: str):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": role},
		"name",
	)


@frappe.whitelist()
def get_roles(name: str) -> dict:
	from lms.lms.utils import get_roles as _original_get_roles

	base = _original_get_roles(name)
	base["manager"] = _has_role(name, "Gestore")
	base["instructor"] = _has_role(name, "Docente")
	base["valutatore"] = _has_role(name, "Valutatore")
	return base
