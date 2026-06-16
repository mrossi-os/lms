import frappe
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

# Fallback used when the welcome notification is enabled but no message is set.
DEFAULT_WELCOME_NOTIFICATION_MESSAGE = (
	"Benvenuto/a nella piattaforma! Siamo felici di averti con noi."
)


def mark_first_login(doc, method=None):
	"""Mark newly created users so they receive the welcome notification at first login."""
	frappe.db.set_value("User", doc.name, "first_login", 1, update_modified=False)


def on_session_creation(login_manager):
	"""Send a one-time welcome notification on the user's first login."""
	logger = frappe.logger("os_lms_auth", allow_site=True)
	user = frappe.session.user
	logger.info(f"on_session_creation fired for user={user}")

	if user in ("Guest", "Administrator"):
		return

	if not frappe.db.get_value("User", user, "first_login"):
		logger.info(f"first_login flag not set for {user}, skipping welcome notification")
		return

	settings = frappe.get_single("LMS Settings")
	if not settings.get("welcome_notification_enabled"):
		frappe.db.set_value("User", user, "first_login", 0)
		frappe.db.commit()
		return

	try:
		message = settings.get("welcome_notification_message") or DEFAULT_WELCOME_NOTIFICATION_MESSAGE
		_create_welcome_notification(user, message)
	except Exception:
		logger.exception(f"Failed to create welcome notification for {user}")
	finally:
		frappe.db.set_value("User", user, "first_login", 0)
		frappe.db.commit()


def _create_welcome_notification(user: str, message: str):
	# Admin-authored plain text: escape HTML and keep line breaks. The notification
	# content is intentionally independent from the welcome video.
	subject = frappe.utils.escape_html(message).replace("\n", "<br>")

	notification = frappe._dict(
		{
			"subject": subject,
			"type": "Alert",
			"from_user": "Administrator",
		}
	)
	make_notification_logs(notification, [user])
