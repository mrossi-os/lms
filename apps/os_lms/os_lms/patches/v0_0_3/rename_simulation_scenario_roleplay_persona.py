"""Rename LMSA Simulation Scenario.customer_persona -> roleplay_persona.

Runs in pre_model_sync so it executes before bench migrate reloads the
updated doctype JSON. The new schema name is `roleplay_persona` to better
reflect that the AI's role in a simulation isn't always a customer
(it could be an examiner, a patient, an interviewer, etc.).
"""
import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "LMSA Simulation Scenario"
	table = f"tab{doctype}"
	if not frappe.db.table_exists(table):
		return

	columns = frappe.db.get_table_columns(doctype)
	if "customer_persona" not in columns:
		# Already migrated or never existed.
		return

	if "roleplay_persona" in columns:
		# Both columns exist (partial migration). Copy data over where the
		# destination is still empty, then drop the old column.
		frappe.db.sql(
			f"""
			UPDATE `{table}`
			SET roleplay_persona = customer_persona
			WHERE (roleplay_persona IS NULL OR roleplay_persona = '')
			  AND customer_persona IS NOT NULL
			"""
		)
		frappe.db.sql(f"ALTER TABLE `{table}` DROP COLUMN `customer_persona`")
	else:
		# Standard rename — rename_field also updates property_setters,
		# custom_fields and any other doctype-level references.
		rename_field(doctype, "customer_persona", "roleplay_persona")

	frappe.db.commit()
