"""Drop the LMSA Scenario Golden Run feature.

The golden-run authoring path was never adopted in production and has been
removed from the codebase. This patch cleans up the database so a `bench
migrate` after the code removal leaves no dangling references:

1. delete every LMSA Quality Evaluation with run_mode='golden_regression'
   (cascade drops the related Evaluation Trace rows via Frappe's child
   table mechanics on doc delete)
2. drop the `source_golden` column from `tabLMSA Evaluation Trace` if the
   doctype sync has not already removed it
3. delete the LMSA Scenario Golden Run doctype + table

Runs in pre_model_sync so column/doctype removal happens before Frappe
reloads the (already-updated) JSON schemas. Idempotent: every step checks
existence before acting.
"""
import frappe


def execute():
	_delete_golden_evaluations()
	_drop_source_golden_column()
	_drop_doctype()
	frappe.db.commit()


def _delete_golden_evaluations() -> None:
	if not frappe.db.table_exists("tabLMSA Quality Evaluation"):
		return
	names = frappe.db.get_all(
		"LMSA Quality Evaluation",
		filters={"run_mode": "golden_regression"},
		pluck="name",
	)
	for name in names:
		frappe.delete_doc(
			"LMSA Quality Evaluation",
			name,
			ignore_permissions=True,
			delete_permanently=True,
			force=True,
		)


def _drop_source_golden_column() -> None:
	table = "tabLMSA Evaluation Trace"
	if not frappe.db.table_exists(table):
		return
	columns = frappe.db.get_table_columns("LMSA Evaluation Trace")
	if "source_golden" in columns:
		frappe.db.sql(f"ALTER TABLE `{table}` DROP COLUMN `source_golden`")


def _drop_doctype() -> None:
	if not frappe.db.exists("DocType", "LMSA Scenario Golden Run"):
		return
	frappe.delete_doc(
		"DocType",
		"LMSA Scenario Golden Run",
		ignore_permissions=True,
		force=True,
	)
