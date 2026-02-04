import frappe
import json

frappe.init(site="lms.localhost")
frappe.connect()

def execute():
	course = frappe.new_doc("LMS Course")
	course.title = "Test Course"
	course.short_introduction = "A test course for AI ingestion"
	course.published = 1
	course.insert(ignore_permissions=True)
	print(f"Created course: {course.name}")

	chapter = frappe.new_doc("Course Chapter")
	chapter.course = course.name
	chapter.title = "Test Chapter"
	chapter.insert(ignore_permissions=True)
	print(f"Created chapter: {chapter.name}")

	lesson = frappe.new_doc("Course Lesson")
	lesson.course = course.name
	lesson.chapter = chapter.name
	lesson.title = "Test Lesson"
	content = {
		"blocks": [
			{"type": "paragraph", "data": {"text": "This is a test lesson about Python programming."}},
			{"type": "paragraph", "data": {"text": "Python is a high-level programming language known for its simplicity and readability."}},
			{"type": "header", "data": {"text": "Key Features", "level": 2}},
			{"type": "list", "data": {"items": ["Easy to learn", "Large standard library", "Cross-platform compatibility"]}},
			{"type": "paragraph", "data": {"text": "Python is widely used in web development, data science, machine learning, and automation."}}
		]
	}
	lesson.content = json.dumps(content)
	lesson.insert(ignore_permissions=True)
	print(f"Created lesson: {lesson.name}")

	frappe.db.commit()
	print("Done!")

if __name__ == "__main__":
	execute()
