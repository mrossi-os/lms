import frappe
from frappe import _

from lms.lms.utils import can_modify_course, has_course_instructor_role, has_moderator_role, is_instructor

from os_lms.os_lms.access_guards import per_user_rate_limit

from .service import IngestionService

# Each run deletes and recomputes the lesson's embeddings (a paid OpenAI call).
INGESTIONS_PER_HOUR = 30


@frappe.whitelist(methods=["POST"])
@per_user_rate_limit(limit=INGESTIONS_PER_HOUR, seconds=60 * 60)
def start_lesson_ingestion(lesson_id):
	"""
	Start ingestion for a lesson. Teacher-only endpoint.

	Args:
	        lesson_id: The Course Lesson name/ID

	Returns:
	        dict with status, message, material name and chunk_count
	"""
	lesson = _load_lesson(lesson_id)
	service = IngestionService()
	service.ingest_lesson(lesson)
	return {"success": True}


@frappe.whitelist(methods=["POST"])
def start_course_feature_ingestion(course_name):
	"""
	Start ingestion of a course's feature sections. Teacher-only endpoint.

	Enqueues the actual work as a background job and returns immediately.

	Args:
	        course_name: The LMS Course name/ID

	Returns:
	        dict with success flag
	"""
	_load_course(course_name)

	"""
	service = IngestionService()
	service.ingest_course_features(course_name)
	"""
	frappe.enqueue(
		"os_lms.os_lms.ai.ingestion.task.run_course_feature_ingestion",
		queue="long",
		timeout=600,
		enqueue_after_commit=True,
		course_name=course_name,
	)
	return {"success": True}


@frappe.whitelist()
def get_lesson_ingestion_status(lesson_id):
	"""
	Get ingestion status for a lesson.

	Args:
	        lesson_id: The Course Lesson name/ID

	Returns:
	        dict with status, chunk_count, last_ingested_on, and needs_update flag
	"""
	if not frappe.db.exists("Course Lesson", lesson_id):
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	lesson = frappe.get_doc("Course Lesson", lesson_id)
	return {
		"status": lesson.index_status or "not_ingested",
		"last_ingested_on": lesson.indexed_at,
	}


def _load_lesson(lesson_id):
	# Only who may edit the course re-indexes it: an enrolled student could start
	# the paid ingestion of any lesson of the course, as often as they liked.
	course = frappe.db.get_value("Course Lesson", lesson_id, "course") if lesson_id else None
	if not course:
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	if can_modify_course(course):
		return frappe.get_doc("Course Lesson", lesson_id)

	frappe.throw(_("You don't have permission to access this lesson"), frappe.PermissionError)


def _load_course(course_name):
	if not frappe.db.exists("LMS Course", course_name):
		frappe.throw(_("Course not found"), frappe.DoesNotExistError)
	course = frappe.get_doc("LMS Course", course_name)
	if has_moderator_role():
		return course
	if has_course_instructor_role() and is_instructor(course.name):
		return course
	frappe.throw(_("You don't have permission to access this course"), frappe.PermissionError)
