import frappe

from .ingestion import get_settings, ingest_lesson, material_hash, normalize_lesson_text


def sync_stale_materials():
	"""Daily job to re-index materials with changed content hash."""
	settings = get_settings()
	if not settings.enabled:
		return

	materials = frappe.get_all(
		"LMSA Material",
		filters={"status": ["in", ["Ready", "Failed"]]},
		fields=["name", "lesson", "source_hash"],
	)

	synced = 0
	failed = 0

	for material in materials:
		if not frappe.db.exists("Course Lesson", material.lesson):
			continue

		try:
			current_text = normalize_lesson_text(material.lesson)
			if not current_text:
				continue

			current_hash = material_hash(current_text)
			if current_hash == material.source_hash:
				continue

			ingest_lesson(material.lesson)
			synced += 1

		except Exception:
			frappe.log_error(f"LMSA scheduler failed to sync lesson {material.lesson}")
			failed += 1

	if synced > 0 or failed > 0:
		frappe.logger().info(f"LMSA sync complete: {synced} updated, {failed} failed")
