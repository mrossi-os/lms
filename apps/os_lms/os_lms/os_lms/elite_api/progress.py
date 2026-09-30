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
