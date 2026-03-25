import frappe
import secrets


def enrollment_column_expanders():
    return {
        "studente email": expand_student_user,
    }


def expand_student_user(cell_value: str, row: dict) -> list[tuple[str, str]]:
    if not cell_value or not cell_value.strip():
        return []
    _ = frappe._

    batch = get_row_value(
        row,
        _("Batch"),
    )

    id = frappe.db.get_value(
        "LMS Batch Enrollment",
        {"member": cell_value, "batch": batch},
        "name",
    )
    if not id:
        id = str(secrets.token_hex(5))

    user = get_user(cell_value, row)
    return [
        (f'{_("ID")}', id),
        (f'{_("Member")}', user.email),
        (f'{_("Member Username")}', user.username),
    ]


def get_row_value(row: dict, code: str):
    if code in row:
        return row[code]
    frappe.throw(f"{code} not found")


def get_user(email: str, row: dict):
    user = frappe.db.get_value(
        "User",
        {"email": email},
    )
    if not user:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "username": email,
                "name": email,
                "first_name": get_row_value(row, "Studente Nome"),
                "last_name": get_row_value(row, "Studente Cognome"),
                "user_type": "Website User",
                "enabled": 1,
                "language": "it",
                "send_welcome_email": 1,
                "roles": [{"role": "LMS Student"}],
            }
        )
        user.insert(ignore_permissions=True)
        frappe.db.commit()
    return user
