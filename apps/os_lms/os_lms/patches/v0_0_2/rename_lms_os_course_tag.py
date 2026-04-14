import frappe


def execute():
	old_name = "LMS OS Course Tag"
	new_name = "LMS OS Tag"

	if not frappe.db.exists("DocType", old_name):
		return

	if frappe.db.exists("DocType", new_name):
		# Both exist: merge records from old into new, then drop old.
		old_table = f"tab{old_name}"
		if frappe.db.table_exists(old_table):
			records = frappe.db.sql(
				f"SELECT `name`, `tag_name`, `color` FROM `{old_table}`", as_dict=True
			)
			for row in records:
				if not frappe.db.exists(new_name, row["name"]):
					doc = frappe.get_doc(
						{
							"doctype": new_name,
							"tag_name": row["tag_name"],
							"color": row["color"],
						}
					)
					doc.insert(ignore_permissions=True)
		frappe.delete_doc("DocType", old_name, ignore_missing=True, force=True)
	else:
		frappe.rename_doc("DocType", old_name, new_name, force=True)

	frappe.db.commit()
