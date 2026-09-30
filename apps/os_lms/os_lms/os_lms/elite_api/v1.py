"""Elite API, version 1. Every endpoint is GET-only and guarded by ``elite_api_endpoint``.

Parameters are declared as ``str | None`` and parsed by ``errors.parse_*``, so a
bad value answers 400 instead of Frappe's 417 type error.
"""

import frappe

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.auth import elite_api_endpoint, get_current_key
from os_lms.os_lms.elite_api.errors import parse_int_param
from os_lms.os_lms.elite_api.progress import batch_summaries, course_summaries

DEFAULT_PAGE_LENGTH = 100
MAX_PAGE_LENGTH = 500


@frappe.whitelist(methods=["GET"])
@elite_api_endpoint
def ping() -> dict:
	"""Let a client check that its key works."""
	return {
		"status": "ok",
		"api_version": "v1",
		"key_name": frappe.db.get_value(keys.KEY_DOCTYPE, get_current_key(), "key_name"),
	}


@frappe.whitelist(methods=["GET"])
@elite_api_endpoint
def list_courses(search: str | None = None, page: str | None = None, page_length: str | None = None) -> dict:
	"""Every course, published or not, with the progress summary of its students."""
	page_no, length = _pagination(page, page_length)
	filters = _title_filter(search)

	courses = frappe.get_all(
		"LMS Course",
		filters=filters,
		fields=["name", "title", "published", "trueskills_certificate_enabled"],
		order_by="title asc, name asc",
		start=(page_no - 1) * length,
		page_length=length,
	)
	summaries = course_summaries([course.name for course in courses])

	return _page(
		total=frappe.db.count("LMS Course", filters),
		page_no=page_no,
		length=length,
		data=[
			{
				"id": course.name,
				"title": course.title,
				"published": bool(course.published),
				"trueskills_certificate_enabled": bool(course.trueskills_certificate_enabled),
				"students": summaries[course.name],
			}
			for course in courses
		],
	)


@frappe.whitelist(methods=["GET"])
@elite_api_endpoint
def list_batches(search: str | None = None, page: str | None = None, page_length: str | None = None) -> dict:
	"""Every batch with its courses and the progress summary of its students."""
	page_no, length = _pagination(page, page_length)
	filters = _title_filter(search)

	batches = frappe.get_all(
		"LMS Batch",
		filters=filters,
		fields=["name", "title", "start_date", "end_date", "published"],
		order_by="start_date desc, title asc, name asc",
		start=(page_no - 1) * length,
		page_length=length,
	)
	names = [batch.name for batch in batches]
	summaries = batch_summaries(names)
	courses = _batch_courses(names)

	return _page(
		total=frappe.db.count("LMS Batch", filters),
		page_no=page_no,
		length=length,
		data=[
			{
				"id": batch.name,
				"title": batch.title,
				"start_date": batch.start_date,
				"end_date": batch.end_date,
				"published": bool(batch.published),
				"courses": courses.get(batch.name, []),
				"students": summaries[batch.name],
			}
			for batch in batches
		],
	)


def _pagination(page: str | None, page_length: str | None) -> tuple[int, int]:
	return (
		parse_int_param("page", page, default=1, minimum=1),
		parse_int_param(
			"page_length", page_length, default=DEFAULT_PAGE_LENGTH, minimum=1, maximum=MAX_PAGE_LENGTH
		),
	)


def _title_filter(search: str | None) -> dict:
	search = (search or "").strip()
	if not search:
		return {}
	# Match the text literally: % and _ are LIKE wildcards.
	escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
	return {"title": ["like", f"%{escaped}%"]}


def _page(total: int, page_no: int, length: int, data: list) -> dict:
	return {"total": total, "page": page_no, "page_length": length, "data": data}


def _batch_courses(batches: list[str]) -> dict[str, list[dict]]:
	"""Return ``{batch: [{id, title}]}`` in the order the courses appear in each batch."""
	if not batches:
		return {}
	batch_course = frappe.qb.DocType("Batch Course")
	course = frappe.qb.DocType("LMS Course")
	rows = (
		frappe.qb.from_(batch_course)
		.inner_join(course)
		.on(course.name == batch_course.course)
		.select(batch_course.parent, course.name, course.title)
		.where((batch_course.parenttype == "LMS Batch") & batch_course.parent.isin(batches))
		.orderby(batch_course.parent)
		.orderby(batch_course.idx)
		.run(as_dict=True)
	)
	courses: dict[str, list[dict]] = {}
	for row in rows:
		courses.setdefault(row.parent, []).append({"id": row.name, "title": row.title})
	return courses
