import frappe
from frappe import _

from ._lesson_access import load_lesson
from .ingestion import IngestionService


@frappe.whitelist()
def ask_lmsa_chat(lesson_id, question):
	"""
	Ask a question to the LMSA chatbot.

	Args:
	        course_id: The LMS Course name/ID
	        lesson_id: The Course Lesson name/ID
	        question: The user's question

	Returns:
	        dict with answer, sources, and status
	"""
	if not question or not question.strip():
		frappe.throw(_("Question cannot be empty"))

	lesson = load_lesson(lesson_id)
	service = IngestionService()
	result = service.ask(lesson, question)
	if not result:
		result = "I couldn't find relevant information in the lesson content to answer your question."
	return {"answer": result}


@frappe.whitelist(allow_guest=True)
def get_lmsa_openapi_spec():
	"""Return OpenAPI/Swagger spec for LMSA endpoints."""
	base_url = frappe.utils.get_url()
	return {
		"openapi": "3.0.0",
		"info": {
			"title": "LMSA API",
			"description": "API for LMS AI Assistant ingestion and chat endpoints",
			"version": "1.0.0",
		},
		"servers": [{"url": base_url}],
		"paths": {
			"/api/method/os_lms.os_lms.ai.ingestion.api.start_lesson_ingestion": {
				"post": {
					"summary": "Start lesson ingestion",
					"description": "Trigger ingestion for a specific lesson. Requires teacher permissions.",
					"requestBody": {
						"required": True,
						"content": {
							"application/x-www-form-urlencoded": {
								"schema": {
									"type": "object",
									"properties": {
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										}
									},
									"required": ["lesson_id"],
								}
							},
							"application/json": {
								"schema": {
									"type": "object",
									"properties": {
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										}
									},
									"required": ["lesson_id"],
								}
							},
						},
					},
					"responses": {
						"200": {
							"description": "Successful ingestion",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"status": {"type": "string"},
													"message": {"type": "string"},
													"material": {"type": "string"},
													"chunk_count": {"type": "integer"},
												},
											}
										},
									}
								}
							},
						},
						"403": {"description": "Permission denied"},
						"500": {"description": "Server error"},
					},
				}
			},
			"/api/method/os_lms.os_lms.ai.ingestion.api.get_lesson_ingestion_status": {
				"get": {
					"summary": "Get lesson ingestion status",
					"description": "Retrieve the current ingestion status for a lesson.",
					"parameters": [
						{
							"name": "lesson_id",
							"in": "query",
							"required": True,
							"schema": {"type": "string"},
							"description": "Course Lesson ID",
						}
					],
					"responses": {
						"200": {
							"description": "Status retrieved",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"status": {"type": "string"},
													"chunk_count": {"type": "integer"},
													"last_ingested_on": {
														"type": "string",
														"nullable": True,
													},
													"needs_update": {"type": "boolean"},
													"material": {"type": "string"},
												},
											}
										},
									}
								}
							},
						},
						"404": {"description": "Lesson not found"},
					},
				}
			},
			"/api/method/os_lms.os_lms.ai.api.ask_lmsa_chat": {
				"post": {
					"summary": "Ask LMSA chatbot",
					"description": "Ask a question about lesson content. Requires course enrollment.",
					"requestBody": {
						"required": True,
						"content": {
							"application/json": {
								"schema": {
									"type": "object",
									"properties": {
										"course_id": {
											"type": "string",
											"description": "LMS Course ID",
										},
										"lesson_id": {
											"type": "string",
											"description": "Course Lesson ID",
										},
										"question": {
											"type": "string",
											"description": "User question",
										},
									},
									"required": ["course_id", "lesson_id", "question"],
								}
							},
						},
					},
					"responses": {
						"200": {
							"description": "Chat response",
							"content": {
								"application/json": {
									"schema": {
										"type": "object",
										"properties": {
											"message": {
												"type": "object",
												"properties": {
													"answer": {"type": "string"},
													"sources": {
														"type": "array",
														"items": {
															"type": "object",
															"properties": {
																"lesson_id": {"type": "string"},
																"chunk_index": {"type": "integer"},
																"score": {"type": "number"},
																"excerpt": {"type": "string"},
															},
														},
													},
													"status": {
														"type": "string",
														"enum": [
															"answered",
															"not_found",
														],
													},
												},
											}
										},
									}
								}
							},
						},
						"403": {"description": "Access denied"},
						"500": {"description": "Server error"},
					},
				}
			},
		},
		"components": {
			"securitySchemes": {
				"cookieAuth": {"type": "apiKey", "in": "cookie", "name": "sid"},
				"tokenAuth": {
					"type": "apiKey",
					"in": "header",
					"name": "Authorization",
				},
			}
		},
		"security": [{"cookieAuth": []}, {"tokenAuth": []}],
	}
