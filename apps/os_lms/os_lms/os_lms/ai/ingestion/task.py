from .service import IngestionService


def run_course_feature_ingestion(course_name: str) -> None:
	"""Background job entry point for course feature ingestion.

	Invoked via ``frappe.enqueue`` from
	``os_lms.os_lms.ai.ingestion.api.start_course_feature_ingestion``.

	``ingest_course_features`` expects the course *name* (a string), not a
	Document: it looks the feature sections up via ``frappe.db.get_value``.
	Passing a Document made the lookup return nothing, so ingestion silently
	indexed no content.
	"""
	IngestionService().ingest_course_features(course_name)
