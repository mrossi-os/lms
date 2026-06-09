from os_lms.os_lms.ai.utils.rag.redis_rag_storage import RedisRagStorage
import frappe


def ensure_italian_language():
    if not frappe.db.exists("Language", "it"):
        frappe.get_doc(
            {
                "doctype": "Language",
                "language_code": "it",
                "language_name": "Italiano",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
        print("Create italian language and enabled it")
        return

    doc = frappe.get_doc("Language", "it")
    if not doc.enabled:
        doc.enabled = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("Enable italian language")
    else:
        print("Ok")

    frappe.clear_cache()


CUSTOM_FIELDS = {
    "LMS Course": [
        {
            "fieldname": "feature_sections",
            "fieldtype": "Long Text",
            "label": "Feature Sections",
            "insert_after": "related_courses",
        },
    ],
    "User": [
        {
            "fieldname": "codice_fiscale",
            "fieldtype": "Data",
            "label": "Codice Fiscale",
            "insert_after": "last_name",
            "unique": 1,
            "length": 16,
        },
    ],
    "Email Template": [
        {
            "fieldname": "custom_available_for_announcements",
            "fieldtype": "Check",
            "label": "Available for Batch Announcements",
            "insert_after": "subject",
            "description": (
                "Show this template in the batch announcement composer so moderators "
                "can pick it as a starting point. The template itself is never modified."
            ),
        },
    ],
    "LMS Batch": [
        {
            "fieldname": "valutatori",
            "fieldtype": "Table MultiSelect",
            "label": "Valutatori",
            "options": "LMS Batch Valutatore",
            "insert_after": "instructors",
            "description": (
                "Non-student users who can evaluate this batch: they may view the "
                "batch dashboard, live classes and announcements, and grade the "
                "quizzes/assignments of the students enrolled in this batch only."
            ),
        },
    ],
}


# Custom role used as the technical container for the per-batch valutatore
# permissions. Scoping to a single batch is enforced at runtime in
# os_lms.os_lms.valutatore (query conditions + has_permission).
VALUTATORE_ROLE = "Valutatore"
VALUTATORE_DOCPERMS = {
    "LMS Batch Enrollment": {"read": 1},
    "LMS Live Class": {"read": 1},
    "LMS Quiz Submission": {"read": 1},
    "LMS Assignment Submission": {"read": 1, "write": 1},
}


def setup_valutatore_role_and_permissions():
    """Ensure the "Valutatore" role exists and carries the baseline DocPerms.

    Idempotent: skips creation when the admin has already created the role in the
    desk. The per-batch scoping lives in os_lms.os_lms.valutatore, not here.
    """
    from frappe.permissions import add_permission, update_permission_property

    if not frappe.db.exists("Role", VALUTATORE_ROLE):
        role = frappe.new_doc("Role")
        role.update({"role_name": VALUTATORE_ROLE, "desk_access": 0, "home_page": ""})
        role.insert(ignore_permissions=True)
        print(f"Created Role: {VALUTATORE_ROLE}")

    for doctype, perms in VALUTATORE_DOCPERMS.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        add_permission(doctype, VALUTATORE_ROLE, 0)
        for ptype, value in perms.items():
            update_permission_property(
                doctype, VALUTATORE_ROLE, 0, ptype, value, validate=False
            )
    frappe.db.commit()


def create_custom_fields():
    for dt, fields in CUSTOM_FIELDS.items():
        for field_def in fields:
            name = f"{dt}-{field_def['fieldname']}"
            if not frappe.db.exists("Custom Field", name):
                doc = frappe.get_doc(
                    {
                        "doctype": "Custom Field",
                        "dt": dt,
                        **field_def,
                    }
                )
                doc.insert(ignore_permissions=True)
                print(f"Created Custom Field: {name}")
            else:
                print(f"Custom Field already exists: {name}")
    frappe.db.commit()


def remove_deprecated_custom_fields():
    """
    Rimuove i campi custom non più utilizzati.
    """
    deprecated = [
        ("LMS Course", "LMS Course-learning_items"),
    ]
    for dt, name in deprecated:
        if frappe.db.exists("Custom Field", name):
            frappe.delete_doc("Custom Field", name, ignore_permissions=True)
            print(f"Removed deprecated Custom Field: {name}")
    frappe.db.commit()


def create_redis_index():
    redis_url = frappe.conf.get("redis_vector_store")
    if not redis_url:
        return
    storage = RedisRagStorage()
    storage.create_index()


def rebuild_search_index():
    from os_lms.overrides.sqlite import CustomLearningSearch

    CustomLearningSearch().build_index()
    print("Rebuilt SQLite search index with CustomLearningSearch")
