import frappe


def get_exp_column_name(name: str) -> str:
    return frappe._(name).lower()
