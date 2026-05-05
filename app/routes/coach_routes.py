"""
coach_routes.py — Coach portal blueprint for Ufit Motion.

All routes require a coach-group role:
  head_coach, assistant_coach, site_coordinator, coach_overseer

Route inventory:
  GET/POST  /api/sessions
  GET/POST  /api/eod-reports
  GET/POST  /api/incidents
  GET/POST  /api/assessments
  GET       /api/my-students
"""

import datetime
import math
import re
import sys
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, jsonify, request

from app.auth import admin_required, coach_required, current_user, login_required, roles_required
from app.database import get_db
from app.extensions import limiter
from app.routes._helpers import (
    audit, now_utc, parse_json,
    serialize_assessment, serialize_assessment_score,
    serialize_eod_report, serialize_incident, serialize_session, serialize_student,
)
from app.routes._scoring import (
    normalized_score as compute_normalized_score,
    recalculate_student_summaries,
    VALID_OBSERVATION_TAGS,
)

coach_bp = Blueprint("coach", __name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_SESSION_TYPES = frozenset({"regular", "makeup", "enrichment", "assessment"})
_STR_LIMITS = {
    "location": 200,
    "planned_activity": 500,
    "actual_activity": 500,
    "student_group_name": 200,
    "notes": 1000,
}
_EOD_STR_LIMITS = {
    "activities_completed": 2000,
    "student_engagement_summary": 1000,
    "attendance_summary": 500,
    "behavior_summary": 500,
    "success_story": 500,
    "challenge_summary": 500,
    "notes": 1000,
    "school_concerns": 1000,
    "school_concerns_notes": 1000,
    "schedule_changes": 500,
    "late_arrivals": 500,
    "verbal_warnings": 500,
    "hr_app_issues": 500,
    "safety_hazards": 500,
    "equipment_requests": 500,
    "principal_communication_notes": 1000,
    "ufit_standards_notes": 1000,
}

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _get_today() -> datetime.date:
    """Return today's UTC date. Monkeypatchable in tests."""
    return datetime.date.today()


def _now_pacific() -> datetime.datetime:
    """Return current Pacific wall-clock datetime. Monkeypatchable in tests."""
    return datetime.datetime.now(tz=_PACIFIC)


# ===========================================================================
# SESSIONS
# ===========================================================================

@coach_bp.route("/api/sessions", methods=["GET"])
@coach_required
def list_sessions():
    # GET /api/sessions response contains only aggregate counts, not student PII.
    # FERPA §99.2(b) audit is therefore not required here — see spec §4.3.
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    role = user["role"]
    staff_id = user.get("staff_id")

    raw_page = request.args.get("page", "1")
    raw_per_page = request.args.get("per_page", "20")
    try:
        page = int(raw_page)
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "page must be a positive integer."}), 400
    try:
        per_page = int(raw_per_page)
        if not (1 <= per_page <= 100):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "per_page must be between 1 and 100."}), 400

    today = _get_today()
    default_from = (today - datetime.timedelta(days=30)).isoformat()
    default_to = today.isoformat()
    from_date = request.args.get("from", default_from)
    to_date = request.args.get("to", default_to)

    try:
        datetime.date.fromisoformat(from_date)
        datetime.date.fromisoformat(to_date)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    if from_date > to_date:
        return jsonify({"error": "from must be before or equal to to."}), 400

    school_id_filter = request.args.get("school_id")
    if school_id_filter is not None:
        try:
            school_id_filter = int(school_id_filter)
            if school_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "school_id must be a positive integer."}), 400

    db = get_db()
    try:
        if role in ("head_coach", "assistant_coach"):
            user_school_id = user.get("school_id")
            if not user_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            scope_sql = "AND se.school_id = ?"
            scope_params = [user_school_id]
            # school_id filter is ignored for head/assistant (spec §4.1) — they only see their school

        elif role == "site_coordinator":
            sp_row = db.execute(
                "SELECT assigned_region_id FROM staff_profiles WHERE staff_id = ?",
                (staff_id,),
            ).fetchone()
            coord_region_id = sp_row["assigned_region_id"] if sp_row else None
            if not coord_region_id and user.get("school_id"):
                sc_row = db.execute(
                    "SELECT region_id FROM schools WHERE school_id = ?",
                    (user["school_id"],),
                ).fetchone()
                coord_region_id = sc_row["region_id"] if sc_row else None
            if not coord_region_id:
                return jsonify({
                    "error": "You have no active region assignment. Contact your administrator."
                }), 403
            scope_sql = "AND sc.region_id = ?"
            scope_params = [coord_region_id]
            if school_id_filter is not None:
                filter_sc = db.execute(
                    "SELECT region_id FROM schools WHERE school_id = ?",
                    (school_id_filter,),
                ).fetchone()
                if not filter_sc or filter_sc["region_id"] != coord_region_id:
                    return jsonify({"error": "You do not have access to this school."}), 403

        elif role == "coach_overseer":
            overseer_school_id = user.get("school_id")
            if not overseer_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (overseer_school_id,),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            if not org_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            scope_sql = "AND sc.organization_id = ?"
            scope_params = [org_id]
            if school_id_filter is not None:
                filter_sc = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?",
                    (school_id_filter,),
                ).fetchone()
                if not filter_sc or filter_sc["organization_id"] != org_id:
                    return jsonify({"error": "You do not have access to this school."}), 403

        else:
            scope_sql = "AND 1=0"
            scope_params = []

        # school_id filter only applies for site_coordinator and overseer (handled above)
        school_filter_sql = ""
        school_filter_params: list = []
        if school_id_filter is not None and role not in ("head_coach", "assistant_coach"):
            school_filter_sql = "AND se.school_id = ?"
            school_filter_params = [school_id_filter]

        # scope_sql and school_filter_sql contain only hardcoded SQL fragments — no user data
        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM sessions se
            JOIN schools sc ON sc.school_id = se.school_id
            WHERE se.session_date >= ? AND se.session_date <= ?
              AND se.deleted_at IS NULL
              {scope_sql}
              {school_filter_sql}
        """
        count_params = [from_date, to_date] + scope_params + school_filter_params
        total = db.execute(count_sql, count_params).fetchone()["cnt"]
        pages = math.ceil(total / per_page) if total > 0 else 0
        offset = (page - 1) * per_page

        main_sql = f"""
            SELECT se.session_id, se.school_id, sc.school_name, se.program_id, p.program_name,
                   se.session_date, se.start_time, se.end_time, se.duration_minutes, se.session_type, se.location,
                   se.planned_activity, se.actual_activity, se.student_group_name,
                   se.session_status, se.total_students_present, se.notes, se.created_at,
                   (u.first_name || ' ' || u.last_name) AS coach_name
            FROM sessions se
            JOIN schools sc ON sc.school_id = se.school_id
            JOIN programs p ON p.program_id = se.program_id AND p.deleted_at IS NULL
            LEFT JOIN session_staff ss ON ss.session_id = se.session_id AND ss.role = 'lead'
            LEFT JOIN staff_profiles sp2 ON sp2.staff_id = ss.staff_id
            LEFT JOIN users u ON u.user_id = sp2.user_id
            WHERE se.session_date >= ? AND se.session_date <= ?
              AND se.deleted_at IS NULL
              {scope_sql}
              {school_filter_sql}
            ORDER BY se.session_date DESC, se.session_id DESC
            LIMIT ? OFFSET ?
        """
        main_params = [from_date, to_date] + scope_params + school_filter_params + [per_page, offset]
        rows = db.execute(main_sql, main_params).fetchall()

        eod_set: set = set()
        if staff_id:
            eod_rows = db.execute(
                "SELECT school_id, report_date FROM eod_reports"
                " WHERE staff_id = ? AND deleted_at IS NULL",
                (staff_id,),
            ).fetchall()
            eod_set = {(r["school_id"], r["report_date"]) for r in eod_rows}

        sessions_out = []
        for row in rows:
            s = serialize_session(row)
            s["eod_filed"] = (row["school_id"], row["session_date"]) in eod_set
            sessions_out.append(s)

        return jsonify({
            "ok": True,
            "sessions": sessions_out,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        })

    except Exception as exc:
        current_app.logger.error("list_sessions ERROR: %s", exc)
        return jsonify({"error": "Could not load sessions — please try again or contact support."}), 500
    finally:
        db.close()


@coach_bp.route("/api/sessions", methods=["POST"])
@limiter.limit("20 per minute")
@coach_required
def create_session():
    data = parse_json()

    # Rule 1: school_id — required, positive integer
    school_id = data.get("school_id")
    if school_id is None:
        return jsonify({"error": "Missing required field: school_id."}), 400
    if not isinstance(school_id, int) or isinstance(school_id, bool) or school_id <= 0:
        return jsonify({"error": "school_id must be an integer."}), 400

    # Rule 2: program_id — required, positive integer
    program_id = data.get("program_id")
    if program_id is None:
        return jsonify({"error": "Missing required field: program_id."}), 400
    if not isinstance(program_id, int) or isinstance(program_id, bool) or program_id <= 0:
        return jsonify({"error": "program_id must be an integer."}), 400

    # Rule 3: session_date — required, valid ISO date
    session_date_raw = data.get("session_date")
    if not session_date_raw:
        return jsonify({"error": "Missing required field: session_date."}), 400
    try:
        session_date = datetime.date.fromisoformat(str(session_date_raw))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Rule 4: date range — not future, not > 7 days past
    today = _get_today()
    if session_date > today:
        return jsonify({"error": "Session date cannot be in the future."}), 400
    if (today - session_date).days > 7:
        return jsonify({"error": "Session date cannot be more than 7 days in the past."}), 400

    # Rule 5: start/end pairing — if either provided, both required
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    if (start_time is None) != (end_time is None):
        return jsonify({"error": "Both start_time and end_time are required if either is provided."}), 400

    # Rule 6: time format
    if start_time is not None and (not isinstance(start_time, str) or not _TIME_RE.match(start_time)):
        return jsonify({"error": "Invalid time format. Use HH:MM (24-hour)."}), 400
    if end_time is not None and (not isinstance(end_time, str) or not _TIME_RE.match(end_time)):
        return jsonify({"error": "Invalid time format. Use HH:MM (24-hour)."}), 400

    # Rule 7: start < end
    if start_time and end_time and end_time <= start_time:
        return jsonify({"error": "start_time must be before end_time."}), 400

    # Rule 8: session_type enum
    session_type = data.get("session_type", "regular")
    if session_type not in _SESSION_TYPES:
        return jsonify({
            "error": "Invalid session_type. Must be one of: regular, makeup, enrichment, assessment."
        }), 400

    # Rule 8b: duration_minutes — optional positive integer ≤ 480
    duration_minutes = data.get("duration_minutes")
    if duration_minutes is not None:
        if not isinstance(duration_minutes, int) or isinstance(duration_minutes, bool) or not (1 <= duration_minutes <= 480):
            return jsonify({"error": "duration_minutes must be an integer between 1 and 480."}), 400

    # Rule 9: string length limits
    location = data.get("location")
    planned_activity = data.get("planned_activity")
    actual_activity = data.get("actual_activity")
    student_group_name = data.get("student_group_name")
    notes = data.get("notes")
    session_status = "completed"
    for field, val in [
        ("location", location), ("planned_activity", planned_activity),
        ("actual_activity", actual_activity), ("student_group_name", student_group_name),
        ("notes", notes),
    ]:
        if val is not None and len(str(val)) > _STR_LIMITS[field]:
            return jsonify({"error": f"Field '{field}' exceeds maximum length of {_STR_LIMITS[field]} characters."}), 400

    # Rule 10: student_ids — optional, array of positive integers, no duplicates
    student_ids_raw = data.get("student_ids")
    student_ids: list = []
    if student_ids_raw is not None:
        if not isinstance(student_ids_raw, list):
            return jsonify({"error": "student_ids must be an array of positive integers."}), 400
        for sid in student_ids_raw:
            if not isinstance(sid, int) or isinstance(sid, bool) or sid <= 0:
                return jsonify({"error": "student_ids must be an array of positive integers."}), 400
        if len(student_ids_raw) != len(set(student_ids_raw)):
            return jsonify({"error": "student_ids contains duplicate values."}), 400
        student_ids = list(student_ids_raw)

    # Rule 11: staff_id must exist (data integrity guard)
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    staff_id = user.get("staff_id")
    if not staff_id:
        return jsonify({
            "error": "Staff profile missing for this account. Contact your administrator."
        }), 500

    role = user["role"]

    # Rules 12-13: head/assistant — school must match their assignment
    if role in ("head_coach", "assistant_coach"):
        user_school_id = user.get("school_id")
        if not user_school_id:
            return jsonify({
                "error": "You have no active school assignment. Contact your administrator."
            }), 403
        if school_id != user_school_id:
            return jsonify({"error": "You are not assigned to this school."}), 403

    db = get_db()
    try:
        # Rule 14: site_coordinator — region-based auth
        if role == "site_coordinator":
            sp_row = db.execute(
                "SELECT assigned_region_id FROM staff_profiles WHERE staff_id = ?",
                (staff_id,),
            ).fetchone()
            coord_region_id = sp_row["assigned_region_id"] if sp_row else None
            if not coord_region_id and user.get("school_id"):
                sc_row = db.execute(
                    "SELECT region_id FROM schools WHERE school_id = ?",
                    (user["school_id"],),
                ).fetchone()
                coord_region_id = sc_row["region_id"] if sc_row else None
            if not coord_region_id:
                return jsonify({
                    "error": "You have no active region assignment. Contact your administrator."
                }), 403
            target_sc = db.execute(
                "SELECT region_id FROM schools WHERE school_id = ? AND deleted_at IS NULL",
                (school_id,),
            ).fetchone()
            if not target_sc or target_sc["region_id"] != coord_region_id:
                return jsonify({"error": "This school is not in your region."}), 403

        # Rule 15: coach_overseer — org-based auth
        elif role == "coach_overseer":
            overseer_school_id = user.get("school_id")
            if not overseer_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (overseer_school_id,),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            if not org_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            target_sc = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ? AND deleted_at IS NULL",
                (school_id,),
            ).fetchone()
            if not target_sc or target_sc["organization_id"] != org_id:
                return jsonify({"error": "School is not in your organization."}), 403

        # Rule 16: program must be active at this school
        prog_row = db.execute(
            "SELECT program_id FROM programs"
            " WHERE program_id = ? AND school_id = ? AND program_status = 'active' AND deleted_at IS NULL",
            (program_id, school_id),
        ).fetchone()
        if not prog_row:
            return jsonify({"error": "Program not found at this school."}), 400

        # Rule 17: each student_id must be active at this school
        if student_ids:
            # placeholders contains only "?" repetitions — no user data interpolated
            placeholders = ",".join("?" * len(student_ids))
            valid_rows = db.execute(
                f"SELECT student_id FROM students"
                f" WHERE student_id IN ({placeholders})"
                f" AND school_id = ? AND active_status = 1 AND deleted_at IS NULL",
                (*student_ids, school_id),
            ).fetchall()
            valid_set = {r["student_id"] for r in valid_rows}
            invalid_ids = sorted(sid for sid in student_ids if sid not in valid_set)
            if invalid_ids:
                return jsonify({"error": f"Invalid student IDs: {invalid_ids}"}), 400

        # Rule 18: duplicate guard — same coach + school + program + date
        dup_row = db.execute(
            """SELECT s.session_id FROM sessions s
               JOIN session_staff ss ON ss.session_id = s.session_id
               WHERE s.school_id = ? AND s.program_id = ? AND s.session_date = ?
                 AND ss.staff_id = ? AND ss.role = 'lead'
               LIMIT 1""",
            (school_id, program_id, session_date_raw, staff_id),
        ).fetchone()
        if dup_row:
            return jsonify({
                "error": (
                    "A session for this school, program, and date has already been logged by you. "
                    "Use the existing session ID to file an EOD report."
                ),
                "existing_session_id": dup_row["session_id"],
            }), 409

        # Rule 19: single atomic transaction — all 4 inserts + audit + commit
        n_students = len(student_ids)
        created_at_val = now_utc()

        cur = db.execute(
            """INSERT INTO sessions
               (school_id, program_id, session_date, start_time, end_time,
                session_type, location, planned_activity, actual_activity,
                student_group_name, session_status, total_students_present,
                duration_minutes, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, program_id, session_date_raw, start_time, end_time,
             session_type, location, planned_activity, actual_activity,
             student_group_name, session_status, n_students,
             duration_minutes, notes, created_at_val),
        )
        new_session_id = cur.lastrowid

        db.execute(
            "INSERT INTO session_staff (session_id, staff_id, role) VALUES (?, ?, 'lead')",
            (new_session_id, staff_id),
        )

        att_ts = now_utc()
        for sid in student_ids:
            db.execute(
                """INSERT INTO student_session_attendance
                   (session_id, student_id, attendance_status, created_at)
                   VALUES (?, ?, 'present', ?)""",
                (new_session_id, sid, att_ts),
            )

        audit(
            db, user["user_id"], "INSERT", "sessions", new_session_id,
            new_values={
                "school_id": school_id,
                "program_id": program_id,
                "session_date": session_date_raw,
                "student_count": n_students,
            },
        )
        db.commit()

        # Post-commit: fetch display names for confirmation banner (SOUL.md voice contract)
        names_row = db.execute(
            "SELECT sc.school_name, p.program_name FROM schools sc, programs p"
            " WHERE sc.school_id = ? AND p.program_id = ?",
            (school_id, program_id),
        ).fetchone()
        school_name = names_row["school_name"] if names_row else None
        program_name = names_row["program_name"] if names_row else None

        return jsonify({
            "ok": True,
            "session": {
                "session_id": new_session_id,
                "school_id": school_id,
                "school_name": school_name,
                "program_id": program_id,
                "program_name": program_name,
                "session_date": session_date_raw,
                "start_time": start_time,
                "end_time": end_time,
                "session_type": session_type,
                "location": location,
                "planned_activity": planned_activity,
                "actual_activity": actual_activity,
                "student_group_name": student_group_name,
                "session_status": session_status,
                "total_students_present": n_students,
                "notes": notes,
                "student_ids": sorted(student_ids),
                "created_at": created_at_val,
            },
        }), 201

    except Exception as exc:
        db.rollback()
        current_app.logger.error("create_session ERROR: %s", exc)
        return jsonify({"error": "Session could not be saved — please try again or contact support."}), 500
    finally:
        db.close()


# ===========================================================================
# EOD REPORTS
# ===========================================================================

@coach_bp.route("/api/eod-reports", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer", "site_coordinator", "head_coach", "assistant_coach")
def list_eod_reports():
    # GET /api/eod-reports — response contains no student PII; FERPA audit not required.
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    role = user["role"]
    staff_id = user.get("staff_id")

    raw_page = request.args.get("page", "1")
    raw_per_page = request.args.get("per_page", "20")
    try:
        page = int(raw_page)
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "page must be a positive integer."}), 400
    try:
        per_page = int(raw_per_page)
        if not (1 <= per_page <= 100):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "per_page must be between 1 and 100."}), 400

    today = _get_today()
    default_from = (today - datetime.timedelta(days=30)).isoformat()
    default_to = today.isoformat()
    from_date = request.args.get("from", default_from)
    to_date = request.args.get("to", default_to)
    try:
        datetime.date.fromisoformat(from_date)
        datetime.date.fromisoformat(to_date)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    if from_date > to_date:
        return jsonify({"error": "from must be before or equal to to."}), 400

    school_id_filter = request.args.get("school_id")
    if school_id_filter is not None:
        try:
            school_id_filter = int(school_id_filter)
            if school_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "school_id must be a positive integer."}), 400

    program_id_filter = request.args.get("program_id")
    if program_id_filter is not None:
        try:
            program_id_filter = int(program_id_filter)
            if program_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "program_id must be a positive integer."}), 400

    db = get_db()
    try:
        if role in ("head_coach", "assistant_coach"):
            user_school_id = user.get("school_id")
            if not user_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            # EOD reports are coach-scoped (not school-scoped like sessions).
            # Only current school — school_id filter silently ignored for head/assistant.
            scope_sql = "AND er.staff_id = ? AND er.school_id = ?"
            scope_params = [staff_id, user_school_id]

        elif role == "site_coordinator":
            if not staff_id:
                return jsonify({
                    "error": "You have no active region assignment. Contact your administrator."
                }), 403
            # Phase 2B: scope via staff_assignments.
            # Broader region-based scoping requires a region_id column on schools (schema gap).
            scope_sql = (
                "AND er.school_id IN"
                " (SELECT school_id FROM staff_assignments"
                "  WHERE staff_id = ? AND active_status = 1 AND deleted_at IS NULL)"
            )
            scope_params = [staff_id]
            if school_id_filter is not None:
                assigned = db.execute(
                    "SELECT 1 FROM staff_assignments"
                    " WHERE staff_id = ? AND school_id = ? AND active_status = 1 AND deleted_at IS NULL",
                    (staff_id, school_id_filter),
                ).fetchone()
                if not assigned:
                    return jsonify({"error": "You do not have access to this school."}), 403

        elif role == "coach_overseer":
            overseer_school_id = user.get("school_id")
            if not overseer_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (overseer_school_id,),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            if not org_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            scope_sql = "AND sc.organization_id = ?"
            scope_params = [org_id]
            if school_id_filter is not None:
                filter_sc = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?",
                    (school_id_filter,),
                ).fetchone()
                if not filter_sc or filter_sc["organization_id"] != org_id:
                    return jsonify({"error": "You do not have access to this school."}), 403

        elif role in ("ceo", "admin"):
            # Full access — no org restriction for HQ admin/CEO
            scope_sql = ""
            scope_params = []

        else:
            scope_sql = "AND 1=0"
            scope_params = []

        # scope_sql, school_filter_sql, program_filter_sql contain only hardcoded fragments
        school_filter_sql = ""
        school_filter_params: list = []
        if school_id_filter is not None and role not in ("head_coach", "assistant_coach"):
            school_filter_sql = "AND er.school_id = ?"
            school_filter_params = [school_id_filter]

        program_filter_sql = ""
        program_filter_params: list = []
        if program_id_filter is not None:
            program_filter_sql = "AND er.program_id = ?"
            program_filter_params = [program_id_filter]

        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM eod_reports er
            JOIN schools sc ON sc.school_id = er.school_id
            WHERE er.deleted_at IS NULL
              AND er.report_date >= ? AND er.report_date <= ?
              {scope_sql}
              {school_filter_sql}
              {program_filter_sql}
        """
        count_params = (
            [from_date, to_date] + scope_params + school_filter_params + program_filter_params
        )
        total = db.execute(count_sql, count_params).fetchone()["cnt"]
        pages = math.ceil(total / per_page) if total > 0 else 0
        offset = (page - 1) * per_page

        main_sql = f"""
            SELECT er.eod_id, er.school_id, sc.school_name, er.staff_id,
                   (u.first_name || ' ' || u.last_name) AS coach_name,
                   er.program_id, er.report_date, er.activities_completed,
                   er.student_engagement_summary, er.attendance_summary,
                   er.behavior_summary, er.success_story, er.challenge_summary,
                   er.notes, er.injury_incident_flag, er.followup_needed,
                   er.principal_communication_needed, er.submitted_on_time,
                   er.session_id, ses.session_type, er.created_at,
                   er.incident_report_filed, er.school_concerns,
                   er.school_concerns_resolved, er.school_concerns_notes,
                   er.schedule_changes, er.coaches_clocked_in, er.late_arrivals,
                   er.coaches_in_uniform, er.verbal_warnings, er.hr_app_issues,
                   er.coaches_setup_ready, er.equipment_accounted,
                   er.transitions_orderly, er.safety_hazards, er.yard_supervised,
                   er.curriculum_followed, er.equipment_requests,
                   er.principal_communication_notes, er.ufit_standards_notes
            FROM eod_reports er
            JOIN schools sc ON sc.school_id = er.school_id
            LEFT JOIN staff_profiles sp ON sp.staff_id = er.staff_id
            LEFT JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
            LEFT JOIN sessions ses ON ses.session_id = er.session_id AND ses.deleted_at IS NULL
            WHERE er.deleted_at IS NULL
              AND er.report_date >= ? AND er.report_date <= ?
              {scope_sql}
              {school_filter_sql}
              {program_filter_sql}
            ORDER BY er.report_date DESC, er.eod_id DESC
            LIMIT ? OFFSET ?
        """
        main_params = (
            [from_date, to_date] + scope_params + school_filter_params + program_filter_params
            + [per_page, offset]
        )
        rows = db.execute(main_sql, main_params).fetchall()

        serialized = [serialize_eod_report(r) for r in rows]
        return jsonify({
            "ok": True,
            "reports": serialized,
            "eod_reports": serialized,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        })

    except Exception as exc:
        current_app.logger.error("list_eod_reports ERROR: %s", exc)
        return jsonify({"error": "Could not load EOD reports — please try again or contact support."}), 500
    finally:
        db.close()


@coach_bp.route("/api/eod-reports/<int:eod_id>", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer", "site_coordinator", "head_coach", "assistant_coach")
def get_eod_report(eod_id: int):
    """Fetch a single EOD report by ID. Admin/CEO see any; coaches see only their own."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    role = user["role"]
    staff_id = user.get("staff_id")

    db = get_db()
    try:
        row = db.execute(
            """SELECT er.eod_id, er.school_id, sc.school_name, er.staff_id,
                      (u.first_name || ' ' || u.last_name) AS coach_name,
                      er.program_id, er.report_date, er.activities_completed,
                      er.student_engagement_summary, er.attendance_summary,
                      er.behavior_summary, er.success_story, er.challenge_summary,
                      er.notes, er.injury_incident_flag, er.followup_needed,
                      er.principal_communication_needed, er.submitted_on_time,
                      er.session_id, ses.session_type, er.created_at,
                      er.incident_report_filed, er.school_concerns,
                      er.school_concerns_resolved, er.school_concerns_notes,
                      er.schedule_changes, er.coaches_clocked_in, er.late_arrivals,
                      er.coaches_in_uniform, er.verbal_warnings, er.hr_app_issues,
                      er.coaches_setup_ready, er.equipment_accounted,
                      er.transitions_orderly, er.safety_hazards, er.yard_supervised,
                      er.curriculum_followed, er.equipment_requests,
                      er.principal_communication_notes, er.ufit_standards_notes
               FROM eod_reports er
               JOIN schools sc ON sc.school_id = er.school_id
               LEFT JOIN staff_profiles sp ON sp.staff_id = er.staff_id
               LEFT JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
               LEFT JOIN sessions ses ON ses.session_id = er.session_id AND ses.deleted_at IS NULL
               WHERE er.eod_id = ? AND er.deleted_at IS NULL""",
            (eod_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "EOD report not found."}), 404

        # Coaches can only view their own reports
        if role in ("head_coach", "assistant_coach") and row["staff_id"] != staff_id:
            return jsonify({"error": "Access denied."}), 403

        return jsonify({"ok": True, "report": serialize_eod_report(row)})
    finally:
        db.close()


@coach_bp.route("/api/eod-reports", methods=["POST"])
@limiter.limit("10 per minute")
@coach_required
def create_eod_report():
    # Rule 1: site_coordinator blocked before body parsing (role known from session)
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    if user["role"] == "site_coordinator":
        return jsonify({"error": "You do not have permission to submit EOD reports."}), 403

    data = parse_json()

    # Rule 2: school_id — required, positive integer
    school_id = data.get("school_id")
    if school_id is None:
        return jsonify({"error": "Missing required field: school_id."}), 400
    if not isinstance(school_id, int) or isinstance(school_id, bool) or school_id <= 0:
        return jsonify({"error": "school_id must be an integer."}), 400

    # Rule 3: report_date — required, valid YYYY-MM-DD calendar date
    report_date_raw = data.get("report_date")
    if not report_date_raw:
        return jsonify({"error": "Missing required field: report_date."}), 400
    try:
        report_dt = datetime.date.fromisoformat(str(report_date_raw))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Rule 4: date range — UTC comparison is acceptable for calendar-date checks
    today = _get_today()
    if report_dt > today:
        return jsonify({"error": "Report date cannot be in the future."}), 400
    if (today - report_dt).days > 7:
        return jsonify({"error": "Report date cannot be more than 7 days in the past."}), 400

    # Rule 5: activities_completed — required, non-empty after strip
    activities_raw = data.get("activities_completed")
    if not isinstance(activities_raw, str) or not activities_raw.strip():
        return jsonify({"error": "Missing required field: activities_completed."}), 400

    # Rule 6: student_engagement_summary — required, non-empty after strip
    engagement_raw = data.get("student_engagement_summary")
    if not isinstance(engagement_raw, str) or not engagement_raw.strip():
        return jsonify({"error": "Missing required field: student_engagement_summary."}), 400

    # Rule 7: ufit_standards_notes — required, non-empty after strip (Q26)
    ufit_standards_raw = data.get("ufit_standards_notes")
    if not isinstance(ufit_standards_raw, str) or not ufit_standards_raw.strip():
        return jsonify({"error": "Missing required field: ufit_standards_notes."}), 400

    # Rule 8: string length limits (checked against raw values, not stripped)
    for field, limit in _EOD_STR_LIMITS.items():
        val = data.get(field)
        if val is not None and len(str(val)) > limit:
            return jsonify({"error": f"Field '{field}' exceeds maximum length of {limit} characters."}), 400

    # Rule 9: non-nullable boolean fields — must be actual JSON booleans
    for bool_field in ("injury_incident_flag", "followup_needed", "principal_communication_needed"):
        val = data.get(bool_field)
        if val is not None and not isinstance(val, bool):
            return jsonify({"error": f"{bool_field} must be a boolean."}), 400

    # Nullable boolean fields — JSON null accepted (stored as NULL); non-null must be bool
    for bool_field in (
        "incident_report_filed", "school_concerns_resolved", "coaches_clocked_in",
        "coaches_in_uniform", "coaches_setup_ready", "equipment_accounted",
        "transitions_orderly", "yard_supervised", "curriculum_followed",
    ):
        val = data.get(bool_field)
        if val is not None and not isinstance(val, bool):
            return jsonify({"error": f"{bool_field} must be a boolean."}), 400

    injury_incident_flag = data.get("injury_incident_flag", False)
    followup_needed = data.get("followup_needed", False)
    principal_communication_needed = data.get("principal_communication_needed", False)

    # Rule 9: program_id — optional, positive integer if provided
    program_id = data.get("program_id")
    if program_id is not None:
        if not isinstance(program_id, int) or isinstance(program_id, bool) or program_id <= 0:
            return jsonify({"error": "program_id must be an integer."}), 400

    # Rule 10: session_id — optional, positive integer if provided
    session_id = data.get("session_id")
    if session_id is not None:
        if not isinstance(session_id, int) or isinstance(session_id, bool) or session_id <= 0:
            return jsonify({"error": "session_id must be a positive integer."}), 400

    # Rule 11: staff profile guard
    staff_id = user.get("staff_id")
    if not staff_id:
        return jsonify({
            "error": "Staff profile missing for this account. Contact your administrator."
        }), 500

    role = user["role"]

    # Rule 12: school assignment guard — head/assistant/overseer must have a school
    if role in ("head_coach", "assistant_coach", "coach_overseer"):
        if not user.get("school_id"):
            return jsonify({
                "error": "You have no active school assignment. Contact your administrator."
            }), 403

    # Rule 13: head/assistant — school must match their active assignment
    if role in ("head_coach", "assistant_coach"):
        if school_id != user["school_id"]:
            return jsonify({"error": "You are not assigned to this school."}), 403

    # submitted_on_time — computed in Pacific time, not UTC.
    # Backdated check uses Pacific calendar date to avoid false "late" at 00:00-03:00 UTC
    # (which is still the prior evening in Pacific).
    now_pacific = _now_pacific()
    today_pacific = now_pacific.date()
    if report_dt < today_pacific:
        submitted_on_time = False
    else:
        deadline_pacific = now_pacific.replace(hour=18, minute=0, second=0, microsecond=0)
        submitted_on_time = now_pacific <= deadline_pacific

    # followup_needed override: injury forces followup — coach cannot override this direction
    if injury_incident_flag:
        followup_needed = True

    attendance_summary = data.get("attendance_summary") or None
    behavior_summary = data.get("behavior_summary") or None
    success_story = data.get("success_story") or None
    challenge_summary = data.get("challenge_summary") or None
    notes = data.get("notes") or None
    incident_report_filed = data.get("incident_report_filed")
    school_concerns = data.get("school_concerns") or None
    school_concerns_resolved = data.get("school_concerns_resolved")
    school_concerns_notes = data.get("school_concerns_notes") or None
    schedule_changes = data.get("schedule_changes") or None
    coaches_clocked_in = data.get("coaches_clocked_in")
    late_arrivals = data.get("late_arrivals") or None
    coaches_in_uniform = data.get("coaches_in_uniform")
    verbal_warnings = data.get("verbal_warnings") or None
    hr_app_issues = data.get("hr_app_issues") or None
    coaches_setup_ready = data.get("coaches_setup_ready")
    equipment_accounted = data.get("equipment_accounted")
    transitions_orderly = data.get("transitions_orderly")
    safety_hazards = data.get("safety_hazards") or None
    yard_supervised = data.get("yard_supervised")
    curriculum_followed = data.get("curriculum_followed")
    equipment_requests = data.get("equipment_requests") or None
    principal_communication_notes = data.get("principal_communication_notes") or None

    db = get_db()
    try:
        # Rule 14: coach_overseer — org-based school authorization
        if role == "coach_overseer":
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (user["school_id"],),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            if not org_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            target_sc = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (school_id,),
            ).fetchone()
            if not target_sc or target_sc["organization_id"] != org_id:
                return jsonify({"error": "School is not in your organization."}), 403

        # Rule 15: program_id validation (if provided)
        if program_id is not None:
            prog_row = db.execute(
                "SELECT program_id FROM programs"
                " WHERE program_id = ? AND school_id = ? AND program_status = 'active' AND deleted_at IS NULL",
                (program_id, school_id),
            ).fetchone()
            if not prog_row:
                return jsonify({"error": "Program not found at this school."}), 400

        # Rule 16: duplicate guard inside transaction — no DB UNIQUE constraint exists
        dup_row = db.execute(
            "SELECT eod_id FROM eod_reports"
            " WHERE staff_id = ? AND school_id = ? AND report_date = ? AND deleted_at IS NULL"
            " LIMIT 1",
            (staff_id, school_id, report_date_raw),
        ).fetchone()
        if dup_row:
            return jsonify({
                "error": "An EOD report for this school and date has already been submitted.",
                "existing_eod_id": dup_row["eod_id"],
            }), 409

        # Rule 17: session_id validation (if provided)
        if session_id is not None:
            sess_row = db.execute(
                "SELECT session_id FROM sessions"
                " WHERE session_id = ? AND school_id = ? AND session_date = ? AND deleted_at IS NULL",
                (session_id, school_id, report_date_raw),
            ).fetchone()
            if not sess_row:
                return jsonify({
                    "error": "session_id does not match a session at this school on this date."
                }), 400

        created_at_val = now_utc()
        cur = db.execute(
            """INSERT INTO eod_reports
               (school_id, staff_id, program_id, session_id, report_date,
                activities_completed, student_engagement_summary, attendance_summary,
                behavior_summary, success_story, challenge_summary, notes,
                injury_incident_flag, followup_needed, principal_communication_needed,
                submitted_on_time,
                incident_report_filed, school_concerns, school_concerns_resolved,
                school_concerns_notes, schedule_changes, coaches_clocked_in,
                late_arrivals, coaches_in_uniform, verbal_warnings, hr_app_issues,
                coaches_setup_ready, equipment_accounted, transitions_orderly,
                safety_hazards, yard_supervised, curriculum_followed,
                equipment_requests, principal_communication_notes, ufit_standards_notes,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, staff_id, program_id, session_id, report_date_raw,
             activities_raw, engagement_raw, attendance_summary,
             behavior_summary, success_story, challenge_summary, notes,
             injury_incident_flag, followup_needed, principal_communication_needed,
             submitted_on_time,
             incident_report_filed, school_concerns, school_concerns_resolved,
             school_concerns_notes, schedule_changes, coaches_clocked_in,
             late_arrivals, coaches_in_uniform, verbal_warnings, hr_app_issues,
             coaches_setup_ready, equipment_accounted, transitions_orderly,
             safety_hazards, yard_supervised, curriculum_followed,
             equipment_requests, principal_communication_notes, ufit_standards_raw,
             created_at_val),
        )
        new_eod_id = cur.lastrowid

        audit(
            db, user["user_id"], "INSERT", "eod_reports", new_eod_id,
            new_values={
                "school_id": school_id,
                "report_date": report_date_raw,
                "injury_incident_flag": injury_incident_flag,
                "followup_needed": followup_needed,
                "submitted_on_time": submitted_on_time,
            },
        )
        db.commit()

        # Post-commit: fetch display names for the confirmation banner (SOUL.md voice contract)
        display_row = db.execute(
            """SELECT er.eod_id, er.school_id, sc.school_name, er.staff_id,
                      (u.first_name || ' ' || u.last_name) AS coach_name,
                      er.program_id, er.report_date, er.activities_completed,
                      er.student_engagement_summary, er.attendance_summary,
                      er.behavior_summary, er.success_story, er.challenge_summary,
                      er.notes, er.injury_incident_flag, er.followup_needed,
                      er.principal_communication_needed, er.submitted_on_time,
                      er.session_id, er.created_at,
                      er.incident_report_filed, er.school_concerns,
                      er.school_concerns_resolved, er.school_concerns_notes,
                      er.schedule_changes, er.coaches_clocked_in, er.late_arrivals,
                      er.coaches_in_uniform, er.verbal_warnings, er.hr_app_issues,
                      er.coaches_setup_ready, er.equipment_accounted,
                      er.transitions_orderly, er.safety_hazards, er.yard_supervised,
                      er.curriculum_followed, er.equipment_requests,
                      er.principal_communication_notes, er.ufit_standards_notes
               FROM eod_reports er
               JOIN schools sc ON sc.school_id = er.school_id
               LEFT JOIN staff_profiles sp ON sp.staff_id = er.staff_id
               LEFT JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
               WHERE er.eod_id = ?""",
            (new_eod_id,),
        ).fetchone()

        return jsonify({"ok": True, "eod_report": serialize_eod_report(display_row)}), 201

    except Exception as exc:
        db.rollback()
        current_app.logger.error("create_eod_report ERROR: %s", exc)
        return jsonify({"error": "EOD report could not be saved — please try again or contact support."}), 500
    finally:
        db.close()


# ===========================================================================
# INCIDENTS
# ===========================================================================

_INCIDENT_TYPES = frozenset({"injury", "behavior", "property", "medical", "safety", "other"})
_SEVERITY_LEVELS = frozenset({"low", "medium", "high", "critical"})
_INCIDENT_STR_LIMITS = {
    "description": 2000,
    "immediate_action_taken": 1000,
    "resolution_notes": 1000,
}


@coach_bp.route("/api/incidents", methods=["GET"])
@coach_required
def list_incidents():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    role = user["role"]
    staff_id = user["staff_id"]
    db = get_db()

    # --- Pagination ---
    page_raw = request.args.get("page", "1")
    per_page_raw = request.args.get("per_page", "20")
    try:
        page = int(page_raw)
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "page must be a positive integer."}), 400
    try:
        per_page = min(int(per_page_raw), 100)
        if per_page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "per_page must be a positive integer."}), 400

    offset = (page - 1) * per_page

    # --- Optional filters ---
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")

    _VALID_STATUSES = frozenset(("open", "under_review", "in_progress", "resolved", "closed"))
    _VALID_SEVERITIES = frozenset(("low", "medium", "high", "critical"))

    filter_sql = ""
    filter_params: list = []

    if from_date:
        try:
            datetime.date.fromisoformat(str(from_date))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid from date format. Use YYYY-MM-DD."}), 400
        filter_sql += " AND ir.report_date >= ?"
        filter_params.append(from_date)
    if to_date:
        try:
            datetime.date.fromisoformat(str(to_date))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid to date format. Use YYYY-MM-DD."}), 400
        filter_sql += " AND ir.report_date <= ?"
        filter_params.append(to_date)
    if status_filter:
        if status_filter not in _VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Valid values: {', '.join(sorted(_VALID_STATUSES))}."}), 422
        filter_sql += " AND ir.status = ?"
        filter_params.append(status_filter)
    if severity_filter:
        if severity_filter not in _VALID_SEVERITIES:
            return jsonify({"error": f"Invalid severity. Valid values: {', '.join(sorted(_VALID_SEVERITIES))}."}), 422
        filter_sql += " AND ir.severity_level = ?"
        filter_params.append(severity_filter)

    # --- Role scoping ---
    if role in ("head_coach", "assistant_coach"):
        scope_sql = "AND ir.reported_by_staff_id = ? AND ir.school_id = ?"
        scope_params = [staff_id, user["school_id"]]
    elif role == "site_coordinator":
        scope_sql = (
            "AND ir.school_id IN"
            " (SELECT school_id FROM staff_assignments"
            "  WHERE staff_id = ? AND active_status = 1 AND deleted_at IS NULL)"
        )
        scope_params = [staff_id]
    else:  # coach_overseer
        overseer_school_id = user["school_id"]
        if not overseer_school_id:
            return jsonify({"error": "You have no active school assignment."}), 403
        org_row = db.execute(
            "SELECT organization_id FROM schools WHERE school_id = ?",
            (overseer_school_id,),
        ).fetchone()
        if not org_row:
            return jsonify({"error": "You have no active school assignment."}), 403
        scope_sql = "AND sc.organization_id = ?"
        scope_params = [org_row["organization_id"]]

    base_join = (
        " FROM incident_reports ir"
        " JOIN schools sc ON sc.school_id = ir.school_id"
        " LEFT JOIN users u ON u.user_id = ("
        "   SELECT sp2.user_id FROM staff_profiles sp2"
        "   WHERE sp2.staff_id = ir.reported_by_staff_id"
        " ) AND u.deleted_at IS NULL"
        " WHERE ir.deleted_at IS NULL"
        f" {scope_sql}"
        f" {filter_sql}"
    )

    count_params = scope_params + filter_params
    total = db.execute(
        "SELECT COUNT(*) AS cnt" + base_join,
        count_params,
    ).fetchone()["cnt"]

    rows = db.execute(
        "SELECT ir.incident_id, ir.school_id, sc.school_name,"
        " ir.reported_by_staff_id AS staff_id,"
        " (u.first_name || ' ' || u.last_name) AS coach_name,"
        " ir.session_id, ir.student_id,"
        " ir.report_date, ir.incident_type, ir.severity_level,"
        " ir.description, ir.immediate_action_taken,"
        " ir.school_notified, ir.family_notified, ir.escalated_to_supervisor,"
        " ir.status, ir.resolution_notes, ir.admin_response, ir.acknowledged_at, ir.created_at"
        + base_join
        + " ORDER BY ir.report_date DESC, ir.incident_id DESC"
        + " LIMIT ? OFFSET ?",
        count_params + [per_page, offset],
    ).fetchall()

    db.close()
    return jsonify({
        "ok": True,
        "total": total,
        "page": page,
        "per_page": per_page,
        "incidents": [serialize_incident(r) for r in rows],
    })


@coach_bp.route("/api/incidents", methods=["POST"])
@limiter.limit("10 per minute")
@coach_required
def create_incident():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    # Rule 1-2: only field coaches can file
    if user["role"] in ("site_coordinator", "coach_overseer"):
        return jsonify({"error": "Incident reports must be filed by a coach."}), 403

    data = parse_json()
    role = user["role"]
    staff_id = user["staff_id"]

    # Rule 3: school_id
    school_id_raw = data.get("school_id")
    if not isinstance(school_id_raw, int) or school_id_raw <= 0:
        return jsonify({"error": "school_id is required and must be a positive integer."}), 400
    school_id = school_id_raw

    # Rule 4-6: report_date
    report_date_raw = data.get("report_date")
    if not isinstance(report_date_raw, str) or not report_date_raw.strip():
        return jsonify({"error": "report_date is required in YYYY-MM-DD format."}), 400
    try:
        report_date = datetime.date.fromisoformat(report_date_raw.strip())
    except ValueError:
        return jsonify({"error": "report_date is required in YYYY-MM-DD format."}), 400

    today = _get_today()
    if report_date > today:
        return jsonify({"error": "report_date cannot be in the future."}), 400
    if (today - report_date).days > 7:
        return jsonify({"error": "report_date cannot be more than 7 days in the past."}), 400

    # Rule 7: incident_type
    incident_type = data.get("incident_type")
    if not isinstance(incident_type, str) or incident_type not in _INCIDENT_TYPES:
        return jsonify({"error": f"incident_type must be one of: {', '.join(sorted(_INCIDENT_TYPES))}."}), 400

    # Rule 8: severity_level
    severity_level = data.get("severity_level")
    if not isinstance(severity_level, str) or severity_level not in _SEVERITY_LEVELS:
        return jsonify({"error": f"severity_level must be one of: {', '.join(sorted(_SEVERITY_LEVELS))}."}), 400

    # Rule 9-10: description
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "description is required."}), 400
    if len(description) > 2000:
        return jsonify({"error": "description cannot exceed 2000 characters."}), 400

    # Rule 11-12: immediate_action_taken
    immediate_action = data.get("immediate_action_taken")
    if not isinstance(immediate_action, str) or not immediate_action.strip():
        return jsonify({"error": "immediate_action_taken is required."}), 400
    if len(immediate_action) > 1000:
        return jsonify({"error": "immediate_action_taken cannot exceed 1000 characters."}), 400

    # Rule 13: optional text length limits
    resolution_notes = data.get("resolution_notes")
    if resolution_notes is not None:
        if not isinstance(resolution_notes, str):
            resolution_notes = str(resolution_notes)
        if len(resolution_notes) > 1000:
            return jsonify({"error": "resolution_notes cannot exceed 1000 characters."}), 400

    # Rule 14: boolean fields
    for bool_field in ("school_notified", "family_notified", "escalated_to_supervisor"):
        val = data.get(bool_field)
        if val is not None and not isinstance(val, bool):
            return jsonify({"error": f"{bool_field} must be a boolean."}), 400

    school_notified = data.get("school_notified", False)
    family_notified = data.get("family_notified", False)
    escalated = data.get("escalated_to_supervisor", False)

    # Rule 15: school access check
    if role in ("head_coach", "assistant_coach"):
        if user["school_id"] != school_id:
            return jsonify({"error": "You are not assigned to this school."}), 403

    db = get_db()

    # Rule 16: validate session_id
    session_id = data.get("session_id")
    if session_id is not None:
        if not isinstance(session_id, int) or session_id <= 0:
            return jsonify({"error": "session_id does not match a valid session for this school and date."}), 400
        sess_row = db.execute(
            "SELECT session_id FROM sessions"
            " WHERE session_id = ? AND school_id = ? AND session_date = ? AND deleted_at IS NULL",
            (session_id, school_id, report_date_raw),
        ).fetchone()
        if not sess_row:
            return jsonify({"error": "session_id does not match a valid session for this school and date."}), 400

    # Rule 17: validate student_id
    student_id = data.get("student_id")
    if student_id is not None:
        if not isinstance(student_id, int) or student_id <= 0:
            return jsonify({"error": "student_id does not belong to this school."}), 400
        stud_row = db.execute(
            "SELECT student_id FROM students WHERE student_id = ? AND school_id = ? AND deleted_at IS NULL",
            (student_id, school_id),
        ).fetchone()
        if not stud_row:
            return jsonify({"error": "student_id does not belong to this school."}), 400

    created_at_val = now_utc()

    try:
        cur = db.execute(
            """INSERT INTO incident_reports
               (school_id, session_id, report_date, reported_by_staff_id,
                student_id, incident_type, severity_level, description,
                immediate_action_taken, school_notified, family_notified,
                escalated_to_supervisor, status, resolution_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (school_id, session_id, report_date_raw, staff_id,
             student_id, incident_type, severity_level, description,
             immediate_action, school_notified, family_notified, escalated,
             resolution_notes, created_at_val),
        )
        incident_id = cur.lastrowid

        # Critical incident: notify admin/ceo/overseer users in same org
        if severity_level == "critical":
            db.execute(
                """INSERT INTO notifications
                   (recipient_user_id, type, message, reference_table, reference_id, created_at)
                   SELECT DISTINCT u.user_id,
                          'incident_filed',
                          'A critical incident was filed at ' || sc.school_name || ' on ' || ?,
                          'incident_reports',
                          ?,
                          ?
                   FROM users u
                   JOIN staff_profiles sp ON sp.user_id = u.user_id
                   JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = 1 AND sa.deleted_at IS NULL
                   JOIN schools sa_sc ON sa_sc.school_id = sa.school_id
                   JOIN schools sc ON sc.school_id = ?
                   WHERE u.role IN ('ceo', 'admin', 'coach_overseer')
                     AND sa_sc.organization_id = sc.organization_id
                     AND u.deleted_at IS NULL""",
                (report_date_raw, incident_id, created_at_val, school_id),
            )

        audit(
            db,
            user["user_id"],
            "INSERT",
            "incident_reports",
            incident_id,
            None,
            {
                "school_id": school_id,
                "report_date": report_date_raw,
                "incident_type": incident_type,
                "severity_level": severity_level,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        raise

    # Fetch display row with school_name + coach_name
    display_row = db.execute(
        """SELECT ir.incident_id, ir.school_id, sc.school_name,
                  ir.reported_by_staff_id AS staff_id,
                  (u.first_name || ' ' || u.last_name) AS coach_name,
                  ir.session_id, ir.student_id,
                  ir.report_date, ir.incident_type, ir.severity_level,
                  ir.description, ir.immediate_action_taken,
                  ir.school_notified, ir.family_notified, ir.escalated_to_supervisor,
                  ir.status, ir.resolution_notes, ir.created_at
           FROM incident_reports ir
           JOIN schools sc ON sc.school_id = ir.school_id
           LEFT JOIN users u ON u.user_id = (
             SELECT sp2.user_id FROM staff_profiles sp2
             WHERE sp2.staff_id = ir.reported_by_staff_id
           ) AND u.deleted_at IS NULL
           WHERE ir.incident_id = ?""",
        (incident_id,),
    ).fetchone()
    db.close()

    return jsonify({"ok": True, "incident": serialize_incident(display_row)}), 201


# ===========================================================================
# ASSESSMENTS
# ===========================================================================

@coach_bp.route("/api/assessments", methods=["GET"])
@coach_required
def list_assessments():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    role = user["role"]
    staff_id = user.get("staff_id")

    raw_page = request.args.get("page", "1")
    raw_per_page = request.args.get("per_page", "20")
    try:
        page = int(raw_page)
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "page must be a positive integer."}), 400
    try:
        per_page = int(raw_per_page)
        if not (1 <= per_page <= 100):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "per_page must be between 1 and 100."}), 400

    student_id_filter = request.args.get("student_id")
    if student_id_filter is not None:
        try:
            student_id_filter = int(student_id_filter)
            if student_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "student_id must be a positive integer."}), 400

    window_id_filter = request.args.get("window_id")
    if window_id_filter is not None:
        try:
            window_id_filter = int(window_id_filter)
            if window_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "window_id must be a positive integer."}), 400

    school_id_filter = request.args.get("school_id")
    if school_id_filter is not None:
        try:
            school_id_filter = int(school_id_filter)
            if school_id_filter <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "school_id must be a positive integer."}), 400

    db = get_db()
    try:
        if role in ("head_coach", "assistant_coach"):
            user_school_id = user.get("school_id")
            if not user_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            scope_sql = "AND a.school_id = ?"
            scope_params = [user_school_id]

        elif role == "site_coordinator":
            if not staff_id:
                return jsonify({
                    "error": "You have no active region assignment. Contact your administrator."
                }), 403
            scope_sql = (
                "AND a.school_id IN"
                " (SELECT school_id FROM staff_assignments"
                "  WHERE staff_id = ? AND active_status = 1 AND deleted_at IS NULL)"
            )
            scope_params = [staff_id]
            if school_id_filter is not None:
                assigned = db.execute(
                    "SELECT 1 FROM staff_assignments"
                    " WHERE staff_id = ? AND school_id = ? AND active_status = 1 AND deleted_at IS NULL",
                    (staff_id, school_id_filter),
                ).fetchone()
                if not assigned:
                    return jsonify({"error": "You do not have access to this school."}), 403

        elif role == "coach_overseer":
            overseer_school_id = user.get("school_id")
            if not overseer_school_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (overseer_school_id,),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            if not org_id:
                return jsonify({
                    "error": "You have no active school assignment. Contact your administrator."
                }), 403
            scope_sql = "AND sc.organization_id = ?"
            scope_params = [org_id]
            if school_id_filter is not None:
                filter_sc = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?",
                    (school_id_filter,),
                ).fetchone()
                if not filter_sc or filter_sc["organization_id"] != org_id:
                    return jsonify({"error": "You do not have access to this school."}), 403

        else:
            scope_sql = "AND 1=0"
            scope_params = []

        school_filter_sql = ""
        school_filter_params: list = []
        if school_id_filter is not None and role not in ("head_coach", "assistant_coach"):
            school_filter_sql = "AND a.school_id = ?"
            school_filter_params = [school_id_filter]

        student_filter_sql = ""
        student_filter_params: list = []
        if student_id_filter is not None:
            stu_row = db.execute(
                "SELECT school_id FROM students WHERE student_id = ? AND deleted_at IS NULL",
                (student_id_filter,),
            ).fetchone()
            if not stu_row:
                return jsonify({"error": "Student not found."}), 404
            stu_school = stu_row["school_id"]
            if role in ("head_coach", "assistant_coach") and stu_school != user.get("school_id"):
                return jsonify({"error": "You do not have access to this student."}), 403
            if role == "site_coordinator":
                allowed = db.execute(
                    "SELECT 1 FROM staff_assignments"
                    " WHERE staff_id = ? AND school_id = ? AND active_status = 1 AND deleted_at IS NULL",
                    (staff_id, stu_school),
                ).fetchone()
                if not allowed:
                    return jsonify({"error": "You do not have access to this student."}), 403
            if role == "coach_overseer":
                stu_org = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?", (stu_school,)
                ).fetchone()
                if not stu_org or stu_org["organization_id"] != org_id:
                    return jsonify({"error": "You do not have access to this student."}), 403
            student_filter_sql = "AND a.student_id = ?"
            student_filter_params = [student_id_filter]

        window_filter_sql = ""
        window_filter_params: list = []
        if window_id_filter is not None:
            window_filter_sql = "AND a.window_id = ?"
            window_filter_params = [window_id_filter]

        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM assessments a
            JOIN schools sc ON sc.school_id = a.school_id
            WHERE a.deleted_at IS NULL
              {scope_sql}
              {school_filter_sql}
              {student_filter_sql}
              {window_filter_sql}
        """
        count_params = (
            scope_params + school_filter_params + student_filter_params + window_filter_params
        )
        total = db.execute(count_sql, count_params).fetchone()["cnt"]
        pages = math.ceil(total / per_page) if total > 0 else 0
        offset = (page - 1) * per_page

        main_sql = f"""
            SELECT a.assessment_id, a.student_id,
                   st.student_first_name, st.student_last_name,
                   a.school_id, sc.school_name,
                   a.window_id, aw.window_name, a.assessed_by_staff_id,
                   (u.first_name || ' ' || u.last_name) AS assessor_name,
                   a.assessment_date, a.assessment_method,
                   a.overall_assessment_notes, a.created_at
            FROM assessments a
            JOIN schools sc ON sc.school_id = a.school_id
            LEFT JOIN students st ON st.student_id = a.student_id
            LEFT JOIN assessment_windows aw ON aw.window_id = a.window_id
            LEFT JOIN staff_profiles sp ON sp.staff_id = a.assessed_by_staff_id
            LEFT JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
            WHERE a.deleted_at IS NULL
              {scope_sql}
              {school_filter_sql}
              {student_filter_sql}
              {window_filter_sql}
            ORDER BY a.assessment_date DESC, a.assessment_id DESC
            LIMIT ? OFFSET ?
        """
        main_params = count_params + [per_page, offset]
        rows = db.execute(main_sql, main_params).fetchall()

        assessments_out = []
        for row in rows:
            score_rows = db.execute(
                """SELECT s.score_id, s.skill_id, sk.skill_name, s.raw_level, s.normalized_score
                   FROM assessment_scores s
                   LEFT JOIN skills sk ON sk.skill_id = s.skill_id
                   WHERE s.assessment_id = ?""",
                (row["assessment_id"],),
            ).fetchall()
            assessments_out.append(
                serialize_assessment(row, [serialize_assessment_score(sr) for sr in score_rows])
            )

        audit(db, user["user_id"], "READ", "assessments", None,
              new_values={"scope": "coach_list", "total": total})
        db.commit()
        return jsonify({
            "ok": True,
            "assessments": assessments_out,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        })

    except Exception as exc:
        current_app.logger.error("list_assessments ERROR: %s", exc)
        return jsonify({"error": "Could not load assessments — please try again or contact support."}), 500
    finally:
        db.close()


@coach_bp.route("/api/assessments", methods=["POST"])
@limiter.limit("30 per minute")
@coach_required
def submit_assessment():
    # Rule 1: site_coordinator blocked before body parsing
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    if user["role"] == "site_coordinator":
        return jsonify({"error": "You do not have permission to submit assessments."}), 403

    data = parse_json()

    # Rule 2: student_id — required, positive integer
    student_id = data.get("student_id")
    if student_id is None:
        return jsonify({"error": "Missing required field: student_id."}), 400
    if not isinstance(student_id, int) or isinstance(student_id, bool) or student_id <= 0:
        return jsonify({"error": "student_id must be a positive integer."}), 400

    # Rule 3: window_id — optional, positive integer if provided
    window_id = data.get("window_id")
    if window_id is not None:
        if not isinstance(window_id, int) or isinstance(window_id, bool) or window_id <= 0:
            return jsonify({"error": "window_id must be a positive integer."}), 400

    # Rule 4: scores — required, non-empty list
    scores_raw = data.get("scores")
    if scores_raw is None:
        return jsonify({"error": "Missing required field: scores."}), 400
    if not isinstance(scores_raw, list) or len(scores_raw) == 0:
        return jsonify({"error": "scores must be a non-empty array."}), 400

    # Rule 5: validate each score item
    for item in scores_raw:
        if not isinstance(item, dict):
            return jsonify({"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}), 400
        sid = item.get("skill_id")
        rs = item.get("raw_score")
        if not isinstance(sid, int) or isinstance(sid, bool) or sid <= 0:
            return jsonify({"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}), 400
        if not isinstance(rs, int) or isinstance(rs, bool) or not (1 <= rs <= 5):
            return jsonify({"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}), 400
        obs_tag = item.get("observation_tag")
        if obs_tag is not None and obs_tag not in VALID_OBSERVATION_TAGS:
            valid = ", ".join(VALID_OBSERVATION_TAGS)
            return jsonify({"error": f"Invalid observation_tag '{obs_tag}'. Must be one of: {valid}."}), 400

    # Rule 6: assessor_staff_id — optional, positive integer if provided
    assessor_staff_id = data.get("assessor_staff_id")
    if assessor_staff_id is not None:
        if not isinstance(assessor_staff_id, int) or isinstance(assessor_staff_id, bool) or assessor_staff_id <= 0:
            return jsonify({"error": "assessor_staff_id must be a positive integer."}), 400

    # Rule 7: assessment_date — optional, valid date, not future, not > 7 days past
    assessment_date_raw = data.get("assessment_date")
    if assessment_date_raw is not None:
        try:
            assessment_dt = datetime.date.fromisoformat(str(assessment_date_raw))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
        today = _get_today()
        if assessment_dt > today:
            return jsonify({"error": "Assessment date cannot be in the future."}), 400
        if (today - assessment_dt).days > 7:
            return jsonify({"error": "Assessment date cannot be more than 7 days in the past."}), 400
        assessment_date_val = assessment_date_raw
    else:
        assessment_date_val = _get_today().isoformat()

    # Rule 8: overall_assessment_notes length
    notes = data.get("overall_assessment_notes") or None
    if notes is not None and len(str(notes)) > 2000:
        return jsonify({"error": "Field 'overall_assessment_notes' exceeds maximum length of 2000 characters."}), 400

    assessment_method = (data.get("assessment_method") or "observational").strip()
    VALID_ASSESSMENT_METHODS = ("observational", "performance", "direct")
    if assessment_method not in VALID_ASSESSMENT_METHODS:
        return jsonify({"error": f"Invalid assessment_method. Must be one of: {', '.join(VALID_ASSESSMENT_METHODS)}."}), 400

    # Rule 9: staff profile guard
    staff_id = user.get("staff_id")
    if not staff_id:
        return jsonify({
            "error": "Staff profile missing for this account. Contact your administrator."
        }), 500

    role = user["role"]

    # Rule 10: school assignment guard
    if role in ("head_coach", "assistant_coach", "coach_overseer"):
        if not user.get("school_id"):
            return jsonify({
                "error": "You have no active school assignment. Contact your administrator."
            }), 403

    if assessor_staff_id is None:
        assessor_staff_id = staff_id

    db = get_db()
    try:
        # Rule 11: student existence and school scope
        student_row = db.execute(
            "SELECT student_id, school_id FROM students"
            " WHERE student_id = ? AND active_status = 1 AND deleted_at IS NULL",
            (student_id,),
        ).fetchone()
        if not student_row:
            return jsonify({"error": "Student not found or is not active."}), 403

        student_school_id = student_row["school_id"]

        if role in ("head_coach", "assistant_coach"):
            if student_school_id != user["school_id"]:
                return jsonify({"error": "Student does not belong to your school."}), 403
        elif role == "coach_overseer":
            org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (user["school_id"],),
            ).fetchone()
            org_id = org_row["organization_id"] if org_row else None
            target_org_row = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ?",
                (student_school_id,),
            ).fetchone()
            target_org_id = target_org_row["organization_id"] if target_org_row else None
            if org_id != target_org_id:
                return jsonify({"error": "Student does not belong to a school in your organization."}), 403

        # Rule 12: window validation (skipped when window_id is omitted)
        if window_id is not None:
            window_row = db.execute(
                "SELECT window_id, school_id, status FROM assessment_windows WHERE window_id = ? AND deleted_at IS NULL",
                (window_id,),
            ).fetchone()
            if not window_row:
                return jsonify({"error": "Assessment window not found."}), 400
            if window_row["status"] != "active":
                return jsonify({"error": "Assessment window is not active."}), 400
            if window_row["school_id"] != student_school_id:
                return jsonify({"error": "Assessment window does not belong to the student's school."}), 400

        # Rule 13: skill_id validation
        for item in scores_raw:
            skill_row = db.execute(
                "SELECT skill_id FROM skills WHERE skill_id = ? AND active_status = 1",
                (item["skill_id"],),
            ).fetchone()
            if not skill_row:
                return jsonify({"error": f"Invalid or inactive skill_id: {item['skill_id']}."}), 400

        # Rule 14: duplicate assessment guard
        if window_id is not None:
            dup_row = db.execute(
                "SELECT assessment_id FROM assessments"
                " WHERE student_id = ? AND window_id = ? AND deleted_at IS NULL LIMIT 1",
                (student_id, window_id),
            ).fetchone()
        else:
            dup_row = db.execute(
                "SELECT assessment_id FROM assessments"
                " WHERE student_id = ? AND assessment_date = ? AND window_id IS NULL"
                " AND deleted_at IS NULL LIMIT 1",
                (student_id, assessment_date_val),
            ).fetchone()
        if dup_row:
            return jsonify({
                "error": "An assessment for this student already exists"
                         + (" for this window." if window_id else " on this date."),
                "existing_assessment_id": dup_row["assessment_id"],
            }), 409

        created_at_val = now_utc()
        cur = db.execute(
            """INSERT INTO assessments
               (student_id, school_id, program_id, session_id, window_id,
                assessed_by_staff_id, assessment_date, assessment_method,
                overall_assessment_notes, created_at)
               VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)""",
            (student_id, student_school_id, window_id,
             assessor_staff_id, assessment_date_val, assessment_method,
             notes, created_at_val),
        )
        new_assessment_id = cur.lastrowid

        for item in scores_raw:
            raw = item["raw_score"]
            norm = compute_normalized_score(raw)  # server-computed: raw * 20
            obs_tag = item.get("observation_tag")

            # growth_flag: 1 if this score beats the student's most recent prior score for this skill
            prev = db.execute(
                """SELECT a_sc.normalized_score
                   FROM assessment_scores a_sc
                   JOIN assessments a ON a.assessment_id = a_sc.assessment_id
                   WHERE a_sc.student_id = ? AND a_sc.skill_id = ? AND a.deleted_at IS NULL
                   ORDER BY a_sc.created_at DESC LIMIT 1""",
                (student_id, item["skill_id"]),
            ).fetchone()
            growth_flag = 1 if (prev and norm > prev["normalized_score"]) else 0

            db.execute(
                """INSERT INTO assessment_scores
                   (assessment_id, student_id, skill_id, raw_level, normalized_score,
                    benchmark_id, observed_independence, observed_consistency,
                    observed_accuracy, growth_flag, observation_tag, created_at)
                   VALUES (?, ?, ?, ?, ?, NULL, 1, 0, 0, ?, ?, ?)""",
                (new_assessment_id, student_id, item["skill_id"],
                 raw, norm, growth_flag, obs_tag, created_at_val),
            )

        # Recalculate all summary tables in the same transaction
        recalculate_student_summaries(db, student_id, student_school_id)

        audit(
            db, user["user_id"], "INSERT", "assessments", new_assessment_id,
            new_values={
                "student_id": student_id,
                "school_id": student_school_id,
                "window_id": window_id,
                "score_count": len(scores_raw),
            },
        )
        db.commit()

        # Post-commit: fetch for response
        display_row = db.execute(
            """SELECT a.assessment_id, a.student_id, a.school_id, sc.school_name,
                      a.window_id, aw.window_name, a.assessed_by_staff_id,
                      (u.first_name || ' ' || u.last_name) AS assessor_name,
                      a.assessment_date, a.assessment_method,
                      a.overall_assessment_notes, a.created_at
               FROM assessments a
               JOIN schools sc ON sc.school_id = a.school_id
               LEFT JOIN assessment_windows aw ON aw.window_id = a.window_id
               LEFT JOIN staff_profiles sp ON sp.staff_id = a.assessed_by_staff_id
               LEFT JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
               WHERE a.assessment_id = ?""",
            (new_assessment_id,),
        ).fetchone()

        score_rows = db.execute(
            """SELECT s.score_id, s.skill_id, sk.skill_name, s.raw_level, s.normalized_score
               FROM assessment_scores s
               LEFT JOIN skills sk ON sk.skill_id = s.skill_id
               WHERE s.assessment_id = ?""",
            (new_assessment_id,),
        ).fetchall()

        return jsonify({
            "ok": True,
            "assessment": serialize_assessment(
                display_row, [serialize_assessment_score(sr) for sr in score_rows]
            ),
        }), 201

    except Exception as exc:
        db.rollback()
        current_app.logger.error("submit_assessment ERROR: %s", exc)
        return jsonify({"error": "Assessment could not be saved — please try again or contact support."}), 500
    finally:
        db.close()


# ===========================================================================
# MY STUDENTS
# ===========================================================================

@coach_bp.route("/api/my-students", methods=["GET"])
@coach_required
def my_students():
    """
    Return students at the coach's currently assigned school.

    Scoped strictly to the coach's school_id from their active staff_assignment.
    coach_overseer sees all students (no school restriction).
    Supports ?grade_level=, ?search= query params.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    # Input validation — FERPA: limit surface area
    grade_filter = request.args.get("grade_level", "").strip()[:20]
    search_raw = request.args.get("search", "").strip()[:100]
    search = search_raw.lower()
    if search_raw and not re.match(r"^[a-zA-Z0-9\s\-']+$", search_raw):
        return jsonify({"error": "Invalid search term."}), 400

    db = get_db()
    try:
        # coach_overseer is scoped to their org only (not all orgs).
        # Regular coaches are scoped to their assigned school only.
        # Students table does NOT have organization_id — scope via schools JOIN.
        if user["role"] == "coach_overseer":
            # Overseer sees all schools in their organization
            # Get overseer's org via their staff assignment
            overseer_school = user.get("school_id")
            if overseer_school:
                org_row = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?",
                    (overseer_school,)
                ).fetchone()
                org_id = org_row["organization_id"] if org_row else None
            else:
                org_id = None

            if org_id:
                base_sql = """
                    SELECT s.student_id, s.student_first_name, s.student_last_name,
                           s.grade_level, s.school_id, s.active_status, s.created_at,
                           sc.school_name,
                           la.latest_assessment_date,
                           ROUND(AVG(CAST(asco.raw_level AS REAL)), 1) AS avg_raw_level
                    FROM students s
                    JOIN schools sc ON sc.school_id = s.school_id
                    LEFT JOIN (
                        SELECT student_id, MAX(assessment_date) AS latest_assessment_date
                        FROM assessments WHERE deleted_at IS NULL GROUP BY student_id
                    ) la ON la.student_id = s.student_id
                    LEFT JOIN assessments a
                        ON a.student_id = s.student_id
                        AND a.assessment_date = la.latest_assessment_date
                        AND a.deleted_at IS NULL
                    LEFT JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
                    WHERE s.active_status = TRUE AND s.deleted_at IS NULL
                      AND sc.organization_id = ?
                """
                params: list = [org_id]
            else:
                return jsonify({"ok": True, "students": [], "total": 0})
        else:
            school_id = user.get("school_id")
            if not school_id:
                return jsonify({
                    "ok": True, "students": [], "total": 0,
                    "message": "No school assignment found for this coach.",
                })
            base_sql = """
                SELECT s.student_id, s.student_first_name, s.student_last_name,
                       s.grade_level, s.school_id, s.active_status, s.created_at,
                       sc.school_name,
                       la.latest_assessment_date,
                       ROUND(AVG(CAST(asco.raw_level AS REAL)), 1) AS avg_raw_level
                FROM students s
                JOIN schools sc ON sc.school_id = s.school_id
                LEFT JOIN (
                    SELECT student_id, MAX(assessment_date) AS latest_assessment_date
                    FROM assessments WHERE deleted_at IS NULL GROUP BY student_id
                ) la ON la.student_id = s.student_id
                LEFT JOIN assessments a
                    ON a.student_id = s.student_id
                    AND a.assessment_date = la.latest_assessment_date
                    AND a.deleted_at IS NULL
                LEFT JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
                WHERE s.active_status = TRUE AND s.deleted_at IS NULL
                  AND s.school_id = ?
            """
            params = [school_id]

        if grade_filter:
            base_sql += " AND s.grade_level = ?"
            params.append(grade_filter)

        if search:
            base_sql += (
                " AND (LOWER(s.student_first_name) LIKE ?"
                " OR LOWER(s.student_last_name) LIKE ?)"
            )
            pattern = f"%{search.lower()}%"
            params.extend([pattern, pattern])

        base_sql += (
            " GROUP BY s.student_id, s.student_first_name, s.student_last_name,"
            " s.grade_level, s.school_id, s.active_status, s.created_at, sc.school_name,"
            " la.latest_assessment_date"
            " ORDER BY s.student_last_name ASC, s.student_first_name ASC LIMIT 500"
        )

        rows = db.execute(base_sql, params).fetchall()
        students = [serialize_student(r) for r in rows]

        # FERPA §99.2(b): audit every access to student records
        try:
            audit(
                db, user["user_id"], "READ", "students", None,
                new_values={"count": len(students), "scope": "my_students"},
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            current_app.logger.error("AUDIT FAILURE in my_students: %s", exc)

        return jsonify({"ok": True, "students": students, "total": len(students)})
    finally:
        db.close()


# ===========================================================================
# BEHAVIOR OBSERVATIONS  (TABLE 17)
# Lightweight per-session SEL tracking — separate from formal assessments.
# ===========================================================================

@coach_bp.route("/api/behavior-observations", methods=["POST"])
@limiter.limit("20 per minute")
@coach_required
def submit_behavior_observation():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    observation_date = data.get("observation_date")

    if not student_id or not isinstance(student_id, int) or student_id <= 0:
        return jsonify({"error": "student_id is required."}), 400

    score_fields = ("teamwork_score", "effort_score", "self_control_score",
                    "listening_score", "sportsmanship_score", "confidence_score")
    scores = {}
    for field in score_fields:
        val = data.get(field)
        if val is not None:
            if not isinstance(val, int) or not (1 <= val <= 5):
                return jsonify({"error": f"{field} must be an integer 1–5."}), 400
            scores[field] = val

    if not scores:
        return jsonify({"error": "At least one behavior score is required."}), 400

    if observation_date:
        try:
            datetime.date.fromisoformat(str(observation_date))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid observation_date. Use YYYY-MM-DD."}), 400
    else:
        observation_date = _get_today().isoformat()

    staff_id = user.get("staff_id")
    if not staff_id:
        return jsonify({"error": "Staff profile missing for this account."}), 500

    db = get_db()
    try:
        student = db.execute(
            "SELECT student_id, school_id FROM students WHERE student_id = ? AND active_status = 1 AND deleted_at IS NULL",
            (student_id,),
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found or not active."}), 404

        school_id = student["school_id"]
        if user["role"] in ("head_coach", "assistant_coach") and user.get("school_id") != school_id:
            return jsonify({"error": "Student does not belong to your school."}), 403

        if session_id is not None:
            sess = db.execute(
                "SELECT session_id FROM sessions WHERE session_id = ? AND school_id = ? AND deleted_at IS NULL",
                (session_id, school_id),
            ).fetchone()
            if not sess:
                return jsonify({"error": "Session not found."}), 404

        cur = db.execute(
            """INSERT INTO behavior_observations
               (student_id, school_id, session_id, observed_by_staff_id, observation_date,
                teamwork_score, effort_score, self_control_score, listening_score,
                sportsmanship_score, confidence_score, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id, school_id, session_id, staff_id, observation_date,
             scores.get("teamwork_score"), scores.get("effort_score"),
             scores.get("self_control_score"), scores.get("listening_score"),
             scores.get("sportsmanship_score"), scores.get("confidence_score"),
             (data.get("notes") or "")[:1000] or None, now_utc()),
        )
        audit(db, user["user_id"], "INSERT", "behavior_observations", cur.lastrowid,
              new_values={"student_id": student_id, "session_id": session_id})
        db.commit()
        return jsonify({"ok": True, "behavior_observation_id": cur.lastrowid}), 201
    finally:
        db.close()


@coach_bp.route("/api/behavior-observations", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer", "site_coordinator", "head_coach", "assistant_coach")
def list_behavior_observations():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    student_id = request.args.get("student_id", type=int)
    session_id = request.args.get("session_id", type=int)
    role = user["role"]
    staff_id = user["staff_id"]

    db = get_db()
    try:
        sql = """
            SELECT bo.*,
                   st.student_first_name, st.student_last_name,
                   (u.first_name || ' ' || u.last_name) AS observer_name
            FROM behavior_observations bo
            JOIN students st ON st.student_id = bo.student_id AND st.deleted_at IS NULL
            JOIN staff_profiles sp ON sp.staff_id = bo.observed_by_staff_id
            JOIN users u ON u.user_id = sp.user_id AND u.deleted_at IS NULL
            WHERE bo.deleted_at IS NULL
        """
        params: list = []

        if student_id:
            # Validate student access
            student = db.execute(
                "SELECT school_id FROM students WHERE student_id = ? AND active_status = 1 AND deleted_at IS NULL",
                (student_id,),
            ).fetchone()
            if not student:
                return jsonify({"error": "Student not found."}), 404
            if role in ("head_coach", "assistant_coach") and user.get("school_id") != student["school_id"]:
                return jsonify({"error": "Student does not belong to your school."}), 403
            sql += " AND bo.student_id = ?"
            params.append(student_id)
        else:
            # Scope to the coach's school(s) when no student filter is given.
            if role in ("head_coach", "assistant_coach"):
                school_id = user.get("school_id")
                if not school_id:
                    return jsonify({"error": "You have no active school assignment."}), 403
                sql += " AND bo.school_id = ?"
                params.append(school_id)
            elif role == "site_coordinator":
                sql += (" AND bo.school_id IN"
                        " (SELECT school_id FROM staff_assignments"
                        "  WHERE staff_id = ? AND active_status = 1 AND deleted_at IS NULL)")
                params.append(staff_id)
            elif role == "coach_overseer":
                overseer_school = user.get("school_id")
                if not overseer_school:
                    return jsonify({"error": "You have no active school assignment."}), 403
                org_row = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ? AND deleted_at IS NULL",
                    (overseer_school,),
                ).fetchone()
                if not org_row:
                    return jsonify({"error": "You have no active school assignment."}), 403
                sql += " AND bo.school_id IN (SELECT school_id FROM schools WHERE organization_id = ? AND deleted_at IS NULL)"
                params.append(org_row["organization_id"])
            else:
                # admin / ceo — scope to their org; CEO with no org sees all (intentional)
                from app.routes.admin_routes import _get_org_scope
                org_id = _get_org_scope(db, user)
                if org_id:
                    sql += " AND bo.school_id IN (SELECT school_id FROM schools WHERE organization_id = ? AND deleted_at IS NULL)"
                    params.append(org_id)

        if session_id:
            sql += " AND bo.session_id = ?"
            params.append(session_id)
        sql += " ORDER BY bo.observation_date DESC, bo.created_at DESC LIMIT 100"

        rows = db.execute(sql, params).fetchall()
        audit(db, user["user_id"], "READ", "behavior_observations", None,
              new_values={"scope": "coach_list", "count": len(rows)})
        db.commit()
        return jsonify({"ok": True, "observations": [dict(r) for r in rows]})
    finally:
        db.close()


# ===========================================================================
# ASSESSMENT WINDOWS  (TABLE 14)
# Coaches read windows; admins create them (see admin_routes.py).
# ===========================================================================

@coach_bp.route("/api/coach/assessment-windows", methods=["GET"])
@coach_required
def list_assessment_windows():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    school_id = request.args.get("school_id", type=int) or user.get("school_id")
    if not school_id:
        return jsonify({"ok": True, "windows": []})

    if user["role"] in ("head_coach", "assistant_coach") and school_id != user.get("school_id"):
        return jsonify({"error": "You can only view windows for your assigned school."}), 403

    status_filter = request.args.get("status", "").strip()

    db = get_db()
    try:
        sql = """
            SELECT aw.window_id, aw.school_id, sc.school_name,
                   aw.program_id, p.program_name,
                   aw.window_name, aw.start_date, aw.end_date,
                   aw.assessment_focus, aw.status, aw.created_at
            FROM assessment_windows aw
            JOIN schools sc ON sc.school_id = aw.school_id
            LEFT JOIN programs p ON p.program_id = aw.program_id
            WHERE aw.school_id = ? AND aw.deleted_at IS NULL
        """
        params = [school_id]
        if status_filter in ("upcoming", "active", "closed"):
            sql += " AND aw.status = ?"
            params.append(status_filter)
        sql += " ORDER BY aw.start_date DESC"

        rows = db.execute(sql, params).fetchall()
        return jsonify({"ok": True, "windows": [dict(r) for r in rows]})
    finally:
        db.close()


# ===========================================================================
# COACH OBSERVATIONS  (TABLE 20)
# Evaluators (head_coach, coach_overseer, admin) score coach performance.
# ===========================================================================

@coach_bp.route("/api/coach-observations", methods=["POST"])
@limiter.limit("10 per minute")
@coach_required
def submit_coach_observation():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    # Only head_coach and coach_overseer can evaluate from this portal
    if user["role"] not in ("head_coach", "coach_overseer"):
        return jsonify({"error": "Only head coaches and overseers can submit coach observations."}), 403

    data = parse_json()
    observed_staff_id = data.get("observed_staff_id")
    school_id = data.get("school_id") or user.get("school_id")
    observation_date = data.get("observation_date")

    if not observed_staff_id or not isinstance(observed_staff_id, int) or observed_staff_id <= 0:
        return jsonify({"error": "observed_staff_id is required."}), 400

    if not school_id:
        return jsonify({"error": "school_id is required."}), 400

    score_fields = ("transitions_score", "engagement_score", "lesson_fidelity_score",
                    "sel_language_score", "safety_score", "organization_score")
    scores = {}
    for field in score_fields:
        val = data.get(field)
        if val is not None:
            if not isinstance(val, int) or not (1 <= val <= 5):
                return jsonify({"error": f"{field} must be an integer 1–5."}), 400
            scores[field] = val

    if len(scores) < 6:
        return jsonify({"error": "All 6 observation scores are required: " + ", ".join(score_fields)}), 400

    if observation_date:
        try:
            datetime.date.fromisoformat(str(observation_date))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid observation_date. Use YYYY-MM-DD."}), 400
    else:
        observation_date = _get_today().isoformat()

    staff_id = user.get("staff_id")
    if not staff_id:
        return jsonify({"error": "Staff profile missing for this account."}), 500

    db = get_db()
    try:
        observed = db.execute(
            "SELECT staff_id FROM staff_profiles WHERE staff_id = ? AND status = 'active'",
            (observed_staff_id,),
        ).fetchone()
        if not observed:
            return jsonify({"error": "Observed staff member not found."}), 404

        if observed_staff_id == staff_id:
            return jsonify({"error": "You cannot submit a self-observation."}), 400

        cur = db.execute(
            """INSERT INTO coach_observations
               (observed_staff_id, evaluator_staff_id, school_id, observation_date,
                transitions_score, engagement_score, lesson_fidelity_score,
                sel_language_score, safety_score, organization_score,
                notes, action_plan, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (observed_staff_id, staff_id, school_id, observation_date,
             scores["transitions_score"], scores["engagement_score"],
             scores["lesson_fidelity_score"], scores["sel_language_score"],
             scores["safety_score"], scores["organization_score"],
             (data.get("notes") or "")[:2000] or None,
             (data.get("action_plan") or "")[:2000] or None, now_utc()),
        )
        audit(db, user["user_id"], "INSERT", "coach_observations", cur.lastrowid,
              new_values={"observed_staff_id": observed_staff_id, "school_id": school_id})
        db.commit()

        avg = round(sum(scores.values()) / 6, 1)
        return jsonify({
            "ok": True,
            "coach_observation_id": cur.lastrowid,
            "average_score": avg,
        }), 201
    finally:
        db.close()


@coach_bp.route("/api/coach-observations", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer", "head_coach")
def list_coach_observations():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    staff_id_filter = request.args.get("staff_id", type=int)
    school_id_filter = request.args.get("school_id", type=int) or user.get("school_id")

    if user["role"] in ("head_coach",) and school_id_filter != user.get("school_id"):
        return jsonify({"error": "You can only view observations for your assigned school."}), 403

    db = get_db()
    try:
        sql = """
            SELECT co.*,
                   (ou.first_name || ' ' || ou.last_name) AS observed_name,
                   (eu.first_name || ' ' || eu.last_name) AS evaluator_name,
                   sc.school_name,
                   ROUND((co.transitions_score + co.engagement_score + co.lesson_fidelity_score +
                          co.sel_language_score + co.safety_score + co.organization_score) / 6.0, 1) AS average_score
            FROM coach_observations co
            JOIN staff_profiles osp ON osp.staff_id = co.observed_staff_id
            JOIN users ou ON ou.user_id = osp.user_id AND ou.deleted_at IS NULL
            JOIN staff_profiles esp ON esp.staff_id = co.evaluator_staff_id
            JOIN users eu ON eu.user_id = esp.user_id AND eu.deleted_at IS NULL
            JOIN schools sc ON sc.school_id = co.school_id
            WHERE co.school_id = ? AND co.deleted_at IS NULL
        """
        params = [school_id_filter]
        if staff_id_filter:
            sql += " AND co.observed_staff_id = ?"
            params.append(staff_id_filter)
        sql += " ORDER BY co.observation_date DESC, co.created_at DESC LIMIT 200"

        rows = db.execute(sql, params).fetchall()
        return jsonify({"ok": True, "observations": [dict(r) for r in rows]})
    finally:
        db.close()


@coach_bp.route("/api/coach/my-score", methods=["GET"])
@coach_required
def my_score():
    """Returns the requesting coach's rolling 30-day scorecard."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    staff_id  = user.get("staff_id")
    school_id = user.get("school_id")
    if not staff_id or not school_id:
        return jsonify({"error": "No active staff assignment."}), 403

    from app.routes._coach_scoring import calculate_coach_score, rolling_period
    period_start, period_end = rolling_period()

    db = get_db()
    try:
        try:
            scorecard = calculate_coach_score(db, staff_id, school_id, period_start, period_end)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        # Keep rolling_score / rolling_band current so admin coaches list reflects live data.
        try:
            db.execute(
                "UPDATE staff_profiles SET rolling_score = ?, rolling_band = ? WHERE staff_id = ?",
                (scorecard["overall_score"], scorecard["performance_band"], staff_id),
            )
            db.commit()
        except Exception:
            db.rollback()
        snapshots = db.execute(
            "SELECT * FROM coach_performance_snapshots"
            " WHERE staff_id=? AND school_id=? ORDER BY period_end DESC LIMIT 12",
            (staff_id, school_id),
        ).fetchall()
        return jsonify({
            "ok": True,
            "scorecard": scorecard,
            "snapshots": [dict(r) for r in snapshots],
        })
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Coach Evaluations (head_coach only)
# ---------------------------------------------------------------------------

def _get_head_coach_staff_id(db, user_id: int):
    row = db.execute(
        """SELECT sp.staff_id, sa.school_id
           FROM staff_profiles sp
           JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
           WHERE sp.user_id = ?
             AND sa.active_status = 1
             AND sa.deleted_at IS NULL
             AND sp.deleted_at IS NULL
           ORDER BY sa.created_at DESC LIMIT 1""",
        (user_id,),
    ).fetchone()
    return (row["staff_id"], row["school_id"]) if row else (None, None)


@coach_bp.route("/api/coach/subordinates", methods=["GET"])
@roles_required("head_coach", "site_coordinator", "coach_overseer")
def get_coach_subordinates():
    """Return assistant coaches at the same school as the authenticated head coach."""
    user = current_user()
    db = get_db()
    try:
        _, school_id = _get_head_coach_staff_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found."}), 403

        rows = db.execute(
            """SELECT u.user_id, u.first_name, u.last_name, u.role,
                      sp.staff_id, sp.position_title
               FROM users u
               JOIN staff_profiles sp ON sp.user_id = u.user_id AND sp.deleted_at IS NULL
               JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
               WHERE sa.school_id = ?
                 AND sa.active_status = 1
                 AND sa.deleted_at IS NULL
                 AND u.active_status = 1
                 AND u.deleted_at IS NULL
                 AND u.role = 'assistant_coach'
               ORDER BY u.last_name ASC, u.first_name ASC""",
            (school_id,),
        ).fetchall()

        coaches = [
            {
                "staff_id": r["staff_id"],
                "user_id": r["user_id"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "role": r["role"],
                "position_title": r["position_title"],
            }
            for r in rows
        ]
        return jsonify({"ok": True, "coaches": coaches, "school_id": school_id})
    except Exception:
        import logging
        logging.exception("get_coach_subordinates error")
        return jsonify({"error": "Could not load subordinates."}), 500
    finally:
        db.close()


@coach_bp.route("/api/coach/evaluations", methods=["POST"])
@limiter.limit("5 per minute")
@roles_required("head_coach", "site_coordinator", "coach_overseer")
def submit_coach_evaluation():
    """Head coach submits an evaluation for an assistant coach at their school."""
    user = current_user()
    data = parse_json()
    db = get_db()
    try:
        evaluator_staff_id, school_id = _get_head_coach_staff_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found."}), 403

        # Validate evaluated coach is at same school
        evaluated_staff_id = data.get("evaluated_staff_id")
        try:
            evaluated_staff_id = int(evaluated_staff_id)
        except (TypeError, ValueError):
            return jsonify({"error": "evaluated_staff_id is required."}), 422

        row = db.execute(
            """SELECT sa.staff_id FROM staff_assignments sa
               JOIN staff_profiles sp ON sp.staff_id = sa.staff_id
               JOIN users u ON u.user_id = sp.user_id
               WHERE sa.staff_id = ? AND sa.school_id = ?
                 AND sa.active_status = 1 AND sa.deleted_at IS NULL
                 AND sp.deleted_at IS NULL AND u.role = 'assistant_coach'""",
            (evaluated_staff_id, school_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Coach not found at your school."}), 404

        def _r(key):
            v = data.get(key)
            try:
                v = int(v)
                if not (1 <= v <= 5):
                    raise ValueError
                return v
            except (TypeError, ValueError):
                return None

        rating_fields = [
            "shows_up_consistently", "reports_on_time", "processes_consistently",
            "follows_sop", "problem_solves", "demonstrates_improvement",
            "apprises_lead_coach", "provides_feedback_to_lead", "follows_up_timely", "communicates_regularly",
            "practices_restorative_justice", "creates_inclusive_environment", "teaches_transferable_skills",
            "maintains_positive_atmosphere", "uses_reward_systems", "implements_activities_fidelity",
            "learns_student_names", "provides_student_feedback", "uses_positive_language",
            "provides_supervision", "uses_designated_spaces", "ensures_safe_areas", "determines_best_areas",
            "follows_safety_procedures", "maintains_equipment", "maintains_orderly_flow",
            "implements_rules_safeguards",
        ]
        ratings = {f: _r(f) for f in rating_fields}
        missing = [f for f, v in ratings.items() if v is None]
        if missing:
            return jsonify({"error": f"Missing or invalid rating fields: {', '.join(missing)}"}), 422

        same_day_calloff = 1 if data.get("same_day_calloff") else 0
        email = str(data.get("email") or "").strip()[:200] or None
        if email and not re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            return jsonify({"error": "Invalid email format."}), 422
        coach_strengths = str(data.get("coach_strengths") or "").strip()[:5000] or None
        coach_weaknesses = str(data.get("coach_weaknesses") or "").strip()[:5000] or None
        improvement_plan = str(data.get("improvement_plan") or "").strip()[:5000] or None

        cols = ["school_id", "evaluator_staff_id", "evaluated_staff_id", "email",
                "same_day_calloff"] + rating_fields + ["coach_strengths", "coach_weaknesses",
                "improvement_plan", "submitted_at"]
        vals = ([school_id, evaluator_staff_id, evaluated_staff_id, email, same_day_calloff]
                + [ratings[f] for f in rating_fields]
                + [coach_strengths, coach_weaknesses, improvement_plan, now_utc()])

        placeholders = ", ".join("?" * len(cols))
        col_names = ", ".join(cols)
        db.execute(
            f"INSERT INTO coach_evaluations ({col_names}) VALUES ({placeholders})",
            vals,
        )
        audit(db, user["user_id"], "CREATE", "coach_evaluations", None,
              new_values={"evaluated_staff_id": evaluated_staff_id, "school_id": school_id})
        db.commit()
        return jsonify({"ok": True}), 201
    except Exception:
        import logging
        logging.exception("submit_coach_evaluation error")
        return jsonify({"error": "Could not submit evaluation."}), 500
    finally:
        db.close()


@coach_bp.route("/api/coach/evaluations", methods=["GET"])
@roles_required("head_coach", "site_coordinator", "coach_overseer")
def list_coach_evaluations():
    """Return evaluations submitted by the authenticated head coach."""
    user = current_user()
    db = get_db()
    try:
        evaluator_staff_id, school_id = _get_head_coach_staff_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found."}), 403

        rows = db.execute(
            """SELECT ce.*,
                      COALESCE(u.first_name || ' ' || u.last_name, '[Deleted]') AS evaluated_name,
                      u.role AS evaluated_role
               FROM coach_evaluations ce
               LEFT JOIN staff_profiles sp ON sp.staff_id = ce.evaluated_staff_id
               LEFT JOIN users u ON u.user_id = sp.user_id
               WHERE ce.evaluator_staff_id = ?
               ORDER BY ce.submitted_at DESC LIMIT 50""",
            (evaluator_staff_id,),
        ).fetchall()
        return jsonify({"ok": True, "evaluations": [dict(r) for r in rows]})
    except Exception:
        import logging
        logging.exception("list_coach_evaluations error")
        return jsonify({"error": "Could not load evaluations."}), 500
    finally:
        db.close()
