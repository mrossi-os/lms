# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSATranscriptCache(Document):
    def before_save(self):
        if self.video_id and self.source:
            self.name_key = generate_uid(self.source, self.video_id)


def generate_uid(provider: str, id: str) -> str:
    return f"{provider.lower()}-{id}"
