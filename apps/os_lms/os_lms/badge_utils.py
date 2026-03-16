import frappe


def clear_cache_on_badge_create(doc, method):
    frappe.clear_doctype_cache()
    frappe.db.commit()
   