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

import re
import sys
from flask import Blueprint, jsonify, request

from app.auth import coach_required, current_user
from app.database import get_db
from app.routes._helpers import audit, now_utc, parse_json, serialize_student

coach_bp = Blueprint("coach", __name__)


# ===========================================================================
# SESSIONS
# ===========================================================================

@coach_bp.route("/api/sessions", methods=["GET"])
@coach_required
def list_sessions():
    """
    TODO: Return sessions for the coach's assigned school(s).
    - head_coach / assistant_coach: see sessions at their assigned school only.
    - site_coordinator: see sessions across all schools in their region.
    - coach_overseer: see all sessions.
    Supports ?school_id=, ?from=, ?to=, ?page=, ?per_page= query params.
    Returns session date, school name, attending student count, coach names,
    and EOD report filed status.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/sessions"})


@coach_bp.route("/api/sessions", methods=["POST"])
@coach_required
def create_session():
    """
    TODO: Log a new PE session.
    Body: {
      school_id, program_id, session_date, start_time, end_time,
      location, student_ids (list), notes
    }
    Validate school assignment matches coach's school (unless overseer).
    Insert session row, insert session_staff row for the current coach,
    insert student_session_attendance rows for each student_id.
    Audit. Return created session.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/sessions"}), 201


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
