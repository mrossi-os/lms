# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSAUserAccess(Document):
	"""Per-user access aggregates, one record per user (named by the user id).

	System-maintained from login events (see os_lms.os_lms.access_tracking); it
	is the durable, retention-independent source for the access columns of the
	student-statistics export, replacing reads against the Activity Log.
	"""

	pass
