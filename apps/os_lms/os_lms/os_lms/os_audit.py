# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""OS Audit: student activity audit trail (phase 1 of docs/audit-studenti/PIANO.md).

What lives here
- ``record``: the only way an event enters ``OS Audit Event``. It never raises (the
  student must never be blocked by the audit), records only what ``OS Audit
  Settings`` enables, only for courses in scope, and never without a retention
  period (PIANO D9).
- The hash chain: events are queued during the request and written by
  ``flush`` once the request transaction COMMITTED (``frappe.db.after_commit``),
  so an action that rolls back leaves no event. The write takes a MariaDB named
  lock (GET_LOCK) for a few milliseconds, numbers the events (``seq``, unique)
  and links each one to the previous (``prev_hash``/``hash``). On a GET request,
  which Frappe rolls back, ``frappe.local.flags.commit`` is set so it commits.
- Each event hashes a fingerprint of its personal fields (``content_hash``, salted
  per event) instead of the fields themselves. Erasing a user (account deletion,
  course purge) blanks those fields and the salt but keeps the fingerprint, so
  the chain stays verifiable and the data cannot be recomputed from it.
- Time in lessons: ``open_session`` (from get_lesson) and ``heartbeat`` (every
  30 s from frontend/src/oslms/composables/useOsAudit.ts). Time is computed on
  the server from the gaps between heartbeats, capped, and credited per user
  so that two open tabs never count twice.
- Jobs: ``close_stale_sessions`` (every 15 min), ``daily_seal`` and
  ``apply_retention`` (daily).

Extension points for the later phases
- Event types: the Select of ``OS Audit Event.event_type`` already lists the
  phase 2-4 types (audit_export, live_attendance, video_*, pdf_open, download).
  A new course-bound type needs an entry in ``EVENT_TOGGLES``; a type that is not
  bound to a course goes in ``UNSCOPED_EVENTS`` or ``SYSTEM_EVENTS``.
- Settings: a new per-event toggle is a Check field on ``OS Audit Settings``
  plus its default in ``TOGGLE_DEFAULTS`` (phase 3: track_videos, track_pdfs).
- ``heartbeat(events=...)`` accepts the batched client events of phase 3; it
  ignores them for now.
- ``verify_chain`` and ``can_use_os_audit`` are the gates the phase 2 page uses.
"""

import hashlib
import ipaddress
import json
import re
import secrets
from datetime import timedelta

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, format_date, get_datetime, getdate, now_datetime

SETTINGS = "OS Audit Settings"
EVENT = "OS Audit Event"
SESSION = "OS Audit Session"

# The only roles that configure, read, export and verify the audit (PIANO §8).
OS_AUDIT_ROLES = ("System Manager", "Gestore")

# Heartbeat rules (PIANO §5).
HEARTBEAT_SECONDS = 30
MIN_HEARTBEAT_GAP = 20
FULL_CREDIT_GAP = 45
CAPPED_CREDIT = 30
SESSION_GRACE_SECONDS = 120

LOCK_TIMEOUT = 10
DELETE_CHUNK = 5000
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Login events of these accounts are never recorded.
SKIP_LOGIN_USERS = {"Guest", "Administrator"}

# Per-event toggle on OS Audit Settings.
EVENT_TOGGLES = {
	"login": "track_logins",
	"logout": "track_logins",
	"login_failed": "track_logins",
	"course_view": "track_course_lesson",
	"lesson_open": "track_course_lesson",
	"lesson_complete": "track_course_lesson",
	"quiz_start": "track_quizzes",
	"quiz_submit": "track_quizzes",
	"assignment_submit": "track_assignments",
	"live_class_join": "track_live_classes",
	"scorm_open": "track_scorm",
	"certificate_issued": "track_certificates",
}
TOGGLE_DEFAULTS = {
	"track_logins": 1,
	"track_course_lesson": 1,
	"track_lesson_time": 1,
	"track_quizzes": 1,
	"track_assignments": 1,
	"track_live_classes": 1,
	"track_scorm": 1,
	"track_certificates": 1,
	"store_device": 1,
}
# Events not bound to a course: recorded for any real user while the audit is on.
UNSCOPED_EVENTS = {"login", "logout", "login_failed"}
# Events about the audit itself: written whenever a retention period is set, even
# with the audit off (a session closed after the audit was turned off still holds
# time collected while it was on).
SYSTEM_EVENTS = {"audit_settings_changed", "audit_data_erased", "daily_seal", "session_closed"}

# The event fields covered by the salted fingerprint, in canonical order. Erasure
# blanks exactly these (plus the salt).
CONTENT_FIELDS = (
	"user",
	"course",
	"lesson",
	"batch",
	"reference_doctype",
	"reference_name",
	"session",
	"device",
	"ip_address",
	"data",
)

SESSION_FIELDS = [
	"name",
	"user",
	"course",
	"lesson",
	"started_at",
	"last_seen_at",
	"last_active_at",
	"closed",
	"presence_seconds",
	"active_seconds",
	"video_seconds",
	"device",
	"ip_address",
]


# ---------------------------------------------------------------------------
# Settings and scope
# ---------------------------------------------------------------------------


def get_settings():
	return frappe.get_cached_doc(SETTINGS)


def _flag(settings, fieldname: str) -> int:
	# A Single never saved has no stored values: fall back to the field default.
	value = settings.get(fieldname)
	if value is None:
		return cint(TOGGLE_DEFAULTS.get(fieldname, 0))
	return cint(value)


def has_retention(settings) -> bool:
	return cint(settings.get("retention_days")) > 0


def is_enabled(settings=None) -> bool:
	settings = settings or get_settings()
	return bool(cint(settings.get("enabled")) and has_retention(settings))


def inactivity_seconds(settings) -> int:
	return max(cint(settings.get("inactivity_minutes")) or 3, 1) * 60


def course_in_scope(course: str | None, settings) -> bool:
	if not course:
		return False
	if settings.get("scope") == "All Courses":
		return True
	return any(row.course == course for row in settings.get("courses") or [])


def batch_in_scope(batch: str | None, settings) -> bool:
	if not batch:
		return False
	if settings.get("scope") == "All Courses":
		return True
	courses = frappe.get_all(
		"Batch Course", filters={"parent": batch, "parenttype": "LMS Batch"}, pluck="course"
	)
	return any(course_in_scope(course, settings) for course in courses)


def is_enrolled(user: str | None, course: str | None) -> bool:
	if not user or user == "Guest" or not course:
		return False
	return bool(frappe.db.exists("LMS Enrollment", {"course": course, "member": user}))


def can_use_os_audit(user: str | None = None) -> bool:
	return bool(set(OS_AUDIT_ROLES) & set(frappe.get_roles(user)))


def assert_can_use_os_audit() -> None:
	if not can_use_os_audit():
		frappe.throw(_("You are not allowed to use OS Audit."), frappe.PermissionError)


def _should_record(event_type: str, settings, course=None, batch=None) -> bool:
	if not has_retention(settings):
		return False
	if event_type in SYSTEM_EVENTS:
		return True
	if not cint(settings.get("enabled")):
		return False
	toggle = EVENT_TOGGLES.get(event_type)
	if toggle and not _flag(settings, toggle):
		return False
	if event_type in UNSCOPED_EVENTS:
		return True
	if course:
		return course_in_scope(course, settings)
	if batch:
		return batch_in_scope(batch, settings)
	return False


# ---------------------------------------------------------------------------
# Request details (device, IP)
# ---------------------------------------------------------------------------

_TABLET_UA = re.compile(r"iPad|Tablet|PlayBook|Silk|Kindle|Android(?!.*Mobile)", re.I)
_MOBILE_UA = re.compile(r"Mobi|iPhone|iPod|Android|Windows Phone", re.I)


def classify_device(user_agent: str | None) -> str | None:
	"""desktop / tablet / mobile from the User-Agent. iPadOS reports a desktop
	Safari by default, so it reads as desktop."""
	if not user_agent:
		return None
	if _TABLET_UA.search(user_agent):
		return "tablet"
	if _MOBILE_UA.search(user_agent):
		return "mobile"
	return "desktop"


def format_ip(ip: str | None, mode: str | None) -> str | None:
	if not ip or mode not in ("Truncated", "Full Address"):
		return None
	try:
		address = ipaddress.ip_address(ip.strip())
	except ValueError:
		return None
	if mode == "Full Address":
		return str(address)
	prefix = 24 if address.version == 4 else 48
	return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False).network_address)


def _request_details(settings) -> tuple[str | None, str | None]:
	request = getattr(frappe.local, "request", None)
	if not request:
		return None, None
	device = None
	if _flag(settings, "store_device"):
		device = classify_device(request.headers.get("User-Agent"))
	ip = format_ip(getattr(frappe.local, "request_ip", None), settings.get("store_ip"))
	return device, ip


def _commit_safe_request() -> None:
	# Frappe rolls back GET requests: make this one commit, so its audit rows land.
	request = getattr(frappe.local, "request", None)
	if request and request.method not in UNSAFE_METHODS:
		frappe.local.flags.commit = True


# ---------------------------------------------------------------------------
# Recorder and chain
# ---------------------------------------------------------------------------


def record(
	event_type: str,
	*,
	user: str | None = None,
	course: str | None = None,
	lesson: str | None = None,
	batch: str | None = None,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	session: str | None = None,
	data: dict | None = None,
	request_info: bool = False,
	device: str | None = None,
	ip_address: str | None = None,
	settings=None,
) -> bool:
	"""Queue one audit event for the chain. Never raises; True when queued."""
	try:
		settings = settings or get_settings()
		if not _should_record(event_type, settings, course=course, batch=batch):
			return False
		if request_info:
			device, ip_address = _request_details(settings)
		event = frappe._dict(
			event_type=event_type,
			timestamp=now_datetime(),
			user=user or None,
			course=course or None,
			lesson=lesson or None,
			batch=batch or None,
			reference_doctype=reference_doctype or None,
			reference_name=reference_name or None,
			session=session or None,
			device=device or None,
			ip_address=ip_address or None,
			data=_dump(data),
		)
		_queue(event)
		return True
	except Exception:
		frappe.log_error(title="OS Audit: event not recorded")
		return False


def _dump(data) -> str | None:
	if not data:
		return None
	return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _pending() -> list:
	pending = getattr(frappe.local, "os_audit_pending", None)
	if pending is None:
		pending = frappe.local.os_audit_pending = []
	return pending


def _queue(event) -> None:
	pending = _pending()
	if not pending:
		# A commit clears the rollback callbacks and a rollback the commit ones, so
		# they are registered again with the first event of each transaction.
		frappe.db.after_commit.add(_flush_after_commit)
		frappe.db.after_rollback.add(_discard_pending)
		_commit_safe_request()
	pending.append(event)


def _discard_pending() -> None:
	frappe.local.os_audit_pending = []


def _drop_pending(predicate) -> None:
	frappe.local.os_audit_pending = [e for e in _pending() if not predicate(e)]


def _flush_after_commit() -> None:
	flush(commit=True)


def flush(commit: bool = True) -> int:
	"""Write the queued events to the chain. Called after the request committed;
	tests call it with commit=False to stay inside their transaction."""
	pending = list(_pending())
	frappe.local.os_audit_pending = []
	if not pending:
		return 0
	locked = False
	try:
		locked = _acquire_lock()
		if not locked:
			raise RuntimeError("OS Audit chain lock not acquired")
		seq, prev_hash = chain_head()
		for event in pending:
			seq += 1
			prev_hash = _insert_event(event, seq, prev_hash)
		if commit:
			frappe.db.commit()
		return len(pending)
	except Exception:
		if commit:
			frappe.db.rollback()
		frappe.log_error(title="OS Audit: events not written")
		if commit:
			frappe.db.commit()
		return 0
	finally:
		if locked:
			_release_lock()


def _lock_name() -> str:
	# GET_LOCK names are server-wide: scope the lock to this site's database.
	return "os_audit:" + (frappe.conf.db_name or frappe.local.site or "")[:50]


def _acquire_lock() -> bool:
	return cint(frappe.db.sql("SELECT GET_LOCK(%s, %s)", (_lock_name(), LOCK_TIMEOUT))[0][0]) == 1


def _release_lock() -> None:
	try:
		frappe.db.sql("SELECT RELEASE_LOCK(%s)", (_lock_name(),))
	except Exception:
		pass


def chain_head() -> tuple[int, str]:
	"""(seq, hash) of the last event, or the retention anchor of an empty table."""
	row = frappe.db.sql(f"SELECT seq, hash FROM `tab{EVENT}` ORDER BY seq DESC LIMIT 1")
	if row:
		return cint(row[0][0]), row[0][1] or ""
	anchor_seq, anchor_hash = _anchor()
	return (anchor_seq - 1 if anchor_seq else 0), anchor_hash


def _anchor() -> tuple[int, str]:
	return (
		cint(frappe.db.get_single_value(SETTINGS, "chain_anchor_seq")),
		frappe.db.get_single_value(SETTINGS, "chain_anchor_hash") or "",
	)


def _sha256(payload: list) -> str:
	text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_time(value) -> str:
	return get_datetime(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def compute_content_hash(salt: str | None, row) -> str:
	return _sha256([salt or ""] + [row.get(field) or "" for field in CONTENT_FIELDS])


def compute_hash(prev_hash: str | None, seq: int, name: str, event_type: str, timestamp, content_hash: str) -> str:
	return _sha256([prev_hash or "", cint(seq), name, event_type, _canonical_time(timestamp), content_hash])


def _insert_event(event, seq: int, prev_hash: str) -> str:
	now = now_datetime()
	salt = secrets.token_hex(16)
	content_hash = compute_content_hash(salt, event)
	doc = frappe.new_doc(EVENT)
	doc.update(event)
	doc.name = frappe.generate_hash(length=16)
	doc.seq = seq
	doc.salt = salt
	doc.content_hash = content_hash
	doc.prev_hash = prev_hash or None
	doc.hash = compute_hash(prev_hash, seq, doc.name, event.event_type, event.timestamp, content_hash)
	doc.redacted = 0
	doc.owner = doc.modified_by = frappe.session.user or "Administrator"
	doc.creation = doc.modified = now
	doc.db_insert()
	return doc.hash


@frappe.whitelist()
def verify_chain() -> dict:
	"""Recompute the whole chain. For the phase 2 "Verify integrity" button."""
	assert_can_use_os_audit()
	return verify()


def verify(batch_size: int = 2000) -> dict:
	"""Recompute the chain in order: {"ok": True, ...} or the first event that is
	missing, altered or no longer linked to the previous one."""
	anchor_seq, anchor_hash = _anchor()
	expected = anchor_seq or 1
	prev_hash = anchor_hash if anchor_seq else ""
	last_seq = 0
	checked = 0
	columns = ", ".join(
		f"`{c}`"
		for c in (
			"name",
			"seq",
			"event_type",
			"timestamp",
			*CONTENT_FIELDS,
			"salt",
			"content_hash",
			"prev_hash",
			"hash",
			"redacted",
		)
	)
	while True:
		rows = frappe.db.sql(
			f"SELECT {columns} FROM `tab{EVENT}` WHERE seq > %s ORDER BY seq LIMIT %s",
			(last_seq, batch_size),
			as_dict=True,
		)
		if not rows:
			break
		for row in rows:
			problem = None
			if cint(row.seq) != expected:
				problem = "missing"
			elif (row.prev_hash or "") != prev_hash:
				problem = "broken_link"
			elif cint(row.redacted):
				if row.salt or any(row.get(field) for field in CONTENT_FIELDS):
					problem = "altered"
			elif compute_content_hash(row.salt, row) != row.content_hash:
				problem = "altered"
			if not problem and compute_hash(
				row.prev_hash, row.seq, row.name, row.event_type, row.timestamp, row.content_hash
			) != row.hash:
				problem = "altered"
			if problem:
				return {
					"ok": False,
					"checked": checked,
					"reason": problem,
					"seq": cint(row.seq),
					"expected_seq": expected,
					"event": row.name,
				}
			prev_hash = row.hash
			expected += 1
			checked += 1
			last_seq = cint(row.seq)
	return {"ok": True, "checked": checked, "last_seq": last_seq or None, "last_hash": prev_hash or None}


# ---------------------------------------------------------------------------
# Lesson sessions and heartbeat
# ---------------------------------------------------------------------------


def on_lesson_open(course: str, lesson: str) -> dict | None:
	"""get_lesson hook: record lesson_open and open the time session. Returns what
	the page needs to send heartbeats, or None when nothing is tracked."""
	try:
		user = frappe.session.user
		settings = get_settings()
		if not is_enabled(settings) or not course_in_scope(course, settings) or not is_enrolled(user, course):
			return None
		session = None
		if _flag(settings, "track_lesson_time"):
			session = open_session(user, course, lesson, settings)
		record(
			"lesson_open",
			user=user,
			course=course,
			lesson=lesson,
			session=session,
			request_info=True,
			settings=settings,
		)
		if not session:
			return None
		return {
			"session": session,
			"heartbeat_seconds": HEARTBEAT_SECONDS,
			"inactivity_minutes": inactivity_seconds(settings) // 60,
		}
	except Exception:
		frappe.log_error(title="OS Audit: lesson open not recorded")
		return None


def open_session(user: str, course: str, lesson: str, settings=None) -> str:
	settings = settings or get_settings()
	now = now_datetime()
	close_stale_sessions(user=user, settings=settings, now=now)
	device, ip_address = _request_details(settings)
	doc = frappe.new_doc(SESSION)
	doc.update(
		{
			"user": user,
			"course": course,
			"lesson": lesson,
			"started_at": now,
			"last_seen_at": now,
			"closed": 0,
			"presence_seconds": 0,
			"active_seconds": 0,
			"video_seconds": 0,
			"device": device,
			"ip_address": ip_address,
		}
	)
	doc.name = frappe.generate_hash(length=16)
	doc.owner = doc.modified_by = user
	doc.creation = doc.modified = now
	doc.db_insert()
	_commit_safe_request()
	return doc.name


def _session_row(name: str, for_update: bool = False):
	return frappe.db.get_value(SESSION, name, SESSION_FIELDS, as_dict=True, for_update=for_update)


@frappe.whitelist(methods=["POST"])
# Per IP and session: a class behind one office NAT must not share a single budget.
@rate_limit(key="session", limit=300, seconds=60 * 60)
def heartbeat(session: str, active: bool = False, events: list | None = None, close: bool = False) -> dict:
	"""Periodic "still here" signal of a lesson page (PIANO §5).

	Answers {"session": name} with the session to keep using (a new one after a
	long gap), or {"stop": 1} when the page should stop sending. ``events`` is
	reserved for the batched client events of phase 3 and ignored for now.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Log in to continue."), frappe.PermissionError)
	row = _session_row(session, for_update=True) if isinstance(session, str) else None
	if not row or row.user != user:
		frappe.throw(_("This audit session does not belong to you."), frappe.PermissionError)

	settings = get_settings()
	if not is_enabled(settings) or not _flag(settings, "track_lesson_time"):
		if not cint(row.closed):
			close_session(row.name, "audit_disabled")
		return {"stop": 1}

	now = now_datetime()
	if cint(row.closed):
		return {"stop": 1} if close else _reopen(row, settings)

	delta = (now - get_datetime(row.last_seen_at)).total_seconds()
	if delta > inactivity_seconds(settings) + SESSION_GRACE_SECONDS:
		close_session(row.name, "timeout")
		return {"stop": 1} if close else _reopen(row, settings)

	if delta >= MIN_HEARTBEAT_GAP or close:
		presence, active_seconds = credit_seconds(row, now, bool(active), delta)
		frappe.db.sql(
			f"""
			UPDATE `tab{SESSION}`
			SET last_seen_at = %(now)s,
				presence_seconds = presence_seconds + %(presence)s,
				active_seconds = active_seconds + %(active_seconds)s,
				last_active_at = IF(%(active)s, %(now)s, last_active_at)
			WHERE name = %(name)s AND closed = 0
			""",
			{
				"now": now,
				"presence": presence,
				"active_seconds": active_seconds,
				"active": 1 if active else 0,
				"name": row.name,
			},
		)
	if close:
		close_session(row.name, "page_closed")
		return {"stop": 1}
	return {"session": row.name}


def credit_seconds(row, now, active: bool, delta: float) -> tuple[int, int]:
	"""Seconds this heartbeat adds to presence and active time.

	The window starts at this session's previous heartbeat, or later if another
	open session of the same user was credited after it: time already credited to
	another tab is never credited again. A gap up to FULL_CREDIT_GAP counts in
	full; a longer one counts CAPPED_CREDIT at most.
	"""
	cap = delta if delta <= FULL_CREDIT_GAP else CAPPED_CREDIT
	# A session that never had a heartbeat has last_seen_at == started_at and was
	# credited nothing: it does not cover any time yet.
	other_seen, other_active = frappe.db.sql(
		f"""
		SELECT MAX(CASE WHEN last_seen_at > started_at THEN last_seen_at END), MAX(last_active_at)
		FROM `tab{SESSION}`
		WHERE user = %s AND closed = 0 AND name != %s
		""",
		(row.user, row.name),
	)[0]
	own = get_datetime(row.last_seen_at)
	presence = _window(now, own, other_seen, cap)
	active_seconds = _window(now, own, other_active, cap) if active else 0
	return presence, active_seconds


def _window(now, own, other, cap: float) -> int:
	start = max(own, get_datetime(other)) if other else own
	return int(max(0, min((now - start).total_seconds(), cap)))


def _reopen(row, settings) -> dict:
	# The page is still open after a long pause: go on in a new session, as long as
	# the student is still enrolled and the course still audited.
	if not course_in_scope(row.course, settings) or not is_enrolled(row.user, row.course):
		return {"stop": 1}
	return {"session": open_session(row.user, row.course, row.lesson, settings)}


def close_session(name: str, reason: str) -> bool:
	"""Close an open session once and write its totals in a session_closed event."""
	row = _session_row(name, for_update=True)
	if not row or cint(row.closed):
		return False
	frappe.db.sql(f"UPDATE `tab{SESSION}` SET closed = 1 WHERE name = %s", (name,))
	record(
		"session_closed",
		user=row.user,
		course=row.course,
		lesson=row.lesson,
		session=row.name,
		device=row.device,
		ip_address=row.ip_address,
		data={
			"reason": reason,
			"started_at": row.started_at,
			"ended_at": row.last_seen_at,
			"presence_seconds": cint(row.presence_seconds),
			"active_seconds": cint(row.active_seconds),
			"video_seconds": cint(row.video_seconds),
		},
	)
	return True


def close_stale_sessions(user: str | None = None, settings=None, now=None) -> int:
	"""Close the sessions with no heartbeat for longer than the inactivity
	threshold plus the grace period. Scheduled every 15 minutes; also run for one
	user when they open a new session."""
	settings = settings or get_settings()
	now = now or now_datetime()
	cutoff = now - timedelta(seconds=inactivity_seconds(settings) + SESSION_GRACE_SECONDS)
	filters = {"closed": 0, "last_seen_at": ["<", cutoff]}
	if user:
		filters["user"] = user
	names = frappe.get_all(SESSION, filters=filters, pluck="name", limit=DELETE_CHUNK)
	return sum(1 for name in names if close_session(name, "timeout"))


# ---------------------------------------------------------------------------
# Server events
# ---------------------------------------------------------------------------


def _student_event(event_type: str, user: str, course: str, **fields) -> None:
	"""A course event of an enrolled student; device and IP only when the student
	is the one making the request."""
	try:
		if not is_enrolled(user, course):
			return
		record(
			event_type,
			user=user,
			course=course,
			request_info=frappe.session.user == user,
			**fields,
		)
	except Exception:
		frappe.log_error(title=f"OS Audit: {event_type} not recorded")


def on_course_view(course: str) -> None:
	"""get_course_details hook."""
	_student_event("course_view", frappe.session.user, course)


def on_scorm_open(playback: dict) -> None:
	"""get_scorm_playback hook: only a playable package counts as opened."""
	if not isinstance(playback, dict) or not playback.get("launch_file"):
		return
	_student_event(
		"scorm_open",
		frappe.session.user,
		playback.get("course"),
		lesson=playback.get("lesson"),
		reference_doctype="Course Chapter",
		reference_name=playback.get("chapter"),
	)


def on_scorm_progress_update(lesson: str, course: str) -> None:
	"""save_progress hook for the SCORM path that updates an existing progress
	row with db.set_value, which fires no document hook."""
	user = frappe.session.user
	name = frappe.db.get_value("LMS Course Progress", {"lesson": lesson, "member": user, "status": "Complete"})
	if name:
		_student_event(
			"lesson_complete",
			user,
			course,
			lesson=lesson,
			reference_doctype="LMS Course Progress",
			reference_name=name,
		)


def on_course_progress_insert(doc, method=None) -> None:
	if doc.status == "Complete":
		_student_event(
			"lesson_complete",
			doc.member,
			doc.course,
			lesson=doc.lesson,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)


def on_quiz_submission_insert(doc, method=None) -> None:
	try:
		quiz = frappe.db.get_value("LMS Quiz", doc.quiz, ["course", "lesson"], as_dict=True) or {}
		course = doc.get("course") or quiz.get("course")
		duration = quiz_duration_seconds(doc.member, doc.quiz, doc.name, doc.creation)
		_student_event(
			"quiz_submit",
			doc.member,
			course,
			lesson=quiz.get("lesson"),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			data={
				"quiz": doc.quiz,
				"score": doc.get("score"),
				"score_out_of": doc.get("score_out_of"),
				"percentage": doc.get("percentage"),
				"passing_percentage": doc.get("passing_percentage"),
				"duration_seconds": duration,
			},
		)
	except Exception:
		frappe.log_error(title="OS Audit: quiz_submit not recorded")


def quiz_duration_seconds(member: str, quiz: str, submission: str, submitted_at) -> int | None:
	"""Seconds from the last quiz_start of this attempt to the submission, both
	server timestamps. None when the start was not recorded."""
	submitted_at = get_datetime(submitted_at or now_datetime())
	filters = [
		["event_type", "=", "quiz_start"],
		["user", "=", member],
		["reference_name", "=", quiz],
		["timestamp", "<=", submitted_at],
	]
	previous = frappe.db.get_value(
		"LMS Quiz Submission",
		{"member": member, "quiz": quiz, "name": ["!=", submission], "creation": ["<", submitted_at]},
		"creation",
		order_by="creation desc",
	)
	if previous:
		filters.append(["timestamp", ">", previous])
	started = frappe.get_all(EVENT, filters=filters, pluck="timestamp", order_by="seq desc", limit=1)
	if not started:
		return None
	return max(0, int((submitted_at - get_datetime(started[0])).total_seconds()))


@frappe.whitelist(methods=["POST"])
@rate_limit(key="quiz", limit=60, seconds=60 * 60)
def quiz_start(quiz: str) -> None:
	"""The quiz page calls this when the student starts an attempt."""
	try:
		row = frappe.db.get_value("LMS Quiz", quiz, ["name", "course", "lesson"], as_dict=True)
		if row:
			_student_event(
				"quiz_start",
				frappe.session.user,
				row.course,
				lesson=row.lesson,
				reference_doctype="LMS Quiz",
				reference_name=row.name,
			)
	except Exception:
		frappe.log_error(title="OS Audit: quiz_start not recorded")


def on_assignment_submission_insert(doc, method=None) -> None:
	_student_event(
		"assignment_submit",
		doc.member,
		doc.course,
		lesson=doc.get("lesson"),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		data={"assignment": doc.get("assignment"), "type": doc.get("type")},
	)


def on_certificate_insert(doc, method=None) -> None:
	try:
		user = doc.member
		data = {"issue_date": doc.get("issue_date"), "template": doc.get("template")}
		if doc.get("course"):
			_student_event(
				"certificate_issued",
				user,
				doc.course,
				batch=doc.get("batch_name"),
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				data=data,
			)
		elif doc.get("batch_name") and frappe.db.exists(
			"LMS Batch Enrollment", {"batch": doc.batch_name, "member": user}
		):
			record(
				"certificate_issued",
				user=user,
				batch=doc.batch_name,
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				data=data,
				request_info=frappe.session.user == user,
			)
	except Exception:
		frappe.log_error(title="OS Audit: certificate_issued not recorded")


def on_live_class_join(doc, user: str) -> None:
	"""join_live_class hook, right before the redirect to the meeting. The user may
	be the holder of a signed link on a guest request: they are the ones clicking."""
	try:
		record(
			"live_class_join",
			user=user,
			batch=doc.get("batch_name"),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			data={"host": 1 if user == doc.get("host") else 0},
			request_info=True,
		)
	except Exception:
		frappe.log_error(title="OS Audit: live_class_join not recorded")


def on_activity_log_insert(doc) -> None:
	"""Activity Log hook (access_tracking): login, logout and failed logins."""
	try:
		event_type = None
		if doc.operation == "Login":
			event_type = {"Success": "login", "Failed": "login_failed"}.get(doc.status)
		elif doc.operation == "Logout":
			event_type = "logout"
		user = doc.user
		if not event_type or not user or user in SKIP_LOGIN_USERS:
			return
		if not frappe.db.exists("User", user):
			return
		record(event_type, user=user, request_info=True)
	except Exception:
		frappe.log_error(title="OS Audit: access event not recorded")


# ---------------------------------------------------------------------------
# Settings changes
# ---------------------------------------------------------------------------

_LAYOUT_TYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading"}


def on_settings_update(doc) -> None:
	"""OS Audit Settings.on_update: write who changed what, while the audit is or
	was enabled (turning it on and off included)."""
	try:
		before = doc.get_doc_before_save()
		if not (cint(doc.enabled) or (before and cint(before.enabled))):
			return
		changes = settings_changes(before, doc)
		if changes:
			record(
				"audit_settings_changed",
				user=frappe.session.user,
				data={"changes": changes},
				request_info=True,
				settings=doc,
			)
	except Exception:
		frappe.log_error(title="OS Audit: settings change not recorded")


def settings_changes(before, after) -> dict:
	from os_lms.os_lms.doctype.os_audit_settings.os_audit_settings import INTERNAL_FIELDS

	changes = {}
	for df in after.meta.fields:
		if df.fieldtype in _LAYOUT_TYPES or df.fieldname in INTERNAL_FIELDS:
			continue
		if df.fieldtype == "Table":
			old = _course_rows(before.get(df.fieldname) if before else [])
			new = _course_rows(after.get(df.fieldname))
		else:
			old = before.get(df.fieldname) if before else None
			new = after.get(df.fieldname)
			old, new = _plain(old), _plain(new)
		if old != new:
			changes[df.fieldname] = [old, new]
	return changes


def _plain(value):
	if value in (None, ""):
		return None
	if isinstance(value, (int, float)):
		return value
	return str(value)


def _course_rows(rows) -> list:
	return sorted(
		[row.course, row.planned_hours or 0, row.min_attendance_percent or 0] for row in rows or []
	)


# ---------------------------------------------------------------------------
# Daily seal and retention
# ---------------------------------------------------------------------------


def daily_seal() -> None:
	"""Daily job: seal the previous day with its event count and the chain head;
	optionally email the seal so a copy exists outside the platform."""
	settings = frappe.get_single(SETTINGS)
	if not has_retention(settings):
		return
	day = add_days(getdate(), -1)
	start = get_datetime(day)
	end = start + timedelta(days=1)
	if _seal_exists(day):
		return
	count = frappe.db.sql(
		f"""SELECT COUNT(*) FROM `tab{EVENT}`
		WHERE timestamp >= %s AND timestamp < %s AND event_type != 'daily_seal'""",
		(start, end),
	)[0][0]
	if not cint(settings.enabled) and not count:
		return
	last_seq, last_hash = chain_head()
	data = {"date": str(day), "events": cint(count), "last_seq": last_seq, "last_hash": last_hash}
	if record("daily_seal", user="Administrator", data=data, settings=settings) and settings.seal_email:
		_email_seal(settings.seal_email, day, data)


def _seal_exists(day) -> bool:
	return bool(
		frappe.db.exists(EVENT, {"event_type": "daily_seal", "data": ["like", f'%"date":"{day}"%']})
	)


def _email_seal(recipient: str, day, data: dict) -> None:
	try:
		rows = "".join(
			f"<tr><td style='padding:4px 12px 4px 0'>{frappe.utils.escape_html(label)}</td>"
			f"<td style='font-family:monospace'>{frappe.utils.escape_html(str(value))}</td></tr>"
			for label, value in (
				(_("Date"), format_date(day)),
				(_("Events recorded"), data["events"]),
				(_("Last sequence number"), data["last_seq"]),
				(_("Last hash"), data["last_hash"]),
			)
		)
		message = (
			"<p>"
			+ _("Keep this email: it lets you show later that the audit data up to this day was not altered.")
			+ f"</p><table>{rows}</table>"
		)
		frappe.sendmail(
			recipients=[recipient],
			subject=_("OS Audit daily seal of {0}").format(format_date(day)),
			message=message,
		)
	except Exception:
		frappe.log_error(title="OS Audit: daily seal email not sent")


def apply_retention() -> dict:
	"""Daily job: delete events and sessions older than the retention period.

	Events go as a prefix of the chain; the sequence number and previous hash the
	oldest kept event must carry are stored on the settings (the anchor), so the
	chain stays verifiable from there.
	"""
	days = cint(frappe.db.get_single_value(SETTINGS, "retention_days"))
	if days <= 0:
		return {"events": 0, "sessions": 0}
	cutoff = get_datetime(add_days(now_datetime(), -days))
	deleted = 0
	locked = _acquire_lock()
	try:
		if not locked:
			raise RuntimeError("OS Audit chain lock not acquired")
		last = frappe.db.sql(f"SELECT MAX(seq) FROM `tab{EVENT}` WHERE timestamp < %s", (cutoff,))[0][0]
		if last:
			last_hash = frappe.db.get_value(EVENT, {"seq": last}, "hash")
			frappe.db.set_single_value(
				SETTINGS, {"chain_anchor_seq": cint(last) + 1, "chain_anchor_hash": last_hash}
			)
			while True:
				names = frappe.db.sql_list(
					f"SELECT name FROM `tab{EVENT}` WHERE seq <= %s ORDER BY seq LIMIT %s",
					(last, DELETE_CHUNK),
				)
				if not names:
					break
				frappe.db.delete(EVENT, {"name": ["in", names]})
				deleted += len(names)
	finally:
		if locked:
			_release_lock()
	sessions = frappe.db.count(SESSION, {"last_seen_at": ["<", cutoff]})
	if sessions:
		frappe.db.delete(SESSION, {"last_seen_at": ["<", cutoff]})
	return {"events": deleted, "sessions": sessions}


# ---------------------------------------------------------------------------
# Erasure (account deletion, course purge)
# ---------------------------------------------------------------------------


def keeps_data_on_deletion(settings=None) -> bool:
	settings = settings or frappe.get_single(SETTINGS)
	return settings.get("on_account_deletion") == "Keep Until Expiry"


def erase_user_data(user: str) -> int:
	"""account_deletion.erase_user: erase the user's audit data unless the settings
	keep it until expiry. Returns the number of events erased."""
	if keeps_data_on_deletion():
		return 0
	_drop_pending(lambda event: event.user == user)
	frappe.db.delete(SESSION, {"user": user})
	erased = _redact({"user": user})
	if erased:
		record("audit_data_erased", data={"reason": "account_deletion", "events": erased})
	return erased


def erase_course_member(course: str, member: str) -> int:
	"""course_students purge: same rule as the account deletion, for one course."""
	if keeps_data_on_deletion():
		return 0
	_drop_pending(lambda event: event.user == member and event.course == course)
	frappe.db.delete(SESSION, {"user": member, "course": course})
	erased = _redact({"user": member, "course": course})
	if erased:
		record("audit_data_erased", data={"reason": "course_purge", "course": course, "events": erased})
	return erased


def _redact(filters: dict) -> int:
	names = frappe.get_all(EVENT, filters={**filters, "redacted": 0}, pluck="name")
	for start in range(0, len(names), DELETE_CHUNK):
		chunk = names[start : start + DELETE_CHUNK]
		frappe.db.sql(
			f"""UPDATE `tab{EVENT}` SET redacted = 1, salt = NULL, user = NULL, course = NULL,
				lesson = NULL, batch = NULL, reference_doctype = NULL, reference_name = NULL,
				session = NULL, device = NULL, ip_address = NULL, data = NULL
			WHERE name IN %s""",
			(tuple(chunk),),
		)
	return len(names)
