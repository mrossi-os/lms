import json

import frappe
from frappe import _

from lms.lms.utils import (
    has_course_instructor_role,
    has_moderator_role,
    is_instructor,
    validate_course_access,
)

from .ingestion import ask_chat, get_settings, ingest_lesson


def check_lesson_permission(lesson_id):
    """Check if current user can manage ingestion for the lesson."""
    lesson = frappe.get_doc("Course Lesson", lesson_id)
    course_id = lesson.course

    if has_moderator_role():
        return True

    if has_course_instructor_role() and is_instructor(course_id):
        return True

    frappe.throw(
        _("You don't have permission to manage this lesson"), frappe.PermissionError
    )


@frappe.whitelist()
def start_lesson_ingestion(lesson_id):
    """
    Start ingestion for a lesson. Teacher-only endpoint.

    Args:
            lesson_id: The Course Lesson name/ID

    Returns:
            dict with status, message, material name and chunk_count
    """
    check_lesson_permission(lesson_id)

    result = ingest_lesson(lesson_id)
    return result


@frappe.whitelist()
def get_lesson_ingestion_status(lesson_id):
    """
    Get ingestion status for a lesson.

    Args:
            lesson_id: The Course Lesson name/ID

    Returns:
            dict with status, chunk_count, last_ingested_on, and needs_update flag
    """
    if not frappe.db.exists("Course Lesson", lesson_id):
        frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)

    material = frappe.db.get_value(
        "LMSA Material",
        {"lesson": lesson_id},
        ["name", "status", "chunk_count", "last_ingested_on", "source_hash"],
        as_dict=True,
    )

    if not material:
        return {
            "status": "not_ingested",
            "chunk_count": 0,
            "last_ingested_on": None,
            "needs_update": True,
        }

    from .ingestion import material_hash, normalize_lesson_text

    current_text = normalize_lesson_text(lesson_id)
    current_hash = material_hash(current_text) if current_text else ""
    needs_update = material.source_hash != current_hash
    if material.status and material.status.lower() == "failed":
        needs_update = True

    return {
        "status": material.status.lower(),
        "chunk_count": material.chunk_count or 0,
        "last_ingested_on": (
            str(material.last_ingested_on) if material.last_ingested_on else None
        ),
        "needs_update": needs_update,
        "material": material.name,
    }


@frappe.whitelist()
def ask_lmsa_chat(course_id, lesson_id, question):
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

    validate_course_access(lesson_id)

    lesson = frappe.get_doc("Course Lesson", lesson_id)
    if lesson.course != course_id:
        frappe.throw(_("Lesson does not belong to this course"), frappe.ValidationError)

    result = ask_chat(course_id, lesson_id, question)
    """
	log = frappe.new_doc("LMSA Query Log")
	log.course = course_id
	log.lesson = lesson_id
	log.member = frappe.session.user
	log.question = question
	log.answer = result.get("answer", "")
	log.context = json.dumps(result.get("sources", []))
	log.status = "Answered" if result.get("status") == "answered" else "Failed"
	log.save(ignore_permissions=True)
	frappe.db.commit()
	"""
    return result


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
            "/api/method/os_lms.os_lms.ai.api.start_lesson_ingestion": {
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
            "/api/method/os_lms.os_lms.ai.api.get_lesson_ingestion_status": {
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
                                                                "lesson_id": {
                                                                    "type": "string"
                                                                },
                                                                "chunk_index": {
                                                                    "type": "integer"
                                                                },
                                                                "score": {
                                                                    "type": "number"
                                                                },
                                                                "excerpt": {
                                                                    "type": "string"
                                                                },
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
