import frappe

from .ingestion_service import IngestionService


def reindex_lesson_content():
    """Daily job to re-index materials with changed content hash."""
    service = IngestionService()
