# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

# import frappe
import base64
import re
import unittest

import frappe
from frappe.exceptions import ValidationError

from lms.lms.doctype.lms_quiz.lms_quiz import _save_file

# 1x1 transparent PNG, used to assert that genuine images are still accepted.
ONE_PIXEL_PNG = base64.b64decode(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)
# Same matcher process_results() uses to feed data: URIs to _save_file().
IMAGE_DATA_URI_PATTERN = r'<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']'


class TestLMSQuiz(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		frappe.get_doc({"doctype": "LMS Quiz", "title": "Test Quiz", "passing_percentage": 90}).save()

	def test_with_multiple_options(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "Choices"
		question.option_1 = "Option 1"
		question.is_correct_1 = 1
		question.option_2 = "Option 2"
		question.is_correct_2 = 1
		question.save()
		self.assertTrue(question.multiple)

	def test_with_no_correct_option(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "Choices"
		question.option_1 = "Option 1"
		question.option_2 = "Option 2"
		self.assertRaises(frappe.ValidationError, question.save)

	def test_with_no_possible_answers(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "User Input"
		self.assertRaises(frappe.ValidationError, question.save)

	def test_scores_question_with_ten_options(self):
		from lms.lms.doctype.lms_quiz.lms_quiz import verify_answer

		q = frappe.new_doc("LMS Question")
		q.question = "Ten option question"
		q.type = "Choices"
		for i in range(1, 11):
			q.set(f"option_{i}", f"opt{i}")
		q.is_correct_7 = 1
		q.save()

		self.assertTrue(verify_answer(q.name, ["opt7"]))
		self.assertFalse(verify_answer(q.name, ["opt3"]))

	def test_legacy_two_option_question_still_scores(self):
		from lms.lms.doctype.lms_quiz.lms_quiz import verify_answer

		q = frappe.new_doc("LMS Question")
		q.question = "Two option legacy"
		q.type = "Choices"
		q.option_1 = "yes"
		q.is_correct_1 = 1
		q.option_2 = "no"
		q.save()

		self.assertTrue(verify_answer(q.name, ["yes"]))
		self.assertFalse(verify_answer(q.name, ["no"]))

	def test_user_input_matches_seventh_possibility(self):
		from lms.lms.doctype.lms_quiz.lms_quiz import check_input_answers

		q = frappe.new_doc("LMS Question")
		q.question = "Ten possibility question"
		q.type = "User Input"
		for i in range(1, 11):
			q.set(f"possibility_{i}", f"answer {i}")
		q.save()

		self.assertTrue(bool(check_input_answers(q.name, "answer 7")))
		self.assertFalse(bool(check_input_answers(q.name, "totally different")))

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.db.delete("LMS Quiz", "test-quiz")
		frappe.db.delete("LMS Question")


class TestSkippedQuestions(unittest.TestCase):
	"""A learner may hand a quiz in with questions left blank. Those reach
	process_results() with an empty or null answer, which must score as zero
	rather than take the whole submission down."""

	@classmethod
	def setUpClass(cls) -> None:
		cls.choices = frappe.new_doc("LMS Question")
		cls.choices.question = "Skippable choices"
		cls.choices.type = "Choices"
		cls.choices.option_1 = "right"
		cls.choices.is_correct_1 = 1
		cls.choices.option_2 = "wrong"
		cls.choices.save()

		cls.user_input = frappe.new_doc("LMS Question")
		cls.user_input.question = "Skippable user input"
		cls.user_input.type = "User Input"
		cls.user_input.possibility_1 = "an answer"
		cls.user_input.save()

		cls.open_ended = frappe.new_doc("LMS Question")
		cls.open_ended.question = "Skippable open ended"
		cls.open_ended.type = "Open Ended"
		cls.open_ended.save()

		# A quiz may not mix open ended with the other types, hence two quizzes.
		cls.quiz = frappe.get_doc(
			{"doctype": "LMS Quiz", "title": "Skipped Question Quiz", "passing_percentage": 50}
		)
		for question in (cls.choices, cls.user_input):
			cls.quiz.append("questions", {"question": question.name, "marks": 1})
		cls.quiz.save()

		cls.open_quiz = frappe.get_doc(
			{"doctype": "LMS Quiz", "title": "Skipped Open Ended Quiz", "passing_percentage": 50}
		)
		cls.open_quiz.append("questions", {"question": cls.open_ended.name, "marks": 1})
		cls.open_quiz.save()

	def process(self, quiz, results, enable_negative_marking=0):
		from lms.lms.doctype.lms_quiz.lms_quiz import process_results

		return process_results(
			results,
			frappe._dict(
				{
					"name": quiz.name,
					"enable_negative_marking": enable_negative_marking,
					"marks_to_cut": 1,
				}
			),
		)

	def test_blank_answers_score_zero_instead_of_raising(self):
		data = self.process(
			self.quiz,
			[
				{"question_name": self.choices.name, "answer": []},
				{"question_name": self.user_input.name, "answer": [None]},
			],
		)

		self.assertFalse(data["is_open_ended"])
		for result in data["results"]:
			self.assertEqual(result["answer"], "")
			self.assertEqual(result["marks"], 0)
			self.assertEqual(result["is_correct"], 0)

	def test_blank_open_ended_answer_still_marks_the_quiz_open_ended(self):
		data = self.process(self.open_quiz, [{"question_name": self.open_ended.name, "answer": [""]}])

		self.assertTrue(data["is_open_ended"])
		self.assertEqual(data["results"][0]["answer"], "")

	def test_blank_answer_is_not_penalised_by_negative_marking(self):
		data = self.process(
			self.quiz,
			[{"question_name": self.choices.name, "answer": [None]}],
			enable_negative_marking=1,
		)

		self.assertEqual(data["results"][0]["marks"], 0)

	def test_answered_questions_still_score(self):
		data = self.process(self.quiz, [{"question_name": self.choices.name, "answer": ["right"]}])

		self.assertEqual(data["results"][0]["marks"], 1)
		self.assertEqual(data["results"][0]["is_correct"], 1)

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.db.delete("LMS Quiz", cls.quiz.name)
		frappe.db.delete("LMS Quiz", cls.open_quiz.name)
		frappe.db.delete("LMS Question")


class TestQuizAnswerImageUpload(unittest.TestCase):
	"""Open-ended quiz answers may embed inline images as data: URIs that get
	written to the public /files/ directory. Only image types are allowed: an
	active-document extension (.xhtml, .js, ...) would be served inline and
	enable stored XSS on the LMS origin.
	"""

	def save_answer_image(self, mime_type, filename, content=b"image-bytes"):
		encoded = base64.b64encode(content).decode()
		answer = f'<img src="data:{mime_type};filename={filename},{encoded}">'
		return re.sub(IMAGE_DATA_URI_PATTERN, _save_file, answer)

	def test_rejects_active_document_extension(self):
		with self.assertRaises(ValidationError):
			self.save_answer_image("application/xhtml+xml", "attack.xhtml", b"<script>alert(1)</script>")

	def test_rejects_non_image_mime_type(self):
		with self.assertRaises(ValidationError):
			self.save_answer_image("text/javascript", "attack.js", b"alert(1)")

	def test_rejects_image_mime_with_active_document_extension(self):
		with self.assertRaises(ValidationError):
			self.save_answer_image("image/png", "spoof.xhtml")

	def test_accepts_genuine_image(self):
		rendered = self.save_answer_image("image/png", "answer.png", ONE_PIXEL_PNG)
		self.assertIn("/files/", rendered)

	def tearDown(self):
		for name in frappe.get_all("File", {"file_name": "answer.png"}, pluck="name"):
			frappe.delete_doc("File", name, force=True, ignore_permissions=True)
