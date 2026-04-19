"""
admin_routes.py — Admin portal blueprint for Ufit Motion.

All routes require the 'ceo' or 'admin' role (admin_required decorator).
Stubs return {"ok": true, "stub": true} with a comment describing the
full implementation that will replace each stub.

Route inventory:
  GET/POST   /api/organizations
  GET/POST   /api/schools
  DELETE     /api/schools/<id>
  GET/POST   /api/users
  DELETE     /api/users/<id>
  GET/POST   /api/students
  DELETE     /api/students/<id>
  GET/POST   /api/programs
  DELETE     /api/programs/<id>
  GET        /api/reports
  GET        /api/dashboard
"""

from flask import Blueprint, jsonify, request

from app.auth import admin_required, current_user
from app.database import get_db
from app.routes._helpers import audit, now_utc, parse_json, serialize_school, serialize_student, serialize_user

admin_bp = Blueprint("admin", __name__)


# ===========================================================================
# ORGANIZATIONS
# ===========================================================================

@admin_bp.route("/api/organizations", methods=["GET"])
@admin_required
def list_organizations():
    """
    TODO: Return paginated list of all organizations with school counts,
    active contract status, and billing contact info.
    Supports ?search=, ?status= query params.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/organizations"})


@admin_bp.route("/api/organizations", methods=["POST"])
@admin_required
def create_organization():
    """
    TODO: Create a new organization.
    Body: { organization_name, organization_type, billing_contact, billing_email, contract_status }
    Validate required fields, check for duplicate names, insert, audit, return created row.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/organizations"}), 201


# ===========================================================================
# SCHOOLS
# ===========================================================================

@admin_bp.route("/api/schools", methods=["GET"])
@admin_required
def list_schools():
    """
    TODO: Return all active schools with organization name, region name,
    student count, coach count, and active program count.
    Supports ?org_id=, ?region_id=, ?search= query params.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/schools"})


@admin_bp.route("/api/schools", methods=["POST"])
@admin_required
def create_school():
    """
    TODO: Create a new school.
    Body: { organization_id, region_id, school_name, school_type, address,
            city, state, zip_code, principal_name, principal_email }
    Validate org exists, insert, audit, return created school.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/schools"}), 201


@admin_bp.route("/api/schools/<int:school_id>", methods=["DELETE"])
@admin_required
def delete_school(school_id: int):
    """
    TODO: Soft-delete a school (set deleted_at = NOW()).
    Cascades to deactivate staff assignments and programs at that school.
    Prevent delete if active students are enrolled.
    """
    return jsonify({"ok": True, "stub": True, "route": f"DELETE /api/schools/{school_id}"})


# ===========================================================================
# USERS
# ===========================================================================

@admin_bp.route("/api/users", methods=["GET"])
@admin_required
def list_users():
    """
    TODO: Return paginated list of all staff users (all roles except parent).
    Includes role, assigned school, position_title, active_status.
    Supports ?role=, ?school_id=, ?search=, ?page=, ?per_page= query params.
    Strips password_hash and auth_uid from all rows.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/users"})


@admin_bp.route("/api/users", methods=["POST"])
@admin_required
def create_user():
    """
    TODO: Create a new staff user account.
    Body: { first_name, last_name, email, role, password, school_id, position_title }
    Hash password with werkzeug, create staff_profile, optionally create staff_assignment.
    Audit the creation. Return serialized user (no password_hash).
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/users"}), 201


@admin_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id: int):
    """
    TODO: Soft-delete a user (set deleted_at = NOW(), active_status = FALSE).
    Cannot delete self. Cannot delete last CEO.
    Audit the deletion.
    """
    return jsonify({"ok": True, "stub": True, "route": f"DELETE /api/users/{user_id}"})


# ===========================================================================
# STUDENTS
# ===========================================================================

@admin_bp.route("/api/students", methods=["GET"])
@admin_required
def list_students():
    """
    TODO: Return paginated student list scoped to org (HARD RULE: no cross-org leakage).
    Includes school_name, grade_level, active program enrollments.
    Supports ?school_id=, ?grade_level=, ?search=, ?page=, ?per_page= query params.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/students"})


@admin_bp.route("/api/students", methods=["POST"])
@admin_required
def create_student():
    """
    TODO: Create a new student record.
    Body: { first_name, last_name, grade_level, school_id, gender, date_of_birth }
    Validate school exists and belongs to an org the admin can see.
    Audit the creation. Return serialized student.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/students"}), 201


@admin_bp.route("/api/students/<int:student_id>", methods=["DELETE"])
@admin_required
def delete_student(student_id: int):
    """
    TODO: Soft-delete a student (set deleted_at = NOW(), active_status = FALSE).
    Unenroll from active programs. Retain assessment history.
    Audit the deletion.
    """
    return jsonify({"ok": True, "stub": True, "route": f"DELETE /api/students/{student_id}"})


# ===========================================================================
# PROGRAMS
# ===========================================================================

@admin_bp.route("/api/programs", methods=["GET"])
@admin_required
def list_programs():
    """
    TODO: Return all programs with school name, coach count, student enrollment count,
    start/end dates, and active status.
    Supports ?school_id=, ?active=, ?search= query params.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/programs"})


@admin_bp.route("/api/programs", methods=["POST"])
@admin_required
def create_program():
    """
    TODO: Create a new PE program.
    Body: { school_id, program_name, program_type, start_date, end_date, description }
    Validate school exists. Insert. Audit. Return created program.
    """
    return jsonify({"ok": True, "stub": True, "route": "POST /api/programs"}), 201


@admin_bp.route("/api/programs/<int:program_id>", methods=["DELETE"])
@admin_required
def delete_program(program_id: int):
    """
    TODO: Soft-delete a program. Unenroll all students. Cancel future sessions.
    Audit with full pre-delete snapshot.
    """
    return jsonify({"ok": True, "stub": True, "route": f"DELETE /api/programs/{program_id}"})


# ===========================================================================
# REPORTS
# ===========================================================================

@admin_bp.route("/api/reports", methods=["GET"])
@admin_required
def list_reports():
    """
    TODO: Return list of available reports:
      - EOD report submissions by coach and date range
      - Incident reports by school/severity
      - Student assessment score summaries
      - Coach session compliance (sessions filed vs. scheduled)
      - School progress reports
    Accepts ?type=, ?school_id=, ?from=, ?to= query params.
    Each report type returns aggregated rows, not raw data.
    """
    return jsonify({"ok": True, "stub": True, "route": "GET /api/reports"})


# ===========================================================================
# DASHBOARD
# ===========================================================================

@admin_bp.route("/api/dashboard", methods=["GET"])
@admin_required
def dashboard():
    """
    Return key metrics for the admin dashboard.

    Counts returned:
      - schools: total active schools
      - students: total active students across all schools
      - coaches: total active coach-role users
      - sessions: sessions logged in the last 30 days
      - open_incidents: unresolved incident reports
    """
    db = get_db()
    try:
        schools_count = (db.execute(
            "SELECT COUNT(*) AS cnt FROM schools WHERE active_status = TRUE AND deleted_at IS NULL"
        ).fetchone() or {}).get("cnt", 0)

        students_count = (db.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE active_status = TRUE AND deleted_at IS NULL"
        ).fetchone() or {}).get("cnt", 0)

        coaches_count = (db.execute(
            """SELECT COUNT(*) AS cnt FROM users
               WHERE role IN ('head_coach', 'assistant_coach', 'site_coordinator', 'coach_overseer')
               AND active_status = TRUE AND deleted_at IS NULL"""
        ).fetchone() or {}).get("cnt", 0)

        sessions_count = (db.execute(
            """SELECT COUNT(*) AS cnt FROM sessions
               WHERE session_date >= DATE('now', '-30 days')""",
        ).fetchone() or {}).get("cnt", 0)

        open_incidents = (db.execute(
            "SELECT COUNT(*) AS cnt FROM incident_reports WHERE status NOT IN ('resolved', 'closed')"
        ).fetchone() or {}).get("cnt", 0)

        return jsonify({
            "ok": True,
            "stats": {
                "schools": schools_count,
                "students": students_count,
                "coaches": coaches_count,
                "sessions_last_30_days": sessions_count,
                "open_incidents": open_incidents,
            },
        })
    finally:
        db.close()
