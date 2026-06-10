import json

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


def seed_prompt_templates():
    """Insert one LMSA Prompt Template record per template purpose if missing.

    Covers all three families now merged into a single doctype:
    parametric runtime templates, AI authoring prompts, and evaluation
    judges. The pipeline reads from here at runtime and falls back to the
    in-module defaults under ``ai/utils/default_prompt/`` when a record is
    absent.
    """
    from os_lms.os_lms.ai.utils.template_loader import DEFAULTS

    created = 0
    for purpose, data in DEFAULTS.items():
        if frappe.db.exists("LMSA Prompt Template", purpose):
            continue
        doc = frappe.new_doc("LMSA Prompt Template")
        doc.purpose = purpose
        doc.label = data["label"]
        doc.version = data["version"]
        doc.system_template = data["system_template"]
        doc.user_template = data["user_template"]
        doc.temperature = data["temperature"]
        doc.max_tokens = data["max_tokens"]
        doc.available_placeholders = data["available_placeholders"]
        if data.get("output_schema") is not None:
            doc.output_schema = json.dumps(
                data["output_schema"], indent=2, ensure_ascii=False
            )
        doc.enabled = 1
        doc.insert(ignore_permissions=True)
        created += 1
        print(f"Seeded LMSA Prompt Template: {purpose}")
    if created:
        frappe.db.commit()
    else:
        print("LMSA Prompt Template: all records already present, nothing to seed")


def migrate_judge_prompts_to_template():
    """One-shot migration: port any ``LMSA Judge Prompt`` records into
    ``LMSA Prompt Template`` and drop the old doctype.

    Idempotent — once the old doctype is gone (after the first successful
    migrate), this is a noop. Runs in ``after_migrate`` *before*
    ``seed_prompt_templates`` so operator-customised judge prompts win
    over the freshly-seeded defaults.
    """
    if not frappe.db.exists("DocType", "LMSA Judge Prompt"):
        return

    rows = frappe.get_all("LMSA Judge Prompt", fields=["name"])
    migrated = 0
    for row in rows:
        old = frappe.get_doc("LMSA Judge Prompt", row.name)
        purpose = old.purpose
        if not frappe.db.exists("LMSA Prompt Template", purpose):
            new = frappe.new_doc("LMSA Prompt Template")
            new.purpose = purpose
            new.label = old.label
            new.version = old.version
            # Field rename: judges' `system_prompt` becomes `system_template`
            # in the merged doctype. user_template stays empty (judges build
            # the user message in code).
            new.system_template = old.system_prompt or ""
            new.user_template = ""
            new.output_schema = old.output_schema or ""
            new.temperature = old.temperature
            new.max_tokens = old.max_tokens
            new.enabled = old.enabled
            new.insert(ignore_permissions=True)
            migrated += 1
            print(f"Migrated LMSA Judge Prompt -> LMSA Prompt Template: {purpose}")
        else:
            print(
                f"LMSA Prompt Template already exists for {purpose}, "
                "skipping migration of old judge record"
            )

    for row in rows:
        frappe.delete_doc(
            "LMSA Judge Prompt", row.name, force=1, ignore_permissions=True
        )

    frappe.delete_doc(
        "DocType",
        "LMSA Judge Prompt",
        force=1,
        ignore_missing=True,
        ignore_permissions=True,
    )
    frappe.db.commit()
    print(
        f"Deprecated LMSA Judge Prompt doctype removed "
        f"(records migrated: {migrated}, total processed: {len(rows)})"
    )
