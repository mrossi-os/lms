import frappe
from frappe import _

from lms.lms.utils import has_course_instructor_role, has_moderator_role, is_instructor

from .service import IngestionService


@frappe.whitelist()
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

	material = frappe.db.get_value(
		"LMSA Material",
		{"lesson": lesson_id},
		["name", "status", "chunk_count", "last_ingested_on", "source_hash"],
		as_dict=True,
	)

	if not material:
		return {
			"status": "not_ingested",
			"chunk_count": 0,
			"last_ingested_on": None,
			"needs_update": True,
		}

	from .pipeline import material_hash, normalize_lesson_text

	current_text = normalize_lesson_text(lesson_id)
	current_hash = material_hash(current_text) if current_text else ""
	needs_update = material.source_hash != current_hash
	if material.status and material.status.lower() == "failed":
		needs_update = True

	return {
		"status": material.status.lower(),
		"chunk_count": material.chunk_count or 0,
		"last_ingested_on": (str(material.last_ingested_on) if material.last_ingested_on else None),
		"needs_update": needs_update,
		"material": material.name,
	}


def _load_lesson(lesson_id):
	lesson = frappe.get_doc("Course Lesson", lesson_id)
	if not lesson:
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	if has_moderator_role():
		return lesson

	if has_course_instructor_role() and is_instructor(lesson.course):
		return lesson

	if frappe.db.exists("LMS Enrollment", {"member": frappe.session.user, "course": lesson.course}):
		return lesson

	frappe.throw(_("You don't have permission to access this lesson"), frappe.PermissionError)
