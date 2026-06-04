import frappe

# Modules whose doctypes should be cascade-deleted when a User is deleted.
# Bounds the blast radius to LMS-owned data instead of every app that
# happens to link to User.
LMS_MODULES = ("LMS", "OS LMS", "Job")

# Child tables that link to User. The parent must NOT be deleted (would
# wipe out courses/batches/programs); only the child row referencing the
# user is removed, leaving the parent intact (possibly with no instructor).
CHILD_TABLE_LINKS = (
	("Course Instructor", "instructor"),
	("LMS Program Member", "member"),
)


def delete_lms_user_links(doc, method=None):
	"""on_trash hook on User: removes every LMS/os_lms record that references
	the user, so the User deletion is not blocked by LinkExistsError. Runs
	before Frappe's check_if_doc_is_linked / check_if_doc_is_dynamically_linked
	validation.
	"""
	user = doc.name

	# 1. Direct Link fields (User → LMS-scoped doctypes).
	for doctype, fieldname in _collect_user_link_fields():
		record_names = frappe.get_all(
			doctype,
			filters={fieldname: user},
			pluck="name",
		)
		for name in record_names:
			frappe.delete_doc(
				doctype,
				name,
				ignore_permissions=True,
				delete_permanently=True,
				force=True,
				ignore_on_trash=True,
			)

	# 2. Known LMS child tables with direct Link to User: detach the row,
	# leave the parent doc intact.
	for child_doctype, fieldname in CHILD_TABLE_LINKS:
		frappe.db.delete(child_doctype, {fieldname: user})

	# 3. Dynamic Link references (e.g., Event Participants, ToDo, Comment).
	# These are global by design — Frappe's own delete validation scans every
	# dynamic link to User, so the cascade has to match the same scope.
	_clear_dynamic_links_to_user(user)


def _clear_dynamic_links_to_user(user: str) -> None:
	"""Remove every row that dynamically links to the given user.

	Uses Frappe's `get_dynamic_link_map()` — the same data structure
	`check_if_doc_is_dynamically_linked` consults — so we cover every
	dynamic-link field pointing at User across all installed apps.

	For child tables the row is deleted in place (parent doc is untouched).
	For regular doctypes the whole document is deleted. Singles are skipped:
	dropping a Single isn't meaningful, and clearing one field on a Settings
	doc would be a surprising side effect of deleting a user.
	"""
	from frappe.model.dynamic_links import get_dynamic_link_map

	for df in get_dynamic_link_map().get("User", []):
		meta = frappe.get_meta(df.parent)
		if meta.issingle:
			continue

		filters = {df.options: "User", df.fieldname: user}

		if meta.istable:
			frappe.db.delete(df.parent, filters)
			continue

		for name in frappe.get_all(df.parent, filters=filters, pluck="name"):
			frappe.delete_doc(
				df.parent,
				name,
				ignore_permissions=True,
				delete_permanently=True,
				force=True,
				ignore_on_trash=True,
			)


def _collect_user_link_fields() -> list[tuple[str, str]]:
	"""Return (doctype, fieldname) pairs for every Link-to-User field on
	non-single, non-child-table doctypes in LMS_MODULES, including Custom
	Fields.
	"""
	modules_placeholder = ", ".join(["%s"] * len(LMS_MODULES))

	standard = frappe.db.sql(
		f"""
		SELECT df.parent AS doctype, df.fieldname AS fieldname
		FROM `tabDocField` df
		INNER JOIN `tabDocType` dt ON dt.name = df.parent
		WHERE df.fieldtype = 'Link'
		  AND df.options = 'User'
		  AND dt.istable = 0
		  AND dt.issingle = 0
		  AND dt.module IN ({modules_placeholder})
		""",
		LMS_MODULES,
		as_dict=True,
	)

	custom = frappe.db.sql(
		f"""
		SELECT cf.dt AS doctype, cf.fieldname AS fieldname
		FROM `tabCustom Field` cf
		INNER JOIN `tabDocType` dt ON dt.name = cf.dt
		WHERE cf.fieldtype = 'Link'
		  AND cf.options = 'User'
		  AND dt.istable = 0
		  AND dt.issingle = 0
		  AND dt.module IN ({modules_placeholder})
		""",
		LMS_MODULES,
		as_dict=True,
	)

	seen: set[tuple[str, str]] = set()
	for row in (*standard, *custom):
		seen.add((row["doctype"], row["fieldname"]))
	return sorted(seen)
