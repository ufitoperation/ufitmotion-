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

Phase 3A analytics routes (admin/ceo/coach_overseer):
  GET        /api/admin/dashboard
  GET        /api/admin/schools
  GET        /api/admin/coaches
  GET        /api/admin/incidents
  GET        /api/admin/students/growth
"""

import datetime
from zoneinfo import ZoneInfo
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from app.auth import admin_required, current_user, roles_required
from app.database import get_db
from app.hubspot import trigger_principal_sync
from app.routes._helpers import audit, now_utc, parse_json, serialize_school, serialize_student, serialize_user

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _now_pacific() -> datetime.datetime:
    """Return current Pacific wall-clock datetime. Monkeypatchable in tests."""
    return datetime.datetime.now(tz=_PACIFIC)


def _get_week_bounds() -> tuple:
    """Return (week_start_str, week_end_str) for the current Mon–Sun Pacific week."""
    today = _now_pacific().date()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday
    week_end = week_start + datetime.timedelta(days=6)             # Sunday
    return week_start.isoformat(), week_end.isoformat()

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
    Create a new school.
    Body: { organization_id, school_name, school_type?, region_id?, address?,
            city?, state?, zip_code?, principal_name?, principal_email? }
    """
    actor = current_user()
    data = parse_json()
    organization_id = data.get("organization_id")
    school_name = (data.get("school_name") or "").strip()
    school_type = data.get("school_type", "elementary")

    if not organization_id or not school_name:
        return jsonify({"error": "organization_id and school_name are required."}), 400

    valid_types = ("elementary", "middle", "high", "k8", "other")
    if school_type not in valid_types:
        return jsonify({"error": f"school_type must be one of: {', '.join(valid_types)}."}), 400

    db = get_db()
    try:
        org = db.execute(
            """SELECT organization_id, organization_name FROM organizations
               WHERE organization_id = ? AND deleted_at IS NULL""",
            (organization_id,),
        ).fetchone()
        if not org:
            return jsonify({"error": "Organization not found."}), 404

        principal_name = (data.get("principal_name") or "").strip() or None
        principal_email = (data.get("principal_email") or "").strip().lower() or None
        if principal_email and ("@" not in principal_email or "." not in principal_email.split("@")[-1]):
            return jsonify({"error": "Invalid principal_email format."}), 400

        ts = now_utc()
        cur = db.execute(
            """INSERT INTO schools
               (organization_id, region_id, school_name, school_type,
                address, city, state, zip_code,
                principal_name, principal_email, active_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                organization_id, data.get("region_id"), school_name, school_type,
                data.get("address"), data.get("city"), data.get("state"), data.get("zip_code"),
                principal_name, principal_email, ts,
            ),
        )
        school_id = cur.lastrowid
        audit(db, actor["user_id"] if actor else None, "INSERT", "schools", school_id,
              new_values={"school_name": school_name, "organization_id": organization_id})
        db.commit()

        school = db.execute(
            """SELECT school_id, organization_id, region_id, school_name, school_type,
                      address, city, state, zip_code, principal_name, principal_email,
                      active_status, created_at
               FROM schools WHERE school_id = ?""",
            (school_id,),
        ).fetchone()

        # HubSpot: sync principal if email provided
        if principal_email and principal_name:
            parts = principal_name.split(" ", 1)
            trigger_principal_sync(
                email=principal_email,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
                school_id=school_id,
                school_name=school_name,
                org_id=org["organization_id"],
                org_name=org["organization_name"],
            )

        return jsonify({"ok": True, "school": serialize_school(school)}), 201
    finally:
        db.close()


@admin_bp.route("/api/schools/<int:school_id>", methods=["PATCH"])
@admin_required
def update_school(school_id: int):
    """
    Update a school's principal contact info (and other mutable fields).
    Body: any subset of { school_name, principal_name, principal_email,
                          address, city, state, zip_code }
    Triggers HubSpot sync if principal_email is set after the update.
    """
    actor = current_user()
    data = parse_json()

    mutable = ("school_name", "principal_name", "principal_email",
               "address", "city", "state", "zip_code")
    updates = {k: data[k] for k in mutable if k in data}
    if not updates:
        return jsonify({"error": "No updatable fields provided."}), 400

    db = get_db()
    try:
        school = db.execute(
            """SELECT s.school_id, s.organization_id, s.school_name,
                      s.principal_name, s.principal_email,
                      o.organization_name
               FROM schools s
               JOIN organizations o ON o.organization_id = s.organization_id
               WHERE s.school_id = ? AND s.deleted_at IS NULL""",
            (school_id,),
        ).fetchone()
        if not school:
            return jsonify({"error": "School not found."}), 404

        # Build UPDATE using only the validated allowlist — never interpolate untrusted input.
        _COL_SQL = {
            "school_name": "school_name = ?",
            "principal_name": "principal_name = ?",
            "principal_email": "principal_email = ?",
            "address": "address = ?",
            "city": "city = ?",
            "state": "state = ?",
            "zip_code": "zip_code = ?",
        }
        clauses = [_COL_SQL[k] for k in updates]
        params = list(updates.values()) + [school_id]
        db.execute(
            f"UPDATE schools SET {', '.join(clauses)} WHERE school_id = ?",
            params,
        )
        audit(db, actor["user_id"] if actor else None, "UPDATE", "schools", school_id,
              old_values=dict(school), new_values=updates)
        db.commit()

        updated = db.execute(
            """SELECT school_id, organization_id, region_id, school_name, school_type,
                      address, city, state, zip_code, principal_name, principal_email,
                      active_status, created_at
               FROM schools WHERE school_id = ?""",
            (school_id,),
        ).fetchone()

        # HubSpot sync if we now have both name and email
        new_email = updates.get("principal_email", school["principal_email"])
        new_name = updates.get("principal_name", school["principal_name"])
        if new_email and new_name:
            parts = new_name.split(" ", 1)
            trigger_principal_sync(
                email=new_email,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
                school_id=school_id,
                school_name=updated["school_name"],
                org_id=school["organization_id"],
                org_name=school["organization_name"],
            )

        return jsonify({"ok": True, "school": serialize_school(updated)})
    finally:
        db.close()


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
    Create a new staff user account.
    Body: { first_name, last_name, email, role, password, school_id?, position_title? }
    Creates user row, staff_profile, and staff_assignment (if school_id provided).
    Triggers HubSpot sync for principal role.
    """
    actor = current_user()
    data = parse_json()

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip()
    password = data.get("password") or ""

    if not all([first_name, last_name, email, role, password]):
        return jsonify({"error": "first_name, last_name, email, role, and password are required."}), 400

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Invalid email format."}), 400

    valid_roles = (
        "ceo", "admin", "coach_overseer", "site_coordinator",
        "head_coach", "assistant_coach", "principal", "school_staff",
    )
    if role not in valid_roles:
        return jsonify({"error": f"role must be one of: {', '.join(valid_roles)}."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    school_id = data.get("school_id")
    position_title = (data.get("position_title") or "").strip() or None

    db = get_db()
    try:
        dup = db.execute(
            "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL",
            (email,),
        ).fetchone()
        if dup:
            return jsonify({"error": "An account with that email already exists."}), 409

        # Validate school if provided
        school = None
        if school_id:
            school = db.execute(
                """SELECT s.school_id, s.school_name, s.organization_id,
                          o.organization_name
                   FROM schools s
                   JOIN organizations o ON o.organization_id = s.organization_id
                   WHERE s.school_id = ? AND s.deleted_at IS NULL""",
                (school_id,),
            ).fetchone()
            if not school:
                return jsonify({"error": "School not found."}), 404

        ts = now_utc()
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        cur = db.execute(
            """INSERT INTO users
               (role, first_name, last_name, email, password_hash, active_status, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (role, first_name, last_name, email, password_hash, ts),
        )
        new_user_id = cur.lastrowid

        # Staff profile for all non-parent roles
        staff_id = None
        if role != "parent":
            sp_cur = db.execute(
                """INSERT INTO staff_profiles
                   (user_id, position_title, status, created_at)
                   VALUES (?, ?, 'active', ?)""",
                (new_user_id, position_title, ts),
            )
            staff_id = sp_cur.lastrowid

            if school_id and staff_id:
                db.execute(
                    """INSERT INTO staff_assignments
                       (staff_id, school_id, assignment_role, start_date, active_status, created_at)
                       VALUES (?, ?, ?, DATE('now'), 1, ?)""",
                    (staff_id, school_id, role, ts),
                )

        audit(db, actor["user_id"] if actor else None, "INSERT", "users", new_user_id,
              new_values={"role": role, "email": email, "school_id": school_id})
        db.commit()

        user = db.execute(
            """SELECT u.user_id, u.role, u.first_name, u.last_name, u.email,
                      u.active_status, u.created_at,
                      sp.staff_id, sp.position_title,
                      s.school_id, s.school_name
               FROM users u
               LEFT JOIN staff_profiles sp ON sp.user_id = u.user_id
               LEFT JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = 1
               LEFT JOIN schools s ON s.school_id = sa.school_id
               WHERE u.user_id = ?""",
            (new_user_id,),
        ).fetchone()

        # HubSpot sync for principals
        if role == "principal" and school and email:
            trigger_principal_sync(
                email=email,
                first_name=first_name,
                last_name=last_name,
                school_id=school["school_id"],
                school_name=school["school_name"],
                org_id=school["organization_id"],
                org_name=school["organization_name"],
            )

        return jsonify({"ok": True, "user": serialize_user(dict(user))}), 201
    finally:
        db.close()


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
    user = current_user()
    db = get_db()
    try:
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()

        # CEO sees all orgs; admin is scoped to their own org.
        org_id = None
        if user and user.get("role") == "admin":
            school_id = user.get("school_id")
            if school_id:
                org_row = db.execute(
                    "SELECT organization_id FROM schools WHERE school_id = ?",
                    (school_id,),
                ).fetchone()
                org_id = org_row["organization_id"] if org_row else None

        if org_id:
            schools_count = (db.execute(
                """SELECT COUNT(*) AS cnt FROM schools
                   WHERE active_status = TRUE AND deleted_at IS NULL AND organization_id = ?""",
                (org_id,),
            ).fetchone() or {}).get("cnt", 0)

            students_count = (db.execute(
                """SELECT COUNT(*) AS cnt FROM students s
                   JOIN schools sc ON sc.school_id = s.school_id
                   WHERE s.active_status = TRUE AND s.deleted_at IS NULL
                     AND sc.organization_id = ?""",
                (org_id,),
            ).fetchone() or {}).get("cnt", 0)

            coaches_count = (db.execute(
                """SELECT COUNT(*) AS cnt FROM users u
                   JOIN staff_profiles sp ON sp.user_id = u.user_id
                   JOIN staff_assignments sa
                          ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
                   JOIN schools sc ON sc.school_id = sa.school_id
                   WHERE u.role IN ('head_coach', 'assistant_coach',
                                    'site_coordinator', 'coach_overseer')
                     AND u.active_status = TRUE AND u.deleted_at IS NULL
                     AND sc.organization_id = ?""",
                (org_id,),
            ).fetchone() or {}).get("cnt", 0)

            sessions_count = (db.execute(
                """SELECT COUNT(*) AS cnt FROM sessions se
                   JOIN schools sc ON sc.school_id = se.school_id
                   WHERE se.session_date >= ? AND sc.organization_id = ?""",
                (thirty_days_ago, org_id),
            ).fetchone() or {}).get("cnt", 0)

            open_incidents = (db.execute(
                """SELECT COUNT(*) AS cnt FROM incident_reports ir
                   JOIN schools sc ON sc.school_id = ir.school_id
                   WHERE ir.status NOT IN ('resolved', 'closed')
                     AND sc.organization_id = ?""",
                (org_id,),
            ).fetchone() or {}).get("cnt", 0)

        else:
            # CEO or admin with no school assignment: global counts.
            schools_count = (db.execute(
                "SELECT COUNT(*) AS cnt FROM schools WHERE active_status = TRUE AND deleted_at IS NULL"
            ).fetchone() or {}).get("cnt", 0)

            students_count = (db.execute(
                "SELECT COUNT(*) AS cnt FROM students WHERE active_status = TRUE AND deleted_at IS NULL"
            ).fetchone() or {}).get("cnt", 0)

            coaches_count = (db.execute(
                """SELECT COUNT(*) AS cnt FROM users
                   WHERE role IN ('head_coach', 'assistant_coach',
                                  'site_coordinator', 'coach_overseer')
                     AND active_status = TRUE AND deleted_at IS NULL"""
            ).fetchone() or {}).get("cnt", 0)

            sessions_count = (db.execute(
                "SELECT COUNT(*) AS cnt FROM sessions WHERE session_date >= ?",
                (thirty_days_ago,),
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
    except Exception:
        return jsonify({"error": "Unable to fetch dashboard data."}), 500
    finally:
        db.close()


# ===========================================================================
# PHASE 3A — ADMIN ANALYTICS
# ===========================================================================

@admin_bp.route("/api/admin/dashboard", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_dashboard():
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        active_schools = db.execute(
            "SELECT COUNT(*) AS cnt FROM schools WHERE active_status=1 AND deleted_at IS NULL"
        ).fetchone()["cnt"]

        active_coaches = db.execute(
            """SELECT COUNT(*) AS cnt FROM users
               WHERE role IN ('head_coach','assistant_coach')
                 AND active_status=1 AND deleted_at IS NULL"""
        ).fetchone()["cnt"]

        sessions_this_week = db.execute(
            """SELECT COUNT(*) AS cnt FROM sessions
               WHERE session_date BETWEEN ? AND ? AND deleted_at IS NULL""",
            (week_start, week_end),
        ).fetchone()["cnt"]

        # EOD compliance: actual / expected, capped at 1.0
        expected_row = db.execute(
            """SELECT COUNT(*) AS cnt FROM (
                 SELECT DISTINCT ss.staff_id, s.session_date
                 FROM sessions s
                 JOIN session_staff ss ON ss.session_id = s.session_id
                 WHERE s.session_date BETWEEN ? AND ?
                   AND s.deleted_at IS NULL
               )""",
            (week_start, week_end),
        ).fetchone()
        expected = expected_row["cnt"] if expected_row else 0

        actual_row = db.execute(
            """SELECT COUNT(*) AS cnt FROM eod_reports
               WHERE report_date BETWEEN ? AND ? AND deleted_at IS NULL""",
            (week_start, week_end),
        ).fetchone()
        actual = actual_row["cnt"] if actual_row else 0

        if expected > 0:
            eod_compliance_rate = round(min(1.0, actual / expected), 2)
        else:
            eod_compliance_rate = 0.0

        open_incidents = db.execute(
            """SELECT COUNT(*) AS cnt FROM incident_reports
               WHERE status='open' AND deleted_at IS NULL"""
        ).fetchone()["cnt"]

        return jsonify({
            "ok": True,
            "active_schools": active_schools,
            "active_coaches": active_coaches,
            "sessions_this_week": sessions_this_week,
            "eod_compliance_rate": eod_compliance_rate,
            "open_incidents": open_incidents,
        })
    except Exception:
        return jsonify({"error": "Could not load dashboard — please try again or contact support."}), 500
    finally:
        db.close()


@admin_bp.route("/api/admin/schools", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_list_schools():
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        rows = db.execute(
            """SELECT
                 s.school_id, s.organization_id, s.region_id,
                 s.school_name, s.school_type, s.address, s.city, s.state,
                 s.zip_code, s.principal_name, s.principal_email,
                 s.active_status, s.created_at,
                 (SELECT COUNT(*) FROM users u
                  JOIN staff_profiles sp ON sp.user_id = u.user_id
                  JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
                  WHERE sa.school_id = s.school_id
                    AND sa.active_status = 1
                    AND u.role IN ('head_coach','assistant_coach')
                    AND u.active_status = 1
                    AND u.deleted_at IS NULL
                 ) AS coach_count,
                 (SELECT COUNT(*) FROM sessions ses
                  WHERE ses.school_id = s.school_id
                    AND ses.session_date BETWEEN ? AND ?
                    AND ses.deleted_at IS NULL
                 ) AS session_count_this_week,
                 (SELECT MAX(e.report_date) FROM eod_reports e
                  WHERE e.school_id = s.school_id
                    AND e.deleted_at IS NULL
                 ) AS last_eod_date
               FROM schools s
               WHERE s.active_status = 1 AND s.deleted_at IS NULL
               ORDER BY s.school_name ASC""",
            (week_start, week_end),
        ).fetchall()

        schools = []
        for r in rows:
            school = serialize_school(r)
            school["coach_count"] = r["coach_count"]
            school["session_count_this_week"] = r["session_count_this_week"]
            school["last_eod_date"] = r["last_eod_date"]
            schools.append(school)

        return jsonify({"ok": True, "schools": schools, "total": len(schools)})
    except Exception:
        return jsonify({"error": "Could not load schools — please try again or contact support."}), 500
    finally:
        db.close()


@admin_bp.route("/api/admin/coaches", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_list_coaches():
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        rows = db.execute(
            """SELECT
                 u.user_id, u.role, u.first_name, u.last_name, u.email,
                 u.active_status, u.created_at,
                 sp.staff_id, sp.position_title,
                 s.school_id, s.school_name,
                 (SELECT COUNT(*) FROM eod_reports e
                  WHERE e.staff_id = sp.staff_id
                    AND e.report_date BETWEEN ? AND ?
                    AND e.deleted_at IS NULL
                 ) AS eod_submissions_this_week,
                 (SELECT COUNT(*) FROM eod_reports e
                  WHERE e.staff_id = sp.staff_id
                    AND e.report_date BETWEEN ? AND ?
                    AND e.submitted_on_time = 0
                    AND e.deleted_at IS NULL
                 ) AS late_submissions_this_week,
                 (SELECT COUNT(*) FROM incident_reports ir
                  WHERE ir.reported_by_staff_id = sp.staff_id
                    AND ir.report_date BETWEEN ? AND ?
                    AND ir.deleted_at IS NULL
                 ) AS incidents_filed_this_week
               FROM users u
               LEFT JOIN staff_profiles sp ON sp.user_id = u.user_id
               LEFT JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
                          AND sa.active_status = 1
               LEFT JOIN schools s ON s.school_id = sa.school_id
               WHERE u.role IN ('head_coach','assistant_coach')
                 AND u.active_status = 1
                 AND u.deleted_at IS NULL
               ORDER BY u.last_name ASC, u.first_name ASC""",
            (week_start, week_end, week_start, week_end, week_start, week_end),
        ).fetchall()

        coaches = []
        for r in rows:
            coach = serialize_user(r)
            coach["eod_submissions_this_week"] = r["eod_submissions_this_week"]
            coach["late_submissions_this_week"] = r["late_submissions_this_week"]
            coach["incidents_filed_this_week"] = r["incidents_filed_this_week"]
            coaches.append(coach)

        return jsonify({"ok": True, "coaches": coaches, "total": len(coaches)})
    except Exception:
        return jsonify({"error": "Could not load coaches — please try again or contact support."}), 500
    finally:
        db.close()


@admin_bp.route("/api/admin/incidents", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_incidents():
    raw_weeks = request.args.get("weeks", "4")
    try:
        weeks = int(raw_weeks)
        if not (1 <= weeks <= 12):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "weeks must be an integer between 1 and 12."}), 422

    week_start_str, _ = _get_week_bounds()
    week_start_date = datetime.date.fromisoformat(week_start_str)
    window_start = week_start_date - datetime.timedelta(weeks=weeks)
    window_end = week_start_date - datetime.timedelta(days=1)
    window_start_str = window_start.isoformat()
    window_end_str = window_end.isoformat()

    db = get_db()
    try:
        total_row = db.execute(
            """SELECT COUNT(*) AS cnt FROM incident_reports
               WHERE report_date BETWEEN ? AND ? AND deleted_at IS NULL""",
            (window_start_str, window_end_str),
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        severity_rows = db.execute(
            """SELECT severity_level, COUNT(*) AS cnt
               FROM incident_reports
               WHERE report_date BETWEEN ? AND ? AND deleted_at IS NULL
               GROUP BY severity_level
               ORDER BY cnt DESC""",
            (window_start_str, window_end_str),
        ).fetchall()
        by_severity = [{"severity_level": r["severity_level"], "count": r["cnt"]}
                       for r in severity_rows]

        school_rows = db.execute(
            """SELECT ir.school_id, s.school_name, COUNT(*) AS cnt
               FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.report_date BETWEEN ? AND ? AND ir.deleted_at IS NULL
               GROUP BY ir.school_id, s.school_name
               ORDER BY cnt DESC""",
            (window_start_str, window_end_str),
        ).fetchall()
        by_school = [{"school_id": r["school_id"], "school_name": r["school_name"], "count": r["cnt"]}
                     for r in school_rows]

        # Build week list — N entries, zero-fill missing weeks
        week_counts = {}
        for week_rows in db.execute(
            """SELECT report_date, COUNT(*) AS cnt
               FROM incident_reports
               WHERE report_date BETWEEN ? AND ? AND deleted_at IS NULL
               GROUP BY report_date""",
            (window_start_str, window_end_str),
        ).fetchall():
            d = datetime.date.fromisoformat(week_rows["report_date"])
            # Align to Monday of that week
            monday = (d - datetime.timedelta(days=d.weekday())).isoformat()
            week_counts[monday] = week_counts.get(monday, 0) + week_rows["cnt"]

        by_week = []
        for i in range(weeks):
            w_start = (window_start + datetime.timedelta(weeks=i)).isoformat()
            by_week.append({"week_start": w_start, "count": week_counts.get(w_start, 0)})

        return jsonify({
            "ok": True,
            "weeks": weeks,
            "window_start": window_start_str,
            "window_end": window_end_str,
            "total": total,
            "by_severity": by_severity,
            "by_school": by_school,
            "by_week": by_week,
        })
    except Exception:
        return jsonify({"error": "Could not load incidents — please try again or contact support."}), 500
    finally:
        db.close()


@admin_bp.route("/api/admin/students/growth", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_students_growth():
    raw_window_id = request.args.get("window_id")
    window_id = None
    if raw_window_id is not None:
        try:
            window_id = int(raw_window_id)
            if window_id < 1:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "window_id must be a positive integer."}), 400

    db = get_db()
    try:
        # Total active students
        total_students = db.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE active_status=1 AND deleted_at IS NULL"
        ).fetchone()["cnt"]

        # Assessed students (with optional window filter)
        if window_id is not None:
            assessed_students = db.execute(
                """SELECT COUNT(DISTINCT student_id) AS cnt
                   FROM assessments WHERE deleted_at IS NULL AND window_id=?""",
                (window_id,),
            ).fetchone()["cnt"]
        else:
            assessed_students = db.execute(
                "SELECT COUNT(DISTINCT student_id) AS cnt FROM assessments WHERE deleted_at IS NULL"
            ).fetchone()["cnt"]

        # by_school: all active schools, left-join assessed counts
        school_rows = db.execute(
            "SELECT school_id, school_name FROM schools WHERE active_status=1 AND deleted_at IS NULL ORDER BY school_name ASC"
        ).fetchall()

        if window_id is not None:
            assessed_by_school = {
                r["school_id"]: r["cnt"]
                for r in db.execute(
                    """SELECT school_id, COUNT(DISTINCT student_id) AS cnt
                       FROM assessments WHERE deleted_at IS NULL AND window_id=?
                       GROUP BY school_id""",
                    (window_id,),
                ).fetchall()
            }
        else:
            assessed_by_school = {
                r["school_id"]: r["cnt"]
                for r in db.execute(
                    """SELECT school_id, COUNT(DISTINCT student_id) AS cnt
                       FROM assessments WHERE deleted_at IS NULL
                       GROUP BY school_id"""
                ).fetchall()
            }

        total_by_school = {
            r["school_id"]: r["cnt"]
            for r in db.execute(
                """SELECT school_id, COUNT(*) AS cnt
                   FROM students WHERE active_status=1 AND deleted_at IS NULL
                   GROUP BY school_id"""
            ).fetchall()
        }

        by_school = [
            {
                "school_id": r["school_id"],
                "school_name": r["school_name"],
                "assessed_count": assessed_by_school.get(r["school_id"], 0),
                "total_students": total_by_school.get(r["school_id"], 0),
            }
            for r in school_rows
        ]

        # by_skill_domain — avg raw_level per domain
        if window_id is not None:
            domain_rows = db.execute(
                """SELECT sd.domain_id AS skill_domain_id, sd.domain_name,
                          ROUND(AVG(CAST(asco.raw_level AS REAL)), 2) AS avg_raw_level
                   FROM assessment_scores asco
                   JOIN skills sk ON sk.skill_id = asco.skill_id
                   JOIN skill_domains sd ON sd.domain_id = sk.domain_id
                   JOIN assessments a ON a.assessment_id = asco.assessment_id
                   WHERE a.deleted_at IS NULL AND a.window_id = ?
                   GROUP BY sd.domain_id, sd.domain_name
                   ORDER BY sd.domain_name ASC""",
                (window_id,),
            ).fetchall()
        else:
            domain_rows = db.execute(
                """SELECT sd.domain_id AS skill_domain_id, sd.domain_name,
                          ROUND(AVG(CAST(asco.raw_level AS REAL)), 2) AS avg_raw_level
                   FROM assessment_scores asco
                   JOIN skills sk ON sk.skill_id = asco.skill_id
                   JOIN skill_domains sd ON sd.domain_id = sk.domain_id
                   JOIN assessments a ON a.assessment_id = asco.assessment_id
                   WHERE a.deleted_at IS NULL
                   GROUP BY sd.domain_id, sd.domain_name
                   ORDER BY sd.domain_name ASC"""
            ).fetchall()

        by_skill_domain = [
            {
                "skill_domain_id": r["skill_domain_id"],
                "domain_name": r["domain_name"],
                "avg_raw_level": r["avg_raw_level"],
            }
            for r in domain_rows
        ]

        return jsonify({
            "ok": True,
            "window_id": window_id,
            "assessed_students": assessed_students,
            "total_students": total_students,
            "by_school": by_school,
            "by_skill_domain": by_skill_domain,
        })
    except Exception:
        return jsonify({"error": "Could not load student growth data — please try again or contact support."}), 500
    finally:
        db.close()


# ===========================================================================
# EOD COMPLIANCE ALERTS
# ===========================================================================

@admin_bp.route("/api/admin/eod-alerts", methods=["POST"])
@roles_required("ceo", "admin", "coach_overseer")
def trigger_eod_alerts():
    """
    Trigger EOD compliance notifications for coaches who had sessions today
    but have not yet submitted an EOD report.

    Intended to be called at 20:00 Pacific by a scheduler (cron/Railway).
    Safe to call multiple times — idempotent per coach per calendar day.

    Returns:
      { ok, alerts_sent, skipped_already_alerted, coaches_flagged: [{staff_id, coach_name}] }
    """
    now = _now_pacific()
    today = now.date().isoformat()          # Pacific date — used for session_date queries
    today_utc = now_utc()[:10]              # UTC date prefix — used for created_at idempotency

    db = get_db()
    try:
        # Find coaches who had a session today but no EOD submitted today.
        missing_rows = db.execute(
            """SELECT DISTINCT sp.staff_id,
                      u.user_id,
                      u.first_name || ' ' || u.last_name AS coach_name
               FROM sessions ses
               JOIN session_staff ss ON ss.session_id = ses.session_id
               JOIN staff_profiles sp ON sp.staff_id = ss.staff_id
               JOIN users u ON u.user_id = sp.user_id
               WHERE ses.session_date = ?
                 AND ses.deleted_at IS NULL
                 AND u.deleted_at IS NULL
                 AND u.active_status = 1
                 AND sp.staff_id NOT IN (
                   SELECT staff_id FROM eod_reports
                   WHERE report_date = ? AND deleted_at IS NULL
                 )""",
            (today, today),
        ).fetchall()

        alerts_sent = 0
        skipped = 0
        coaches_flagged = []

        for row in missing_rows:
            staff_id = row["staff_id"]
            user_id = row["user_id"]
            coach_name = row["coach_name"]

            # Idempotency: skip if we already sent an eod_late alert today for this coach
            existing = db.execute(
                """SELECT notification_id FROM notifications
                   WHERE user_id = ?
                     AND notification_type = 'eod_late'
                     AND related_table = 'staff_profiles'
                     AND related_id = ?
                     AND SUBSTR(created_at, 1, 10) = ?""",
                (user_id, staff_id, today_utc),
            ).fetchone()

            if existing:
                skipped += 1
                continue

            db.execute(
                """INSERT INTO notifications
                   (user_id, title, body, notification_type,
                    related_table, related_id, created_at)
                   VALUES (?, ?, ?, 'eod_late', 'staff_profiles', ?, ?)""",
                (
                    user_id,
                    "EOD Report Due",
                    f"Your End-of-Day report for {today} has not been submitted. "
                    "Please submit it now to stay compliant.",
                    staff_id,
                    now_utc(),
                ),
            )
            alerts_sent += 1
            coaches_flagged.append({"staff_id": staff_id, "coach_name": coach_name})

        db.commit()

        return jsonify({
            "ok": True,
            "alerts_sent": alerts_sent,
            "skipped_already_alerted": skipped,
            "coaches_flagged": coaches_flagged,
        })
    finally:
        db.close()
