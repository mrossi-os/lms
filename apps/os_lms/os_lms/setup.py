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