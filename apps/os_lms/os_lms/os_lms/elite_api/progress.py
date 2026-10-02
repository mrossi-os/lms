"""Progress summaries of the Elite API (docs/elite-api/fase-3-analisi.md).

Rules shared by every endpoint:

- a student counts only with an existing, enabled user (disabled users are
  excluded, D13); course enrollments also need member_type "Student" (D3);
- one state per student and course: duplicated LMS Enrollment rows (4 pairs in
  production) collapse to their highest progress;
- course: completed = 100, in progress = between 0 and 100, not started = 0;
- batch: computed on the batch COURSES only, not its assessments (D4); a batch
  course the student never opened has no LMS Enrollment yet and counts as 0%;
  completed_all = every course at 100, partial = at least one course started
  but not all completed, not_started = no course started (also when the batch
  has no courses).

Each function answers a whole page with one aggregate query. The queries are
plain literals: only values travel as parameters.
"""

from __future__ import annotations

import frappe

COURSE_SUMMARY_SQL = """
	select p.course,
		count(*) as total,
		sum(p.progress >= 100) as completed,
		sum(p.progress > 0 and p.progress < 100) as in_progress,
		sum(p.progress <= 0) as not_started
	from (
		select e.course, e.member, max(ifnull(e.progress, 0)) as progress
		from `tabLMS Enrollment` e
		where e.member_type = 'Student' and e.course in %(courses)s
		group by e.course, e.member
	) p
	inner join `tabUser` u on u.name = p.member and u.enabled = 1
	group by p.course
"""

BATCH_SUMMARY_SQL = """
	select s.batch,
		count(*) as total,
		sum(s.courses_total > 0 and s.completed = s.courses_total) as completed_all,
		sum(s.started > 0 and not (s.courses_total > 0 and s.completed = s.courses_total)) as partial,
		sum(s.started = 0) as not_started
	from (
		select be.batch, be.member,
			count(bc.course) as courses_total,
			ifnull(sum(ifnull(p.progress, 0) >= 100), 0) as completed,
			ifnull(sum(ifnull(p.progress, 0) > 0), 0) as started
		from `tabLMS Batch Enrollment` be
		inner join `tabUser` u on u.name = be.member and u.enabled = 1
		left join (
			select distinct parent, course
			from `tabBatch Course`
			where parenttype = 'LMS Batch' and parent in %(batches)s
		) bc on bc.parent = be.batch
		left join (
			select e.course, e.member, max(ifnull(e.progress, 0)) as progress
			from `tabLMS Enrollment` e
			where e.member_type = 'Student' and e.course in (
				select course from `tabBatch Course`
				where parenttype = 'LMS Batch' and parent in %(batches)s
			)
			group by e.course, e.member
		) p on p.course = bc.course and p.member = be.member
		where be.batch in %(batches)s
		group by be.batch, be.member
	) s
	group by s.batch
"""


def empty_course_summary() -> dict:
	return {"total": 0, "completed": 0, "in_progress": 0, "not_started": 0}


def empty_batch_summary() -> dict:
	return {"total": 0, "completed_all": 0, "partial": 0, "not_started": 0}


def course_summaries(courses: list[str]) -> dict[str, dict]:
	"""Return ``{course: {total, completed, in_progress, not_started}}``."""
	summaries = {course: empty_course_summary() for course in courses}
	if not courses:
		return summaries

	for row in frappe.db.sql(COURSE_SUMMARY_SQL, {"courses": tuple(courses)}, as_dict=True):
		summaries[row.course] = {
			"total": int(row.total),
			"completed": int(row.completed or 0),
			"in_progress": int(row.in_progress or 0),
			"not_started": int(row.not_started or 0),
		}
	return summaries


def batch_summaries(batches: list[str]) -> dict[str, dict]:
	"""Return ``{batch: {total, completed_all, partial, not_started}}``."""
	summaries = {batch: empty_batch_summary() for batch in batches}
	if not batches:
		return summaries

	for row in frappe.db.sql(BATCH_SUMMARY_SQL, {"batches": tuple(batches)}, as_dict=True):
		summaries[row.batch] = {
			"total": int(row.total),
			"completed_all": int(row.completed_all or 0),
			"partial": int(row.partial or 0),
			"not_started": int(row.not_started or 0),
		}
	return summaries


# -- Student lists (same rules as the summaries above) ------------------------

COURSE_STATUSES = ("completed", "in_progress", "not_started")
BATCH_STATUSES = ("completed_all", "partial", "not_started")

# The status filter lives in the queries, so that totals and pages match it.
# Each list query has a count twin with the same FROM/WHERE: keep them in sync.

COURSE_STUDENTS_SQL = """
	select u.first_name, u.last_name, u.codice_fiscale, u.email, p.enrolled_on, p.progress
	from (
		select e.member, max(ifnull(e.progress, 0)) as progress, min(e.creation) as enrolled_on
		from `tabLMS Enrollment` e
		where e.member_type = 'Student' and e.course = %(course)s
		group by e.member
	) p
	inner join `tabUser` u on u.name = p.member and u.enabled = 1
	where %(status)s is null
		or (%(status)s = 'completed' and p.progress >= 100)
		or (%(status)s = 'in_progress' and p.progress > 0 and p.progress < 100)
		or (%(status)s = 'not_started' and p.progress <= 0)
	order by u.last_name, u.first_name, u.email
	limit %(limit)s offset %(offset)s
"""

COURSE_STUDENTS_COUNT_SQL = """
	select count(*)
	from (
		select e.member, max(ifnull(e.progress, 0)) as progress
		from `tabLMS Enrollment` e
		where e.member_type = 'Student' and e.course = %(course)s
		group by e.member
	) p
	inner join `tabUser` u on u.name = p.member and u.enabled = 1
	where %(status)s is null
		or (%(status)s = 'completed' and p.progress >= 100)
		or (%(status)s = 'in_progress' and p.progress > 0 and p.progress < 100)
		or (%(status)s = 'not_started' and p.progress <= 0)
"""

BATCH_STUDENTS_SQL = """
	select u.name as member, u.first_name, u.last_name, u.codice_fiscale, u.email,
		s.enrolled_on, s.courses_total, s.completed, s.started
	from (
		select be.member, be.creation as enrolled_on,
			count(bc.course) as courses_total,
			ifnull(sum(ifnull(p.progress, 0) >= 100), 0) as completed,
			ifnull(sum(ifnull(p.progress, 0) > 0), 0) as started
		from `tabLMS Batch Enrollment` be
		left join (
			select distinct course
			from `tabBatch Course`
			where parenttype = 'LMS Batch' and parent = %(batch)s
		) bc on 1 = 1
		left join (
			select e.course, e.member, max(ifnull(e.progress, 0)) as progress
			from `tabLMS Enrollment` e
			where e.member_type = 'Student' and e.course in (
				select course from `tabBatch Course`
				where parenttype = 'LMS Batch' and parent = %(batch)s
			)
			group by e.course, e.member
		) p on p.course = bc.course and p.member = be.member
		where be.batch = %(batch)s
		group by be.member, be.creation
	) s
	inner join `tabUser` u on u.name = s.member and u.enabled = 1
	where %(status)s is null
		or (%(status)s = 'completed_all' and s.courses_total > 0 and s.completed = s.courses_total)
		or (%(status)s = 'partial' and s.started > 0 and not (s.courses_total > 0 and s.completed = s.courses_total))
		or (%(status)s = 'not_started' and s.started = 0)
	order by u.last_name, u.first_name, u.email
	limit %(limit)s offset %(offset)s
"""

BATCH_STUDENTS_COUNT_SQL = """
	select count(*)
	from (
		select be.member,
			count(bc.course) as courses_total,
			ifnull(sum(ifnull(p.progress, 0) >= 100), 0) as completed,
			ifnull(sum(ifnull(p.progress, 0) > 0), 0) as started
		from `tabLMS Batch Enrollment` be
		left join (
			select distinct course
			from `tabBatch Course`
			where parenttype = 'LMS Batch' and parent = %(batch)s
		) bc on 1 = 1
		left join (
			select e.course, e.member, max(ifnull(e.progress, 0)) as progress
			from `tabLMS Enrollment` e
			where e.member_type = 'Student' and e.course in (
				select course from `tabBatch Course`
				where parenttype = 'LMS Batch' and parent = %(batch)s
			)
			group by e.course, e.member
		) p on p.course = bc.course and p.member = be.member
		where be.batch = %(batch)s
		group by be.member
	) s
	inner join `tabUser` u on u.name = s.member and u.enabled = 1
	where %(status)s is null
		or (%(status)s = 'completed_all' and s.courses_total > 0 and s.completed = s.courses_total)
		or (%(status)s = 'partial' and s.started > 0 and not (s.courses_total > 0 and s.completed = s.courses_total))
		or (%(status)s = 'not_started' and s.started = 0)
"""

# Per-course progress of one page of batch students.
BATCH_STUDENT_COURSES_SQL = """
	select e.member, e.course, max(ifnull(e.progress, 0)) as progress
	from `tabLMS Enrollment` e
	where e.member_type = 'Student' and e.member in %(members)s and e.course in (
		select course from `tabBatch Course`
		where parenttype = 'LMS Batch' and parent = %(batch)s
	)
	group by e.member, e.course
"""


def course_status(progress: float) -> str:
	if progress >= 100:
		return "completed"
	return "in_progress" if progress > 0 else "not_started"


def batch_status(courses_total: int, completed: int, started: int) -> str:
	if courses_total and completed == courses_total:
		return "completed_all"
	return "partial" if started else "not_started"


def course_students(course: str, status: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
	"""Return ``(students, total)``; ``total`` counts every student matching ``status``."""
	values = {"course": course, "status": status, "limit": limit, "offset": offset}
	students = [
		{
			**_identity(row),
			"enrolled_on": _iso(row.enrolled_on),
			"progress": _progress(row.progress),
			"status": course_status(_progress(row.progress)),
		}
		for row in frappe.db.sql(COURSE_STUDENTS_SQL, values, as_dict=True)
	]
	total = frappe.db.sql(COURSE_STUDENTS_COUNT_SQL, values)[0][0]
	return students, int(total)


def batch_students(
	batch: str, courses: list[str], status: str | None, limit: int, offset: int
) -> tuple[list[dict], int]:
	"""Return ``(students, total)``; ``courses`` are the batch course names, in batch order."""
	values = {"batch": batch, "status": status, "limit": limit, "offset": offset}
	rows = frappe.db.sql(BATCH_STUDENTS_SQL, values, as_dict=True)
	total = frappe.db.sql(BATCH_STUDENTS_COUNT_SQL, values)[0][0]

	progress_by_member: dict[str, dict[str, float]] = {}
	if rows and courses:
		for row in frappe.db.sql(
			BATCH_STUDENT_COURSES_SQL,
			{"batch": batch, "members": tuple(row.member for row in rows)},
			as_dict=True,
		):
			progress_by_member.setdefault(row.member, {})[row.course] = _progress(row.progress)

	students = []
	for row in rows:
		progress = progress_by_member.get(row.member, {})
		students.append(
			{
				**_identity(row),
				"enrolled_on": _iso(row.enrolled_on),
				"courses_completed": int(row.completed),
				"courses_total": int(row.courses_total),
				"status": batch_status(int(row.courses_total), int(row.completed), int(row.started)),
				"courses": [
					{
						"id": course,
						"progress": progress.get(course, 0.0),
						"status": course_status(progress.get(course, 0.0)),
					}
					for course in courses
				],
			}
		)
	return students, int(total)


def _identity(row) -> dict:
	fiscal_code = "".join((row.codice_fiscale or "").split()).upper()
	return {
		"first_name": row.first_name or "",
		"last_name": row.last_name or "",
		"fiscal_code": fiscal_code or None,
		"email": row.email,
	}


def _progress(value) -> float:
	return round(float(value or 0), 2)


def _iso(value) -> str | None:
	return value.replace(microsecond=0).isoformat() if value else None
