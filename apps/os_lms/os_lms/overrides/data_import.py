import frappe
import csv
from frappe.core.doctype.data_import.data_import import DataImport

from os_lms.data_import.course import course_column_expanders
from os_lms.data_import.enrollment import enrollment_column_expanders


class CustomDataImport(DataImport):

    def start_import(self):
        self._check_csv_file()
        super().start_import()

    def _check_csv_file(self):
        column_expanders = None
        if self.reference_doctype == "LMS Course":
            column_expanders = course_column_expanders()
        if self.reference_doctype == "LMS Batch Enrollment":
            column_expanders = enrollment_column_expanders()
        if not column_expanders:
            return
        self._expand_csv_columns(column_expanders)

    def _expand_csv_columns(self, column_expanders):
        file_doc = frappe.get_doc("File", {"file_url": self.import_file})
        file_path = file_doc.get_full_path()

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            original_fields = reader.fieldnames or []

        special_cols = {}
        for field in original_fields:
            key = field.strip().lower()
            if key in column_expanders:
                special_cols[field] = column_expanders[key]

        if not special_cols:
            return

        # Build new rows with expanded columns
        new_fields = [f for f in original_fields if f not in special_cols]
        extra_fields_ordered = []
        expanded_rows = []

        for row in rows:
            extra_cells = {}
            for col, expander_fn in special_cols.items():
                expanded = expander_fn(row.get(col, ""), row)
                for col_name, value in expanded:
                    extra_cells[col_name] = value
                    if col_name not in extra_fields_ordered:
                        extra_fields_ordered.append(col_name)

            expanded_rows.append({**{f: row[f] for f in new_fields}, **extra_cells})

        # Overwrite the CSV with the new columns
        all_fields = new_fields + extra_fields_ordered
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_fields)
            writer.writeheader()
            for row in expanded_rows:
                writer.writerow({f: row.get(f, "") for f in all_fields})
