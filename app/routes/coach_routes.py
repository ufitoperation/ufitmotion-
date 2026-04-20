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
from flask import Blueprint, jsonify, request

from app.auth import coach_required, current_user
from app.database import get_db
from app.routes._helpers import (
    audit, now_utc, parse_json,
    serialize_eod_report, serialize_incident, serialize_session, serialize_student,
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
              {scope_sql}
              {school_filter_sql}
        """
        count_params = [from_date, to_date] + scope_params + school_filter_params
        total = db.execute(count_sql, count_params).fetchone()["cnt"]
        pages = math.ceil(total / per_page) if total > 0 else 0
        offset = (page - 1) * per_page

        main_sql = f"""
            SELECT se.session_id, se.school_id, sc.school_name, se.program_id, p.program_name,
                   se.session_date, se.start_time, se.end_time, se.session_type, se.location,
                   se.planned_activity, se.actual_activity, se.student_group_name,
                   se.session_status, se.total_students_present, se.notes, se.created_at,
                   (u.first_name || ' ' || u.last_name) AS coach_name
            FROM sessions se
            JOIN schools sc ON sc.school_id = se.school_id
            JOIN programs p ON p.program_id = se.program_id
            LEFT JOIN session_staff ss ON ss.session_id = se.session_id AND ss.role = 'lead'
            LEFT JOIN staff_profiles sp2 ON sp2.staff_id = ss.staff_id
            LEFT JOIN users u ON u.user_id = sp2.user_id
            WHERE se.session_date >= ? AND se.session_date <= ?
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
        print(f"list_sessions ERROR: {exc}", file=sys.stderr, flush=True)
        return jsonify({"error": "Could not load sessions — please try again or contact support."}), 500
    finally:
        db.close()


@coach_bp.route("/api/sessions", methods=["POST"])
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
            " WHERE program_id = ? AND school_id = ? AND program_status = 'active'",
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
                student_group_name, session_status, total_students_present, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, program_id, session_date_raw, start_time, end_time,
             session_type, location, planned_activity, actual_activity,
             student_group_name, session_status, n_students, notes, created_at_val),
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
        print(f"create_session ERROR: {exc}", file=sys.stderr, flush=True)
        return jsonify({"error": "Session could not be saved — please try again or contact support."}), 500
    finally:
        db.close()


# ===========================================================================
# EOD REPORTS
# ===========================================================================

@coach_bp.route("/api/eod-reports", methods=["GET"])
@coach_required
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
                "  WHERE staff_id = ? AND active_status = 1)"
            )
            scope_params = [staff_id]
            if school_id_filter is not None:
                assigned = db.execute(
                    "SELECT 1 FROM staff_assignments"
                    " WHERE staff_id = ? AND school_id = ? AND active_status = 1",
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

        return jsonify({
            "ok": True,
            "eod_reports": [serialize_eod_report(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        })

    except Exception as exc:
        print(f"list_eod_reports ERROR: {exc}", file=sys.stderr, flush=True)
        return jsonify({"error": "Could not load EOD reports — please try again or contact support."}), 500
    finally:
        db.close()


@coach_bp.route("/api/eod-reports", methods=["POST"])
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
        deadline_pacific = now_pacific.replace(hour=20, minute=0, second=0, microsecond=0)
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
                " WHERE program_id = ? AND school_id = ? AND program_status = 'active'",
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
        print(f"create_eod_report ERROR: {exc}", file=sys.stderr, flush=True)
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

    filter_sql = ""
    filter_params: list = []

    if from_date:
        filter_sql += " AND ir.report_date >= ?"
        filter_params.append(from_date)
    if to_date:
        filter_sql += " AND ir.report_date <= ?"
        filter_params.append(to_date)
    if status_filter:
        filter_sql += " AND ir.status = ?"
        filter_params.append(status_filter)
    if severity_filter:
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
            "  WHERE staff_id = ? AND active_status = 1)"
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
        " ir.status, ir.resolution_notes, ir.created_at"
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
                   (user_id, title, body, notification_type, related_table, related_id, created_at)
                   SELECT DISTINCT u.user_id,
                          'Critical Incident Filed',
                          'A critical incident was filed at ' || sc.school_name || ' on ' || ?,
                          'incident',
                          'incident_reports',
                          ?,
                          ?
                   FROM users u
                   JOIN staff_profiles sp ON sp.user_id = u.user_id
                   JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
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
    """
    TODO: Return assessment records for students at the coach's school.
    Supports ?student_id=, ?window_id=, ?domain_id=, ?school_id= query params.
    Returns skill scores, domain averages, benchmark comparisons.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/assessments"})


@coach_bp.route("/api/assessments", methods=["POST"])
@coach_required
def submit_assessment():
    """
    TODO: Submit skill assessment scores for a student.
    Body: {
      student_id, window_id, assessor_staff_id,
      scores: [{ skill_id, raw_score, benchmark_id }]
    }
    Validate student belongs to coach's school (no cross-org access).
    Insert into assessments + assessment_scores.
    Trigger re-calculation of student_skill_summary, student_domain_summary,
    student_overall_summary via summary update helper.
    Audit. Return assessment with scores.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/assessments"}), 201


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
                           sc.school_name
                    FROM students s
                    JOIN schools sc ON sc.school_id = s.school_id
                    WHERE s.active_status = TRUE AND s.deleted_at IS NULL
                      AND sc.organization_id = ?
                """
                params: list = [org_id]
            else:
                return jsonify({"ok": True, "students": [], "count": 0})
        else:
            school_id = user.get("school_id")
            if not school_id:
                return jsonify({
                    "ok": True, "students": [], "count": 0,
                    "message": "No school assignment found for this coach.",
                })
            base_sql = """
                SELECT s.student_id, s.student_first_name, s.student_last_name,
                       s.grade_level, s.school_id, s.active_status, s.created_at,
                       sc.school_name
                FROM students s
                JOIN schools sc ON sc.school_id = s.school_id
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
            pattern = f"%{search}%"
            params.extend([pattern, pattern])

        base_sql += " ORDER BY s.student_last_name ASC, s.student_first_name ASC"

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
            print(f"AUDIT FAILURE in my_students: {exc}", file=sys.stderr, flush=True)

        return jsonify({"ok": True, "students": students, "count": len(students)})
    finally:
        db.close()
