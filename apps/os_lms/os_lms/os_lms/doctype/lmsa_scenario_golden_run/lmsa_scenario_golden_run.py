import json

import frappe
from frappe.model.document import Document


class LMSAScenarioGoldenRun(Document):
	def validate(self):
		# Parse turns JSON; raise ValidationError if malformed.
		raw = (self.turns or "").strip() or "[]"
		try:
			parsed = json.loads(raw)
		except json.JSONDecodeError as e:
			frappe.throw(f"Turns is not valid JSON: {e}")
		if not isinstance(parsed, list):
			frappe.throw("Turns must be a JSON array.")
		for i, turn in enumerate(parsed):
			if not isinstance(turn, dict):
				frappe.throw(f"Turn {i} is not an object.")
			if turn.get("role") not in ("user", "assistant"):
				frappe.throw(f"Turn {i} role must be 'user' or 'assistant'.")
			if not isinstance(turn.get("text", ""), str):
				frappe.throw(f"Turn {i} text must be a string.")
