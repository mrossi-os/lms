"""Shared helpers for the Data Import column expanders.

An expander turns one human-friendly CSV column into the columns the Frappe
importer expects. See `os_lms.overrides.data_import.CustomDataImport`.
"""

import frappe
from frappe import _


class DropRow:
    """Returned by an expander to exclude the current row from the import.

    `reason` is collected and shown to the user in the skipped-rows report.
    """

    def __init__(self, reason: str = ""):
        self.reason = reason


class ImportRow(dict):
    """A CSV row, its position in the file and a context shared by all rows.

    Subclasses `dict` so expanders can keep reading it as a plain row.
    `number` is the spreadsheet line (the header is line 1) so it can be quoted
    back to the user in error messages. `context` is a scratch dict shared
    across the whole file, used to detect duplicates within the file itself.
    """

    def __init__(self, data: dict, number: int, context: dict):
        super().__init__(data)
        self.number = number
        self.context = context


def normalize_header(header: str) -> str:
    """Lowercase a column header, stripping spaces and the BOM Excel prepends."""
    return (header or "").replace("\ufeff", "").strip().lower()


def get_row_value(row: dict, aliases: tuple[str, ...], required: bool = True) -> str:
    """Return the value of the first column matching one of `aliases`.

    Headers are matched case-insensitively and ignoring surrounding spaces, so
    the file does not depend on how the column was typed. `aliases` must be
    given already normalized (lowercase).
    """
    values = {normalize_header(key): value for key, value in row.items()}

    for alias in aliases:
        if alias not in values:
            continue

        value = (values[alias] or "").strip()
        if not value and required:
            frappe.throw(
                _("Row {0}: column {1} is empty.").format(get_row_number(row), format_alias(aliases[0]))
            )

        return value

    if required:
        frappe.throw(_("Missing column: {0}").format(" / ".join(format_alias(a) for a in aliases)))

    return ""


def format_alias(alias: str) -> str:
    """Turn a normalized alias back into something readable in a message."""
    return alias.title()


def get_row_number(row: dict) -> str:
    """Spreadsheet line of the row, for error messages."""
    return str(getattr(row, "number", "?"))


def is_empty_row(row: dict) -> bool:
    """True when every cell is blank, as in the trailing lines Excel leaves behind."""
    return not any((value or "").strip() for value in row.values())
