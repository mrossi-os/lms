import frappe

def ensure_italian_language():
    if not frappe.db.exists("Language", "it"):
        frappe.get_doc({
            "doctype": "Language",
            "language_code": "it",
            "language_name": "Italiano",
            "enabled": 1
        }).insert(ignore_permissions=True)
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
}


def create_custom_fields():
    for dt, fields in CUSTOM_FIELDS.items():
        for field_def in fields:
            name = f"{dt}-{field_def['fieldname']}"
            if not frappe.db.exists("Custom Field", name):
                doc = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": dt,
                    **field_def,
                })
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