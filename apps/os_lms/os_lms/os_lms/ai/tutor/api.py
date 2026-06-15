import json

import frappe

from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi


@frappe.whitelist()
def ask(
	course: str,
	lesson: str,
	question: str,
	history: list[dict] | None = None,
) -> dict:
	"""Answer a learner's question about a course or lesson."""
	# Frappe forwards complex args as JSON strings when the client posts
	# form-encoded data; normalize before use.
	if isinstance(history, str):
		history = json.loads(history)

	tutor = TutorAi(course=course, lesson=lesson or None, user=frappe.session.user)
	answer = tutor.ask(question, history or [])
	return {"answer": answer}
