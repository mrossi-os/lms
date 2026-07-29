import csv
import os
from io import StringIO

import frappe
from frappe import _
from frappe.core.doctype.data_import.data_import import DataImport
from frappe.utils.xlsxutils import (
    read_xls_file_from_attached_file,
    read_xlsx_file_from_attached_file,
)

from os_lms.data_import.course import course_column_expanders
from os_lms.data_import.enrollment import enrollment_column_expanders
from os_lms.data_import.utility import DropRow, ImportRow, normalize_header

SKIPPED_ROWS_SHOWN = 25
SUPPORTED_EXTENSIONS = ("csv", "xlsx", "xls")


class CustomDataImport(DataImport):

    def start_import(self):
        self._expand_import_file()
        super().start_import()

    def _expand_import_file(self):
        """Rewrite the uploaded file into the columns the importer expects.

        Whatever the uploaded format, the expanded file is always written back
        as a new CSV: the original upload is left untouched.
        """
        column_expanders = self._get_column_expanders()
        if not column_expanders:
            return

        rows, fields = self._read_import_file()

        special_cols = {}
        for field in fields:
            key = normalize_header(field)
            if key in column_expanders:
                special_cols[field] = column_expanders[key]

        if not special_cols:
            return

        all_fields, expanded_rows, dropped = self._expand_rows(rows, fields, special_cols)

        if not expanded_rows:
            frappe.throw(_("Nothing to import: every row of the file was skipped."))

        self._write_expanded_file(all_fields, expanded_rows)

        # Records created while expanding (students, for instance) are only
        # committed once the whole file went through, so a failure halfway
        # leaves nothing behind.
        frappe.db.commit()

        self._report_skipped_rows(dropped)

    def _get_column_expanders(self):
        if self.reference_doctype == "LMS Course":
            return course_column_expanders()
        if self.reference_doctype == "LMS Batch Enrollment":
            return enrollment_column_expanders()
        return None

    def _read_import_file(self):
        """Return the uploaded file as (rows, column names), from CSV or Excel."""
        if self.google_sheets_url:
            frappe.throw(
                _("Google Sheets is not supported for this import. Upload a .csv, .xlsx or .xls file.")
            )

        extension = os.path.splitext(self.import_file or "")[1][1:].lower()
        if extension not in SUPPORTED_EXTENSIONS:
            frappe.throw(_("Import file should be of type .csv, .xlsx or .xls"))

        file_path = frappe.get_doc("File", {"file_url": self.import_file}).get_full_path()

        if extension == "csv":
            # utf-8-sig: Excel writes a BOM that would otherwise end up glued to
            # the first column header.
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                table = list(csv.reader(f))
        elif extension == "xlsx":
            table = read_xlsx_file_from_attached_file(filepath=file_path)
        else:
            with open(file_path, "rb") as f:
                table = read_xls_file_from_attached_file(f.read())

        return self._rows_from_table(table or [])

    def _rows_from_table(self, table):
        """Turn a table of cells into dict rows keyed by the header line."""
        if not table:
            frappe.throw(_("The import file is empty."))

        fields = [stringify_cell(cell).strip() for cell in table[0]]
        rows = []

        for cells in table[1:]:
            row = {
                field: stringify_cell(cells[index]) if index < len(cells) else ""
                for index, field in enumerate(fields)
                if field
            }
            # Spreadsheets carry trailing blank rows: they are noise, not data.
            if any(value.strip() for value in row.values()):
                rows.append(row)

        return rows, [field for field in fields if field]

    def _expand_rows(self, rows, fields, special_cols):
        new_fields = [f for f in fields if f not in special_cols]
        extra_fields_ordered = []
        expanded_rows = []
        dropped = []
        context = {}

        for index, data in enumerate(rows):
            row = ImportRow(data, index + 2, context)
            extra_cells = {}
            drop = None

            for col, expander_fn in special_cols.items():
                expanded = expander_fn(data.get(col, ""), row)
                if isinstance(expanded, DropRow):
                    drop = expanded
                    break
                for col_name, value in expanded:
                    extra_cells[col_name] = value
                    if col_name not in extra_fields_ordered:
                        extra_fields_ordered.append(col_name)

            if drop:
                dropped.append(drop)
                continue

            expanded_rows.append({**{f: data.get(f) or "" for f in new_fields}, **extra_cells})

        return new_fields + extra_fields_ordered, expanded_rows, dropped

    def _write_expanded_file(self, fields, rows):
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

        base_name = os.path.splitext(os.path.basename(self.import_file))[0]
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"{base_name}-expanded.csv",
                "content": output.getvalue(),
                "is_private": 1,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
            }
        ).insert(ignore_permissions=True)

        self.db_set("import_file", file_doc.file_url)

    def _report_skipped_rows(self, dropped):
        # Blank rows carry no reason: they are file noise, not skipped data.
        reasons = [drop.reason for drop in dropped if drop.reason]
        if not reasons:
            return

        message = [_("{0} row(s) were skipped.").format(len(reasons))]
        message += reasons[:SKIPPED_ROWS_SHOWN]

        if len(reasons) > SKIPPED_ROWS_SHOWN:
            message.append(_("... and {0} more.").format(len(reasons) - SKIPPED_ROWS_SHOWN))

        frappe.msgprint("<br>".join(message), title=_("Skipped Rows"), indicator="orange")


def stringify_cell(value) -> str:
    """Spreadsheet cells arrive as numbers, dates or None: the importer wants text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, float) and value.is_integer():
        # Excel stores every number as a float: 42 must not become "42.0".
        return str(int(value))
    return str(value)
