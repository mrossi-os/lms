import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs


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
	if not settings.get("welcome_video_enabled"):
		frappe.db.set_value("User", user, "first_login", 0)
		frappe.db.commit()
		return

	try:
		_create_welcome_notification(user)
	except Exception:
		logger.exception(f"Failed to create welcome notification for {user}")
	finally:
		frappe.db.set_value("User", user, "first_login", 0)
		frappe.db.commit()


def _create_welcome_notification(user: str):
	replay_link = "/api/method/os_lms.os_lms.api.replay_welcome_video"
	anchor_style = (
		"color: var(--ink-blue-3, #2563eb); text-decoration: underline; font-weight: 500;"
	)
	subject = _(
		"Benvenuto/a nella piattaforma SaleScience!<br><br>"
		"Per iniziare al meglio, ti invitiamo a guardare il video di presentazione della piattaforma, "
		"in cui troverai una breve introduzione alle principali funzionalità e alle modalità di utilizzo.<br><br>"
		'Guarda il video di presentazione qui quando vuoi: <a href="{0}" style="{1}">apri il video</a>.'
	).format(replay_link, anchor_style)

	notification = frappe._dict(
		{
			"subject": subject,
			"type": "Alert",
			"from_user": "Administrator",
		}
	)
	make_notification_logs(notification, [user])
