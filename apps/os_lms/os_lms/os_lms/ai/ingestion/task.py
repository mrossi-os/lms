import frappe

from .service import IngestionService


def run_course_feature_ingestion(course_name: str) -> None:
	"""Background job entry point for course feature ingestion.

	Invoked via ``frappe.enqueue`` from
	``os_lms.os_lms.ai.ingestion.api.start_course_feature_ingestion``.
	"""
	course = frappe.get_doc("LMS Course", course_name)
	IngestionService().ingest_course_features(course)
