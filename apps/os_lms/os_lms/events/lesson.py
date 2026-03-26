import frappe


def reset_index_status_on_content_change(doc, method):
    if not doc.is_new() and (
        doc.has_value_changed("content") or doc.has_value_changed("instructor_content")
    ):
        doc.index_status = "pending"
