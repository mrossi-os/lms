"""Column expanders for the LMS Batch Enrollment data import.

The uploaded file describes students, not enrollment records: one row carries
the batch, the student email and the data needed to create the student if they
are not registered yet. These expanders turn that into the columns the Frappe
importer expects, creating missing users along the way.

Emitted columns use fieldnames rather than translated labels, so the file does
not depend on the language of the user running the import.
"""

import re

import frappe
from frappe import _

from os_lms.data_import.utility import (
    DropRow,
    ImportRow,
    format_alias,
    get_row_value,
    is_empty_row,
)

BATCH_ALIASES = ("classe", "batch")
EMAIL_ALIASES = ("studente email", "student email")
FIRST_NAME_ALIASES = ("studente nome", "nome", "first name")
LAST_NAME_ALIASES = ("studente cognome", "cognome", "last name")
FISCAL_CODE_ALIASES = ("studente codice fiscale", "codice fiscale", "cf")

# Italian codice fiscale: 6 letters + 2 digits + letter + 2 digits + letter + 3 digits + letter
FISCAL_CODE_PATTERN = re.compile(r"^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$")


def enrollment_column_expanders():
    expanders = {alias: expand_batch for alias in BATCH_ALIASES}
    expanders.update({alias: expand_student_user for alias in EMAIL_ALIASES})
    return expanders


def expand_batch(cell_value: str, row: ImportRow) -> list[tuple[str, str]]:
    """Re-emit the batch column by fieldname."""
    return [("batch", (cell_value or "").strip())]


def expand_student_user(cell_value: str, row: ImportRow) -> list[tuple[str, str]] | DropRow:
    """Resolve the student into a `member` column, creating the user if needed.

    Rows for students already enrolled in the batch are dropped: the importer
    would reject them as duplicates, and dropping them lets a file mixing new
    and existing students go through in one pass.
    """
    if is_empty_row(row):
        return DropRow()

    email = (cell_value or "").strip().lower()
    if not email:
        frappe.throw(
            _("Row {0}: column {1} is empty.").format(row.number, format_alias(EMAIL_ALIASES[0]))
        )

    batch = get_row_value(row, BATCH_ALIASES)

    if is_already_enrolled(email, batch, row):
        return DropRow(_("Row {0}: {1} is already enrolled in {2}.").format(row.number, email, batch))

    return [("member", get_or_create_user(email, row))]


def is_already_enrolled(email: str, batch: str, row: ImportRow) -> bool:
    """True when the enrollment exists, either in the database or earlier in the file."""
    seen = row.context.setdefault("enrollments", set())
    key = (email, batch)

    if key in seen:
        return True

    seen.add(key)
    return bool(frappe.db.exists("LMS Batch Enrollment", {"member": email, "batch": batch}))


def get_or_create_user(email: str, row: ImportRow) -> str:
    """Return the User name for `email`, creating the student if not registered."""
    fiscal_code = get_fiscal_code(row)
    name = frappe.db.get_value("User", {"email": email}, "name")

    if name:
        sync_fiscal_code(name, fiscal_code, row)
        return name

    if fiscal_code:
        validate_fiscal_code_owner(fiscal_code, email, row)

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "username": email,
            "name": email,
            "first_name": get_row_value(row, FIRST_NAME_ALIASES),
            "last_name": get_row_value(row, LAST_NAME_ALIASES),
            # Never store an empty string: the field is unique, and MariaDB
            # allows many NULLs but only one "".
            "codice_fiscale": fiscal_code or None,
            "user_type": "Website User",
            "enabled": 1,
            "language": "it",
            "send_welcome_email": 1,
            "roles": [{"role": "LMS Student"}],
        }
    )
    user.insert(ignore_permissions=True)
    return user.name


def get_fiscal_code(row: ImportRow) -> str:
    """Read and validate the optional codice fiscale column."""
    fiscal_code = get_row_value(row, FISCAL_CODE_ALIASES, required=False).upper()

    if fiscal_code and not FISCAL_CODE_PATTERN.match(fiscal_code):
        frappe.throw(_("Row {0}: {1} is not a valid Codice Fiscale.").format(row.number, fiscal_code))

    return fiscal_code


def sync_fiscal_code(user: str, fiscal_code: str, row: ImportRow):
    """Fill in the codice fiscale of an existing user, never overwriting a different one."""
    if not fiscal_code:
        return

    current = (frappe.db.get_value("User", user, "codice_fiscale") or "").strip().upper()
    if current == fiscal_code:
        return

    if current:
        frappe.throw(
            _("Row {0}: {1} already has a different Codice Fiscale ({2}).").format(
                row.number, user, current
            )
        )

    validate_fiscal_code_owner(fiscal_code, user, row)
    frappe.db.set_value("User", user, "codice_fiscale", fiscal_code)


def validate_fiscal_code_owner(fiscal_code: str, user: str, row: ImportRow):
    """Fail with a readable message instead of a duplicate key error."""
    owner = frappe.db.get_value(
        "User",
        {"codice_fiscale": fiscal_code, "name": ("!=", user)},
        "name",
    )

    if owner:
        frappe.throw(
            _("Row {0}: Codice Fiscale {1} already belongs to {2}.").format(row.number, fiscal_code, owner)
        )
