import hashlib
import json
import re

import frappe
import requests

from os_lms.os_lms.email_utils import send_templated_email

VIMEO_URL_RE = re.compile(r"vimeo\.com/(\d+)(?:/([a-zA-Z0-9]+))?")


@frappe.whitelist()
def set_lesson_as_current(course: str, lesson: str):
	"""Update the current_lesson on the user's enrollment for the given course."""
	if not course or not lesson:
		frappe.throw("course and lesson are required", frappe.ValidationError)

	enrollment = frappe.db.get_value(
		"LMS Enrollment",
		{"course": course, "member": frappe.session.user},
		"name",
	)
	if not enrollment:
		frappe.throw("Enrollment not found", frappe.DoesNotExistError)

	frappe.db.set_value("LMS Enrollment", enrollment, "current_lesson", lesson)
	return {"success": True}


@frappe.whitelist()
def get_lesson_position(lesson_name):
	"""
	Restituisce chapter_number e lesson_number (1-based) per costruire
	l'URL /courses/:courseName/learn/:chapterNumber-:lessonNumber
	Usa Chapter Reference e Lesson Reference, come fa mark_lesson_progress.
	"""
	lesson = frappe.db.get_value(
		"Course Lesson",
		lesson_name,
		["chapter", "course"],
		as_dict=True,
	)
	if not lesson:
		return None

	# chapter_number = idx del Chapter Reference nel corso
	chapter_number = frappe.db.get_value(
		"Chapter Reference",
		{"parent": lesson.course, "chapter": lesson.chapter},
		"idx",
	)

	# lesson_number = idx del Lesson Reference nel chapter
	lesson_number = frappe.db.get_value(
		"Lesson Reference",
		{"parent": lesson.chapter, "lesson": lesson_name},
		"idx",
	)

	return {
		"course": lesson.course,
		"chapter_number": chapter_number,
		"lesson_number": lesson_number,
	}


@frappe.whitelist(allow_guest=True)
def get_course_duration(course: str):
	"""
	Somma il campo duration (minuti) di tutte le lezioni del corso.
	Restituisce il totale in minuti.
	"""
	result = frappe.db.sql(
		"""
        SELECT COALESCE(SUM(cl.duration), 0) as total_minutes
        FROM `tabLesson Reference` lr
        JOIN `tabChapter Reference` cr ON lr.parent = cr.chapter
        JOIN `tabCourse Lesson` cl ON lr.lesson = cl.name
        WHERE cr.parent = %s
    """,
		course,
		as_dict=True,
	)

	return result[0].total_minutes if result else 0


@frappe.whitelist()
def get_evaluator_details(evaluator: str):
	frappe.only_for("Batch Evaluator")
	calendar_name = None
	is_authorised = None

	if not frappe.db.exists("Google Calendar", {"user": evaluator}):
		try:
			calendar = frappe.new_doc("Google Calendar")
			calendar.update({"user": evaluator, "calendar_name": evaluator})
			calendar.insert()
			calendar_name = calendar.name
			is_authorised = calendar.authorization_code
		except Exception:
			pass  # Google API non configurata, ignora
	else:
		calendar = frappe.db.get_value(
			"Google Calendar",
			{"user": evaluator},
			["name", "authorization_code"],
			as_dict=1,
		)
		calendar_name = calendar.name
		is_authorised = calendar.authorization_code

	if frappe.db.exists("Course Evaluator", {"evaluator": evaluator}):
		doc = frappe.get_doc("Course Evaluator", evaluator)
	else:
		doc = frappe.new_doc("Course Evaluator")
		doc.evaluator = evaluator
		doc.insert()

	return {
		"slots": doc.as_dict(),
		"calendar": calendar_name,
		"is_authorised": is_authorised,
	}


@frappe.whitelist()
def try_import():
	data_import = frappe.get_doc(
		{
			"doctype": "Data Import",
			"reference_doctype": "LMS Batch Enrollment",
			"import_type": "Insert New Records",  # o "Update Existing Records"
			"import_file": "/files/LMS Batch Enrollment_full.csv",  # path relativo a site
		}
	)
	data_import.insert()
	data_import.start_import()
	frappe.db.commit()


def evaluate_lesson_access(course: str, lesson: str) -> dict:
	"""
	Verifica se l'utente può accedere alla lezione richiesta.
	Se il corso ha enforce_lesson_order attivo, controlla che
	la lezione precedente sia completata.
	"""
	course_doc = frappe.get_doc("LMS Course", course)

	if not course_doc.get("enforce_lesson_order"):
		return {"allowed": True}

	all_lessons = []
	for chapter_ref in course_doc.chapters:
		chapter = frappe.get_doc("Course Chapter", chapter_ref.chapter)
		for lesson_ref in chapter.lessons:
			all_lessons.append(lesson_ref.lesson)

	if lesson not in all_lessons:
		return {"allowed": True}

	lesson_index = all_lessons.index(lesson)
	if lesson_index == 0:
		return {"allowed": True}

	prev_lesson = all_lessons[lesson_index - 1]
	is_completed = frappe.db.exists(
		"LMS Course Progress",
		{
			"member": frappe.session.user,
			"lesson": prev_lesson,
			"course": course,
			"status": "Complete",
		},
	)

	if is_completed:
		return {"allowed": True}
	return {
		"allowed": False,
		"reason": "Completa la lezione precedente prima di continuare.",
	}


@frappe.whitelist()
def check_lesson_access(course, lesson):
	return evaluate_lesson_access(course, lesson)


@frappe.whitelist()
def get_file_urls(names: list[str]):
	"""Return file_url and file_name for a list of File document names, ignoring permissions."""
	if not names:
		return []
	return frappe.get_all(
		"File",
		filters={"name": ["in", names]},
		fields=["name", "file_name", "file_url"],
		ignore_permissions=True,
		limit_page_length=0,
	)


def evaluate_quiz_access(course: str, lesson: str | None = None) -> dict:
	"""
	Verifica se l'utente può accedere al quiz.
	Se il corso ha enforce_quiz_on_completion attivo, controlla
	che tutte le lezioni precedenti alla lezione-quiz siano completate.
	Se `lesson` non è specificata, esclude dal controllo le lezioni
	che contengono un quiz (fallback per evitare deadlock).
	"""
	course_doc = frappe.get_doc("LMS Course", course)

	if not course_doc.get("enforce_quiz_on_completion"):
		return {"allowed": True}

	all_lessons = []
	for chapter_ref in course_doc.chapters:
		chapter = frappe.get_doc("Course Chapter", chapter_ref.chapter)
		for lesson_ref in chapter.lessons:
			all_lessons.append(lesson_ref.lesson)

	if not all_lessons:
		return {"allowed": True}

	if lesson and lesson in all_lessons:
		idx = all_lessons.index(lesson)
		lessons_to_check = all_lessons[:idx]
	else:
		lessons_to_check = [l for l in all_lessons if not frappe.db.get_value("Course Lesson", l, "quiz_id")]

	for l in lessons_to_check:
		is_completed = frappe.db.exists(
			"LMS Course Progress",
			{
				"member": frappe.session.user,
				"lesson": l,
				"course": course,
				"status": "Complete",
			},
		)
		if not is_completed:
			return {
				"allowed": False,
				"reason": "Completa tutte le lezioni precedenti prima di accedere al quiz.",
			}

	return {"allowed": True}


@frappe.whitelist()
def check_quiz_access(course, lesson=None):
	return evaluate_quiz_access(course, lesson)


@frappe.whitelist()
def send_batch_announcement(
	batch: str,
	recipients,
	subject: str,
	content: str,
	message: str = "",
	send_email: bool | int | str = True,
) -> dict:
	"""
	Invia un annuncio a una LMS Batch con rendering Jinja dell'HTML.
	Il parametro `message` viene iniettato nel context come {{ message }}
	per permettere all'utente di scrivere il testo senza toccare l'HTML.
	Se `send_email` è falso viene creata solo la notifica in-app.
	"""
	if not frappe.db.exists("LMS Batch", batch):
		frappe.throw("Batch non trovata")

	user_roles = frappe.get_roles(frappe.session.user)
	if not any(role in user_roles for role in ["Moderator", "Batch Evaluator", "System Manager"]):
		frappe.throw("Non hai i permessi per inviare annunci", frappe.PermissionError)

	if isinstance(recipients, str):
		recipients = [r.strip() for r in recipients.split(",") if r.strip()]
	if not recipients:
		frappe.throw("Nessun destinatario specificato")

	send_email_flag = str(send_email).lower() not in ("0", "false", "no", "")

	announcement_url = f"{frappe.utils.get_url()}/lms/batches/details/{batch}#announcements"
	context = {"message": message or "", "announcement_url": announcement_url}
	rendered_content = frappe.render_template(content, context)
	rendered_subject = frappe.render_template(subject, context)

	from frappe.core.doctype.communication.email import make

	# Resolve the sender to the actor's actual email address. frappe.session.user is
	# the login name, which equals the email for regular users but not for the
	# Administrator account — and frappe.sendmail silently drops a sender that is not
	# a valid email, which would queue zero emails.
	sender = frappe.db.get_value("User", frappe.session.user, "email") or frappe.session.user
	sender_full_name = frappe.utils.get_fullname(frappe.session.user)

	# Single Communication record drives the announcements tab and audit trail.
	# Emails are sent individually below, so this record never sends mail itself.
	make(
		recipients=", ".join(recipients),
		sender=sender,
		sender_full_name=sender_full_name,
		subject=rendered_subject,
		content=rendered_content,
		doctype="LMS Batch",
		name=batch,
		send_email=0,
	)

	# One email per recipient: each student gets a private message (no shared To),
	# the From is the announcement author, and replies go back to the author via
	# Reply-To so they land in the author's mailbox (e.g. when replying from Gmail).
	if send_email_flag:
		for recipient in recipients:
			frappe.sendmail(
				recipients=[recipient],
				sender=sender,
				reply_to=sender,
				subject=rendered_subject,
				message=rendered_content,
				reference_doctype="LMS Batch",
				reference_name=batch,
			)

	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	batch_title = frappe.db.get_value("LMS Batch", batch, "title") or batch
	notification = frappe._dict(
		{
			"subject": frappe._("Hai un nuovo messaggio in annunci: {0}").format(batch_title),
			"from_user": frappe.session.user,
			"type": "Alert",
			"link": f"/lms/batches/details/{batch}#announcements",
		}
	)
	make_notification_logs(notification, recipients)

	return {"ok": True, "recipients_count": len(recipients)}


@frappe.whitelist()
def search_non_student_users(txt: str = "", page_length: int = 20, names=None) -> list[dict]:
	"""Users that can be assigned as batch "Valutatori": everyone except students.

	Mirrors the shape returned by ``lms.lms.api.search_users_by_role`` so it can
	back a frappe-ui MultiSelect (value/description/label/user_image). ``names``
	is used to hydrate already-selected chips after a page reload.
	"""
	frappe.only_for(["Moderator", "Course Creator", "Batch Evaluator", "System Manager"])

	if isinstance(names, str):
		names = json.loads(names) if names.strip().startswith("[") else [names]

	student_users = set(
		frappe.get_all(
			"Has Role",
			filters={"role": "LMS Student", "parenttype": "User"},
			pluck="parent",
		)
	)

	filters = {
		"enabled": 1,
		"name": ["not in", ["Administrator", "Guest"]],
	}
	or_filters = None
	if names:
		filters["name"] = ["in", names]
	elif txt:
		or_filters = {
			"full_name": ["like", f"%{txt}%"],
			"name": ["like", f"%{txt}%"],
		}

	users = frappe.get_all(
		"User",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "full_name", "user_image"],
		order_by="full_name asc",
		limit_page_length=int(page_length) * 4,
	)

	out = []
	for user in users:
		if user.name in student_users:
			continue
		out.append(
			{
				"value": user.name,
				"description": user.full_name or user.name,
				"label": user.full_name or user.name,
				"user_image": user.user_image,
			}
		)
		if len(out) >= int(page_length):
			break
	return out


@frappe.whitelist()
def get_batch_certified_count(batch: str) -> dict:
	"""Summary stats for the admin batch dashboard, fetched in a single call:

	- ``certified_count``: number of certificates issued for the batch.
	- ``students_progress``: ``{member: average_progress}`` mapping, the average
	  course progress per enrolled student across every course of the batch (a
	  missing enrollment counts as 0, matching ``calculate_course_progress`` in
	  lms.lms.utils).

	Available to batch admins and to the batch's valutatori (scoped read).
	"""
	from pypika import functions as fn

	from frappe.utils import flt

	from lms.lms.utils import can_modify_batch, is_batch_valutatore

	if not (can_modify_batch(batch) or is_batch_valutatore(batch)):
		frappe.throw(
			frappe._("You are not authorized to view this batch."),
			frappe.PermissionError,
		)

	BatchCourse = frappe.qb.DocType("Batch Course")
	BatchEnrollment = frappe.qb.DocType("LMS Batch Enrollment")
	Enrollment = frappe.qb.DocType("LMS Enrollment")

	rows = (
		frappe.qb.from_(BatchEnrollment)
		.left_join(BatchCourse)
		.on(BatchCourse.parent == BatchEnrollment.batch)
		.left_join(Enrollment)
		.on((Enrollment.course == BatchCourse.course) & (Enrollment.member == BatchEnrollment.member))
		.where(BatchEnrollment.batch == batch)
		.groupby(BatchEnrollment.member)
		.select(
			BatchEnrollment.member,
			fn.Avg(fn.Coalesce(Enrollment.progress, 0)).as_("progress"),
		)
	).run(as_dict=True)

	return {
		"certified_count": frappe.db.count("LMS Certificate", {"batch_name": batch}),
		"students_progress": {row.member: flt(row.progress, 2) for row in rows},
	}


BATCH_TAB_SECTIONS = ("classes", "announcements", "discussions")


def get_batch_tab_unread_counts(batch: str) -> dict:
	"""Unread Notification Log counts for the given batch, split by tab section."""
	user = frappe.session.user
	if not user or user == "Guest":
		return {section: 0 for section in BATCH_TAB_SECTIONS}
	return {
		section: frappe.db.count(
			"Notification Log",
			{
				"for_user": user,
				"read": 0,
				"link": ["like", f"%{batch}#{section}%"],
			},
		)
		for section in BATCH_TAB_SECTIONS
	}


@frappe.whitelist()
def get_welcome_video_config() -> dict:
	"""Return welcome video settings for the current user to display on first login."""
	if frappe.session.user == "Guest":
		return {"enabled": False}

	settings = frappe.get_single("LMS Settings")
	if not settings.get("welcome_video_enabled"):
		return {"enabled": False}

	return {
		"enabled": True,
		"title": settings.get("welcome_video_title") or "",
		"subtitle": settings.get("welcome_video_subtitle") or "",
		"video_source": settings.get("welcome_video_file") or "",
	}


@frappe.whitelist()
def mark_welcome_video_seen() -> dict:
	"""Mark the welcome video as seen for the current user."""
	if frappe.session.user == "Guest":
		return {"ok": False}
	frappe.db.set_value("User", frappe.session.user, "welcome_video_seen", 1)
	return {"ok": True}


@frappe.whitelist()
def replay_welcome_video():
	"""Reset welcome_video_seen and redirect to the LMS home so the video plays again."""
	if frappe.session.user != "Guest":
		frappe.db.set_value("User", frappe.session.user, "welcome_video_seen", 0)
		# GET requests do not cause an implicit commit
		frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/lms/"


@frappe.whitelist()
def mark_batch_tab_notifications_read(batch: str, section: str) -> dict:
	"""Mark as read all unread Notification Log entries for a batch tab section."""
	if section not in BATCH_TAB_SECTIONS:
		frappe.throw(frappe._("Invalid section: {0}").format(section))

	user = frappe.session.user
	frappe.db.sql(
		"""
        UPDATE `tabNotification Log`
        SET `read` = 1
        WHERE for_user = %(user)s
          AND `read` = 0
          AND `link` LIKE %(link)s
        """,
		{"user": user, "link": f"%{batch}#{section}%"},
	)
	frappe.publish_realtime("publish_lms_notifications", user=user)
	return {"ok": True}


# ----- Push notifications: device token registration -----


def _token_hash(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


@frappe.whitelist()
def register_push_token(token: str, platform: str = None, device_id: str = None) -> dict:
	"""Register (or refresh) the calling user's FCM device token.

	Upserts a "Push Device Token" record keyed by the token hash. When a
	``device_id`` is supplied, any other token previously stored for that same
	device is removed first, so a device keeps exactly one active token even
	after FCM rotates it.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(frappe._("Authentication required"), frappe.PermissionError)
	if not token:
		frappe.throw(frappe._("token is required"))

	token_hash = _token_hash(token)

	# Drop stale tokens for the same physical device.
	if device_id:
		for stale in frappe.get_all(
			"Push Device Token",
			filters={"user": user, "device_id": device_id, "token_hash": ["!=", token_hash]},
			pluck="name",
		):
			frappe.delete_doc("Push Device Token", stale, ignore_permissions=True, force=True)

	existing = frappe.db.get_value("Push Device Token", {"token_hash": token_hash}, "name")
	if existing:
		doc = frappe.get_doc("Push Device Token", existing)
		doc.user = user
		if platform:
			doc.platform = platform
		if device_id:
			doc.device_id = device_id
		doc.enabled = 1
		doc.last_active = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Push Device Token",
				"user": user,
				"token": token,
				"token_hash": token_hash,
				"platform": platform,
				"device_id": device_id,
				"enabled": 1,
				"last_active": frappe.utils.now_datetime(),
			}
		)
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def unregister_push_token(token: str) -> dict:
	"""Remove a device token (e.g. on logout). Idempotent."""
	if not token:
		return {"ok": True}

	name = frappe.db.get_value("Push Device Token", {"token_hash": _token_hash(token)}, "name")
	if name:
		frappe.delete_doc("Push Device Token", name, ignore_permissions=True, force=True)
		frappe.db.commit()
	return {"ok": True}


# ----- Live Class management -----

LIVE_CLASS_EDITABLE_FIELDS = ("title", "description")
MIN_REMINDER_MINUTES = 15


def _ensure_live_class_admin():
	frappe.only_for(["Moderator", "Batch Evaluator"])


def _validate_reminders(reminders) -> None:
	from os_lms.os_lms.doctype.lms_live_class_reminder.lms_live_class_reminder import (
		offset_to_minutes,
	)

	for row in reminders or []:
		offset_minutes = offset_to_minutes(row.get("offset_value"), row.get("offset_unit"))
		if offset_minutes < MIN_REMINDER_MINUTES:
			frappe.throw(frappe._("Each reminder must be at least 15 minutes before the class."))


@frappe.whitelist()
def update_live_class(name: str, payload: dict) -> dict:
	"""Update editable fields and the reminders child table on a Live Class."""
	_ensure_live_class_admin()

	if isinstance(payload, str):
		payload = json.loads(payload)

	doc = frappe.get_doc("LMS Live Class", name)

	for field in LIVE_CLASS_EDITABLE_FIELDS:
		if field in payload:
			doc.set(field, payload.get(field))

	if "reminders" in payload:
		_validate_reminders(payload.get("reminders"))
		doc.set("reminders", [])
		for row in payload.get("reminders") or []:
			doc.append(
				"reminders",
				{
					"offset_value": row.get("offset_value"),
					"offset_unit": row.get("offset_unit"),
					# preserve sent_at when row was already persisted
					"sent_at": row.get("sent_at"),
				},
			)

	doc.save()
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist()
def start_live_class(name: str) -> dict:
	"""Mark a Live Class as started by the host so enrolled students can join."""
	_ensure_live_class_admin()

	doc = frappe.get_doc("LMS Live Class", name)

	if not doc.get("started_at"):
		now = frappe.utils.now_datetime()
		frappe.db.set_value("LMS Live Class", name, "started_at", now)
		frappe.db.commit()
		started_at = now
		frappe.publish_realtime(
			"lms_live_class_started",
			{"name": name, "started_at": str(now)},
			doctype="LMS Live Class",
			docname=name,
		)
	else:
		started_at = doc.started_at

	return {
		"name": name,
		"start_url": doc.start_url or doc.join_url,
		"join_url": doc.join_url,
		"started_at": str(started_at),
	}


@frappe.whitelist()
def delete_live_class(name: str, notify_students: int = 0) -> dict:
	"""Delete a Live Class. Optionally notify enrolled students by email + Notification Log."""
	_ensure_live_class_admin()

	doc = frappe.get_doc("LMS Live Class", name)
	title = doc.title
	date = doc.date
	time = doc.time
	batch = doc.batch_name
	provider = doc.conferencing_provider
	zoom_account = doc.get("zoom_account")
	meeting_id = doc.get("meeting_id")

	if int(notify_students or 0):
		_notify_students_class_cancelled(doc)

	frappe.delete_doc("LMS Live Class", name)

	if provider == "Zoom" and zoom_account and meeting_id:
		_delete_zoom_meeting(zoom_account, meeting_id)

	frappe.db.commit()
	return {
		"ok": True,
		"title": title,
		"date": str(date),
		"time": str(time),
		"batch": batch,
	}


@frappe.whitelist()
def get_evaluation_batches() -> list:
	"""Batch cards for the batches the current user evaluates (Valutatore home)."""
	from lms.lms.utils import get_batch_details
	from os_lms.os_lms.valutatore import get_valutatore_batches

	out = []
	for name in get_valutatore_batches():
		details = get_batch_details(name)
		if details:
			out.append(details)
	return out


def _notify_students_class_cancelled(live_class) -> None:
	from frappe.desk.doctype.notification_log.notification_log import (
		make_notification_logs,
	)
	from frappe.utils import format_date, format_time

	students = frappe.get_all(
		"LMS Batch Enrollment",
		{"batch": live_class.batch_name},
		["member", "member_name"],
	)
	if not students:
		return

	formatted_date = format_date(live_class.date, "medium")
	formatted_time = format_time(live_class.time, "hh:mm a")

	subject = frappe._("La lezione dal vivo {0} del {1} alle {2} è stata annullata").format(
		frappe.bold(live_class.title), formatted_date, formatted_time
	)

	notification = frappe._dict(
		{
			"subject": subject,
			"type": "Alert",
			"from_user": frappe.session.user,
		}
	)
	make_notification_logs(notification, [s.member for s in students])

	for student in students:
		try:
			send_templated_email(
				template_key="live_class_cancelled",
				recipients=student.member,
				subject=frappe._("Lezione annullata: {0}").format(live_class.title),
				args={
					"student_name": student.member_name,
					"title": live_class.title,
					"date": live_class.date,
					"time": live_class.time,
					"batch_name": live_class.batch_name,
				},
				header=[frappe._("Lezione annullata"), "red"],
			)
		except Exception:
			frappe.logger("os_lms_live_class", allow_site=True).exception(
				f"Failed to send cancellation email to {student.member}"
			)


def _delete_zoom_meeting(zoom_account: str, meeting_id: str) -> None:
	"""Best-effort delete of the Zoom meeting; failures are logged but do not block deletion."""
	try:
		from lms.lms.doctype.lms_batch.lms_batch import authenticate

		headers = {"Authorization": "Bearer " + authenticate(zoom_account)}
		requests.delete(
			f"https://api.zoom.us/v2/meetings/{meeting_id}",
			headers=headers,
			timeout=10,
		)
	except Exception:
		frappe.logger("os_lms_live_class", allow_site=True).exception(
			f"Failed to delete Zoom meeting {meeting_id}"
		)


@frappe.whitelist()
def get_lesson_audio_stream(lesson_name: str, force_refresh: bool = False) -> dict:
	"""
	Returns a playable audio stream URL for the given lesson.

	Production mode: parses lesson content for the embedded Vimeo video,
	calls Vimeo API to get the HLS link with caching.

	Test mode: returns the test_audio_url configured in Vimeo Settings,
	bypassing Vimeo entirely.

	When `force_refresh=True`, the Redis cache is skipped and the Vimeo
	API is re-queried; used by the mobile app when the previously
	resolved HLS URL expires mid-playback (~6h signed-URL lifetime).
	"""
	settings = frappe.get_single("Vimeo Settings")

	if not settings.enabled:
		frappe.throw(
			"Integrazione Vimeo non abilitata in Vimeo Settings",
			frappe.ValidationError,
		)

	if settings.test_mode:
		if not settings.test_audio_url:
			frappe.throw("Test Audio URL non configurato in Vimeo Settings")
		return {
			"audio_url": settings.test_audio_url,
			"title": f"[TEST] {lesson_name}",
			"artist": "Test Audio",
			"artwork_url": None,
			"duration": 0,
			"expires_at": None,
			"test_mode": True,
		}

	lesson = frappe.get_doc("Course Lesson", lesson_name)
	if not lesson.content:
		frappe.throw("Lezione senza contenuto")

	try:
		content = json.loads(lesson.content)
	except json.JSONDecodeError:
		frappe.throw("Contenuto lezione malformato")

	vimeo_id, vimeo_hash = None, None
	for block in content.get("blocks", []):
		if block.get("type") == "embed" and block.get("data", {}).get("service") == "vimeo":
			match = VIMEO_URL_RE.search(block["data"].get("source", ""))
			if match:
				vimeo_id = match.group(1)
				vimeo_hash = match.group(2) or ""
				break

	if not vimeo_id:
		frappe.throw("Nessun video Vimeo trovato nella lezione")

	# v3: title/artist now derive from the lesson + course (display names),
	# not from Vimeo data / course slug. Keyed by lesson name since two
	# lessons referencing the same Vimeo video should still get their own
	# title/artist combination.
	cache_key = f"vimeo:stream:v3:{lesson_name}"
	if not force_refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached:
			return cached
	else:
		# Drop the stale entry so the new URL replaces it.
		frappe.cache().delete_value(cache_key)

	from os_lms.os_lms.doctype.vimeo_settings.vimeo_settings import get_vimeo_token

	token = get_vimeo_token()

	try:
		response = requests.get(
			f"https://api.vimeo.com/videos/{vimeo_id}",
			params={"fields": "play.hls.link,name,duration,pictures.sizes"},
			headers={"Authorization": f"Bearer {token}"},
			timeout=settings.api_timeout_seconds or 5,
		)
	except requests.exceptions.Timeout:
		frappe.throw("Vimeo API timeout, riprova piu' tardi")
	except requests.exceptions.RequestException as e:
		frappe.throw(f"Errore comunicazione Vimeo: {str(e)}")

	if response.status_code == 401:
		get_vimeo_token(force_refresh=True)
		frappe.throw("Token Vimeo non valido. Verificare Vimeo Settings.")
	if response.status_code == 403:
		frappe.throw("Video Vimeo non accessibile")
	if response.status_code == 404:
		frappe.throw("Video Vimeo non trovato")
	if response.status_code == 429:
		frappe.throw("Rate limit Vimeo, riprova tra qualche minuto")
	response.raise_for_status()

	data = response.json()
	hls_link = data.get("play", {}).get("hls", {}).get("link")
	if not hls_link:
		frappe.throw("Vimeo non ha restituito stream HLS per il video")

	# MediaSession metadata: lesson title as the main label, course
	# display title as the "artist" line. Fall back to Vimeo's video name
	# or the course slug only if the readable values are missing.
	course_title = frappe.db.get_value("LMS Course", lesson.course, "title") if lesson.course else None

	result = {
		"audio_url": hls_link,
		"title": lesson.title or data.get("name") or "",
		"artist": course_title or lesson.course or "",
		"artwork_url": _pick_vimeo_artwork(data),
		"duration": data.get("duration") or 0,
		"expires_at": None,
		"test_mode": False,
	}

	ttl = settings.cache_ttl_seconds or 18000
	frappe.cache().set_value(cache_key, result, expires_in_sec=ttl)

	return result


def _pick_vimeo_artwork(video_data: dict) -> str | None:
	"""Pick the highest-resolution Vimeo thumbnail capped at 1920px wide.

	Vimeo `pictures.sizes` is an array of {width, height, link} entries
	sorted ascending. We prefer images <= 1920px to keep bandwidth in check
	on lockscreen rendering; if all are larger, fall back to the largest
	available (rare for Vimeo, which usually exposes 100/200/295/640/960/
	1280/1920 variants).
	"""
	sizes = (video_data.get("pictures") or {}).get("sizes") or []
	if not sizes:
		return None
	capped = [s for s in sizes if s.get("width", 0) <= 1920]
	pool = capped if capped else sizes
	largest = max(pool, key=lambda s: s.get("width", 0))
	return largest.get("link")


def _find_adjacent_video_lessons(lesson) -> tuple[dict | None, dict | None]:
	"""Find the immediately prev/next lesson in the same course that has a
	Vimeo embed block. Returns (prev_info, next_info) where each is either
	None (no adjacent lesson, or adjacent has no Vimeo) or a dict:
	    { "name", "course", "chapter_idx", "lesson_idx", "title" }

	Crosses chapter boundaries: the lesson before the first lesson of a
	chapter is the last lesson of the previous chapter.
	"""
	chapter_idx = frappe.db.get_value(
		"Chapter Reference",
		{"parent": lesson.course, "chapter": lesson.chapter},
		"idx",
	)
	lesson_idx = frappe.db.get_value(
		"Lesson Reference",
		{"parent": lesson.chapter, "lesson": lesson.name},
		"idx",
	)
	if not chapter_idx or not lesson_idx:
		return None, None

	prev_pos = _find_lesson_at_offset(lesson.course, lesson.chapter, chapter_idx, lesson_idx, -1)
	next_pos = _find_lesson_at_offset(lesson.course, lesson.chapter, chapter_idx, lesson_idx, +1)

	return (
		_adjacent_lesson_info(prev_pos) if prev_pos else None,
		_adjacent_lesson_info(next_pos) if next_pos else None,
	)


def _find_lesson_at_offset(
	course: str, chapter: str, chapter_idx: int, lesson_idx: int, offset: int
) -> dict | None:
	"""Return the lesson position dict at `lesson_idx + offset` within the
	given chapter, crossing chapter boundaries when needed. Returns None
	when the boundary of the course is reached.
	"""
	target_idx = lesson_idx + offset

	# Stays in the current chapter
	if target_idx >= 1:
		ref = frappe.db.get_value(
			"Lesson Reference",
			{"parent": chapter, "idx": target_idx},
			["lesson", "idx"],
			as_dict=True,
		)
		if ref:
			return {
				"lesson_name": ref.lesson,
				"chapter_idx": chapter_idx,
				"lesson_idx": ref.idx,
			}

	# Crosses chapter boundary
	next_chapter_idx = chapter_idx + (1 if offset > 0 else -1)
	if next_chapter_idx < 1:
		return None

	next_chapter = frappe.db.get_value(
		"Chapter Reference",
		{"parent": course, "idx": next_chapter_idx},
		["chapter", "idx"],
		as_dict=True,
	)
	if not next_chapter:
		return None

	if offset > 0:
		# First lesson of next chapter
		ref = frappe.db.get_value(
			"Lesson Reference",
			{"parent": next_chapter.chapter, "idx": 1},
			["lesson", "idx"],
			as_dict=True,
		)
	else:
		# Last lesson of previous chapter
		rows = frappe.db.sql(
			"""
            SELECT lesson, idx FROM `tabLesson Reference`
            WHERE parent = %s ORDER BY idx DESC LIMIT 1
            """,
			next_chapter.chapter,
			as_dict=True,
		)
		ref = rows[0] if rows else None

	if not ref:
		return None

	return {
		"lesson_name": ref.lesson,
		"chapter_idx": next_chapter.idx,
		"lesson_idx": ref.idx,
	}


def _adjacent_lesson_info(pos: dict) -> dict | None:
	"""Return navigation info for an adjacent lesson, but only if its
	content has a Vimeo embed block — otherwise the skip button on the
	MediaSession would be a dead-end.
	"""
	lesson_doc = frappe.db.get_value(
		"Course Lesson",
		pos["lesson_name"],
		["name", "course", "title", "content"],
		as_dict=True,
	)
	if not lesson_doc or not lesson_doc.content:
		return None

	try:
		content = json.loads(lesson_doc.content)
	except json.JSONDecodeError:
		return None

	has_vimeo = any(
		block.get("type") == "embed" and (block.get("data") or {}).get("service") == "vimeo"
		for block in content.get("blocks", [])
	)
	if not has_vimeo:
		return None

	return {
		"name": lesson_doc.name,
		"course": lesson_doc.course,
		"chapter_idx": pos["chapter_idx"],
		"lesson_idx": pos["lesson_idx"],
		"title": lesson_doc.title,
	}


# ----- Student course-progress reset (desk admin tool) -----

# Roles allowed to wipe a student's course progress / re-issue a certificate.
RESET_PROGRESS_ROLES = ["Moderator", "System Manager"]


@frappe.whitelist()
def get_member_courses(member: str) -> list[dict]:
	"""Courses the given member is enrolled in, for the reset dialog picker.

	Restricted to admins; reads enrollments ignoring the per-doctype query
	conditions so the full list is returned regardless of the caller's scope.
	"""
	frappe.only_for(RESET_PROGRESS_ROLES)
	if not member:
		frappe.throw("member is required", frappe.ValidationError)

	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"member": member},
		fields=["course", "progress"],
		ignore_permissions=True,
		order_by="creation desc",
	)
	out = []
	for row in enrollments:
		out.append(
			{
				"course": row.course,
				"course_title": frappe.db.get_value("LMS Course", row.course, "title") or row.course,
				"progress": row.progress or 0,
			}
		)
	return out


@frappe.whitelist()
def reset_course_progress(member: str, course: str, dry_run: bool | int | str = False) -> dict:
	"""Wipe a student's progress for a course so it can be retaken from scratch.

	Deletes lesson progress, quiz submissions, assignment submissions, the
	issued certificate and its TrueSkills Issue Log rows, then zeroes the
	enrollment (progress / current_lesson / certificate) WITHOUT un-enrolling
	the student. Re-issuing a certificate afterwards re-triggers the TrueSkills
	emission via the LMS Certificate ``after_insert`` hook.

	Certificate Evaluations / Requests are intentionally left untouched.

	With ``dry_run`` truthy, nothing is deleted — only the counts that would be
	affected are returned, so the desk dialog can show a confirmation preview.
	"""
	frappe.only_for(RESET_PROGRESS_ROLES)

	if not member or not course:
		frappe.throw("member and course are required", frappe.ValidationError)
	if not frappe.db.exists("User", member):
		frappe.throw(f"User {member} not found", frappe.DoesNotExistError)
	if not frappe.db.exists("LMS Course", course):
		frappe.throw(f"Course {course} not found", frappe.DoesNotExistError)

	is_dry_run = str(dry_run).lower() not in ("0", "false", "no", "")

	certificates = frappe.get_all(
		"LMS Certificate",
		filters={"member": member, "course": course},
		pluck="name",
	)
	issue_logs = (
		frappe.get_all(
			"TrueSkills Issue Log",
			filters={"lms_certificate": ["in", certificates]},
			pluck="name",
		)
		if certificates
		else []
	)
	course_progress = frappe.get_all(
		"LMS Course Progress",
		filters={"member": member, "course": course},
		pluck="name",
	)
	quiz_submissions = frappe.get_all(
		"LMS Quiz Submission",
		filters={"member": member, "course": course},
		pluck="name",
	)
	assignment_submissions = frappe.get_all(
		"LMS Assignment Submission",
		filters={"member": member, "course": course},
		pluck="name",
	)
	enrollment = frappe.db.get_value("LMS Enrollment", {"member": member, "course": course}, "name")

	summary = {
		"member": member,
		"course": course,
		"course_title": frappe.db.get_value("LMS Course", course, "title") or course,
		"dry_run": is_dry_run,
		"enrollment_reset": bool(enrollment),
		"deleted": {
			"course_progress": len(course_progress),
			"quiz_submissions": len(quiz_submissions),
			"assignment_submissions": len(assignment_submissions),
			"certificates": len(certificates),
			"trueskills_issue_logs": len(issue_logs),
		},
	}

	if is_dry_run:
		return summary

	# Delete in dependency order: Issue Logs link to the certificate, and the
	# enrollment.certificate link is cleared before the certificate is removed.
	for name in issue_logs:
		frappe.delete_doc("TrueSkills Issue Log", name, force=True, ignore_permissions=True)

	if enrollment:
		frappe.db.set_value("LMS Enrollment", enrollment, "certificate", None)

	for name in certificates:
		frappe.delete_doc("LMS Certificate", name, force=True, ignore_permissions=True)

	# delete_doc cascades child tables (e.g. LMS Quiz Result on quiz submissions).
	for name in course_progress:
		frappe.delete_doc("LMS Course Progress", name, force=True, ignore_permissions=True)
	for name in quiz_submissions:
		frappe.delete_doc("LMS Quiz Submission", name, force=True, ignore_permissions=True)
	for name in assignment_submissions:
		frappe.delete_doc("LMS Assignment Submission", name, force=True, ignore_permissions=True)

	if enrollment:
		frappe.db.set_value(
			"LMS Enrollment",
			enrollment,
			{"progress": 0, "current_lesson": None, "certificate": None},
		)

	frappe.db.commit()
	return summary
