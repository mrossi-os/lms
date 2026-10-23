"""Checks shared by the endpoints that hand out lesson content or spend provider
money on a learner's behalf (OWASP A01 Broken Access Control, A06 Insecure Design).

`@frappe.whitelist()` only means "logged in": these helpers are the part that
says whether this user may read this course or lesson, and how often they may
call an endpoint that bills the AI or Vimeo account.
"""

import functools

import frappe
from frappe import _


def assert_course_readable(course: str) -> None:
	"""Pass only someone who follows the course: an author, a Valutatore of a batch
	holding it, or an enrolled member. Being published is not enough here: the
	tutor answers from the lessons themselves."""
	from lms.lms.utils import can_modify_course, get_membership, is_course_valutatore

	if not course or not frappe.db.exists("LMS Course", course):
		frappe.throw(_("Course not found"), frappe.DoesNotExistError)
	if can_modify_course(course) or is_course_valutatore(course) or get_membership(course):
		return
	frappe.throw(_("You are not enrolled in this course."), frappe.PermissionError)


def assert_lesson_readable(lesson: str, course: str | None = None) -> str:
	"""Return the lesson's course after checking the user may open the lesson now.

	Upstream's lesson gate (authors, Valutatore, enrolled members, preview lessons)
	plus the sequential unlock a learner sees in the SPA: an enrolled student
	cannot reach a locked lesson through the tutor or the audio stream either.
	`course`, when given, must be the lesson's own.
	"""
	from lms.lms.permissions import can_access_lesson, get_lesson_gate

	lesson_course = frappe.db.get_value("Course Lesson", lesson, "course") if lesson else None
	if not lesson_course or (course and lesson_course != course):
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	if not can_access_lesson(lesson):
		frappe.throw(_("You do not have access to this lesson."), frappe.PermissionError)
	locked, _resume = get_lesson_gate(lesson_course)
	if lesson in locked:
		frappe.throw(_("Complete the previous lesson before continuing."), frappe.PermissionError)
	return lesson_course


def per_user_rate_limit(limit: int, seconds: int):
	"""Cap how often one user may call the decorated endpoint.

	Per user, not per IP like `frappe.rate_limiter.rate_limit`: a class behind one
	school or company NAT would share a single budget. Like Frappe's, it applies
	only to HTTP requests, not to jobs, the console or tests.
	"""

	def decorator(fn):
		@functools.wraps(fn)
		def wrapper(*args, **kwargs):
			check_user_rate_limit(f"{fn.__module__}.{fn.__name__}", limit, seconds)
			return fn(*args, **kwargs)

		return wrapper

	return decorator


def check_user_rate_limit(action: str, limit: int, seconds: int) -> None:
	"""Count one `action` for the session user; throw 429 past `limit` per window."""
	if not frappe.request:
		return
	key = frappe.cache.make_key(f"os_lms:rl:{action}:{frappe.session.user}")
	if not frappe.cache.get(key):
		frappe.cache.setex(key, seconds, 0)
	if frappe.cache.incrby(key, 1) > limit:
		frappe.throw(_("Too many requests. Please try again later."), frappe.RateLimitExceededError)
