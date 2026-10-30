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

# Link-to-User fields where the user only acted on someone else's record:
# graded it, hosted it, wrote the scenario a student plays. Deleting those
# records would delete other people's data (a teacher's deletion used to take
# every assignment they had graded with it), so the reference is reassigned:
# to Administrator where the field is mandatory, emptied otherwise.
ROLE_LINK_FIELDS = (
	("LMS Assignment Submission", "evaluator"),
	("LMS Certificate Evaluation", "evaluator"),
	("LMS Certificate Request", "evaluator"),
	("LMS Live Class", "host"),
	("LMSA Quality Evaluation", "triggered_by"),
	("LMSA Simulation Debrief", "instructor_reviewed_by"),
	("LMSA Simulation Scenario", "created_by_instructor"),
	("Elite API Key", "revoked_by"),
	# The request stays as the record of the decision, without whom it was about
	# or who took it (user is not mandatory, so it is emptied).
	("OS Account Deletion Request", "user"),
	("OS Account Deletion Request", "decided_by"),
)

# The user's own records that other people's records point to: a course or a
# certificate names its Course Evaluator, a batch or a live class its Zoom or
# Google Meet account. The pointers are emptied before the records go.
SHARED_PERSONAL_DOCTYPES = ("Course Evaluator", "LMS Zoom Settings", "LMS Google Meet Settings")


def delete_lms_user_links(doc, method=None):
	"""on_trash hook on User: removes every LMS/os_lms record that belongs to
	the user and detaches the user from the records of others, so the User
	deletion is not blocked by LinkExistsError. Runs before Frappe's
	check_if_doc_is_linked / check_if_doc_is_dynamically_linked validation.
	"""
	user = doc.name

	# 0. Records of other people that only name the user: keep them.
	_reassign_role_links(user)
	_detach_shared_personal_records(user)

	# 1. Direct Link fields (User → LMS-scoped doctypes).
	for doctype, fieldname in _collect_user_link_fields():
		if (doctype, fieldname) in ROLE_LINK_FIELDS:
			continue
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


def _reassign_role_links(user: str) -> None:
	for doctype, fieldname in ROLE_LINK_FIELDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		field = frappe.get_meta(doctype).get_field(fieldname)
		replacement = "Administrator" if field and field.reqd else None
		_set_link_and_fetched(doctype, fieldname, user, replacement)


def _detach_shared_personal_records(user: str) -> None:
	for target in SHARED_PERSONAL_DOCTYPES:
		if not frappe.db.exists("DocType", target):
			continue
		owner_field = "evaluator" if target == "Course Evaluator" else "member"
		names = frappe.get_all(target, filters={owner_field: user}, pluck="name")
		if not names:
			continue
		for doctype, fieldname in _collect_link_fields_to(target):
			for name in names:
				_set_link_and_fetched(doctype, fieldname, name, None)


def _set_link_and_fetched(doctype: str, fieldname: str, value: str, replacement: str | None) -> None:
	"""Point `fieldname` from `value` to `replacement`, and empty the fields
	fetched through it (e.g. `evaluator_name` from `evaluator.full_name`), which
	would otherwise keep the user's name next to the new value."""
	meta = frappe.get_meta(doctype)
	fetched = [df.fieldname for df in meta.fields if (df.fetch_from or "").startswith(f"{fieldname}.")]
	updates = {fieldname: replacement, **dict.fromkeys(fetched)}
	frappe.db.set_value(doctype, {fieldname: value}, updates, update_modified=False)


def _collect_link_fields_to(target: str) -> list[tuple[str, str]]:
	"""(doctype, fieldname) for every non-single Link field pointing at `target`,
	child tables included, Custom Fields included."""
	standard = frappe.db.sql(
		"""
		SELECT df.parent AS doctype, df.fieldname AS fieldname
		FROM `tabDocField` df
		INNER JOIN `tabDocType` dt ON dt.name = df.parent
		WHERE df.fieldtype = 'Link' AND df.options = %s AND dt.issingle = 0
		""",
		target,
		as_dict=True,
	)
	custom = frappe.db.sql(
		"""
		SELECT cf.dt AS doctype, cf.fieldname AS fieldname
		FROM `tabCustom Field` cf
		INNER JOIN `tabDocType` dt ON dt.name = cf.dt
		WHERE cf.fieldtype = 'Link' AND cf.options = %s AND dt.issingle = 0
		""",
		target,
		as_dict=True,
	)
	return sorted({(row["doctype"], row["fieldname"]) for row in (*standard, *custom)})


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


def grant_student_role_on_gestore_import(doc, method=None):
	"""validate hook on User: a user imported by a Gestore becomes an LMS Student.

	The `roles` table of User sits at permlevel 1, which only System Manager may
	write. Data Import respects permissions, so when a Gestore imports users
	Frappe's validate_higher_perm_levels wipes their roles before validation, the
	"LMS Student" appended by lms' before_insert hook included. The users came
	out with no role at all and could not open any quiz (get_quiz_with_questions
	refuses users without an LMS role). That strip runs before `validate`, so
	appending the role here lets it be saved with the user.

	Only users left with no role at all are touched: an import run by someone who
	may assign roles keeps whatever the file asked for.
	"""
	if not (doc.is_new() and frappe.flags.in_import):
		return
	if doc.get("roles"):
		return
	if "Gestore" not in frappe.get_roles():
		return

	doc.append_roles("LMS Student")
