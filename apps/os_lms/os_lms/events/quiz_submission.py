import frappe
from frappe import _
from frappe.utils import cint


def validate_quiz_rows(doc, method=None):
	"""validate hook on LMS Quiz Submission: one row per question, no more rows than
	the quiz serves, and a percentage that never passes 100.

	The score is the sum of the rows and upstream submit_quiz accepts the same
	question more than once: a student who knows one answer repeats it until the
	quiz is passed, and with it the lesson, the certificate and the TrueSkill badge.
	"""
	questions = [row.question_name for row in doc.result if row.question_name]
	if len(questions) != len(set(questions)):
		frappe.throw(_("Each question of the quiz can be answered only once."))

	# Only on a new attempt: a quiz edited later must not block grading the old ones.
	if doc.is_new() and len(doc.result) > served_question_count(doc.quiz):
		frappe.throw(_("The quiz has more answers than questions."))

	if cint(doc.percentage) > 100:
		doc.percentage = 100


def served_question_count(quiz: str) -> int:
	count = frappe.db.count("LMS Quiz Question", {"parent": quiz, "parenttype": "LMS Quiz"})
	limit = cint(frappe.db.get_value("LMS Quiz", quiz, "limit_questions_to"))
	return min(limit, count) if limit else count
