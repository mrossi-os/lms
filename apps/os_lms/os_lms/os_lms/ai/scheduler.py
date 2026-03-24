import frappe

from .ingestion import get_settings, ingest_lesson, material_hash, normalize_lesson_text


def sync_stale_materials():
    """Daily job to re-index materials with changed content hash."""
    print("s")
