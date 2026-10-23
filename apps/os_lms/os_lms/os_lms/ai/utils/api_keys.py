"""The OpenAI and Vimeo keys of LMSA Settings, stored encrypted (OWASP A04).

They used to be plain `Data` fields: the keys sat in clear in `tabSingles`, in
every backup and in the Version history of the settings (`track_changes`). They
are `Password` fields now. `encrypt_plaintext_api_keys` moves a value still in
clear into the encrypted store; it runs from `after_migrate` rather than as a
patch because the staging deploy marks new patches done without running them.
Until it has run, `get_api_key` still returns the clear value, so nothing stops
working in between.
"""

import json

import frappe
from frappe.utils.password import get_decrypted_password, set_encrypted_password

SETTINGS = "LMSA Settings"
FORMERLY_PLAIN_KEYS = ("openai_key", "vimeo_api_key")
MASK = "*****"


def get_api_key(fieldname: str) -> str:
	stored = frappe.db.get_single_value(SETTINGS, fieldname) or ""
	if not stored:
		return ""
	decrypted = get_decrypted_password(SETTINGS, SETTINGS, fieldname, raise_exception=False)
	if decrypted:
		return decrypted
	# Not migrated yet: the column still holds the key itself, not its mask.
	return "" if _is_mask(stored) else stored


def encrypt_plaintext_api_keys() -> None:
	"""after_migrate: encrypt the keys still in clear and scrub them from Version."""
	moved = []
	for fieldname in FORMERLY_PLAIN_KEYS:
		stored = frappe.db.get_single_value(SETTINGS, fieldname) or ""
		if not stored or _is_mask(stored):
			continue
		set_encrypted_password(SETTINGS, SETTINGS, stored, fieldname)
		# The same placeholder Frappe writes for any Password field.
		frappe.db.set_single_value(SETTINGS, fieldname, "*" * len(stored), update_modified=False)
		moved.append(fieldname)
	scrubbed = _scrub_version_history()
	if moved or scrubbed:
		frappe.db.commit()
		print(f"LMSA Settings: encrypted {moved or 'no'} keys, scrubbed {scrubbed} Version rows")


def _scrub_version_history() -> int:
	"""Blank the key values the settings' change history recorded while in clear."""
	scrubbed = 0
	for row in frappe.get_all(
		"Version", filters={"ref_doctype": SETTINGS, "docname": SETTINGS}, fields=["name", "data"]
	):
		try:
			data = json.loads(row.data or "{}")
		except ValueError:
			continue
		touched = False
		for change in data.get("changed") or []:
			if len(change) == 3 and change[0] in FORMERLY_PLAIN_KEYS:
				for i in (1, 2):
					if change[i] and not _is_mask(str(change[i])):
						change[i] = MASK
						touched = True
		if touched:
			frappe.db.set_value("Version", row.name, "data", json.dumps(data, indent=1), update_modified=False)
			scrubbed += 1
	return scrubbed


def _is_mask(value: str) -> bool:
	return set(value) == {"*"}
