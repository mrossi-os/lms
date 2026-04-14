import frappe

from lms.sqlite import LearningSearch


class CustomLearningSearch(LearningSearch):
	INDEXABLE_DOCTYPES = {
		**LearningSearch.INDEXABLE_DOCTYPES,
		"LMS Course": {
			"fields": [
				"name",
				"title",
				{"content": "description"},
				"short_introduction",
				"published",
				"category",
				"tags",
				"owner",
				{"modified": "published_on"},
			],
		},
		"LMS Program": {
			"fields": [
				"name",
				"title",
				{"content": "title"},
				"published",
				"owner",
				{"modified": "creation"},
			],
		},
		"LMS Quiz": {
			"fields": [
				"name",
				"title",
				{"content": "title"},
				"owner",
				{"modified": "creation"},
			],
		},
		"LMS Assignment": {
			"fields": [
				"name",
				"title",
				{"content": "question"},
				"owner",
				{"modified": "creation"},
			],
		},
		"Course Lesson": {
			"fields": [
				"name",
				"title",
				{"content": "body"},
				"course",
				"tags",
				"owner",
				"modified",
			],
		},
	}

	PROGRAM_FIELDS = [
		"name",
		"title",
		"description",
		"published",
		"creation",
		"modified",
		"owner",
	]

	QUIZ_FIELDS = [
		"name",
		"title",
		"creation",
		"modified",
		"owner",
	]

	ASSIGNMENT_FIELDS = [
		"name",
		"title",
		"question",
		"creation",
		"modified",
		"owner",
	]

	LESSON_FIELDS = [
		"name",
		"title",
		"body",
		"tags",
		"course",
		"creation",
		"modified",
		"owner",
	]

	DOCTYPE_FIELDS = {
		**LearningSearch.DOCTYPE_FIELDS,
		"LMS Quiz": QUIZ_FIELDS,
		"LMS Assignment": ASSIGNMENT_FIELDS,
		"Course Lesson": LESSON_FIELDS,
	}

	def prepare_document(self, doc):
		if doc.doctype == "Course Lesson":
			title = doc.get("title") or ""
			tags = (doc.get("tags") or "").strip()
			body = doc.get("body") or ""
			content_raw = "\n".join(p for p in [title, tags, body] if p)
			if not content_raw.strip():
				return None
			return {
				"name": doc.get("name"),
				"doctype": "Course Lesson",
				"title": self._process_content(title),
				"content": self._process_content(content_raw),
				"parent": doc.get("course"),
				"parenttype": "LMS Course",
				"owner": doc.get("owner"),
				"modified": doc.get("modified"),
			}

		document = super().prepare_document(doc)
		if not document:
			return None

		if doc.doctype == "LMS Course":
			tags = (doc.get("tags") or "").strip()
			if tags:
				document["content"] = self._process_content(
					f"{document.get('content') or ''}\n{tags}"
				)

		return document
