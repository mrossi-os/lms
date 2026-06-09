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
}


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

    Mirrors `seed_judge_prompts` for parametric templates (system + user
    with `{{var}}` placeholders). Pipeline code reads from here at runtime
    and falls back to the in-module defaults when a record is absent.
    """
    from os_lms.os_lms.ai.simulations.prompts.template_loader import DEFAULTS

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
        doc.enabled = 1
        doc.insert(ignore_permissions=True)
        created += 1
        print(f"Seeded LMSA Prompt Template: {purpose}")
    if created:
        frappe.db.commit()
    else:
        print("LMSA Prompt Template: all records already present, nothing to seed")


def seed_judge_prompts():
    """Insert one LMSA Judge Prompt record per judge purpose if missing.

    The pipeline reads judge configuration (system_prompt, output_schema,
    temperature, max_tokens) from this doctype and falls back to the
    hardcoded defaults in the judge modules when a record is missing. This
    seeder makes the defaults editable from the Desk on first install /
    after every migration, without touching existing customised records.
    """
    from os_lms.os_lms.ai.simulations.prompts.judge_loader import DEFAULTS

    created = 0
    for purpose, data in DEFAULTS.items():
        if frappe.db.exists("LMSA Judge Prompt", purpose):
            continue
        doc = frappe.new_doc("LMSA Judge Prompt")
        doc.purpose = purpose
        doc.label = data["label"]
        doc.version = data["version"]
        doc.system_prompt = data["system_prompt"]
        doc.output_schema = json.dumps(data["output_schema"], indent=2, ensure_ascii=False)
        doc.temperature = data["temperature"]
        doc.max_tokens = data["max_tokens"]
        doc.enabled = 1
        doc.insert(ignore_permissions=True)
        created += 1
        print(f"Seeded LMSA Judge Prompt: {purpose}")
    if created:
        frappe.db.commit()
    else:
        print("LMSA Judge Prompt: all records already present, nothing to seed")
