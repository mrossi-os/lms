import hashlib
import json
import re
from datetime import timedelta
from urllib.parse import quote

import frappe
import requests

from os_lms.os_lms.email_utils import send_templated_email

VIMEO_URL_RE = re.compile(r"vimeo\.com/(\d+)(?:/([a-zA-Z0-9]+))?")

VIMEO_SHARE_URL_RE = re.compile(
	r"^https?://(?:www\.)?vimeo\.com/share/"
	r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
	r"/?(?:\?\S*)?$"
)

# The share page is a Next.js app, so the canonical URL only shows up inside
# JSON payloads where slashes may be escaped ("vimeo.com\/123\/abc").
VIMEO_PLAYER_IN_PAGE_RE = re.compile(r"player\.vimeo\.com\\?/video\\?/(\d+)\?h=([a-zA-Z0-9]+)")
VIMEO_CANONICAL_IN_PAGE_RE = re.compile(r"(?<![\w.])vimeo\.com\\?/(\d+)\\?/([a-zA-Z0-9]+)")


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


@frappe.whitelist()
def get_batch_progress_stats(batch: str, course: str | None = None) -> dict:
	"""Progress statistics for the admin batch dashboard, scoped to the batch's
	own students.

	Available to batch admins and to the batch's valutatori (scoped read).

	Without ``course``: returns ``courses`` — one entry per batch course with the
	average course progress across the batch's enrolled students (a missing
	enrollment counts as 0, matching ``get_batch_certified_count``).

	With ``course``: returns ``lessons`` — one entry per lesson with the number of
	batch students who completed it (``completion_count``). ``students_count`` (the
	enrolled batch students) is returned in both cases as the completion-rate
	denominator.
	"""
	from pypika import functions as fn

	from frappe.utils import flt

	from lms.lms.utils import can_modify_batch, is_batch_valutatore

	if not (can_modify_batch(batch) or is_batch_valutatore(batch)):
		frappe.throw(
			frappe._("You are not authorized to view this batch."),
			frappe.PermissionError,
		)

	students_count = frappe.db.count("LMS Batch Enrollment", {"batch": batch})

	if not course:
		BatchCourse = frappe.qb.DocType("Batch Course")
		BatchEnrollment = frappe.qb.DocType("LMS Batch Enrollment")
		Enrollment = frappe.qb.DocType("LMS Enrollment")

		# Cross every batch course with every batch student (left join on the batch),
		# then bring in that student's enrollment progress for the course. Averaging
		# Coalesce(progress, 0) per course yields the batch-scoped average.
		rows = (
			frappe.qb.from_(BatchCourse)
			.left_join(BatchEnrollment)
			.on(BatchEnrollment.batch == BatchCourse.parent)
			.left_join(Enrollment)
			.on((Enrollment.course == BatchCourse.course) & (Enrollment.member == BatchEnrollment.member))
			.where(BatchCourse.parent == batch)
			.groupby(BatchCourse.course)
			.orderby(BatchCourse.idx)
			.select(
				BatchCourse.course,
				BatchCourse.title,
				fn.Avg(fn.Coalesce(Enrollment.progress, 0)).as_("avg_progress"),
			)
		).run(as_dict=True)

		return {
			"students_count": students_count,
			"courses": [
				{
					"course": row.course,
					"title": row.title,
					"avg_progress": flt(row.avg_progress, 2),
				}
				for row in rows
			],
		}

	# A specific course: per-lesson completion count restricted to batch students,
	# so both numerator and denominator are relative to the class.
	members = frappe.get_all("LMS Batch Enrollment", filters={"batch": batch}, pluck="member")
	if not members:
		return {"students_count": 0, "lessons": []}

	CourseProgress = frappe.qb.DocType("LMS Course Progress")
	LessonReference = frappe.qb.DocType("Lesson Reference")
	ChapterReference = frappe.qb.DocType("Chapter Reference")
	Lesson = frappe.qb.DocType("Course Lesson")

	lessons = (
		frappe.qb.from_(LessonReference)
		.join(ChapterReference)
		.on(LessonReference.parent == ChapterReference.chapter)
		.join(Lesson)
		.on(LessonReference.lesson == Lesson.name)
		.left_join(CourseProgress)
		.on(
			(CourseProgress.lesson == LessonReference.lesson)
			& (CourseProgress.course == course)
			& (CourseProgress.status == "Complete")
			& (CourseProgress.member.isin(members))
		)
		.select(
			LessonReference.idx,
			ChapterReference.idx.as_("chapter_idx"),
			Lesson.title,
			Lesson.name.as_("lesson_name"),
			fn.Count(CourseProgress.name).as_("completion_count"),
		)
		.where(ChapterReference.parent == course)
		.groupby(LessonReference.lesson)
		.orderby(ChapterReference.idx, LessonReference.idx)
		.run(as_dict=True)
	)

	return {"students_count": students_count, "lessons": lessons}


@frappe.whitelist()
def get_batch_student_course_progress(batch: str, course: str, member: str) -> dict:
	"""Per-lesson progress of a single batch student in one course.

	Powers the course drill-down in the admin batch dashboard's student dialog:
	each lesson of ``course`` in order, flagged with whether ``member`` has
	completed it.

	Available to batch admins and to the batch's valutatori (scoped read). Going
	through this batch-authorized endpoint lets valutatori — who cannot read
	``LMS Course Progress`` directly — see the drill-down for their own students.
	"""
	from pypika import functions as fn

	from lms.lms.utils import can_modify_batch, is_batch_valutatore

	if not (can_modify_batch(batch) or is_batch_valutatore(batch)):
		frappe.throw(
			frappe._("You are not authorized to view this batch."),
			frappe.PermissionError,
		)

	CourseProgress = frappe.qb.DocType("LMS Course Progress")
	LessonReference = frappe.qb.DocType("Lesson Reference")
	ChapterReference = frappe.qb.DocType("Chapter Reference")
	Lesson = frappe.qb.DocType("Course Lesson")

	# Left-join this member's "Complete" progress row onto every lesson of the
	# course, so a missing row reads as not-completed. Count is 0 or 1 per lesson
	# (a member completes a lesson at most once).
	lessons = (
		frappe.qb.from_(LessonReference)
		.join(ChapterReference)
		.on(LessonReference.parent == ChapterReference.chapter)
		.join(Lesson)
		.on(LessonReference.lesson == Lesson.name)
		.left_join(CourseProgress)
		.on(
			(CourseProgress.lesson == LessonReference.lesson)
			& (CourseProgress.course == course)
			& (CourseProgress.status == "Complete")
			& (CourseProgress.member == member)
		)
		.select(
			LessonReference.idx,
			ChapterReference.idx.as_("chapter_idx"),
			Lesson.title,
			Lesson.name.as_("lesson_name"),
			fn.Count(CourseProgress.name).as_("completed"),
		)
		.where(ChapterReference.parent == course)
		.groupby(LessonReference.lesson)
		.orderby(ChapterReference.idx, LessonReference.idx)
		.run(as_dict=True)
	)

	for lesson in lessons:
		lesson["completed"] = bool(lesson["completed"])

	return {"lessons": lessons}


@frappe.whitelist()
def export_batch_progress(batch: str, file_format: str = "xlsx"):
	"""Download a report of the batch students' course progress. Labels are in Italian.

	``file_format="xlsx"`` (default) — human-readable summary: one row per
	(student, started course) with the started / not-started course counts and the
	completed / not-completed lesson names. Students with no started course still
	get a row so the roster stays complete.

	``file_format="csv"`` — raw, un-aggregated dataset for downstream (e.g. AI)
	analysis: one row per (student, course, lesson) with completion flags, covering
	every batch course and lesson.

	A course is "started" when the student has any progress row for it; a lesson
	counts as completed when its status is ``Complete``.

	Streams the file back via ``frappe.response`` (content-disposition), so the
	frontend just opens the endpoint URL. Available to batch admins and to the
	batch's valutatori (scoped read).
	"""
	from lms.lms.utils import can_modify_batch, is_batch_valutatore

	if not (can_modify_batch(batch) or is_batch_valutatore(batch)):
		frappe.throw(
			frappe._("You are not authorized to view this batch."),
			frappe.PermissionError,
		)

	students = frappe.get_all(
		"LMS Batch Enrollment",
		filters={"batch": batch},
		fields=["member", "member_name"],
		order_by="member_name asc",
	)

	courses = frappe.get_all(
		"Batch Course",
		filters={"parent": batch, "parenttype": "LMS Batch"},
		fields=["course", "title"],
		order_by="idx asc",
	)
	course_ids = [c.course for c in courses]
	course_title = {c.course: c.title for c in courses}

	# Ordered lessons for every batch course in a single query.
	lessons_by_course = {cid: [] for cid in course_ids}
	if course_ids:
		LessonReference = frappe.qb.DocType("Lesson Reference")
		ChapterReference = frappe.qb.DocType("Chapter Reference")
		Lesson = frappe.qb.DocType("Course Lesson")
		lesson_rows = (
			frappe.qb.from_(LessonReference)
			.join(ChapterReference)
			.on(LessonReference.parent == ChapterReference.chapter)
			.join(Lesson)
			.on(LessonReference.lesson == Lesson.name)
			.select(
				ChapterReference.parent.as_("course"),
				ChapterReference.idx.as_("chapter_idx"),
				LessonReference.idx.as_("lesson_idx"),
				Lesson.name.as_("lesson"),
				Lesson.title,
			)
			.where(ChapterReference.parent.isin(course_ids))
			.orderby(ChapterReference.parent, ChapterReference.idx, LessonReference.idx)
			.run(as_dict=True)
		)
		for row in lesson_rows:
			lessons_by_course.setdefault(row.course, []).append(row)

	# All progress rows for the batch's members and courses: presence marks the
	# course as started; a "Complete" row marks the lesson as completed.
	members = [s.member for s in students]
	completed = {}  # (member, course) -> set(lesson)
	started = {}  # member -> set(course)
	if members and course_ids:
		CourseProgress = frappe.qb.DocType("LMS Course Progress")
		progress_rows = (
			frappe.qb.from_(CourseProgress)
			.select(
				CourseProgress.member,
				CourseProgress.course,
				CourseProgress.lesson,
				CourseProgress.status,
			)
			.where(CourseProgress.member.isin(members) & CourseProgress.course.isin(course_ids))
			.run(as_dict=True)
		)
		for row in progress_rows:
			started.setdefault(row.member, set()).add(row.course)
			if row.status == "Complete":
				completed.setdefault((row.member, row.course), set()).add(row.lesson)

	batch_title = frappe.db.get_value("LMS Batch", batch, "title") or batch
	safe_title = re.sub(r"[^\w\- ]", "_", batch_title).strip() or "batch"

	if file_format == "csv":
		# Raw, un-aggregated matrix for AI analysis: one row per
		# (student, course, lesson), covering every batch course and lesson.
		import csv
		import io

		buffer = io.StringIO()
		writer = csv.writer(buffer)
		writer.writerow(
			["Studente", "Email", "Corso", "Corso avviato", "Capitolo", "Lezione n.", "Lezione", "Completata"]
		)
		for student in students:
			student_started = started.get(student.member, set())
			for cid in course_ids:
				is_started = 1 if cid in student_started else 0
				done = completed.get((student.member, cid), set())
				for lesson in lessons_by_course.get(cid, []):
					writer.writerow(
						[
							student.member_name or student.member,
							student.member,
							course_title.get(cid, cid),
							is_started,
							lesson.chapter_idx,
							lesson.lesson_idx,
							lesson.title,
							1 if lesson.lesson in done else 0,
						]
					)

		frappe.response["filename"] = f"{safe_title} - Dati grezzi.csv"
		frappe.response["filecontent"] = buffer.getvalue().encode("utf-8")
		frappe.response["type"] = "download"
		frappe.response["content_type"] = "text/csv; charset=utf-8"
		return

	# Default: human-readable XLSX summary, one row per (student, started course).
	from frappe.utils.xlsxutils import make_xlsx

	data = [
		[
			"Studente",
			"Email",
			"Corsi avviati",
			"Corsi non iniziati",
			"Corso",
			"Lezioni completate",
			"Nomi lezioni completate",
			"Lezioni non completate",
			"Nomi lezioni non completate",
		]
	]

	total_courses = len(course_ids)
	for student in students:
		student_started = started.get(student.member, set())
		started_courses = [cid for cid in course_ids if cid in student_started]
		started_count = len(started_courses)
		not_started_count = total_courses - started_count

		if not started_courses:
			data.append(
				[student.member_name or student.member, student.member, started_count, not_started_count, "", "", "", "", ""]
			)
			continue

		for cid in started_courses:
			lessons = lessons_by_course.get(cid, [])
			done = completed.get((student.member, cid), set())
			done_lessons = [lesson for lesson in lessons if lesson.lesson in done]
			todo_lessons = [lesson for lesson in lessons if lesson.lesson not in done]
			data.append(
				[
					student.member_name or student.member,
					student.member,
					started_count,
					not_started_count,
					course_title.get(cid, cid),
					len(done_lessons),
					"; ".join(lesson.title for lesson in done_lessons),
					len(todo_lessons),
					"; ".join(lesson.title for lesson in todo_lessons),
				]
			)

	xlsx_file = make_xlsx(data, "Statistiche")

	frappe.response["filename"] = f"{safe_title} - Statistiche.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "download"
	frappe.response["content_type"] = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


# ---------------------------------------------------------------------------
# Student statistics export
#
# A role-gated CSV/XLSX export of student statistics. The available report
# types and their selectable columns are declared once in
# STUDENT_STATS_REPORTS, so the SPA (get_student_stats_schema) and the export
# builders can never diverge. Reuses the CSV/XLSX streaming mechanics of
# export_batch_progress above.
# ---------------------------------------------------------------------------

STUDENT_STATS_REPORTS = {
	"users": {
		"label": "Utenti",
		"columns": [
			{"key": "user_id", "label": "ID utente"},
			{"key": "full_name", "label": "Nome e cognome"},
			{"key": "email", "label": "Email"},
			{"key": "role", "label": "Ruolo"},
			{"key": "class", "label": "Classe"},
			{"key": "registered_on", "label": "Data di registrazione"},
			{"key": "status", "label": "Stato utente"},
			{"key": "last_login", "label": "Ultimo accesso"},
		],
	},
	"user_courses": {
		"label": "Utenti x Corsi",
		"columns": [
			{"key": "user_id", "label": "ID utente"},
			{"key": "full_name", "label": "Nome e cognome"},
			{"key": "email", "label": "Email"},
			{"key": "course_id", "label": "ID corso"},
			{"key": "course_title", "label": "Titolo corso"},
			{"key": "enrolled_on", "label": "Data di iscrizione"},
			{"key": "progress", "label": "Completamento (%)"},
			{"key": "started_on", "label": "Data di primo avvio"},
			{"key": "last_activity_on", "label": "Ultima attivita"},
			{"key": "completed_on", "label": "Data di completamento"},
			# Lesson-level columns: selecting any of these switches the report to
			# one row per lesson (see _build_user_courses_rows / dynamic granularity).
			# default=False so the report stays course-level until the user opts in.
			{"key": "chapter", "label": "Capitolo", "default": False},
			{"key": "content_id", "label": "ID contenuto", "default": False},
			{"key": "content_title", "label": "Titolo contenuto", "default": False},
			{"key": "content_type", "label": "Tipo contenuto", "default": False},
			{"key": "content_status", "label": "Stato completamento contenuto", "default": False},
			{"key": "content_completed_on", "label": "Data completamento contenuto", "default": False},
		],
	},
	"quizzes": {
		"label": "Quiz",
		"columns": [
			{"key": "user_id", "label": "ID utente"},
			{"key": "full_name", "label": "Nome e cognome"},
			{"key": "course_title", "label": "Titolo corso"},
			{"key": "quiz_id", "label": "ID quiz"},
			{"key": "quiz_title", "label": "Titolo quiz"},
			{"key": "attempts", "label": "N. tentativi"},
			{"key": "first_attempt_on", "label": "Primo tentativo"},
			{"key": "last_attempt_on", "label": "Ultimo tentativo"},
			{"key": "last_score", "label": "Punteggio ultimo tentativo (%)"},
			{"key": "best_score", "label": "Punteggio migliore (%)"},
			{"key": "max_score", "label": "Punteggio massimo"},
		],
	},
	"ai": {
		"label": "Interazioni AI",
		"columns": [
			{"key": "student_id", "label": "ID studente"},
			{"key": "interacted_on", "label": "Data e ora"},
			{"key": "course", "label": "Corso"},
			{"key": "lesson", "label": "Contenuto / lezione"},
			{"key": "question", "label": "Domanda"},
			{"key": "answer", "label": "Risposta"},
			{"key": "context", "label": "Contesto"},
			{"key": "server_error", "label": "Errore del server"},
			{"key": "cannot_answer", "label": "Non posso rispondere"},
		],
	},
}

STUDENT_STATS_FILTERS = ["course", "batch", "students", "activity_from", "activity_to"]


def can_export_student_stats() -> bool:
	"""Single source of truth for who may export student statistics.

	For now only System Manager (Administrator). Add further roles here when the
	product decides to broaden access (keep override_api.get_user_info in sync).
	"""
	return "System Manager" in frappe.get_roles()


def _ensure_can_export_student_stats():
	if not can_export_student_stats():
		frappe.throw(
			frappe._("You are not authorized to export student statistics."),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_student_stats_schema():
	"""Return the report types, their selectable columns and the supported
	filters. Single source of truth shared with the SPA export page."""
	_ensure_can_export_student_stats()
	return {
		"reports": STUDENT_STATS_REPORTS,
		"filters": STUDENT_STATS_FILTERS,
	}


def _fmt_dt(value) -> str:
	if not value:
		return ""
	from frappe.utils import format_datetime

	return format_datetime(value, "yyyy-MM-dd HH:mm")


def _fmt_date(value) -> str:
	if not value:
		return ""
	from frappe.utils import formatdate

	return formatdate(value, "yyyy-MM-dd")


def _parse_stats_filters(filters) -> dict:
	"""Normalize the (JSON-encoded) filters payload into a predictable dict."""
	filters = frappe.parse_json(filters) if filters else {}
	if not isinstance(filters, dict):
		filters = {}

	def _as_list(value):
		if not value:
			return []
		if isinstance(value, str):
			return [value]
		return list(value)

	return {
		"course": _as_list(filters.get("course")),
		"batch": _as_list(filters.get("batch")),
		"students": _as_list(filters.get("students")),
		"activity_from": filters.get("activity_from") or None,
		"activity_to": filters.get("activity_to") or None,
	}


def _member_scope(filters: dict):
	"""Member set implied by the batch + students filters (the course filter is
	applied per-report on the row's own course field). Returns None when no
	member-scoping filter is set, meaning "no restriction"."""
	member_sets = []
	if filters["students"]:
		member_sets.append(set(filters["students"]))
	if filters["batch"]:
		rows = frappe.get_all(
			"LMS Batch Enrollment",
			filters={"batch": ["in", filters["batch"]]},
			fields=["member"],
		)
		member_sets.append({r.member for r in rows})

	if not member_sets:
		return None

	result = member_sets[0]
	for extra in member_sets[1:]:
		result &= extra
	return result


def _role_label(roles: set) -> str:
	"""Collapse a user's roles into a single LMS-facing label."""
	if "Moderator" in roles or "Gestore" in roles:
		return "Moderatore"
	if "Course Creator" in roles or "Docente" in roles:
		return "Docente"
	if "Batch Evaluator" in roles or "Valutatore" in roles:
		return "Valutatore"
	return "Studente"


def _build_users_rows(filters: dict, selected: list | None = None) -> list:
	member_scope = _member_scope(filters)

	# A course filter narrows the user set to that course's enrolled members.
	if filters["course"]:
		enrolled = frappe.get_all(
			"LMS Enrollment",
			filters={"course": ["in", filters["course"]]},
			fields=["member"],
		)
		course_members = {r.member for r in enrolled}
		member_scope = course_members if member_scope is None else (member_scope & course_members)

	conditions = [["enabled", "=", 1], ["name", "not in", ["Guest", "Administrator"]]]
	if member_scope is not None:
		if not member_scope:
			return []
		conditions.append(["name", "in", list(member_scope)])
	if filters["activity_from"]:
		conditions.append(["last_login", ">=", filters["activity_from"]])
	if filters["activity_to"]:
		conditions.append(["last_login", "<=", filters["activity_to"]])

	users = frappe.get_all(
		"User",
		filters=conditions,
		fields=["name", "full_name", "email", "enabled", "creation", "last_login"],
		order_by="full_name asc",
	)
	if not users:
		return []

	names = [u.name for u in users]

	# Roles and class (batch) memberships in bulk to avoid per-user queries.
	roles_by_user = {}
	for r in frappe.get_all(
		"Has Role",
		filters={"parent": ["in", names], "parenttype": "User"},
		fields=["parent", "role"],
	):
		roles_by_user.setdefault(r.parent, set()).add(r.role)

	class_by_user = {}
	batch_rows = frappe.get_all(
		"LMS Batch Enrollment",
		filters={"member": ["in", names]},
		fields=["member", "batch"],
	)
	batch_ids = list({b.batch for b in batch_rows if b.batch})
	batch_title = {}
	if batch_ids:
		for bt in frappe.get_all(
			"LMS Batch", filters={"name": ["in", batch_ids]}, fields=["name", "title"]
		):
			batch_title[bt.name] = bt.title
	for b in batch_rows:
		if b.batch:
			class_by_user.setdefault(b.member, []).append(batch_title.get(b.batch, b.batch))

	rows = []
	for u in users:
		rows.append(
			{
				"user_id": u.name,
				"full_name": u.full_name or "",
				"email": u.email or u.name,
				"role": _role_label(roles_by_user.get(u.name, set())),
				"class": ", ".join(sorted(set(class_by_user.get(u.name, [])))),
				"registered_on": _fmt_dt(u.creation),
				"status": "Attivo" if u.enabled else "Disattivato",
				"last_login": _fmt_dt(u.last_login),
			}
		)
	return rows


# Selecting any of these lesson-level columns switches the "Utenti x Corsi"
# report from one row per (student, course) to one row per (student, lesson).
USER_COURSES_LESSON_COLUMNS = {
	"chapter",
	"content_id",
	"content_title",
	"content_type",
	"content_status",
	"content_completed_on",
}

# get_lesson_icon (the same helper that drives the course-outline icon) mapped
# to a human-readable content type, so the report always matches the UI.
_CONTENT_TYPE_LABEL = {
	"icon-youtube": "Video",
	"icon-quiz": "Quiz",
	"icon-assignment": "Esercizio",
	"icon-code": "Programma",
	"icon-list": "Testo",
}

# LMS Course Progress.status -> label. A missing progress row means the student
# has not started that lesson.
_LESSON_STATUS_LABEL = {
	"Complete": "Completato",
	"Partially Complete": "Parzialmente completato",
	"Incomplete": "Non completato",
}


def _build_user_courses_rows(filters: dict, selected: list | None = None) -> list:
	member_scope = _member_scope(filters)

	conditions = []
	if filters["course"]:
		conditions.append(["course", "in", filters["course"]])
	if member_scope is not None:
		if not member_scope:
			return []
		conditions.append(["member", "in", list(member_scope)])
	if filters["activity_from"]:
		conditions.append(["creation", ">=", filters["activity_from"]])
	if filters["activity_to"]:
		conditions.append(["creation", "<=", filters["activity_to"]])

	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters=conditions or None,
		fields=["member", "member_name", "course", "creation", "progress"],
		order_by="member_name asc",
	)
	if not enrollments:
		return []

	lesson_mode = bool(selected) and any(k in USER_COURSES_LESSON_COLUMNS for k in selected)

	members = list({e.member for e in enrollments})
	course_ids = list({e.course for e in enrollments})

	user_map = {
		u.name: u
		for u in frappe.get_all(
			"User", filters={"name": ["in", members]}, fields=["name", "full_name", "email"]
		)
	}
	course_title = {
		c.name: c.title
		for c in frappe.get_all(
			"LMS Course", filters={"name": ["in", course_ids]}, fields=["name", "title"]
		)
	}

	# Per (member, course) progress aggregates: first/last activity and the
	# timestamp of the last completed lesson (the completion moment at 100%).
	# In lesson mode we also keep the per-lesson status/timestamp.
	first_on, last_on, complete_last = {}, {}, {}
	lesson_progress = {}
	for r in frappe.get_all(
		"LMS Course Progress",
		filters={"member": ["in", members], "course": ["in", course_ids]},
		fields=["member", "course", "lesson", "status", "creation"],
	):
		key = (r.member, r.course)
		if key not in first_on or r.creation < first_on[key]:
			first_on[key] = r.creation
		if key not in last_on or r.creation > last_on[key]:
			last_on[key] = r.creation
		if r.status == "Complete" and (key not in complete_last or r.creation > complete_last[key]):
			complete_last[key] = r.creation
		if lesson_mode and r.lesson:
			lesson_progress[(r.member, r.lesson)] = (r.status, r.creation)

	# Explicit completion date from the certificate, when the course issues one.
	cert_date = {}
	for c in frappe.get_all(
		"LMS Certificate",
		filters={"member": ["in", members], "course": ["in", course_ids]},
		fields=["member", "course", "issue_date"],
	):
		if c.issue_date:
			cert_date[(c.member, c.course)] = c.issue_date

	def base_row(e):
		key = (e.member, e.course)
		u = user_map.get(e.member)
		completed = None
		if key in cert_date:
			completed = cert_date[key]
		elif (e.progress or 0) >= 100:
			completed = complete_last.get(key)
		return {
			"user_id": e.member,
			"full_name": e.member_name or (u.full_name if u else "") or "",
			"email": (u.email if u else "") or e.member,
			"course_id": e.course,
			"course_title": course_title.get(e.course, e.course),
			"enrolled_on": _fmt_dt(e.creation),
			"progress": e.progress or 0,
			"started_on": _fmt_dt(first_on.get(key)),
			"last_activity_on": _fmt_dt(last_on.get(key)),
			"completed_on": _fmt_date(completed),
		}

	if not lesson_mode:
		return [base_row(e) for e in enrollments]

	# --- Lesson mode: expand each enrollment into one row per lesson ---
	course_lessons = _course_outline_lessons(course_ids)
	rows = []
	for e in enrollments:
		base = base_row(e)
		outline = course_lessons.get(e.course, [])
		if not outline:
			# Keep the enrolled student visible even if the course has no lessons.
			rows.append({**base, **_empty_lesson_fields()})
			continue
		for chapter_title, lesson_id, lesson_title, content_type in outline:
			status, cdate = lesson_progress.get((e.member, lesson_id), (None, None))
			rows.append(
				{
					**base,
					"chapter": chapter_title,
					"content_id": lesson_id,
					"content_title": lesson_title,
					"content_type": content_type,
					"content_status": _LESSON_STATUS_LABEL.get(status, "Non iniziato"),
					"content_completed_on": _fmt_dt(cdate) if status == "Complete" else "",
				}
			)
	return rows


def _empty_lesson_fields() -> dict:
	return {
		"chapter": "",
		"content_id": "",
		"content_title": "",
		"content_type": "",
		"content_status": "",
		"content_completed_on": "",
	}


def _course_outline_lessons(course_ids: list) -> dict:
	"""Return, per course, its lessons in outline order as tuples
	(chapter_title, lesson_id, lesson_title, content_type_label).

	Order follows the UI outline: LMS Course.chapters (Chapter Reference) then
	each Course Chapter.lessons (Lesson Reference). content_type reuses
	get_lesson_icon so it matches the icon shown in the course outline.
	"""
	from lms.lms.utils import get_lesson_icon

	if not course_ids:
		return {}

	# Chapters in order per course.
	chapter_refs = frappe.get_all(
		"Chapter Reference",
		filters={"parenttype": "LMS Course", "parent": ["in", course_ids]},
		fields=["parent as course", "chapter", "idx"],
		order_by="idx asc",
	)
	chapters_of_course = {}
	for c in chapter_refs:
		chapters_of_course.setdefault(c.course, []).append(c.chapter)

	chapter_names = [c.chapter for c in chapter_refs]
	if not chapter_names:
		return {}

	chapter_title = {
		c.name: c.title
		for c in frappe.get_all(
			"Course Chapter", filters={"name": ["in", chapter_names]}, fields=["name", "title"]
		)
	}

	# Lessons in order per chapter.
	lesson_refs = frappe.get_all(
		"Lesson Reference",
		filters={"parenttype": "Course Chapter", "parent": ["in", chapter_names]},
		fields=["parent as chapter", "lesson", "idx"],
		order_by="idx asc",
	)
	lessons_of_chapter = {}
	for lr in lesson_refs:
		lessons_of_chapter.setdefault(lr.chapter, []).append(lr.lesson)

	lesson_ids = [lr.lesson for lr in lesson_refs]
	lesson_map = {
		lesson.name: lesson
		for lesson in frappe.get_all(
			"Course Lesson",
			filters={"name": ["in", lesson_ids]},
			fields=["name", "title", "body", "content"],
		)
	}

	outline = {}
	for course in course_ids:
		items = []
		for chapter in chapters_of_course.get(course, []):
			for lesson_id in lessons_of_chapter.get(chapter, []):
				lesson = lesson_map.get(lesson_id)
				if not lesson:
					continue
				content_type = _CONTENT_TYPE_LABEL.get(
					get_lesson_icon(lesson.body, lesson.content), "Testo"
				)
				items.append(
					(chapter_title.get(chapter, chapter), lesson_id, lesson.title or "", content_type)
				)
		outline[course] = items
	return outline


def _build_quizzes_rows(filters: dict, selected: list | None = None) -> list:
	member_scope = _member_scope(filters)

	conditions = []
	if filters["course"]:
		conditions.append(["course", "in", filters["course"]])
	if member_scope is not None:
		if not member_scope:
			return []
		conditions.append(["member", "in", list(member_scope)])
	if filters["activity_from"]:
		conditions.append(["creation", ">=", filters["activity_from"]])
	if filters["activity_to"]:
		conditions.append(["creation", "<=", filters["activity_to"]])

	# Ordered ascending so the last submission processed per (member, quiz) is
	# the most recent one, which drives "last_score".
	subs = frappe.get_all(
		"LMS Quiz Submission",
		filters=conditions or None,
		fields=[
			"member",
			"member_name",
			"quiz",
			"quiz_title",
			"course",
			"percentage",
			"score_out_of",
			"creation",
		],
		order_by="creation asc",
	)
	if not subs:
		return []

	members = list({s.member for s in subs})
	course_ids = list({s.course for s in subs if s.course})
	user_map = {
		u.name: u
		for u in frappe.get_all("User", filters={"name": ["in", members]}, fields=["name", "full_name"])
	}
	course_title = (
		{
			c.name: c.title
			for c in frappe.get_all(
				"LMS Course", filters={"name": ["in", course_ids]}, fields=["name", "title"]
			)
		}
		if course_ids
		else {}
	)

	agg = {}
	for s in subs:
		key = (s.member, s.quiz)
		a = agg.get(key)
		if a is None:
			a = agg[key] = {
				"member": s.member,
				"member_name": s.member_name,
				"quiz": s.quiz,
				"quiz_title": s.quiz_title,
				"course": s.course,
				"attempts": 0,
				"first_on": s.creation,
				"last_on": s.creation,
				"last_score": s.percentage or 0,
				"best_score": s.percentage or 0,
				"max_score": s.score_out_of or 0,
			}
		a["attempts"] += 1
		if s.creation < a["first_on"]:
			a["first_on"] = s.creation
		if s.creation >= a["last_on"]:
			a["last_on"] = s.creation
			a["last_score"] = s.percentage or 0
		a["best_score"] = max(a["best_score"], s.percentage or 0)
		if s.score_out_of:
			a["max_score"] = s.score_out_of

	rows = []
	for a in agg.values():
		u = user_map.get(a["member"])
		rows.append(
			{
				"user_id": a["member"],
				"full_name": a["member_name"] or (u.full_name if u else "") or "",
				"course_title": course_title.get(a["course"], a["course"] or ""),
				"quiz_id": a["quiz"],
				"quiz_title": a["quiz_title"] or a["quiz"],
				"attempts": a["attempts"],
				"first_attempt_on": _fmt_dt(a["first_on"]),
				"last_attempt_on": _fmt_dt(a["last_on"]),
				"last_score": a["last_score"],
				"best_score": a["best_score"],
				"max_score": a["max_score"],
			}
		)
	rows.sort(key=lambda r: (r["full_name"], r["quiz_title"]))
	return rows


def _build_ai_rows(filters: dict, selected: list | None = None) -> list:
	member_scope = _member_scope(filters)

	conditions = []
	if filters["course"]:
		conditions.append(["course", "in", filters["course"]])
	if member_scope is not None:
		if not member_scope:
			return []
		conditions.append(["member", "in", list(member_scope)])
	if filters["activity_from"]:
		conditions.append(["creation", ">=", filters["activity_from"]])
	if filters["activity_to"]:
		conditions.append(["creation", "<=", filters["activity_to"]])

	logs = frappe.get_all(
		"LMSA Query Log",
		filters=conditions or None,
		fields=["member", "creation", "course", "lesson", "question", "answer", "context", "status"],
		order_by="creation desc",
	)

	rows = []
	for log in logs:
		answer = log.answer or ""
		rows.append(
			{
				"student_id": log.member,
				"interacted_on": _fmt_dt(log.creation),
				"course": log.course or "",
				"lesson": log.lesson or "",
				"question": log.question or "",
				"answer": answer,
				"context": log.context or "",
				# status options are Pending / Answered / Failed
				"server_error": 1 if log.status == "Failed" else 0,
				"cannot_answer": 1 if "non posso rispondere" in answer.lower() else 0,
			}
		)
	return rows


STUDENT_STATS_BUILDERS = {
	"users": _build_users_rows,
	"user_courses": _build_user_courses_rows,
	"quizzes": _build_quizzes_rows,
	"ai": _build_ai_rows,
}


def _normalize_export_columns(report: dict, columns) -> list:
	"""Validate the requested columns against the report and return them in the
	report's declared order. Raises if none are valid."""
	declared = [c["key"] for c in report["columns"]]
	requested = frappe.parse_json(columns) if columns else []
	if isinstance(requested, str):
		requested = [requested]
	requested_set = set(requested)
	selected = [k for k in declared if k in requested_set]
	if not selected:
		frappe.throw(frappe._("Select at least one valid column."), frappe.ValidationError)
	return selected


def _build_export_bytes(report_type: str, columns, file_format: str, parsed_filters: dict):
	"""Build the export file. Returns (filename, content_type, content_bytes,
	row_count). Validates the report type and columns and keeps the report's
	declared column order for a stable layout."""
	report = STUDENT_STATS_REPORTS.get(report_type)
	if not report:
		frappe.throw(frappe._("Unknown report type."), frappe.ValidationError)

	selected = _normalize_export_columns(report, columns)
	label_by_key = {c["key"]: c["label"] for c in report["columns"]}

	rows = STUDENT_STATS_BUILDERS[report_type](parsed_filters, selected)
	header = [label_by_key[k] for k in selected]
	data = [[row.get(k, "") for k in selected] for row in rows]
	safe_label = re.sub(r"[^\w\- ]", "_", report["label"]).strip() or "statistiche"

	if file_format == "csv":
		import csv
		import io

		buffer = io.StringIO()
		writer = csv.writer(buffer)
		writer.writerow(header)
		writer.writerows(data)
		return (
			f"{safe_label}.csv",
			"text/csv; charset=utf-8",
			buffer.getvalue().encode("utf-8"),
			len(rows),
		)

	from frappe.utils.xlsxutils import make_xlsx

	xlsx_file = make_xlsx([header] + data, "Statistiche")
	content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	return f"{safe_label}.xlsx", content_type, xlsx_file.getvalue(), len(rows)


@frappe.whitelist()
def start_student_stats_export(
	report_type: str, columns: str, file_format: str = "csv", filters: str | None = None
):
	"""Queue a student-statistics export.

	Creates a ``Student Stats Export`` record (status Queued) and enqueues the
	build on the standard ``long`` queue (present in every Frappe deployment,
	same queue used by the simulation debrief). Returns the record name; the SPA
	polls ``list_student_stats_exports`` for the status and downloads the file
	once it is Ready. Every export is heavy enough to warrant the background job,
	so there is no synchronous path.
	"""
	_ensure_can_export_student_stats()

	report = STUDENT_STATS_REPORTS.get(report_type)
	if not report:
		frappe.throw(frappe._("Unknown report type."), frappe.ValidationError)
	if file_format not in ("csv", "xlsx"):
		frappe.throw(frappe._("Invalid file format."), frappe.ValidationError)

	selected = _normalize_export_columns(report, columns)

	export = frappe.new_doc("Student Stats Export")
	export.report_type = report_type
	export.report_label = report["label"]
	export.file_format = file_format
	export.columns = frappe.as_json(selected)
	export.filters = filters or "{}"
	export.status = "Queued"
	export.insert(ignore_permissions=True)

	frappe.enqueue(
		"os_lms.os_lms.api.run_student_stats_export",
		queue="long",
		timeout=1800,
		enqueue_after_commit=True,
		export_name=export.name,
	)
	return {"name": export.name}


def run_student_stats_export(export_name: str):
	"""Background job (``long`` queue): build the export file and attach it to
	the record as a private File, flipping the status to Ready/Failed. Never
	streams anything back."""
	export = frappe.get_doc("Student Stats Export", export_name)
	frappe.db.set_value("Student Stats Export", export_name, "status", "Processing")
	frappe.db.commit()
	try:
		parsed_filters = _parse_stats_filters(export.filters)
		filename, _content_type, content, row_count = _build_export_bytes(
			export.report_type, export.columns, export.file_format, parsed_filters
		)

		from frappe.utils.file_manager import save_file

		file_doc = save_file(filename, content, "Student Stats Export", export_name, is_private=1)
		frappe.db.set_value(
			"Student Stats Export",
			export_name,
			{
				"file": file_doc.file_url,
				"row_count": row_count,
				"file_size": len(content),
				"status": "Ready",
				"error": "",
			},
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.db.set_value(
			"Student Stats Export",
			export_name,
			{"status": "Failed", "error": frappe.get_traceback()[:2000]},
		)
		frappe.db.commit()
		frappe.log_error(title="Student stats export failed", message=export_name)
		raise


@frappe.whitelist()
def list_student_stats_exports():
	"""List all student-statistics exports, newest first. Shared: every user who
	can export sees (and can manage) every export."""
	_ensure_can_export_student_stats()
	return frappe.get_all(
		"Student Stats Export",
		fields=[
			"name",
			"report_type",
			"report_label",
			"file_format",
			"status",
			"creation",
			"owner",
			"row_count",
			"file_size",
			"file",
			"error",
		],
		order_by="creation desc",
		limit=200,
	)


@frappe.whitelist()
def delete_student_stats_export(name: str):
	"""Delete an export record and its generated file. Any user who can export may
	delete any export (shared management), so gate on the export capability only."""
	_ensure_can_export_student_stats()
	if frappe.db.exists("Student Stats Export", name):
		frappe.delete_doc(
			"Student Stats Export", name, ignore_permissions=True, delete_permanently=True
		)
	return {"name": name}


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


def _ensure_can_start_live_class(doc) -> None:
	"""Authorize starting a Live Class.

	Starting is broader than the manage-only actions guarded by
	`_ensure_live_class_admin`: besides global admins, a valutatore of this
	class's batch is a host and may start their own batch's classes (but must
	not update/delete them).
	"""
	from os_lms.os_lms.valutatore import is_batch_valutatore

	roles = frappe.get_roles(frappe.session.user)
	if "Moderator" in roles or "Batch Evaluator" in roles:
		return
	if is_batch_valutatore(doc.batch_name, frappe.session.user):
		return
	frappe.throw(
		frappe._("Non hai i permessi per avviare questa lezione."),
		frappe.PermissionError,
	)


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
	doc = frappe.get_doc("LMS Live Class", name)
	_ensure_can_start_live_class(doc)

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


# ----- Live Class: internal gated join link -----

JOIN_METHOD = "os_lms.os_lms.api.join_live_class"
# Students may enter from 15 minutes before the scheduled start until the class
# ends. Keep in sync with JOIN_WINDOW_MINUTES_BEFORE in LiveClassCard.vue.
JOIN_WINDOW_MINUTES_BEFORE = 15


def get_live_class_join_url(name: str) -> str:
	"""Absolute URL of the internal gated join page for a live class.

	Points to :func:`join_live_class`, NOT the raw Zoom/Meet URL, so the meeting
	link stays out of invitation emails and access is enforced server-side.
	"""
	return frappe.utils.get_url(f"/api/method/{JOIN_METHOD}?name={quote(name)}")


def _live_class_access(doc, user: str) -> str | None:
	"""Return the access tier for ``user`` on live class ``doc``, or ``None``.

	- ``"host"`` — moderators, batch evaluators, batch instructors: enter as host
	  (``start_url``), any time before the class ends.
	- ``"observer"`` — batch valutatori: watch (``join_url``) while the class is on,
	  without waiting for the host to start it.
	- ``"student"`` — enrolled members: join (``join_url``) only inside the join
	  window AND once the host has actually started the class (``started_at``).

	Mirrors the client-side gating in LiveClassCard.vue (canStudentJoin /
	canObserverJoin / canModeratorAccessClass).
	"""
	from lms.lms.utils import is_batch_valutatore

	roles = frappe.get_roles(user)
	if "Moderator" in roles or "Batch Evaluator" in roles:
		return "host"

	if frappe.db.exists(
		"Course Instructor",
		{"parenttype": "LMS Batch", "parent": doc.batch_name, "instructor": user},
	):
		return "host"

	if frappe.db.exists("LMS Batch Enrollment", {"batch": doc.batch_name, "member": user}):
		return "student"

	if is_batch_valutatore(doc.batch_name, user):
		return "observer"

	return None


def _live_class_message(message: str, batch_url: str | None = None, color: str = "orange") -> None:
	"""Render a branded message page (used for the non-happy join states)."""
	frappe.respond_as_web_page(
		frappe._("Lezione dal vivo"),
		message,
		indicator_color=color,
		primary_action=batch_url or "/lms",
		primary_label=frappe._("Vai alla classe") if batch_url else frappe._("Vai alla piattaforma"),
	)


@frappe.whitelist(allow_guest=True)
def join_live_class(name: str) -> None:
	"""Gated entry point for a live class join link (used by emails and the SPA card).

	Authenticates the visitor, verifies they are entitled to the class (enrolled
	student, batch instructor, moderator, evaluator or valutatore) and that the
	join window is open, then redirects (302) to the correct meeting URL —
	``start_url`` for hosts, ``join_url`` for everyone else. Any non-happy state
	renders a message page instead of exposing a meeting URL.
	"""
	# Unauthenticated visitors log in first, then come back to this same link.
	if frappe.session.user == "Guest":
		redirect_to = quote(f"/api/method/{JOIN_METHOD}?name={name}", safe="")
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = f"/login?redirect-to={redirect_to}"
		return

	if not name or not frappe.db.exists("LMS Live Class", name):
		_live_class_message(frappe._("Questa lezione dal vivo non esiste o è stata rimossa."), color="red")
		return

	doc = frappe.get_doc("LMS Live Class", name)
	batch_url = frappe.utils.get_url(f"/lms/batches/{doc.batch_name}")

	tier = _live_class_access(doc, frappe.session.user)
	if tier is None:
		_live_class_message(
			frappe._("Non sei autorizzato a partecipare a questa lezione dal vivo."),
			batch_url,
			"red",
		)
		return

	class_start = frappe.utils.get_datetime(f"{doc.date} {doc.time}")
	class_end = class_start + timedelta(minutes=frappe.utils.cint(doc.duration))
	now = frappe.utils.now_datetime()

	if now > class_end:
		_live_class_message(frappe._("Questa lezione dal vivo è terminata."), batch_url)
		return

	# Enrolled students may enter only inside the join window AND once the host
	# has actually started the class (started_at). Hosts and observers are not
	# gated by started_at — the host is the one who starts the class, and
	# valutatori watch without waiting for it.
	if tier == "student":
		window_open = class_start - timedelta(minutes=JOIN_WINDOW_MINUTES_BEFORE)
		if now < window_open:
			_live_class_message(
				frappe._("La lezione non è ancora iniziata. Potrai partecipare a partire dalle {0} del {1}.").format(
					frappe.utils.format_time(doc.time, "HH:mm"),
					frappe.utils.format_date(doc.date, "dd-MM-yyyy"),
				),
				batch_url,
			)
			return
		if not doc.started_at:
			_live_class_message(
				frappe._("La lezione non è ancora stata avviata dal docente. Riprova tra qualche istante."),
				batch_url,
			)
			return

	target = (doc.start_url or doc.join_url) if tier == "host" else doc.join_url
	if not target:
		_live_class_message(
			frappe._("Il link per partecipare non è ancora disponibile. Riprova più tardi."),
			batch_url,
		)
		return

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = target


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
def resolve_vimeo_share(url: str) -> dict:
	"""
	Resolve a vimeo.com/share/<uuid> link into its canonical id/hash URLs.

	Share links carry an opaque UUID instead of the video id: they don't redirect,
	Vimeo's oEmbed API rejects them, and the page sets X-Frame-Options, so nothing
	can embed one directly. The id is only recoverable by reading the share page,
	which the browser can't do (no CORS) — hence this endpoint.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("Authentication required"), frappe.PermissionError)

	match = VIMEO_SHARE_URL_RE.match((url or "").strip())
	if not match:
		frappe.throw(frappe._("Not a Vimeo share link"), frappe.ValidationError)

	# Rebuild the URL from the matched UUID rather than fetching the caller's
	# string, so this can't be pointed at anything but a Vimeo share page.
	share_url = f"https://vimeo.com/share/{match.group(1)}"

	cache_key = f"vimeo:share:{match.group(1)}"
	cached = frappe.cache().get_value(cache_key)
	if cached:
		return cached

	try:
		response = requests.get(
			share_url,
			headers={
				"User-Agent": (
					"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
					"(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
				)
			},
			timeout=10,
		)
		response.raise_for_status()
	except requests.RequestException:
		frappe.logger("os_lms", allow_site=True).exception(f"Vimeo share fetch failed: {share_url}")
		frappe.throw(frappe._("Could not reach Vimeo to resolve this share link."))

	found = VIMEO_PLAYER_IN_PAGE_RE.search(response.text) or VIMEO_CANONICAL_IN_PAGE_RE.search(response.text)
	if not found:
		frappe.throw(frappe._("No video found behind this Vimeo share link."))

	video_id, video_hash = found.group(1), found.group(2)
	resolved = {
		"video_id": video_id,
		"video_hash": video_hash,
		# Keep both in the shape the rest of the app expects: `source` is what
		# VIMEO_URL_RE reads for audio streaming, `embed` is what Plyr plays.
		"source": f"https://vimeo.com/{video_id}/{video_hash}",
		"embed": f"https://player.vimeo.com/video/{video_id}?h={video_hash}",
	}
	frappe.cache().set_value(cache_key, resolved, expires_in_sec=60 * 60 * 24)
	return resolved


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
