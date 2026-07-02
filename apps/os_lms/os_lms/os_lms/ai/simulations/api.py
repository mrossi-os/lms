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

from lms.lms.utils import has_course_instructor_role, has_moderator_role, is_instructor

from os_lms.os_lms.ai.audio.pipeline import run_audio_turn

from .orchestrator import (
    QuotaExceededError,
    SessionOrchestrator,
    SessionTerminatedError,
)
from .tasks import generate_debrief as _run_generate_debrief


def _service() -> SessionOrchestrator:
    return SessionOrchestrator()


def _instructor_courses(user: str | None = None) -> list[str]:
    """Return the list of course names where `user` is registered as instructor."""
    user = user or frappe.session.user
    return frappe.get_all(
        "Course Instructor", filters={"instructor": user}, pluck="parent"
    )


def _ensure_instructor_of_course(course: str) -> None:
    """Raise PermissionError if the current user is neither moderator nor an
    instructor of the given course."""
    if has_moderator_role():
        return
    if not has_course_instructor_role() or not is_instructor(course):
        frappe.throw(
            _("You are not an instructor of this course"), frappe.PermissionError
        )


def load_session(session_id: str):
    """Resolve a Session and gate access. Mirrors `load_lesson` in ai/api.py.

    Returns the Document on success. Throws PermissionError otherwise.
    """
    if not session_id or not frappe.db.exists("LMSA Simulation Session", session_id):
        frappe.throw(_("Simulation session not found"), frappe.DoesNotExistError)

    session = frappe.get_doc("LMSA Simulation Session", session_id)
    user = frappe.session.user

    if has_moderator_role():
        return session
    if user == session.student:
        return session
    if has_course_instructor_role() and session.course and is_instructor(session.course):
        return session

    frappe.throw(
        _("You don't have permission to access this simulation session"),
        frappe.PermissionError,
    )


def _resolve_published_scenario(scenario_id: str):
    """Load a Published scenario and gate by enrollment / instructor role."""
    if not scenario_id or not frappe.db.exists("LMSA Simulation Scenario", scenario_id):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)

    scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
    user = frappe.session.user

    if has_moderator_role():
        return scenario
    if has_course_instructor_role() and is_instructor(scenario.lms_course):
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


@frappe.whitelist()
def start_session(scenario_id: str, modality: str = "chat") -> dict:
    """Create a Session for the current user and return the first role-player turn."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    try:
        result = _service().start_session(scenario_id=scenario.name, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return dict(result)


@frappe.whitelist()
def prepare_session(scenario_id: str, modality: str = "chat") -> dict:
    """Phase 1: generate the variant and create a Ready session with a brief."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    if modality == "chat" and scenario.modality not in ("chat", "both"):
        frappe.throw(_("Scenario {0} is not chat-enabled.").format(scenario.name))
    if modality == "voice" and scenario.modality not in ("voice", "both"):
        frappe.throw(_("Scenario {0} is not voice-enabled.").format(scenario.name))

    try:
        result = _service().prepare_session(scenario_id=scenario.name, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}


@frappe.whitelist()
def begin_session(session_id: str) -> dict:
    """Phase 2 (chat): persist the first role-player turn for a prepared session."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can begin the session"), frappe.PermissionError)
    return dict(_service().begin_chat_session(session_id=session.name))


@frappe.whitelist()
def clone_session(session_id: str) -> dict:
    """Restart a session: create a new Ready session reusing the same variant."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can restart it"), frappe.PermissionError)
    result = _service().clone_session(session_id=session.name)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}


@frappe.whitelist()
def send_message(session_id: str, text: str) -> dict:
    """Append a user turn and return the assistant's reply."""
    if not text or not text.strip():
        frappe.throw(_("Message cannot be empty"))

    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(
            _("Only the session owner can send messages"), frappe.PermissionError
        )

    try:
        result = _service().send_message(session_id=session.name, user_text=text)
    except SessionTerminatedError:
        frappe.throw(
            _("This session is no longer accepting messages"), frappe.ValidationError
        )
    return dict(result)


@frappe.whitelist()
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

    holder: dict = {}

    def _produce(q: str) -> str:
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


@frappe.whitelist()
def end_session(session_id: str, reason: str = "completed") -> dict:
    """Mark a session as completed or abandoned."""
    if reason not in ("completed", "abandoned"):
        frappe.throw(_("Unsupported reason: {0}").format(reason))

    session = load_session(session_id)
    if session.student != frappe.session.user and not has_moderator_role():
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
    return _serialize_debrief(debrief)


@frappe.whitelist()
def generate_debrief(session_id: str) -> dict:
    """Run Prompt 3 for `session_id` synchronously and return the debrief payload.

    Designed for manual triggers from the SPA panel ("rigenera debrief") and
    for bench execute. The async path uses `tasks.generate_debrief` directly
    via `frappe.enqueue`.
    """
    if not session_id:
        frappe.throw(_("session_id is required"))

    session = load_session(session_id)
    # Only the owner, course instructors and moderators can trigger a regen.
    if session.student != frappe.session.user and not has_moderator_role():
        _ensure_instructor_of_course(session.course)

    name = _run_generate_debrief(session.name)
    debrief = frappe.get_doc("LMSA Simulation Debrief", name)
    return _serialize_debrief(debrief)



def _serialize_debrief(debrief) -> dict:
    return {
        "status": debrief.status.lower().replace(" ", "_"),
        "session": debrief.session,
        "name": debrief.name,
        "course": debrief.course,
        "overall_score": debrief.overall_score,
        "passed": bool(debrief.passed),
        "behavioral_analysis": debrief.behavioral_analysis,
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
        "instructor_review": debrief.instructor_review or "",
        "instructor_reviewed_by": debrief.instructor_reviewed_by,
        "instructor_reviewed_at": (
            str(debrief.instructor_reviewed_at) if debrief.instructor_reviewed_at else None
        ),
    }


@frappe.whitelist()
def list_scenarios(course: str | None = None) -> list[dict]:
    """List Published scenarios accessible to the current user.

    - Students: scenarios of courses they are enrolled in.
    - Instructors of the course: all scenarios of that course (any status).
    - Moderator / sysadmin: all scenarios (filtered by `course` if provided).
    """
    user = frappe.session.user
    filters: dict = {}
    if course:
        filters["lms_course"] = course

    if has_moderator_role():
        return frappe.get_all(
            "LMSA Simulation Scenario",
            filters=filters,
            fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality", "status"],
            order_by="modified desc",
        )

    if has_course_instructor_role():
        # Restrict to courses the user instructs
        instructor_courses = frappe.get_all(
            "Course Instructor", filters={"instructor": user}, pluck="parent"
        )
        if course and course not in instructor_courses:
            instructor_courses = [c for c in instructor_courses if c == course]
        if instructor_courses:
            filters["lms_course"] = ["in", instructor_courses] if not course else course
            return frappe.get_all(
                "LMSA Simulation Scenario",
                filters=filters,
                fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality", "status"],
                order_by="modified desc",
            )

    # Student path: enrolled courses + Published scenarios
    enrolled = frappe.get_all(
        "LMS Enrollment", filters={"member": user}, pluck="course"
    )
    if not enrolled:
        return []
    filters["status"] = "Published"
    if course:
        if course not in enrolled:
            return []
    else:
        filters["lms_course"] = ["in", enrolled]
    return frappe.get_all(
        "LMSA Simulation Scenario",
        filters=filters,
        fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality"],
        order_by="modified desc",
    )


@frappe.whitelist()
def list_my_sessions(course: str | None = None) -> list[dict]:
    """List the current user's own simulation sessions (optionally by course),
    enriched with the debrief score/status when available."""
    filters: dict = {"student": frappe.session.user}
    if course:
        filters["course"] = course

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
    titles = {
        r["name"]: r["scenario_name"]
        for r in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"name": ["in", list(scenario_names)]},
            fields=["name", "scenario_name"],
        )
    }
    debriefs = {
        d["session"]: d
        for d in frappe.get_all(
            "LMSA Simulation Debrief",
            filters={"session": ["in", [s["name"] for s in sessions]]},
            fields=["session", "overall_score", "passed", "status"],
        )
    }

    for s in sessions:
        s["scenario_name"] = titles.get(s["scenario"], s["scenario"])
        s["started_at"] = str(s["started_at"]) if s["started_at"] else None
        s["ended_at"] = str(s["ended_at"]) if s["ended_at"] else None
        d = debriefs.get(s["name"])
        s["overall_score"] = d["overall_score"] if d else None
        s["passed"] = bool(d["passed"]) if d else None
        s["debrief_status"] = d["status"] if d else None
    return sessions


# ============================================================================
# Instructor endpoints (DOC-4.*)
#
# These power the SPA Vue panel for instructors / moderators. They never go
# through the Desk: the panel is the only supported UI for instructors per
# decision #10 in PROGRESS.md.
# ============================================================================


@frappe.whitelist()
def instructor_review_debrief(session_id: str, review: str) -> dict:
    """Persist the instructor's review note on the debrief of `session_id`."""
    if not review or not review.strip():
        frappe.throw(_("Review cannot be empty"))

    session = load_session(session_id)
    _ensure_instructor_of_course(session.course)

    name = frappe.db.get_value("LMSA Simulation Debrief", {"session": session.name}, "name")
    if not name:
        frappe.throw(_("No debrief available for this session yet"))

    debrief = frappe.get_doc("LMSA Simulation Debrief", name)
    debrief.instructor_review = review.strip()
    debrief.instructor_reviewed_by = frappe.session.user
    debrief.instructor_reviewed_at = frappe.utils.now_datetime()
    debrief.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": debrief.name, "reviewed_at": str(debrief.instructor_reviewed_at)}


@frappe.whitelist()
def instructor_report(
    course: str | None = None,
    student: str | None = None,
    period_days: int = 30,
    scenario: str | None = None,
) -> dict:
    """Aggregated report + sessions list for the courses the user instructs.

    Returns:
      - `kpi`: total_sessions, completed_sessions, avg_score, pass_rate, students_count
      - `score_distribution`: bucketed counts (0-20, 20-40, ...)
      - `top_improvement_titles`: most frequent improvement titles
      - `sessions`: list of session rows with score + status + scenario + student
    """
    allowed_courses = _allowed_report_courses()
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
    session_names = [s["name"] for s in sessions]

    debriefs_by_session: dict[str, dict] = {}
    if session_names:
        for d in frappe.get_all(
            "LMSA Simulation Debrief",
            filters={"session": ["in", session_names]},
            fields=["name", "session", "status", "overall_score", "passed"],
        ):
            debriefs_by_session[d["session"]] = d

    enriched = []
    scores: list[float] = []
    passed_count = 0
    completed_count = 0
    students_seen: set[str] = set()
    for s in sessions:
        d = debriefs_by_session.get(s["name"]) or {}
        s = dict(s)
        s["debrief"] = d.get("name")
        s["overall_score"] = d.get("overall_score")
        s["passed"] = bool(d.get("passed"))
        s["debrief_status"] = d.get("status")
        enriched.append(s)
        students_seen.add(s["student"])
        if s["status"] == "Completed":
            completed_count += 1
        if d.get("overall_score") is not None:
            scores.append(float(d["overall_score"]))
            if d.get("passed"):
                passed_count += 1

    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    pass_rate = round((passed_count / len(scores)) * 100, 1) if scores else None

    return {
        "kpi": {
            "total_sessions": len(sessions),
            "completed_sessions": completed_count,
            "avg_score": avg_score,
            "pass_rate": pass_rate,
            "students_count": len(students_seen),
            "period_days": period_days,
        },
        "score_distribution": _score_buckets(scores),
        "top_improvement_titles": _top_improvements(session_names),
        "sessions": enriched,
    }


def _allowed_report_courses() -> set[str]:
    if has_moderator_role():
        return set(frappe.get_all("LMS Course", pluck="name"))
    return set(_instructor_courses())


def _empty_report() -> dict:
    return {
        "kpi": {
            "total_sessions": 0,
            "completed_sessions": 0,
            "avg_score": None,
            "pass_rate": None,
            "students_count": 0,
            "period_days": 0,
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
    """All scenarios for courses the user instructs (any status)."""
    allowed = _allowed_report_courses()
    if not allowed:
        return []
    filters = {"lms_course": ["in", list(allowed)]}
    if course:
        if course not in allowed:
            return []
        filters["lms_course"] = course
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
    """Evaluation Schemas: instructors see their own + shared ones; moderators see all."""
    if has_moderator_role():
        return frappe.get_all(
            "LMSA Evaluation Schema",
            fields=["name", "schema_name", "scoring_scale", "passing_threshold", "is_shared"],
            order_by="modified desc",
        )

    user = frappe.session.user
    return frappe.get_all(
        "LMSA Evaluation Schema",
        filters=[["owner", "=", user]],
        fields=["name", "schema_name", "scoring_scale", "passing_threshold", "is_shared"],
        order_by="modified desc",
    ) + frappe.get_all(
        "LMSA Evaluation Schema",
        filters=[["is_shared", "=", 1], ["owner", "!=", user]],
        fields=["name", "schema_name", "scoring_scale", "passing_threshold", "is_shared"],
        order_by="modified desc",
    )


@frappe.whitelist()
def get_scenario(name: str) -> dict:
    """Return a scenario with all its child rows. Used by the editor on load."""
    if not frappe.db.exists("LMSA Simulation Scenario", name):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)
    doc = frappe.get_doc("LMSA Simulation Scenario", name)
    _ensure_instructor_of_course(doc.lms_course)
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
        "evaluation_schema": doc.evaluation_schema,
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


@frappe.whitelist()
def save_scenario(payload: dict) -> dict:
    """Create or update a scenario. The payload mirrors `get_scenario`'s shape.

    Returns `{name, updated}`. The `name` field is empty when creating.
    """
    if not isinstance(payload, dict):
        frappe.throw(_("payload must be an object"))

    course = payload.get("lms_course")
    if not course:
        frappe.throw(_("lms_course is required"))
    _ensure_instructor_of_course(course)

    name = payload.get("name")
    if name and frappe.db.exists("LMSA Simulation Scenario", name):
        doc = frappe.get_doc("LMSA Simulation Scenario", name)
        # Forbid moving a scenario to a course you don't instruct
        if doc.lms_course != course:
            _ensure_instructor_of_course(doc.lms_course)
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
        "evaluation_schema",
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


@frappe.whitelist()
def delete_scenario(name: str) -> dict:
    if not frappe.db.exists("LMSA Simulation Scenario", name):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)
    course = frappe.db.get_value("LMSA Simulation Scenario", name, "lms_course")
    _ensure_instructor_of_course(course)
    if frappe.db.exists("LMSA Simulation Session", {"scenario": name}):
        frappe.throw(
            _("Cannot delete a scenario that has sessions. Archive it instead."),
            frappe.ValidationError,
        )
    frappe.delete_doc("LMSA Simulation Scenario", name, force=True, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": name}


@frappe.whitelist()
def get_evaluation_schema(name: str) -> dict:
    if not frappe.db.exists("LMSA Evaluation Schema", name):
        frappe.throw(_("Evaluation schema not found"), frappe.DoesNotExistError)
    doc = frappe.get_doc("LMSA Evaluation Schema", name)
    # Schemas: owner OR moderator OR shared
    user = frappe.session.user
    if not has_moderator_role() and doc.owner != user and not doc.is_shared:
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


@frappe.whitelist()
def save_evaluation_schema(payload: dict) -> dict:
    """Create or update an evaluation schema. Server enforces weight-sum=1.0 via doctype validate()."""
    if not isinstance(payload, dict):
        frappe.throw(_("payload must be an object"))
    if not has_course_instructor_role() and not has_moderator_role():
        frappe.throw(_("Only instructors can manage evaluation schemas"), frappe.PermissionError)

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
        if doc.owner != frappe.session.user and not has_moderator_role():
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


@frappe.whitelist()
def delete_evaluation_schema(name: str) -> dict:
    if not frappe.db.exists("LMSA Evaluation Schema", name):
        frappe.throw(_("Evaluation schema not found"), frappe.DoesNotExistError)
    if frappe.db.exists("LMSA Simulation Scenario", {"evaluation_schema": name}):
        frappe.throw(
            _("Cannot delete a evaluation schema used by one or more scenarios."),
            frappe.ValidationError,
        )
    owner = frappe.db.get_value("LMSA Evaluation Schema", name, "owner")
    if owner != frappe.session.user and not has_moderator_role():
        frappe.throw(_("Only the owner can delete this evaluation schema"), frappe.PermissionError)
    frappe.delete_doc("LMSA Evaluation Schema", name, force=True, ignore_permissions=True)
    frappe.db.commit()
    return {"deleted": name}


# ---------- AI authoring helpers ----------


@frappe.whitelist()
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
    _ensure_instructor_of_course(course)

    from .authoring_ai import generate_scenario_payload

    payload = generate_scenario_payload(
        course=course, lesson=lesson or None, hint=hint or ""
    )
    return {"payload": payload}


@frappe.whitelist()
def ai_generate_evaluation_schema(
    hint: str = "", course: str | None = None, lesson: str | None = None
) -> dict:
    """Generate an evaluation-schema payload via LLM and return it.

    ``course`` and ``lesson`` are optional: when provided they unlock RAG
    context retrieval, otherwise the LLM relies purely on ``hint`` and the
    system prompt. Nothing is persisted.
    """
    if not has_course_instructor_role() and not has_moderator_role():
        frappe.throw(
            _("Only instructors can generate evaluation schemas"),
            frappe.PermissionError,
        )
    if course:
        # When a course is supplied, enforce it belongs to the user.
        _ensure_instructor_of_course(course)

    from .authoring_ai import generate_evaluation_schema_payload

    payload = generate_evaluation_schema_payload(
        hint=hint or "", course=course or None, lesson=lesson or None
    )
    return {"payload": payload}


@frappe.whitelist()
def get_transcript(session_id: str) -> dict:
    """Read-only transcript + debrief lookup for the instructor drill-down."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        # Drill-down is only for moderators and the course's instructors.
        if not has_moderator_role():
            _ensure_instructor_of_course(session.course)
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
        "debrief": _serialize_debrief(frappe.get_doc("LMSA Simulation Debrief", debrief_name))
        if debrief_name
        else None,
    }
