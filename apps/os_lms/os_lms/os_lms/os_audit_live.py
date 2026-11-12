# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""OS Audit phase 4: real attendance of the live classes (docs/audit-studenti/fase-4-analisi.md).

Flow
- ``read_due_live_classes`` (every 15 min) picks the live classes of the batches in
  the audit scope that ended at least READ_DELAY ago and at most READ_WINDOW_DAYS
  ago (Google deletes the Meet conference records after 30 days) and reads, one
  class at a time and each in its own try, the participants the provider reports:
  Zoom ``past_meetings`` (every instance of the meeting, paginated) or the Google
  Meet REST API (conference records, participants, participant sessions).
- Every segment (join, leave) becomes an ``OS Live Attendance`` row, matched to a
  platform user when possible: the Zoom host account (the teacher), an identity
  matched before (``OS Live Identity``), the email, or a display name equal to
  the name of exactly one person of the class. The rest waits for the Gestore,
  who matches it from the OS Audit page or marks it as an external guest.
- The chain receives a ``live_attendance_read`` per class (counts and a SHA-256
  fingerprint of the rows read, no personal data) and a ``live_attendance`` per
  matched person (first entry, last exit, seconds, segments, how they were
  matched). A manual match writes another ``live_attendance`` naming who did it.
- Matched people are also written to upstream's ``LMS Live Class Participant``
  (duration in minutes, as upstream expects), which lights up the attendance
  dialog of the batch page.

Upstream ships an hourly reader (``update_attendance``) that throws on the first
meeting never held and so never read any class: ``stop_upstream_attendance_job``
(after_migrate) stops it; this module replaces it.

Nothing here may block a student: the readers run in the scheduler, and every
class is read inside its own try.
"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import cint, convert_utc_to_system_timezone, get_datetime, now_datetime

from os_lms.os_lms import os_audit
from os_lms.os_lms.google_calendar import MEET_SCOPE
from os_lms.os_lms.live_class_join import class_end

ATTENDANCE = "OS Live Attendance"
IDENTITY = "OS Live Identity"
READ = "OS Live Class Read"
LIVE_CLASS = "LMS Live Class"
PARTICIPANT = "LMS Live Class Participant"

ZOOM = "Zoom"
MEET = "Google Meet"

UPSTREAM_ATTENDANCE_JOB = "lms.lms.doctype.lms_live_class.lms_live_class.update_attendance"

# The provider reports are complete a few minutes after the meeting ends.
READ_DELAY = timedelta(minutes=30)
# Google deletes a conference record 30 days after the meeting: the same window for Zoom.
READ_WINDOW_DAYS = 30
# A class with no meeting instance this long after its end was not held.
NOT_HELD_AFTER = timedelta(hours=48)
# A class whose read failed is tried again at most this often.
ERROR_RETRY = timedelta(hours=1)
# Meeting segments outside this window around the class belong to another use of the room.
WINDOW_BEFORE = timedelta(hours=3)
WINDOW_AFTER = timedelta(hours=6)
# At most this many segments are copied into a live_attendance event.
MAX_EVENT_SEGMENTS = 20
HTTP_TIMEOUT = 15

ZOOM_API = "https://api.zoom.us/v2"
ZOOM_PAGE_SIZE = 300
# Zoom codes for a meeting (instance) that does not exist or has no report yet.
ZOOM_MISSING_CODES = {3001, 3301, 1001}

MEET_API = "https://meet.googleapis.com/v2"
MEET_PAGE_SIZE = 250
MEET_CODE = re.compile(r"meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})", re.I)

STATUS_PENDING = "Pending"
STATUS_READ = "Read"
STATUS_NOT_HELD = "Not Held"
STATUS_ERROR = "Error"

# matched_by values a reread keeps (the provider data cannot rebuild them).
MANUAL_MATCHES = ("manual", "guest")

ROW_FIELDS = [
	"name",
	"live_class",
	"provider",
	"instance",
	"external_id",
	"display_name",
	"email",
	"joined_at",
	"left_at",
	"seconds",
	"user",
	"is_host",
	"matched_by",
	"matched_by_user",
	"matched_at",
]
LIVE_FIELDS = [
	"name",
	"title",
	"date",
	"time",
	"duration",
	"host",
	"batch_name",
	"conferencing_provider",
	"zoom_account",
	"google_meet_account",
	"meeting_id",
	"uuid",
	"join_url",
]


class ProviderError(Exception):
	"""The provider refused or failed: the class is marked Error with this message."""


class NotHeld(Exception):
	"""The provider has no meeting instance for the class (yet)."""


# ---------------------------------------------------------------------------
# Upstream job
# ---------------------------------------------------------------------------


def stop_upstream_attendance_job() -> None:
	"""after_migrate: stop upstream's hourly Zoom reader. Frappe's job sync only
	updates frequency and cron of an existing Scheduled Job Type, so the flag stays."""
	name = frappe.db.get_value("Scheduled Job Type", {"method": UPSTREAM_ATTENDANCE_JOB}, "name")
	if name and not cint(frappe.db.get_value("Scheduled Job Type", name, "stopped")):
		frappe.db.set_value("Scheduled Job Type", name, "stopped", 1, update_modified=False)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


def provider_of(live) -> str | None:
	if live.get("conferencing_provider") == MEET:
		return MEET
	if live.get("zoom_account"):
		return ZOOM
	return None


def class_start(live) -> datetime:
	return get_datetime(f"{live.date} {live.time}")


def tracking_on(settings=None) -> bool:
	settings = settings or os_audit.get_settings()
	return os_audit.is_enabled(settings) and bool(os_audit._flag(settings, "track_live_classes"))


def in_scope(live, settings=None) -> bool:
	"""Live attendance is collected only with the audit and its live toggle on, for a
	batch that contains a course in scope (PIANO principle 7)."""
	settings = settings or os_audit.get_settings()
	return tracking_on(settings) and os_audit.batch_in_scope(live.get("batch_name"), settings)


def due_live_classes(now=None, settings=None) -> list[str]:
	"""Names of the ended live classes whose attendance is still to read."""
	now = now or now_datetime()
	settings = settings or os_audit.get_settings()
	classes = frappe.get_all(
		LIVE_CLASS,
		filters={"date": ["between", [(now - timedelta(days=READ_WINDOW_DAYS + 1)).date(), now.date()]]},
		fields=LIVE_FIELDS,
		order_by="date asc, time asc",
	)
	if not classes:
		return []
	reads = {
		r.name: r
		for r in frappe.get_all(
			READ, filters={"name": ["in", [c.name for c in classes]]}, fields=["name", "status", "modified"]
		)
	}
	due = []
	for live in classes:
		if not provider_of(live):
			continue
		end = class_end(live)
		if now < end + READ_DELAY or now > end + timedelta(days=READ_WINDOW_DAYS):
			continue
		read = reads.get(live.name)
		if read and read.status in (STATUS_READ, STATUS_NOT_HELD):
			continue
		if read and read.status == STATUS_ERROR and get_datetime(read.modified) > now - ERROR_RETRY:
			continue
		if not os_audit.batch_in_scope(live.batch_name, settings):
			continue
		due.append(live.name)
	return due


def read_due_live_classes() -> int:
	"""Scheduler (every 15 min): read every due class. Returns how many were read."""
	settings = os_audit.get_settings()
	if not tracking_on(settings):
		return 0
	done = 0
	for name in due_live_classes(settings=settings):
		if read_live_class(name) == STATUS_READ:
			done += 1
	return done


def read_live_class(name: str, force: bool = False) -> str | None:
	"""Read one class from its provider; returns the resulting status. Never raises."""
	if not _acquire_class_lock(name):
		return None
	try:
		return _read_live_class(name, force)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"OS Audit: live attendance of {name} not read")
		_set_status(name, None, STATUS_ERROR, error=_("Unexpected error: see the Error Log."))
		frappe.db.commit()
		return STATUS_ERROR
	finally:
		_release_class_lock(name)


def _read_live_class(name: str, force: bool) -> str | None:
	live = frappe.db.get_value(LIVE_CLASS, name, LIVE_FIELDS, as_dict=True)
	if not live:
		return None
	provider = provider_of(live)
	if not provider or not in_scope(live):
		return None
	status = frappe.db.get_value(READ, name, "status")
	if status in (STATUS_READ, STATUS_NOT_HELD) and not force:
		return status
	now = now_datetime()
	try:
		segments = read_zoom(live) if provider == ZOOM else read_meet(live)
	except NotHeld:
		# The report may still be on its way; past NOT_HELD_AFTER the class was not held.
		waiting = now <= class_end(live) + NOT_HELD_AFTER
		result = STATUS_PENDING if waiting else STATUS_NOT_HELD
		_set_status(name, provider, result, error=None)
		frappe.db.commit()
		return result
	except ProviderError as e:
		_set_status(name, provider, STATUS_ERROR, error=str(e)[:1000])
		frappe.db.commit()
		return STATUS_ERROR

	start, end = class_start(live), class_end(live)
	segments = [s for s in segments if s["left_at"] >= start - WINDOW_BEFORE and s["joined_at"] <= end + WINDOW_AFTER]
	kept = _manual_matches(name) if force else {}
	frappe.db.delete(ATTENDANCE, {"live_class": name})
	rows = [_insert_row(live, provider, segment) for segment in segments]
	for row in rows:
		previous = kept.get(group_key(row))
		if previous:
			_update_row(row, **previous)
	match_rows(live, rows)
	_record_read(live, provider, rows, reread=force)
	for user in sorted({row.user for row in rows if row.user}):
		record_attendance(live, user, rows, reread=force)
	sync_participants(live, rows)
	matched = sum(1 for row in rows if row.user)
	unmatched = sum(1 for row in rows if not row.user and row.matched_by != "guest")
	_set_status(name, provider, STATUS_READ, error=None, rows=len(rows), matched=matched, unmatched=unmatched)
	frappe.db.commit()
	return STATUS_READ


def _class_lock(name: str) -> str:
	return f"os_live_read_{frappe.local.site}_{name}"[:64]


def _acquire_class_lock(name: str) -> bool:
	return bool(frappe.db.sql("SELECT GET_LOCK(%s, 0)", (_class_lock(name),))[0][0])


def _release_class_lock(name: str) -> None:
	try:
		frappe.db.sql("SELECT RELEASE_LOCK(%s)", (_class_lock(name),))
	except Exception:
		pass


def _set_status(name: str, provider: str | None, status: str, error=None, **counts) -> None:
	now = now_datetime()
	if frappe.db.exists(READ, name):
		values = {"status": status, "error": error, "modified": now, **counts}
		if provider:
			values["provider"] = provider
		if status != STATUS_PENDING or error:
			values["read_at"] = now
		frappe.db.sql(
			f"UPDATE `tab{READ}` SET attempts = attempts + 1 WHERE name = %s",
			(name,),
		)
		frappe.db.set_value(READ, name, values, update_modified=False)
		return
	doc = frappe.new_doc(READ)
	doc.update(
		{
			"live_class": name,
			"provider": provider,
			"status": status,
			"error": error,
			"attempts": 1,
			"read_at": now,
			**counts,
		}
	)
	doc.name = name
	doc.owner = doc.modified_by = "Administrator"
	doc.creation = doc.modified = now
	doc.db_insert()


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------


def zoom_uuid_path(uuid: str) -> str:
	"""Zoom wants a meeting UUID that starts with "/" or contains "//" encoded twice."""
	encoded = quote(uuid, safe="")
	if uuid.startswith("/") or "//" in uuid:
		encoded = quote(encoded, safe="")
	return encoded


def zoom_token(account: str) -> str:
	from lms.lms.doctype.lms_batch.lms_batch import authenticate

	try:
		token = authenticate(account)
	except Exception as e:
		raise ProviderError(_("Zoom account {0}: {1}").format(account, _plain_message(e))) from e
	if not token:
		raise ProviderError(_("Zoom account {0}: no access token.").format(account))
	return token


def zoom_get(path: str, token: str, params: dict | None = None) -> dict:
	"""GET on the Zoom API. NotHeld when the meeting (instance) does not exist."""
	try:
		response = requests.get(
			ZOOM_API + path,
			headers={"Authorization": f"Bearer {token}"},
			params=params,
			timeout=HTTP_TIMEOUT,
		)
	except requests.RequestException as e:
		raise ProviderError(_("Zoom did not answer: {0}").format(e)) from e
	try:
		body = response.json()
	except ValueError:
		body = {}
	if response.status_code == 200:
		return body
	if response.status_code == 404 or cint(body.get("code")) in ZOOM_MISSING_CODES:
		raise NotHeld()
	raise ProviderError(
		_("Zoom answered {0}: {1}").format(response.status_code, body.get("message") or response.text[:300])
	)


def zoom_host_identity(live, token: str, cache: dict) -> dict:
	"""Email and id of the Zoom user that owns the meeting (the account's user)."""
	key = live.zoom_account
	if key not in cache:
		try:
			me = zoom_get("/users/me", token)
		except (NotHeld, ProviderError):
			me = {}
		cache[key] = {"email": (me.get("email") or "").lower(), "id": me.get("id") or ""}
	return cache[key]


def read_zoom(live) -> list[dict]:
	"""Every participant segment of every instance of the class meeting."""
	token = zoom_token(live.zoom_account)
	uuids = []
	if live.meeting_id:
		try:
			instances = zoom_get(f"/past_meetings/{quote(str(live.meeting_id), safe='')}/instances", token)
			uuids.extend(m.get("uuid") for m in instances.get("meetings") or [] if m.get("uuid"))
		except NotHeld:
			pass
	if live.uuid and live.uuid not in uuids:
		uuids.append(live.uuid)
	host = zoom_host_identity(live, token, {})
	segments = []
	found = False
	for uuid in uuids:
		try:
			participants = zoom_participants(uuid, token)
		except NotHeld:
			continue
		found = True
		for p in participants:
			segment = zoom_segment(uuid, p, host)
			if segment:
				segments.append(segment)
	if not found:
		raise NotHeld()
	return segments


def zoom_participants(uuid: str, token: str) -> list[dict]:
	participants, page_token = [], None
	while True:
		params = {"page_size": ZOOM_PAGE_SIZE}
		if page_token:
			params["next_page_token"] = page_token
		body = zoom_get(f"/past_meetings/{zoom_uuid_path(uuid)}/participants", token, params)
		participants.extend(body.get("participants") or [])
		page_token = body.get("next_page_token")
		if not page_token:
			return participants


def zoom_segment(uuid: str, p: dict, host: dict) -> dict | None:
	joined, left = parse_utc(p.get("join_time")), parse_utc(p.get("leave_time"))
	if not joined:
		return None
	left = left or joined
	email = (p.get("user_email") or "").strip().lower()
	external_id = (p.get("id") or p.get("user_id") or "").strip()
	is_host = bool((host["email"] and email == host["email"]) or (host["id"] and external_id == host["id"]))
	return {
		"instance": uuid,
		"external_id": external_id,
		"display_name": (p.get("name") or "").strip(),
		"email": email,
		"joined_at": joined,
		"left_at": left,
		"seconds": max(cint(p.get("duration")), seconds_between(joined, left)),
		"is_host": is_host,
	}


# ---------------------------------------------------------------------------
# Google Meet
# ---------------------------------------------------------------------------


def meeting_code(join_url: str | None) -> str | None:
	match = MEET_CODE.search(join_url or "")
	return match.group(1).lower() if match else None


def meet_token(live) -> str:
	"""An access token for the Meet API from the refresh token of the class's Meet
	calendar. Frappe's own refresh asks only for the calendar scope, so it is not
	reused: this one asks for the Meet scope, which the consent of os_lms
	google_calendar.authorize_access includes."""
	from frappe.integrations.google_oauth import GoogleOAuth

	calendar = frappe.db.get_value("LMS Google Meet Settings", live.google_meet_account, "google_calendar")
	if not calendar:
		raise ProviderError(_("The Google Meet account {0} has no calendar.").format(live.google_meet_account))
	google_calendar = frappe.get_doc("Google Calendar", calendar)
	refresh_token = google_calendar.get_password("refresh_token", raise_exception=False)
	settings = frappe.get_cached_doc("Google Settings")
	if not refresh_token or not settings.client_id:
		raise ProviderError(_("The Google calendar {0} is not authorized.").format(calendar))
	data = {
		"client_id": settings.client_id,
		"client_secret": settings.get_password(fieldname="client_secret", raise_exception=False),
		"refresh_token": refresh_token,
		"grant_type": "refresh_token",
		"scope": MEET_SCOPE,
	}
	try:
		body = requests.post(GoogleOAuth.OAUTH_URL, data=data, timeout=HTTP_TIMEOUT).json()
	except Exception as e:
		raise ProviderError(_("Google did not answer: {0}").format(e)) from e
	if not body.get("access_token"):
		raise ProviderError(
			_(
				"Google Meet attendance is not authorized on the calendar {0}: authorize the calendar again."
			).format(calendar)
		)
	return body["access_token"]


def meet_get(path: str, token: str, params: dict | None = None) -> dict:
	try:
		response = requests.get(
			MEET_API + path,
			headers={"Authorization": f"Bearer {token}"},
			params=params,
			timeout=HTTP_TIMEOUT,
		)
	except requests.RequestException as e:
		raise ProviderError(_("Google Meet did not answer: {0}").format(e)) from e
	try:
		body = response.json()
	except ValueError:
		body = {}
	if response.status_code == 200:
		return body
	message = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
	raise ProviderError(
		_("Google Meet answered {0}: {1}").format(response.status_code, message or response.text[:300])
	)


def meet_list(path: str, key: str, token: str, params: dict | None = None) -> list[dict]:
	items, page_token = [], None
	while True:
		query = {"pageSize": MEET_PAGE_SIZE, **(params or {})}
		if page_token:
			query["pageToken"] = page_token
		body = meet_get(path, token, query)
		items.extend(body.get(key) or [])
		page_token = body.get("nextPageToken")
		if not page_token:
			return items


def rfc3339(value: datetime) -> str:
	"""A naive system-time datetime as an RFC 3339 UTC timestamp."""
	from zoneinfo import ZoneInfo

	from frappe.utils import get_system_timezone

	local = value.replace(tzinfo=ZoneInfo(get_system_timezone()))
	return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_meet(live) -> list[dict]:
	code = meeting_code(live.join_url)
	if not code:
		raise ProviderError(_("The live class has no Google Meet link."))
	token = meet_token(live)
	start, end = class_start(live), class_end(live)
	records = meet_list(
		"/conferenceRecords",
		"conferenceRecords",
		token,
		{
			"filter": (
				f'space.meeting_code = "{code}" AND start_time >= "{rfc3339(start - WINDOW_BEFORE)}"'
				f' AND start_time <= "{rfc3339(end + WINDOW_AFTER)}"'
			)
		},
	)
	if not records:
		raise NotHeld()
	segments = []
	for record in records:
		for participant in meet_list(f"/{record['name']}/participants", "participants", token):
			identity = meet_identity(participant)
			sessions = meet_list(f"/{participant['name']}/participantSessions", "participantSessions", token)
			for session in sessions or [participant]:
				joined = parse_utc(session.get("startTime") or session.get("earliestStartTime"))
				left = parse_utc(session.get("endTime") or session.get("latestEndTime"))
				if not joined:
					continue
				left = left or joined
				segments.append(
					{
						"instance": record["name"],
						**identity,
						"email": "",
						"joined_at": joined,
						"left_at": left,
						"seconds": seconds_between(joined, left),
						"is_host": False,
					}
				)
	return segments


def meet_identity(participant: dict) -> dict:
	"""Meet never reports an email: a signed-in user has a stable users/<id>."""
	for kind in ("signedinUser", "anonymousUser", "phoneUser"):
		person = participant.get(kind)
		if person:
			return {
				"external_id": person.get("user") or "" if kind == "signedinUser" else "",
				"display_name": (person.get("displayName") or "").strip(),
			}
	return {"external_id": "", "display_name": ""}


# ---------------------------------------------------------------------------
# Rows and matching
# ---------------------------------------------------------------------------


def parse_utc(value) -> datetime | None:
	"""A provider timestamp (UTC, RFC 3339) as naive system time."""
	if not value:
		return None
	try:
		parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	except ValueError:
		return None
	return convert_utc_to_system_timezone(parsed).replace(tzinfo=None, microsecond=0)


def seconds_between(start, end) -> int:
	if not start or not end:
		return 0
	return max(int((get_datetime(end) - get_datetime(start)).total_seconds()), 0)


def _insert_row(live, provider: str, segment: dict):
	now = now_datetime()
	doc = frappe.new_doc(ATTENDANCE)
	doc.update(
		{
			"live_class": live.name,
			"batch": live.batch_name,
			"provider": provider,
			"instance": (segment.get("instance") or "")[:140],
			"external_id": (segment.get("external_id") or "")[:140],
			"display_name": (segment.get("display_name") or "")[:140],
			"email": (segment.get("email") or "")[:140],
			"joined_at": segment["joined_at"],
			"left_at": segment["left_at"],
			"seconds": cint(segment.get("seconds")),
			"is_host": 1 if segment.get("is_host") else 0,
		}
	)
	doc.name = frappe.generate_hash(length=16)
	doc.owner = doc.modified_by = "Administrator"
	doc.creation = doc.modified = now
	doc.db_insert()
	return frappe._dict({field: doc.get(field) for field in ROW_FIELDS})


def _update_row(row, **values) -> None:
	frappe.db.set_value(ATTENDANCE, row.name, values, update_modified=False)
	row.update(values)


def group_key(row) -> tuple:
	"""Rows of the same person at the provider: same identity, or else same name and email."""
	if row.get("external_id"):
		return ("id", row.external_id)
	return ("name", normalize_name(row.get("display_name")), (row.get("email") or "").lower())


def _manual_matches(live_class: str) -> dict:
	"""Manual matches and guests of a class, to restore after a reread."""
	kept = {}
	for row in frappe.get_all(
		ATTENDANCE,
		filters={"live_class": live_class, "matched_by": ["in", MANUAL_MATCHES]},
		fields=ROW_FIELDS,
	):
		kept[group_key(row)] = {
			"user": row.user,
			"matched_by": row.matched_by,
			"matched_by_user": row.matched_by_user,
			"matched_at": row.matched_at,
		}
	return kept


def normalize_name(value: str | None) -> str:
	"""Lowercase, no accents or punctuation, words sorted ("Rossi Mario" = "mario rossi")."""
	text = unicodedata.normalize("NFKD", value or "")
	text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
	words = re.findall(r"[a-z0-9]+", text)
	return " ".join(sorted(words))


def teacher_of(live) -> str | None:
	"""Who started the class from the platform first, otherwise its host."""
	started = frappe.get_all(
		os_audit.EVENT,
		filters={"event_type": "live_class_start", "reference_name": live.name, "redacted": 0},
		fields=["user"],
		order_by="seq asc",
		limit=1,
	)
	return (started[0].user if started else None) or live.get("host")


def class_people(live) -> dict:
	"""Users linked to the class: students, teachers and valutatori of its batch, its
	host and whoever started it. {user: full name}."""
	batch = live.get("batch_name")
	users = set()
	if batch:
		users.update(frappe.get_all("LMS Batch Enrollment", filters={"batch": batch}, pluck="member"))
		users.update(
			frappe.get_all(
				"Course Instructor", filters={"parenttype": "LMS Batch", "parent": batch}, pluck="instructor"
			)
		)
		if frappe.db.table_exists("LMS Batch Valutatore"):
			users.update(
				frappe.get_all(
					"LMS Batch Valutatore", filters={"parenttype": "LMS Batch", "parent": batch}, pluck="valutatore"
				)
			)
	for user in (live.get("host"), teacher_of(live)):
		if user:
			users.add(user)
	users.discard(None)
	users.discard("")
	if not users:
		return {}
	return {
		u.name: u.full_name or u.name
		for u in frappe.get_all("User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"])
	}


def match_rows(live, rows: list) -> None:
	"""Match the unmatched rows: Zoom host, known identity, email, unique name."""
	people = class_people(live)
	teacher = teacher_of(live)
	emails = {
		(u.email or "").lower(): u.name
		for u in frappe.get_all("User", filters={"name": ["in", list(people) or [""]]}, fields=["name", "email"])
		if u.email
	}
	emails.update({user.lower(): user for user in people})
	by_name = {}
	for user, full_name in people.items():
		by_name.setdefault(normalize_name(full_name), set()).add(user)
	ids = sorted({row.external_id for row in rows if row.external_id and not row.user})
	identities = {}
	if ids:
		for identity in frappe.get_all(
			IDENTITY,
			filters={"external_id": ["in", ids]},
			fields=["name", "provider", "external_id", "user"],
		):
			identities[(identity.provider, identity.external_id)] = identity
	now = now_datetime()
	for row in rows:
		if row.user or row.matched_by == "guest":
			continue
		user, how = None, None
		identity = identities.get((row.provider, row.external_id)) if row.external_id else None
		if row.is_host and teacher in people:
			user, how = teacher, "host"
		elif identity and identity.user in people:
			user, how = identity.user, "identity"
			frappe.db.set_value(IDENTITY, identity.name, "modified", now, update_modified=False)
		elif row.email and emails.get(row.email.lower()):
			user, how = emails[row.email.lower()], "email"
		else:
			candidates = by_name.get(normalize_name(row.display_name)) if row.display_name else None
			if candidates and len(candidates) == 1:
				user, how = next(iter(candidates)), "name"
		if user:
			_update_row(row, user=user, matched_by=how, matched_at=now, is_host=1 if user == teacher else 0)
			if how == "email" and row.external_id:
				remember_identity(row, user, how)


def remember_identity(row, user: str, how: str, by: str | None = None) -> None:
	"""Remember that a stable provider identity belongs to `user` for the next classes."""
	if not row.get("external_id"):
		return
	now = now_datetime()
	existing = frappe.db.get_value(IDENTITY, {"provider": row.provider, "external_id": row.external_id}, "name")
	values = {
		"user": user,
		"display_name": (row.get("display_name") or "")[:140],
		"matched_by": how,
		"matched_by_user": by,
		"matched_at": now,
		"modified": now,
	}
	if existing:
		frappe.db.set_value(IDENTITY, existing, values, update_modified=False)
		return
	doc = frappe.new_doc(IDENTITY)
	doc.update({"provider": row.provider, "external_id": row.external_id, **values})
	doc.name = frappe.generate_hash(length=16)
	doc.owner = doc.modified_by = "Administrator"
	doc.creation = now
	doc.db_insert()


def remove_identity(row) -> None:
	if row.get("external_id"):
		frappe.db.delete(IDENTITY, {"provider": row.provider, "external_id": row.external_id})


# ---------------------------------------------------------------------------
# Totals, events, upstream participants
# ---------------------------------------------------------------------------


def merged_segments(rows: list) -> list[tuple]:
	"""The (join, leave) intervals of a person, overlaps merged: two devices at once
	do not count twice."""
	intervals = sorted((get_datetime(r.joined_at), get_datetime(r.left_at)) for r in rows if r.joined_at)
	merged = []
	for start, end in intervals:
		end = max(end, start)
		if merged and start <= merged[-1][1]:
			merged[-1] = (merged[-1][0], max(merged[-1][1], end))
		else:
			merged.append((start, end))
	return merged


def person_totals(rows: list) -> dict:
	segments = merged_segments(rows)
	if not segments:
		return {"joined_at": None, "left_at": None, "seconds": 0, "segments": []}
	return {
		"joined_at": segments[0][0],
		"left_at": max(end for _start, end in segments),
		"seconds": sum(seconds_between(start, end) for start, end in segments),
		"segments": segments,
	}


def _fmt(value) -> str | None:
	return get_datetime(value).strftime("%Y-%m-%d %H:%M:%S") if value else None


def record_attendance(live, user: str, rows: list, reread: bool = False, **extra) -> None:
	"""One live_attendance event for `user` with their totals in the class."""
	mine = [row for row in rows if row.user == user]
	totals = person_totals(mine)
	how = sorted({row.matched_by for row in mine if row.matched_by})
	data = {
		"provider": mine[0].provider if mine else None,
		"joined_at": _fmt(totals["joined_at"]),
		"left_at": _fmt(totals["left_at"]),
		"seconds": totals["seconds"],
		"segments": [[_fmt(s), _fmt(e)] for s, e in totals["segments"][:MAX_EVENT_SEGMENTS]],
		"segment_count": len(totals["segments"]),
		"matched_by": how,
		"is_host": 1 if any(row.is_host for row in mine) else 0,
		"names": sorted({row.display_name for row in mine if row.display_name})[:5],
	}
	if reread:
		data["reread"] = 1
	data.update({k: v for k, v in extra.items() if v is not None})
	os_audit.record(
		"live_attendance",
		user=user,
		batch=live.batch_name,
		reference_doctype=LIVE_CLASS,
		reference_name=live.name,
		data=data,
	)


def rows_fingerprint(rows: list) -> str:
	payload = sorted(
		[
			row.instance or "",
			row.external_id or "",
			row.display_name or "",
			row.email or "",
			_fmt(row.joined_at),
			_fmt(row.left_at),
			cint(row.seconds),
		]
		for row in rows
	)
	return hashlib.sha256(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _record_read(live, provider: str, rows: list, reread: bool = False) -> None:
	data = {
		"provider": provider,
		"rows": len(rows),
		"people": len({group_key(row) for row in rows}),
		"matched": sum(1 for row in rows if row.user),
		"unmatched": sum(1 for row in rows if not row.user and row.matched_by != "guest"),
		"fingerprint": rows_fingerprint(rows),
	}
	if reread:
		data["reread"] = 1
	os_audit.record(
		"live_attendance_read",
		batch=live.batch_name,
		reference_doctype=LIVE_CLASS,
		reference_name=live.name,
		data=data,
	)


def sync_participants(live, rows: list | None = None) -> None:
	"""Rewrite upstream's LMS Live Class Participant for the class: one row per
	matched person, duration in minutes as upstream shows it."""
	if rows is None:
		rows = frappe.get_all(ATTENDANCE, filters={"live_class": live.name}, fields=ROW_FIELDS)
	frappe.db.delete(PARTICIPANT, {"live_class": live.name})
	users = sorted({row.user for row in rows if row.user})
	names = (
		{
			u.name: u.full_name
			for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"])
		}
		if users
		else {}
	)
	count = 0
	for user in users:
		if user not in names:
			continue
		totals = person_totals([row for row in rows if row.user == user])
		doc = frappe.new_doc(PARTICIPANT)
		doc.update(
			{
				"live_class": live.name,
				"member": user,
				"member_name": names[user],
				"joined_at": totals["joined_at"],
				"left_at": totals["left_at"],
				"duration": totals["seconds"] // 60,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		count += 1
	frappe.db.set_value(LIVE_CLASS, live.name, "attendees", count, update_modified=False)


# ---------------------------------------------------------------------------
# Page actions (Administrator and Gestore)
# ---------------------------------------------------------------------------


def _live_of(row):
	live = frappe.db.get_value(LIVE_CLASS, row.live_class, LIVE_FIELDS, as_dict=True)
	if not live:
		frappe.throw(_("The live class of this participant no longer exists."))
	return live


def people_options(live) -> list:
	"""The people a participant of `live` can be matched to, for the page's picker."""
	return sorted(
		({"user": user, "full_name": name} for user, name in class_people(live).items()),
		key=lambda p: (p["full_name"] or "").lower(),
	)


@frappe.whitelist(methods=["POST"])
def match_participant(row: str, user: str | None = None, guest: int | str = 0) -> dict:
	"""Match a participant the provider reported (all their segments in the class)
	to a person of the class, or mark them as an external guest. Recorded in the chain."""
	os_audit.assert_can_use_os_audit()
	target = frappe.db.get_value(ATTENDANCE, row, ROW_FIELDS, as_dict=True)
	if not target:
		frappe.throw(_("Participant not found."), frappe.DoesNotExistError)
	live = _live_of(target)
	guest = cint(guest)
	if not guest:
		if not user or user not in class_people(live):
			frappe.throw(_("Choose a person of this class."))
	else:
		user = None
	rows = frappe.get_all(ATTENDANCE, filters={"live_class": live.name}, fields=ROW_FIELDS)
	key = group_key(target)
	group = [r for r in rows if group_key(r) == key]
	previous = sorted({r.user for r in group if r.user})
	now = now_datetime()
	by = frappe.session.user
	teacher = teacher_of(live)
	for r in group:
		_update_row(
			r,
			user=user,
			matched_by="guest" if guest else "manual",
			matched_by_user=by,
			matched_at=now,
			is_host=1 if user and user == teacher else 0,
		)
	if guest:
		remove_identity(target)
	else:
		remember_identity(target, user, "manual", by=by)
		record_attendance(live, user, rows, manual_by=by, replaces=",".join(p for p in previous if p != user) or None)
	for old in previous:
		if old != user:
			# The previous person's totals without these segments (possibly none left).
			record_attendance(live, old, rows, manual_by=by, unmatched_by=by, guest=1 if guest else None)
	sync_participants(live, rows)
	unmatched = sum(1 for r in rows if not r.user and r.matched_by != "guest")
	matched = sum(1 for r in rows if r.user)
	if frappe.db.exists(READ, live.name):
		frappe.db.set_value(READ, live.name, {"matched": matched, "unmatched": unmatched}, update_modified=False)
	return {"matched": matched, "unmatched": unmatched}


@frappe.whitelist(methods=["POST"])
def reread_live_class(live_class: str) -> dict:
	"""Read the provider attendance of an ended class again, in the background.
	Manual matches and guests are kept."""
	os_audit.assert_can_use_os_audit()
	live = frappe.db.get_value(LIVE_CLASS, live_class, LIVE_FIELDS, as_dict=True)
	if not live:
		frappe.throw(_("Live class not found."), frappe.DoesNotExistError)
	if not provider_of(live):
		frappe.throw(_("This live class has no Zoom or Google Meet meeting."))
	if now_datetime() < class_end(live):
		frappe.throw(_("The attendance can be read once the class has ended."))
	if not in_scope(live):
		frappe.throw(
			_("Live attendance is not recorded for this class: check the OS Audit settings.")
		)
	_set_status(live.name, provider_of(live), STATUS_PENDING, error=None)
	frappe.enqueue(
		"os_lms.os_lms.os_audit_live.read_live_class",
		name=live.name,
		force=True,
		queue="short",
		enqueue_after_commit=True,
	)
	return {"status": STATUS_PENDING}


# ---------------------------------------------------------------------------
# Retention and erasure (called by os_audit)
# ---------------------------------------------------------------------------


def apply_retention(cutoff) -> int:
	"""Delete the live attendance data older than the retention cutoff."""
	rows = frappe.db.count(ATTENDANCE, {"joined_at": ["<", cutoff]})
	if rows:
		frappe.db.delete(ATTENDANCE, {"joined_at": ["<", cutoff]})
	frappe.db.delete(IDENTITY, {"modified": ["<", cutoff]})
	frappe.db.delete(READ, {"creation": ["<", cutoff]})
	return rows


def erase_user(user: str) -> int:
	"""Account deletion: the provider rows and identities of the user."""
	rows = frappe.db.count(ATTENDANCE, {"user": user})
	frappe.db.delete(ATTENDANCE, {"user": user})
	frappe.db.delete(IDENTITY, {"user": user})
	return rows


def _plain_message(error: Exception) -> str:
	text = str(error) or error.__class__.__name__
	return re.sub(r"<[^>]+>", "", text)[:300]
