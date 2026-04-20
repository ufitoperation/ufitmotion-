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
from flask import Blueprint, jsonify, request

from app.auth import coach_required, current_user
from app.database import get_db
from app.routes._helpers import audit, now_utc, parse_json, serialize_session, serialize_student

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


def _get_today() -> datetime.date:
    """Return today's date. Monkeypatchable in tests."""
    return datetime.date.today()


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
    """
    TODO: Return EOD reports filed by the current coach.
    - coach_overseer: see all coaches' reports.
    Supports ?school_id=, ?from=, ?to=, ?page=, ?per_page= query params.
    Returns report date, school, summary, incidents_count, filed_at timestamp.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/eod-reports"})


@coach_bp.route("/api/eod-reports", methods=["POST"])
@coach_required
def create_eod_report():
    """
    TODO: Submit an end-of-day report.
    Body: {
      school_id, report_date, session_ids (list),
      highlights, challenges, student_concerns,
      equipment_issues, weather_notes, incidents_count
    }
    Validate: one EOD per coach per date per school.
    Insert into eod_reports. Link to sessions.
    If incidents_count > 0 and no incident report exists, flag for follow-up.
    Audit. Return created report.
    Target: coach can complete this in under 2 minutes on mobile.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/eod-reports"}), 201


# ===========================================================================
# INCIDENTS
# ===========================================================================

@coach_bp.route("/api/incidents", methods=["GET"])
@coach_required
def list_incidents():
    """
    TODO: Return incident reports visible to the current coach.
    - Regular coaches: only their own reports.
    - coach_overseer / site_coordinator: all reports at their scope.
    Supports ?status=, ?severity=, ?school_id=, ?from=, ?to= query params.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/incidents"})


@coach_bp.route("/api/incidents", methods=["POST"])
@coach_required
def create_incident():
    """
    TODO: File an incident report.
    Body: {
      school_id, session_id (optional), student_id (optional),
      incident_date, incident_time, severity,  # 'low' | 'medium' | 'high' | 'critical'
      description, immediate_action_taken,
      parent_notified, admin_notified, medical_attention_required
    }
    severity = 'critical' → auto-notify all admin users via notifications table.
    Audit. Return created incident.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/incidents"}), 201


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
