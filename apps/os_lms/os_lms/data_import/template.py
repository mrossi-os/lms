"""Import templates for the doctypes whose CSV layout we customise.

The stock Frappe template lists the fields of the target doctype. For our
imports that is the wrong shape: the uploaded file describes students, not
enrollment records, and the columns it needs are the ones the expanders in this
package consume. Someone downloading the stock template would get a file that
imports without creating the missing users, so we replace it with our own.

Doctypes we do not customise fall through to the original Frappe template.
"""

import frappe
from frappe import _
from frappe.core.doctype.data_import.data_import import (
    download_template as _original_download_template,
)
from frappe.utils.csvutils import build_csv_response
from frappe.utils.xlsxutils import build_xlsx_response

from os_lms.data_import.enrollment import (
    BATCH_ALIASES,
    EMAIL_ALIASES,
    FIRST_NAME_ALIASES,
    FISCAL_CODE_ALIASES,
    LAST_NAME_ALIASES,
)


def _header(*alias_groups) -> list[str]:
    """Build the header from the first (canonical) alias of each column."""
    return [aliases[0].title() for aliases in alias_groups]


TEMPLATES = {
    "LMS Batch Enrollment": {
        "header": _header(
            BATCH_ALIASES,
            EMAIL_ALIASES,
            FIRST_NAME_ALIASES,
            LAST_NAME_ALIASES,
            FISCAL_CODE_ALIASES,
        ),
        # Two rows, so the format explains itself: the batch column wants the ID,
        # and the fiscal code may be left empty.
        "examples": [
            ["codice-della-classe", "mario.rossi@example.com", "Mario", "Rossi", "RSSMRA85M01H501Z"],
            ["codice-della-classe", "anna.verdi@example.com", "Anna", "Verdi", ""],
        ],
    },
}


@frappe.whitelist()
def download_template(
    doctype: str,
    export_fields: str | None = None,
    export_records: str | None = None,
    export_filters: str | None = None,
    file_type: str = "CSV",
):
    template = TEMPLATES.get(doctype)
    if not template:
        return _original_download_template(
            doctype, export_fields, export_records, export_filters, file_type
        )

    frappe.has_permission(doctype, "read", throw=True)

    # The record-count options of the download dialog do not apply here: this
    # template teaches a format, and exporting real rows would put every
    # student's fiscal code in a downloadable file.
    rows = [template["header"], *template["examples"]]

    if file_type == "Excel":
        build_xlsx_response(rows, _(doctype))
    else:
        build_csv_response(rows, _(doctype))
