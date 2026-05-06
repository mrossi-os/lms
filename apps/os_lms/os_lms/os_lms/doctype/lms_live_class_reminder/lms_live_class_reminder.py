# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSLiveClassReminder(Document):
	pass


UNIT_TO_MINUTES = {
	"Minutes": 1,
	"Hours": 60,
	"Days": 60 * 24,
}


def offset_to_minutes(offset_value: int, offset_unit: str) -> int:
	"""Convert (value, unit) into total minutes."""
	return int(offset_value or 0) * UNIT_TO_MINUTES.get(offset_unit, 0)
