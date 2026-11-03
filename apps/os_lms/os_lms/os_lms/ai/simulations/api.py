"""Whitelisted REST endpoints for the simulations feature.

URL prefix: /api/method/os_lms.os_lms.ai.simulations.api.<name>

The HTTP layer is a thin shell: it validates inputs, gates by permissions,
delegates to SessionOrchestrator, and returns plain dicts. Realtime events
are emitted by the orchestrator (frappe.publish_realtime), so the HTTP
response and the WebSocket stream stay in sync without extra glue.
"""
from __future__ import annotations

import frappe
from frappe import _


from os_lms.os_lms.access_guards import check_user_rate_limit
from os_lms.os_lms.ai.audio.pipeline import run_audio_turn

from .limits import (
    CHAT_MESSAGE_ACTION,
    SESSION_START_ACTION,
    check_message_length,
    load_limits,
)

from .orchestrator import (
    QuotaExceededError,
    SessionOrchestrator,
    SessionTerminatedError,
    closing_input_locked,
    remaining_seconds,
    scenario_time_limit,
)
from .tasks import generate_debrief as _run_generate_debrief
from . import access, teacher_review


def _service() -> SessionOrchestrator:
    return SessionOrchestrator()


def _can_manage_course(course: str) -> bool:
    """Whether the current user may create, edit and list the course's
    scenarios (access.can_manage_course).

    Asked directly, not by catching _ensure_can_manage_course: frappe.throw
    queues its message on the response even when the exception is caught, so a
    student used to see "You are not an instructor of this course" next to an
    answer that had nothing to do with it."""
    return access.can_manage_course(course)


def _ensure_can_manage_course(course: str) -> None:
    if not _can_manage_course(course):
        frappe.throw(
            _("You cannot manage the simulations of this course"), frappe.PermissionError
        )


def _ensure_can_author() -> None:
    if not access.may_author():
        frappe.throw(_("You cannot manage simulations"), frappe.PermissionError)


def load_session(session_id: str):
    """Resolve a Session and gate access. Mirrors `load_lesson` in ai/api.py.

    Returns the Document on success. Throws PermissionError otherwise.
    """
    if not session_id or not frappe.db.exists("LMSA Simulation Session", session_id):
        frappe.throw(_("Simulation session not found"), frappe.DoesNotExistError)

    session = frappe.get_doc("LMSA Simulation Session", session_id)
    user = frappe.session.user

    if user == session.student:
        return session
    if access.can_review(session.course, session.student):
        return session

    frappe.throw(
        _("You don't have permission to access this simulation session"),
        frappe.PermissionError,
    )


def _count_session_start() -> None:
    """Cap the simulations one student may open per hour (OWASP H-3)."""
    check_user_rate_limit(SESSION_START_ACTION, load_limits().session_starts_per_hour, 3600)


def _count_chat_message() -> None:
    """Cap the role-player turns one student may trigger per minute (OWASP H-3)."""
    check_user_rate_limit(CHAT_MESSAGE_ACTION, load_limits().chat_messages_per_minute, 60)


def _resolve_published_scenario(scenario_id: str):
    """Load a Published scenario and gate by enrollment / instructor role."""
    if not scenario_id or not frappe.db.exists("LMSA Simulation Scenario", scenario_id):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)

    scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
    user = frappe.session.user

    if _can_manage_course(scenario.lms_course):
        return scenario
    if scenario.status != "Published":
        frappe.throw(
            _("Scenario {0} is not published").format(scenario.name),
            frappe.PermissionError,
        )
    if not frappe.db.exists(
        "LMS Enrollment", {"member": user, "course": scenario.lms_course}
    ):
        frappe.throw(
            _("You are not enrolled in the course owning this scenario"),
            frappe.PermissionError,
        )
    return scenario


# ----- Endpoints -----


@frappe.whitelist(methods=["POST"])
def start_session(scenario_id: str, modality: str = "chat") -> dict:
    """Create a Session for the current user and return the first role-player turn."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    _count_session_start()
    # Pass the already-authorized document (not its name) so the orchestrator
    # skips its redundant "is Published" re-check: `_resolve_published_scenario`
    # has already gated access, allowing instructors/moderators to launch a
    # "test as student" run on Draft/Archived scenarios.
    try:
        result = _service().start_session(scenario_id=scenario, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return dict(result)


@frappe.whitelist(methods=["POST"])
def prepare_session(scenario_id: str, modality: str = "chat") -> dict:
    """Phase 1: generate the variant and create a Ready session with a brief."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    if modality == "chat" and scenario.modality not in ("chat", "both"):
        frappe.throw(_("Scenario {0} is not chat-enabled.").format(scenario.name))
    if modality == "voice" and scenario.modality not in ("voice", "both"):
        frappe.throw(_("Scenario {0} is not voice-enabled.").format(scenario.name))

    _count_session_start()
    try:
        result = _service().prepare_session(scenario_id=scenario.name, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}


@frappe.whitelist(methods=["POST"])
def begin_session(session_id: str) -> dict:
    """Phase 2 (chat): persist the first role-player turn for a prepared session."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can begin the session"), frappe.PermissionError)
    _count_chat_message()
    return dict(_service().begin_chat_session(session_id=session.name))


@frappe.whitelist(methods=["POST"])
def clone_session(session_id: str) -> dict:
    """Restart a session: create a new Ready session reusing the same variant."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can restart it"), frappe.PermissionError)
    # The restart must pass the same gates as a new session (OWASP L-18): a student
    # no longer enrolled, or a scenario no longer published, cannot keep playing.
    _resolve_published_scenario(session.scenario)
    _count_session_start()
    try:
        result = _service().clone_session(session_id=session.name)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}


@frappe.whitelist(methods=["POST"])
def send_message(session_id: str, text: str) -> dict:
    """Append a user turn and return the assistant's reply."""
    if not text or not text.strip():
        frappe.throw(_("Message cannot be empty"))

    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(
            _("Only the session owner can send messages"), frappe.PermissionError
        )
    check_message_length(text)
    _count_chat_message()

    try:
        result = _service().send_message(session_id=session.name, user_text=text)
    except SessionTerminatedError:
        frappe.throw(
            _("This session is no longer accepting messages"), frappe.ValidationError
        )
    return dict(result)


@frappe.whitelist(methods=["POST"])
def send_message_audio(
    session_id: str,
    text: str | None = None,
    audio: str | None = None,
    mime: str = "audio/webm",
    language: str = "it",
    want_audio: bool = True,
) -> dict:
    """Single-call audio (or text) simulation turn: STT? -> role-player -> TTS?.

    Reuses the orchestrator's send_message (persists both turns + fires the
    realtime event). Returns question/answer text, answer audio, and the turn
    names for client reconciliation.
    """
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can send messages"), frappe.PermissionError)
    check_message_length(text)
    # Counted before the transcription: STT and TTS are billed too.
    _count_chat_message()

    holder: dict = {}

    def _produce(q: str) -> str:
        check_message_length(q)
        r = _service().send_message(session_id=session.name, user_text=q)
        holder["user_turn"] = r.user_turn.name
        holder["assistant_turn"] = r.assistant_turn.name
        holder["injection_attempt"] = bool(r.injection_attempt)
        return r.assistant_turn.text

    try:
        result = run_audio_turn(
            audio=audio, text=text, mime=mime, language=language,
            want_audio=want_audio, produce_answer=_produce,
        )
    except SessionTerminatedError:
        frappe.throw(_("This session is no longer accepting messages"), frappe.ValidationError)
    return {**result, **holder}


@frappe.whitelist(methods=["POST"])
def end_session(session_id: str, reason: str = "completed") -> dict:
    """Mark a session as completed or abandoned."""
    if reason not in ("completed", "abandoned"):
        frappe.throw(_("Unsupported reason: {0}").format(reason))

    session = load_session(session_id)
    if session.student != frappe.session.user and not access.has_full_access():
        frappe.throw(_("Only the session owner can end the session"), frappe.PermissionError)

    return dict(_service().end_session(session_id=session.name, reason=reason))


@frappe.whitelist()
def get_session(session_id: str) -> dict:
    """Return session metadata + ordered list of turns."""
    session = load_session(session_id)
    turns = frappe.get_all(
        "LMSA Simulation Turn",
        filters={"session": session.name},
        fields=[
            "name",
            "turn_index",
            "role",
            "text_content",
            "latency_ms",
            "tokens_input",
            "tokens_output",
            "provider_used",
            "model_used",
            "injection_attempt_detected",
        ],
        order_by="turn_index asc",
    )
    # Time-based natural-close budget: the cap comes from the scenario, the
    # remaining seconds are computed server-side (authoritative clock) and
    # re-synced on every reload, i.e. after each send. None when no cap is set;
    # 0 while the forced close plays out after the time is up.
    time_limit_minutes = scenario_time_limit(session.scenario)
    return {
        "session": {
            "name": session.name,
            "scenario": session.scenario,
            "course": session.course,
            "modality": session.modality,
            "status": session.status,
            "started_at": str(session.started_at) if session.started_at else None,
            "ended_at": str(session.ended_at) if session.ended_at else None,
            "turn_count": session.turn_count,
            "generated_persona": session.generated_persona,
            "generated_situation": session.generated_situation,
            "student_brief": session.student_brief,
            "chat_provider_used": session.chat_provider_used,
            "chat_model_used": session.chat_model_used,
            "time_limit_minutes": time_limit_minutes or None,
            "remaining_seconds": remaining_seconds(session, time_limit_minutes),
            "input_locked": closing_input_locked(session, time_limit_minutes),
        },
        "turns": turns,
    }


@frappe.whitelist()
def get_debrief(session_id: str) -> dict:
    """Return the debrief for `session_id`, or an early-stage placeholder.

    Status values: `not_started` (session not terminal), `pending` (job running),
    `ready`, `needs_review`, `failed`.
    """
    session = load_session(session_id)
    if session.status in ("In Progress", "Ready"):
        return {"status": "not_started", "session": session.name, "course": session.course}

    name = frappe.db.get_value("LMSA Simulation Debrief", {"session": session.name}, "name")
    if not name:
        # Job has been enqueued but the Debrief row hasn't been created yet.
        return {"status": "pending", "session": session.name, "course": session.course}

    debrief = frappe.get_doc("LMSA Simulation Debrief", name)
    payload = _serialize_debrief(debrief, reviewer=_is_reviewer(session))
    # The report page offers "Rifai la simulazione" (clone_session) to the
    # student who played it, not to a reviewer opening it.
    payload["can_retry"] = session.student == frappe.session.user
    return payload


@frappe.whitelist(methods=["POST"])
def generate_debrief(session_id: str) -> dict:
    """Run Prompt 3 for `session_id` synchronously and return the debrief payload.

    Designed for manual triggers from the SPA panel ("rigenera debrief") and
    for bench execute. The async path uses `tasks.generate_debrief` directly
    via `frappe.enqueue`.
    """
    if not session_id:
        frappe.throw(_("session_id is required"))

    session = load_session(session_id)
    # The debrief is the grade the instructor sees, so it is written once, for a
    # finished session (end_session enqueues it). Regenerating an existing one is
    # for course instructors and moderators: a student calling this in a loop used
    # to redraw their score until they liked it, each draw a paid LLM call.
    if session.status in ("In Progress", "Ready"):
        frappe.throw(_("The debrief is generated when the session ends."))
    if not access.can_review(session.course, session.student):
        if session.student != frappe.session.user:
            frappe.throw(_("Not permitted"), frappe.PermissionError)
        existing = frappe.db.get_value("LMSA Simulation Debrief", {"session": session.name}, "status")
        if existing and existing != "Failed":
            frappe.throw(_("The debrief for this session has already been generated."))

    name = _run_generate_debrief(session.name)
    debrief = frappe.get_doc("LMSA Simulation Debrief", name)
    return _serialize_debrief(debrief, reviewer=_is_reviewer(session))



def _is_reviewer(session) -> bool:
    """Whether the current user reviews the session (access.can_review) rather
    than only owning it. A Docente or Valutatore playing their own test
    session is a reviewer of it only when their role reaches its course and
    student."""
    return access.can_review(session.course, session.student)


def _serialize_debrief(debrief, *, reviewer: bool) -> dict:
    """The AI version, scores included, for everyone who may open the
    debrief (docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, decisions 4
    and 6: the student sees the indicative score and the criterion scores).
    The teacher version goes to reviewers from the first draft and to the
    student only once published."""
    has_outcome = teacher_review.scenario_has_outcome(debrief)
    published = debrief.review_status == teacher_review.REVIEW_PUBLISHED
    return {
        "status": debrief.status.lower().replace(" ", "_"),
        "session": debrief.session,
        "name": debrief.name,
        "course": debrief.course,
        "behavioral_analysis": debrief.behavioral_analysis,
        "strengths": [
            {"title": s.title, "detail": s.detail, "quote": s.quote}
            for s in (debrief.strengths or [])
        ],
        "improvements": [
            {
                "title": i.title,
                "detail": i.detail,
                "quote": i.quote,
                "suggestion": i.suggestion,
            }
            for i in (debrief.improvements or [])
        ],
        "recommended_content": [
            {
                "lesson": r.lesson,
                "title": r.title,
                "why": r.why,
                "relevance_score": r.relevance_score,
            }
            for r in (debrief.recommended_content or [])
        ],
        "overall_score": debrief.overall_score,
        "criterion_scores": [
            {
                "criterion_name": c.criterion_name,
                "score": c.score,
                "max_score": c.max_score,
                "evidence_quote": c.evidence_quote,
                "note": c.note,
            }
            for c in (debrief.criterion_scores or [])
        ],
        "teacher_version": (
            teacher_review.serialize_review(debrief) if reviewer or published else None
        ),
        "outcome_required": has_outcome,
        "review_state": teacher_review.review_state(debrief, has_outcome=has_outcome),
    }


@frappe.whitelist()
def list_scenarios(course: str | None = None) -> list[dict]:
    """List the scenarios the current user may play.

    - Courses whose simulations the user manages (access.managed_courses):
      every scenario, any status, so the instructor can try drafts.
    - Courses the user is enrolled in: Published scenarios only.
    """
    user = frappe.session.user
    fields = ["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality", "status"]
    managed = access.managed_courses()
    if managed is None:
        filters: dict = {"lms_course": course} if course else {}
        return frappe.get_all(
            "LMSA Simulation Scenario", filters=filters, fields=fields, order_by="modified desc"
        )

    enrolled = set(frappe.get_all("LMS Enrollment", filters={"member": user}, pluck="course"))
    if course:
        managed &= {course}
        enrolled &= {course}
    enrolled -= managed

    scenarios = []
    if managed:
        scenarios += frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"lms_course": ["in", list(managed)]},
            fields=fields + ["modified"],
        )
    if enrolled:
        # `status` is always "Published" here but is returned so clients can
        # filter uniformly across the managed rows, which include drafts.
        scenarios += frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"lms_course": ["in", list(enrolled)], "status": "Published"},
            fields=fields + ["modified"],
        )
    scenarios.sort(key=lambda r: r.modified, reverse=True)
    for row in scenarios:
        row.pop("modified")
    return scenarios


# A later attempt shows its improvement only above this many points: smaller
# moves are noise (docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, decision 6).
IMPROVEMENT_MIN_POINTS = 5

# Debrief statuses whose AI score is meaningful
SCORED_DEBRIEF_STATUSES = ("Ready", "Needs Review")


@frappe.whitelist()
def list_my_sessions(course: str | None = None, scenario: str | None = None) -> list[dict]:
    """List the current user's own simulation sessions (optionally by course
    and/or scenario), with each attempt's score: the published teacher
    version's when there is one, otherwise the AI's indicative one."""
    filters: dict = {"student": frappe.session.user}
    if course:
        filters["course"] = course
    if scenario:
        filters["scenario"] = scenario

    sessions = frappe.get_all(
        "LMSA Simulation Session",
        filters=filters,
        fields=[
            "name",
            "scenario",
            "modality",
            "status",
            "started_at",
            "ended_at",
            "turn_count",
        ],
        order_by="started_at desc",
    )
    if not sessions:
        return []

    scenario_names = {s["scenario"] for s in sessions if s["scenario"]}
    scenarios = {
        r["name"]: r
        for r in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"name": ["in", list(scenario_names)]},
            fields=["name", "scenario_name", "has_human_outcome"],
        )
    }
    debriefs = {
        d["session"]: d
        for d in frappe.get_all(
            "LMSA Simulation Debrief",
            filters={"session": ["in", [s["name"] for s in sessions]]},
            fields=[
                "session",
                "status",
                "overall_score",
                "review_status",
                "review_overall_score",
                "outcome",
            ],
        )
    }

    for s in sessions:
        sc = scenarios.get(s["scenario"]) or {}
        s["scenario_name"] = sc.get("scenario_name") or s["scenario"]
        s["started_at"] = str(s["started_at"]) if s["started_at"] else None
        s["ended_at"] = str(s["ended_at"]) if s["ended_at"] else None
        d = debriefs.get(s["name"])
        s["debrief_status"] = d["status"] if d else None
        s.update(_attempt_result(d, has_outcome=bool(sc.get("has_human_outcome"))))
    _mark_improvements(sessions)
    return sessions


def _attempt_result(debrief: dict | None, *, has_outcome: bool) -> dict:
    """Score, its source and outcome of one attempt, as its student sees them:
    the teacher version counts only once published."""
    result = {"score": None, "score_source": None, "outcome": "", "review_state": None}
    if not debrief or debrief["status"] not in SCORED_DEBRIEF_STATUSES:
        return result
    result["review_state"] = teacher_review.review_state(
        frappe._dict(debrief), has_outcome=has_outcome
    )
    if result["review_state"] == "published":
        result.update(
            score=debrief["review_overall_score"],
            score_source="teacher",
            outcome=debrief["outcome"] or "",
        )
    else:
        result.update(score=debrief["overall_score"], score_source="ai")
    return result


def _mark_improvements(sessions: list[dict]) -> None:
    """Set `improvement` on each attempt that beats the previous scored
    attempt of the same scenario by more than IMPROVEMENT_MIN_POINTS."""
    previous: dict[str, float] = {}
    for s in sorted(sessions, key=lambda s: s["started_at"] or ""):
        s["improvement"] = None
        if s["score"] is None:
            continue
        last = previous.get(s["scenario"])
        if last is not None and s["score"] - last > IMPROVEMENT_MIN_POINTS:
            s["improvement"] = round(s["score"] - last, 1)
        previous[s["scenario"]] = s["score"]


# ============================================================================
# Instructor endpoints (DOC-4.*)
#
# These power the SPA Vue panel for instructors / moderators. They never go
# through the Desk: the panel is the only supported UI for instructors per
# decision #10 in PROGRESS.md.
# ============================================================================


def _instructor_debrief(session_id: str):
    """Load the debrief of `session_id` for someone who may review it."""
    session = load_session(session_id)
    if not access.can_review(session.course, session.student):
        frappe.throw(_("You cannot review this session"), frappe.PermissionError)

    name = frappe.db.get_value("LMSA Simulation Debrief", {"session": session.name}, "name")
    if not name:
        frappe.throw(_("No debrief available for this session yet"))
    return frappe.get_doc("LMSA Simulation Debrief", name)


def _save_teacher_version(debrief) -> dict:
    debrief.save(ignore_permissions=True)
    frappe.db.commit()
    return _serialize_debrief(debrief, reviewer=True)


@frappe.whitelist(methods=["POST"])
def instructor_start_review(session_id: str) -> dict:
    """Create the teacher version of the debrief as a draft copy of the AI's
    (teacher_review.start_review). Returns the debrief payload."""
    debrief = _instructor_debrief(session_id)
    teacher_review.start_review(debrief)
    return _save_teacher_version(debrief)


@frappe.whitelist(methods=["POST"])
def instructor_save_review(session_id: str, review: dict, publish: bool = False) -> dict:
    """Save the teacher version; with `publish` the student sees it from now
    on. On simulations with an outcome it cannot be published without one.
    Returns the debrief payload."""
    debrief = _instructor_debrief(session_id)
    teacher_review.apply_review(
        debrief,
        review,
        publish=frappe.utils.sbool(publish),
        has_outcome=teacher_review.scenario_has_outcome(debrief),
    )
    return _save_teacher_version(debrief)


@frappe.whitelist(methods=["POST"])
def instructor_discard_review(session_id: str) -> dict:
    """Delete a draft teacher version. Returns the debrief payload."""
    debrief = _instructor_debrief(session_id)
    teacher_review.discard_review(debrief)
    return _save_teacher_version(debrief)


@frappe.whitelist()
def instructor_report(
    course: str | None = None,
    student: str | None = None,
    period_days: int = 30,
    scenario: str | None = None,
) -> dict:
    """Aggregated report + sessions list for the sessions the user may review
    (access.review_scope: a Valutatore sees only the students of their batches).

    Scores are the ones the students see: the published teacher version's,
    otherwise the AI's indicative one (docs/ai-simulator/
    PIANO-esito-e-punteggio-coach.md, phase 7).

    Returns:
      - `kpi`: total_sessions, completed_sessions, avg_score, students_count,
        `reviewed` (AI vs teacher average on the sessions with a published
        teacher version), `outcomes` (passed out of the outcomes people
        decided), `to_evaluate` (sessions waiting for an outcome) and
        `improvement` (first vs last attempt per student and scenario)
      - `score_distribution`: bucketed counts (0-20, 20-40, ...)
      - `top_improvement_titles`: most frequent improvement titles (the AI's)
      - `sessions`: list of session rows with score, outcome, status, scenario
        and student
    """
    scope = access.review_scope()
    allowed_courses = (
        set(frappe.get_all("LMS Course", pluck="name")) if scope.full else scope.course_names()
    )
    if not allowed_courses:
        return _empty_report()

    if course is not None:
        if course not in allowed_courses:
            frappe.throw(_("You cannot view reports for this course"), frappe.PermissionError)
        course_filter = [course]
    else:
        course_filter = list(allowed_courses)

    since = frappe.utils.add_days(frappe.utils.now_datetime(), -max(1, int(period_days)))

    session_filters = [
        ["course", "in", course_filter],
        ["started_at", ">=", since],
    ]
    if student:
        session_filters.append(["student", "=", student])
    if scenario:
        session_filters.append(["scenario", "=", scenario])

    sessions = frappe.get_all(
        "LMSA Simulation Session",
        filters=session_filters,
        fields=[
            "name",
            "student",
            "scenario",
            "course",
            "status",
            "started_at",
            "ended_at",
            "turn_count",
        ],
        order_by="started_at desc",
        limit_page_length=500,
    )
    sessions = [s for s in sessions if scope.allows(s["course"], s["student"])]
    session_names = [s["name"] for s in sessions]

    debriefs_by_session: dict[str, dict] = {}
    if session_names:
        for d in frappe.get_all(
            "LMSA Simulation Debrief",
            filters={"session": ["in", session_names]},
            fields=[
                "name",
                "session",
                "status",
                "overall_score",
                "review_status",
                "review_overall_score",
                "outcome",
            ],
        ):
            debriefs_by_session[d["session"]] = d
    outcome_scenarios = set(
        frappe.get_all(
            "LMSA Simulation Scenario",
            filters={
                "name": ["in", list({s["scenario"] for s in sessions}) or [""]],
                "has_human_outcome": 1,
            },
            pluck="name",
        )
    )

    enriched = []
    completed_count = 0
    students_seen: set[str] = set()
    for s in sessions:
        d = debriefs_by_session.get(s["name"])
        s = dict(s)
        s["debrief"] = d["name"] if d else None
        s["debrief_status"] = d["status"] if d else None
        s["ai_score"] = d["overall_score"] if d else None
        s.update(_attempt_result(d, has_outcome=s["scenario"] in outcome_scenarios))
        s["to_evaluate"] = s["review_state"] == "awaiting_outcome"
        enriched.append(s)
        students_seen.add(s["student"])
        if s["status"] == "Completed":
            completed_count += 1

    scores = [float(s["score"]) for s in enriched if s["score"] is not None]
    avg_score = _mean(scores)

    return {
        "kpi": {
            "total_sessions": len(sessions),
            "completed_sessions": completed_count,
            "avg_score": avg_score,
            "students_count": len(students_seen),
            "period_days": period_days,
            "reviewed": _reviewed_comparison(enriched),
            "outcomes": _human_outcomes(enriched),
            "to_evaluate": sum(1 for s in enriched if s["to_evaluate"]),
            "improvement": _first_to_last_improvement(enriched),
        },
        "score_distribution": _score_buckets(scores),
        "top_improvement_titles": _top_improvements(session_names),
        "sessions": enriched,
    }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _reviewed_comparison(sessions: list[dict]) -> dict:
    """AI vs teacher average on the sessions whose teacher version is
    published: how much the teachers correct the AI."""
    reviewed = [
        s for s in sessions if s["score_source"] == "teacher" and s["ai_score"] is not None
    ]
    return {
        "count": len(reviewed),
        "ai_avg": _mean([float(s["ai_score"]) for s in reviewed]),
        "teacher_avg": _mean([float(s["score"]) for s in reviewed]),
    }


def _human_outcomes(sessions: list[dict]) -> dict:
    """Passed out of the outcomes a person decided and published; the AI
    never decides one, so sessions without it do not count."""
    decided = [s for s in sessions if s["outcome"] in teacher_review.OUTCOMES]
    passed = sum(1 for s in decided if s["outcome"] == teacher_review.OUTCOME_PASSED)
    return {
        "decided": len(decided),
        "passed": passed,
        "rate": round(100 * passed / len(decided), 1) if decided else None,
    }


def _first_to_last_improvement(sessions: list[dict]) -> dict:
    """For each student and scenario with at least two scored attempts, the
    last attempt's score minus the first one's; `improved` counts the gains
    above IMPROVEMENT_MIN_POINTS."""
    attempts: dict[tuple[str, str], list[dict]] = {}
    for s in sessions:
        if s["score"] is not None:
            attempts.setdefault((s["student"], s["scenario"]), []).append(s)
    gains = []
    for rows in attempts.values():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: str(r["started_at"] or ""))
        gains.append(float(rows[-1]["score"]) - float(rows[0]["score"]))
    return {
        "pairs": len(gains),
        "avg_gain": _mean(gains),
        "improved": sum(1 for g in gains if g > IMPROVEMENT_MIN_POINTS),
    }


def _empty_report() -> dict:
    return {
        "kpi": {
            "total_sessions": 0,
            "completed_sessions": 0,
            "avg_score": None,
            "students_count": 0,
            "period_days": 0,
            "reviewed": {"count": 0, "ai_avg": None, "teacher_avg": None},
            "outcomes": {"decided": 0, "passed": 0, "rate": None},
            "to_evaluate": 0,
            "improvement": {"pairs": 0, "avg_gain": None, "improved": 0},
        },
        "score_distribution": [],
        "top_improvement_titles": [],
        "sessions": [],
    }


def _score_buckets(scores: list[float]) -> list[dict]:
    buckets = [
        ("0-20", 0, 20),
        ("20-40", 20, 40),
        ("40-60", 40, 60),
        ("60-80", 60, 80),
        ("80-100", 80, 101),  # inclusive upper bound for 100
    ]
    out = []
    for label, lo, hi in buckets:
        n = sum(1 for s in scores if lo <= s < hi)
        out.append({"label": label, "count": n})
    return out


def _top_improvements(session_names: list[str], limit: int = 5) -> list[dict]:
    if not session_names:
        return []
    debrief_names = frappe.get_all(
        "LMSA Simulation Debrief",
        filters={"session": ["in", session_names], "status": "Ready"},
        pluck="name",
    )
    if not debrief_names:
        return []
    rows = frappe.db.sql(
        """
        SELECT title, COUNT(*) AS occurrences
        FROM `tabLMSA Debrief Improvement`
        WHERE parent IN %(parents)s AND parenttype = 'LMSA Simulation Debrief'
            -- the AI's rows: the teacher version keeps its own in review_improvements
            AND parentfield = 'improvements'
        GROUP BY title
        ORDER BY occurrences DESC
        LIMIT %(limit)s
        """,
        {"parents": tuple(debrief_names), "limit": limit},
        as_dict=True,
    )
    return rows or []


# ---------- Scenario / Evaluation Schema CRUD for the SPA panel ----------


@frappe.whitelist()
def list_my_scenarios(course: str | None = None) -> list[dict]:
    """All scenarios (any status) of the courses whose simulations the user
    manages."""
    managed = access.managed_courses()
    if managed is None:
        filters = {"lms_course": course} if course else {}
    else:
        if course:
            managed &= {course}
        if not managed:
            return []
        filters = {"lms_course": ["in", list(managed)]}
    return frappe.get_all(
        "LMSA Simulation Scenario",
        filters=filters,
        fields=[
            "name",
            "scenario_name",
            "lms_course",
            "course_lesson",
            "difficulty",
            "modality",
            "status",
            "modified",
        ],
        order_by="modified desc",
    )


@frappe.whitelist()
def list_my_evaluation_schemas() -> list[dict]:
    """Evaluation schemas the user may pick: their own, the shared ones and
    those the scenarios of their courses use (a colleague's scenario keeps
    its schema on save); everyone's for full access."""
    fields = ["name", "schema_name", "scoring_scale", "passing_threshold", "is_shared"]
    managed = access.managed_courses()
    if managed is None:
        return frappe.get_all("LMSA Evaluation Schema", fields=fields, order_by="modified desc")

    names = set(
        frappe.get_all(
            "LMSA Evaluation Schema",
            or_filters=[["owner", "=", frappe.session.user], ["is_shared", "=", 1]],
            pluck="name",
        )
    ) | _schemas_used_by_courses(managed)
    if not names:
        return []
    return frappe.get_all(
        "LMSA Evaluation Schema",
        filters={"name": ["in", list(names)]},
        fields=fields,
        order_by="modified desc",
    )


def _schemas_used_by_courses(courses: set[str]) -> set[str]:
    if not courses:
        return set()
    return {
        name
        for name in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"lms_course": ["in", list(courses)]},
            pluck="evaluation_schema",
        )
        if name
    }


@frappe.whitelist()
def get_scenario(name: str) -> dict:
    """Return a scenario with all its child rows. Used by the editor on load."""
    if not frappe.db.exists("LMSA Simulation Scenario", name):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)
    doc = frappe.get_doc("LMSA Simulation Scenario", name)
    _ensure_can_manage_course(doc.lms_course)
    return {
        "name": doc.name,
        "scenario_name": doc.scenario_name,
        "lms_course": doc.lms_course,
        "course_lesson": doc.course_lesson,
        "difficulty": doc.difficulty,
        "modality": doc.modality,
        "status": doc.status,
        "roleplay_persona": doc.roleplay_persona,
        "situation_template": doc.situation_template,
        "student_brief": doc.get("student_brief"),
        "evaluation_schema": doc.evaluation_schema,
        "has_human_outcome": doc.has_human_outcome,
        "max_turns": doc.max_turns,
        "time_limit_minutes": doc.time_limit_minutes,
        "provider_override": doc.provider_override,
        "model_override": doc.model_override,
        "learning_objectives": [
            {"objective_text": r.objective_text, "weight": r.weight}
            for r in (doc.learning_objectives or [])
        ],
        "seed_variations": [
            {"variable_name": r.variable_name, "possible_values": r.possible_values}
            for r in (doc.seed_variations or [])
        ],
    }


@frappe.whitelist(methods=["POST"])
def save_scenario(payload: dict) -> dict:
    """Create or update a scenario. The payload mirrors `get_scenario`'s shape.

    Returns `{name, updated}`. The `name` field is empty when creating.
    """
    if not isinstance(payload, dict):
        frappe.throw(_("payload must be an object"))

    course = payload.get("lms_course")
    if not course:
        frappe.throw(_("lms_course is required"))
    _ensure_can_manage_course(course)

    name = payload.get("name")
    if name and frappe.db.exists("LMSA Simulation Scenario", name):
        doc = frappe.get_doc("LMSA Simulation Scenario", name)
        # Forbid moving a scenario to a course you don't instruct
        if doc.lms_course != course:
            _ensure_can_manage_course(doc.lms_course)
    else:
        doc = frappe.new_doc("LMSA Simulation Scenario")

    for field in (
        "scenario_name",
        "lms_course",
        "course_lesson",
        "difficulty",
        "modality",
        "status",
        "roleplay_persona",
        "situation_template",
        "student_brief",
        "evaluation_schema",
        "has_human_outcome",
        "max_turns",
        "time_limit_minutes",
        "provider_override",
        "model_override",
    ):
        if field in payload:
            doc.set(field, payload[field])

    doc.set("learning_objectives", [])
    for row in payload.get("learning_objectives") or []:
        if not row.get("objective_text"):
            continue
        doc.append("learning_objectives", {
            "objective_text": row["objective_text"],
            "weight": row.get("weight") or 0,
        })

    doc.set("seed_variations", [])
    for row in payload.get("seed_variations") or []:
        if not row.get("variable_name"):
            continue
        doc.append("seed_variations", {
            "variable_name": row["variable_name"],
            "possible_values": row.get("possible_values") or "",
        })

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "updated": True}


@frappe.whitelist(methods=["POST"])
def delete_scenario(name: str) -> dict:
    if not frappe.db.exists("LMSA Simulation Scenario", name):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)
    course = frappe.db.get_value("LMSA Simulation Scenario", name, "lms_course")
    _ensure_can_manage_course(course)
    if frappe.db.exists("LMSA Simulation Session", {"scenario": name}):
        frappe.throw(
            _("Cannot delete a scenario that has sessions. Archive it instead."),
            frappe.ValidationError,
        )
    frappe.delete_doc("LMSA Simulation Scenario", name, force=True, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": name}


def _set_scenario_status(name: str, status: str) -> dict:
    if not frappe.db.exists("LMSA Simulation Scenario", name):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)
    course = frappe.db.get_value("LMSA Simulation Scenario", name, "lms_course")
    _ensure_can_manage_course(course)
    frappe.db.set_value("LMSA Simulation Scenario", name, "status", status)
    frappe.db.commit()
    return {"name": name, "status": status}


@frappe.whitelist(methods=["POST"])
def archive_scenario(name: str) -> dict:
    """Move a scenario to the Archived state. Unlike delete, this is safe on
    scenarios that already have sessions — the history stays intact, the
    scenario just can't be started anymore."""
    return _set_scenario_status(name, "Archived")


@frappe.whitelist(methods=["POST"])
def publish_scenario(name: str) -> dict:
    """Bring an archived scenario back to the Published state so learners can
    start it again."""
    return _set_scenario_status(name, "Published")


@frappe.whitelist()
def get_evaluation_schema(name: str) -> dict:
    if not frappe.db.exists("LMSA Evaluation Schema", name):
        frappe.throw(_("Evaluation schema not found"), frappe.DoesNotExistError)
    doc = frappe.get_doc("LMSA Evaluation Schema", name)
    # The same schemas list_my_evaluation_schemas offers
    managed = access.managed_courses()
    if not (
        managed is None
        or doc.owner == frappe.session.user
        or doc.is_shared
        or doc.name in _schemas_used_by_courses(managed)
    ):
        frappe.throw(_("You cannot view this evaluation schema"), frappe.PermissionError)
    return {
        "name": doc.name,
        "schema_name": doc.schema_name,
        "description": doc.description,
        "scoring_scale": doc.scoring_scale,
        "passing_threshold": doc.passing_threshold,
        "is_shared": bool(doc.is_shared),
        "criteria": [
            {
                "criterion_name": c.criterion_name,
                "description": c.description,
                "weight": c.weight,
                "observable_behaviors": c.observable_behaviors,
            }
            for c in (doc.criteria or [])
        ],
    }


@frappe.whitelist(methods=["POST"])
def save_evaluation_schema(payload: dict) -> dict:
    """Create or update an evaluation schema. Server enforces weight-sum=1.0 via doctype validate()."""
    if not isinstance(payload, dict):
        frappe.throw(_("payload must be an object"))
    _ensure_can_author()

    name = payload.get("name")
    is_update = bool(name)

    if is_update:
        if not frappe.db.exists("LMSA Evaluation Schema", name):
            # Fail loudly instead of silently falling back to "create" — that's
            # how we used to end up with duplicate schemas on every save.
            frappe.throw(
                _("Evaluation schema {0} not found").format(name),
                frappe.DoesNotExistError,
            )
        doc = frappe.get_doc("LMSA Evaluation Schema", name)
        if doc.owner != frappe.session.user and not access.has_full_access():
            frappe.throw(_("You cannot modify this evaluation schema"), frappe.PermissionError)
    else:
        doc = frappe.new_doc("LMSA Evaluation Schema")

    # `schema_name` drives autoname for new docs; for existing docs we apply it
    # via `frappe.rename_doc` after the save so links stay consistent.
    new_schema_name = payload.get("schema_name")
    for field in ("schema_name", "description", "scoring_scale", "passing_threshold", "is_shared"):
        if field in payload:
            doc.set(field, payload[field])

    doc.set("criteria", [])
    for row in payload.get("criteria") or []:
        if not row.get("criterion_name"):
            continue
        doc.append("criteria", {
            "criterion_name": row["criterion_name"],
            "description": row.get("description") or "",
            "weight": row.get("weight") or 0,
            "observable_behaviors": row.get("observable_behaviors") or "",
        })

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
        # Keep `name` aligned with `schema_name` since autoname is field-based.
        # Without this, an instructor renaming a schema would leave the docname
        # frozen at the old value while the displayed name drifts.
        if new_schema_name and new_schema_name != doc.name:
            new_name = frappe.rename_doc(
                "LMSA Evaluation Schema",
                doc.name,
                new_schema_name,
                merge=False,
                ignore_permissions=True,
            )
            doc = frappe.get_doc(
                "LMSA Evaluation Schema",
                new_name if isinstance(new_name, str) else doc.name,
            )
    frappe.db.commit()
    return {"name": doc.name, "updated": True}


@frappe.whitelist(methods=["POST"])
def delete_evaluation_schema(name: str) -> dict:
    if not frappe.db.exists("LMSA Evaluation Schema", name):
        frappe.throw(_("Evaluation schema not found"), frappe.DoesNotExistError)
    if frappe.db.exists("LMSA Simulation Scenario", {"evaluation_schema": name}):
        frappe.throw(
            _("Cannot delete a evaluation schema used by one or more scenarios."),
            frappe.ValidationError,
        )
    owner = frappe.db.get_value("LMSA Evaluation Schema", name, "owner")
    if owner != frappe.session.user and not access.has_full_access():
        frappe.throw(_("Only the owner can delete this evaluation schema"), frappe.PermissionError)
    frappe.delete_doc("LMSA Evaluation Schema", name, force=True, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": name}


# ---------- AI authoring helpers ----------


@frappe.whitelist(methods=["POST"])
def ai_generate_scenario(
    course: str, lesson: str | None = None, hint: str = ""
) -> dict:
    """Generate a scenario payload via LLM and return it to the editor.

    The payload mirrors ``save_scenario``'s input shape (minus ``lms_course``,
    ``course_lesson`` and ``evaluation_schema``, which the editor already
    holds). Nothing is persisted — the user reviews and explicitly saves.
    """
    if not course:
        frappe.throw(_("course is required"))
    _ensure_can_manage_course(course)

    from .authoring_ai import generate_scenario_payload

    payload = generate_scenario_payload(
        course=course, lesson=lesson or None, hint=hint or ""
    )
    return {"payload": payload}


@frappe.whitelist(methods=["POST"])
def ai_generate_student_brief(payload: dict) -> dict:
    """Generate the student_brief ("compito") from the current editor state.

    ``payload`` mirrors the scenario editor model (roleplay_persona,
    situation_template, learning_objectives, seed_variations, difficulty,
    optional provider/model overrides). Returns ``{"student_brief": ...}``.
    Nothing is persisted — the instructor reviews and saves.
    """
    if not isinstance(payload, dict):
        frappe.throw(_("payload must be an object"))

    course = payload.get("lms_course")
    if course:
        _ensure_can_manage_course(course)
    else:
        _ensure_can_author()

    from .authoring_ai import generate_student_brief

    objectives = [
        (row.get("objective_text") or "").strip()
        for row in (payload.get("learning_objectives") or [])
        if isinstance(row, dict)
    ]
    objectives = [o for o in objectives if o]
    variations = {
        (row.get("variable_name") or "").strip(): [
            v.strip()
            for v in (row.get("possible_values") or "").splitlines()
            if v.strip()
        ]
        for row in (payload.get("seed_variations") or [])
        if isinstance(row, dict) and (row.get("variable_name") or "").strip()
    }

    brief = generate_student_brief(
        scenario_name=payload.get("scenario_name") or "",
        roleplay_persona=payload.get("roleplay_persona") or "",
        situation_template=payload.get("situation_template") or "",
        learning_objectives=objectives,
        seed_variations=variations,
        difficulty=payload.get("difficulty") or "medium",
        provider_override=payload.get("provider_override") or "auto",
        model_override=payload.get("model_override") or "",
    )
    return {"student_brief": brief}


@frappe.whitelist(methods=["POST"])
def ai_generate_evaluation_schema(
    hint: str = "", course: str | None = None, lesson: str | None = None
) -> dict:
    """Generate an evaluation-schema payload via LLM and return it.

    ``course`` and ``lesson`` are optional: when provided they unlock RAG
    context retrieval, otherwise the LLM relies purely on ``hint`` and the
    system prompt. Nothing is persisted.
    """
    _ensure_can_author()
    if course:
        # When a course is supplied, enforce it belongs to the user.
        _ensure_can_manage_course(course)

    from .authoring_ai import generate_evaluation_schema_payload

    payload = generate_evaluation_schema_payload(
        hint=hint or "", course=course or None, lesson=lesson or None
    )
    return {"payload": payload}


@frappe.whitelist()
def get_transcript(session_id: str) -> dict:
    """Read-only transcript + debrief lookup for the instructor drill-down."""
    session = load_session(session_id)
    if session.student != frappe.session.user and not access.can_review(
        session.course, session.student
    ):
        # Unreachable while load_session lets in only owners and reviewers;
        # kept so the drill-down stays closed if that ever changes.
        frappe.throw(_("You cannot review this session"), frappe.PermissionError)
    turns = frappe.get_all(
        "LMSA Simulation Turn",
        filters={"session": session.name},
        fields=["name", "turn_index", "role", "text_content", "injection_attempt_detected"],
        order_by="turn_index asc",
    )
    debrief_name = frappe.db.get_value(
        "LMSA Simulation Debrief", {"session": session.name}, "name"
    )
    return {
        "session": {
            "name": session.name,
            "scenario": session.scenario,
            "course": session.course,
            "student": session.student,
            "status": session.status,
            "generated_persona": session.generated_persona,
            "generated_situation": session.generated_situation,
            "turn_count": session.turn_count,
            "started_at": str(session.started_at) if session.started_at else None,
            "ended_at": str(session.ended_at) if session.ended_at else None,
        },
        "turns": turns,
        "debrief": _serialize_debrief(
            frappe.get_doc("LMSA Simulation Debrief", debrief_name),
            reviewer=_is_reviewer(session),
        )
        if debrief_name
        else None,
    }
