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

_date = date

from typing import Optional

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from app.auth import admin_required, current_user, roles_required
from app.database import get_db
from app.hubspot import trigger_principal_sync
from app.routes._hubspot import notify_school_created
from app.routes._helpers import audit, now_utc, parse_json, serialize_school, serialize_student, serialize_user
from app.routes._coach_scoring import calculate_coach_score, rolling_period, coach_performance_band

_PACIFIC = ZoneInfo("America/Los_Angeles")


def _now_pacific() -> datetime.datetime:
    """Return current Pacific wall-clock datetime. Monkeypatchable in tests."""
    return datetime.datetime.now(tz=_PACIFIC)


def _get_week_bounds() -> tuple:
    today = _now_pacific().date()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday
    week_end = week_start + datetime.timedelta(days=6)             # Sunday
    return week_start.isoformat(), week_end.isoformat()

admin_bp = Blueprint("admin", __name__)


def _get_org_scope(db, user) -> Optional[int]:
    """Return org_id to scope queries by, or None for global access."""
    if user is None or user["role"] in ("ceo", "admin"):
        return None
    school_id = user.get("school_id")
    if not school_id:
        return None
    row = db.execute(
        "SELECT organization_id FROM schools WHERE school_id = ?", (school_id,)
    ).fetchone()
    return row["organization_id"] if row else None


# ===========================================================================
# ORGANIZATIONS
# ===========================================================================

@admin_bp.route("/api/organizations", methods=["GET"])
@admin_required
def list_organizations():
    db = get_db()
    try:
        rows = db.execute(
            """SELECT o.organization_id, o.organization_name, o.organization_type,
                      o.contract_status, o.created_at,
                      COUNT(s.school_id) AS school_count
               FROM organizations o
               LEFT JOIN schools s ON s.organization_id = o.organization_id
                 AND s.deleted_at IS NULL AND s.active_status = 1
               WHERE o.deleted_at IS NULL
               GROUP BY o.organization_id
               ORDER BY o.organization_name ASC"""
        ).fetchall()
        orgs = [dict(r) for r in rows]
        return jsonify({"ok": True, "organizations": orgs, "total": len(orgs)})
    finally:
        db.close()


@admin_bp.route("/api/organizations", methods=["POST"])
@admin_required
def create_organization():
    actor = current_user()
    data = parse_json()
    org_name = (data.get("organization_name") or "").strip()
    if not org_name:
        return jsonify({"error": "organization_name is required."}), 400

    db = get_db()
    try:
        dup = db.execute(
            "SELECT organization_id FROM organizations WHERE organization_name = ? AND deleted_at IS NULL",
            (org_name,),
        ).fetchone()
        if dup:
            return jsonify({"error": "An organization with that name already exists."}), 409

        ts = now_utc()
        cur = db.execute(
            """INSERT INTO organizations
               (organization_name, organization_type, contract_status, created_at)
               VALUES (?, ?, ?, ?)""",
            (org_name, data.get("organization_type", "district"),
             data.get("contract_status", "active"), ts),
        )
        org_id = cur.lastrowid
        audit(db, actor["user_id"] if actor else None, "INSERT", "organizations", org_id,
              new_values={"organization_name": org_name})
        db.commit()
        org = db.execute(
            "SELECT organization_id, organization_name, organization_type, contract_status, created_at FROM organizations WHERE organization_id = ?",
            (org_id,),
        ).fetchone()
        return jsonify({"ok": True, "organization": dict(org)}), 201
    finally:
        db.close()


# ===========================================================================
# SCHOOLS
# ===========================================================================

@admin_bp.route("/api/schools", methods=["GET"])
@admin_required
def list_schools():
    search = (request.args.get("search") or "").strip()[:100]
    org_id_raw = request.args.get("org_id")
    db = get_db()
    try:
        params = []
        where = "WHERE s.deleted_at IS NULL AND s.active_status = 1"
        if search:
            where += " AND (s.school_name LIKE ? OR s.city LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        if org_id_raw:
            where += " AND s.organization_id = ?"
            params.append(int(org_id_raw))
        rows = db.execute(
            f"""SELECT s.school_id, s.school_name, s.school_type, s.city, s.state,
                       o.organization_name,
                       COUNT(DISTINCT sa.staff_id) AS coach_count,
                       COUNT(DISTINCT st.student_id) AS student_count
                FROM schools s
                LEFT JOIN organizations o ON o.organization_id = s.organization_id
                LEFT JOIN staff_assignments sa ON sa.school_id = s.school_id AND sa.active_status = 1
                LEFT JOIN students st ON st.school_id = s.school_id
                    AND st.active_status = 1 AND st.deleted_at IS NULL
                {where}
                GROUP BY s.school_id
                ORDER BY s.school_name ASC""",
            params,
        ).fetchall()
        return jsonify({"ok": True, "schools": [dict(r) for r in rows], "total": len(rows)})
    finally:
        db.close()


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

        notify_school_created(dict(school))

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
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT school_id, school_name FROM schools WHERE school_id = ? AND deleted_at IS NULL",
            (school_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "School not found."}), 404

        active_students = db.execute(
            "SELECT COUNT(*) FROM students WHERE school_id = ? AND active_status = 1 AND deleted_at IS NULL",
            (school_id,),
        ).fetchone()[0]
        if active_students > 0:
            return jsonify({"error": f"Cannot delete school with {active_students} active student(s). Deactivate or transfer students first."}), 409

        ts = now_utc()
        db.execute("UPDATE schools SET deleted_at = ? WHERE school_id = ?", (ts, school_id))
        db.execute("UPDATE staff_assignments SET active_status = 0 WHERE school_id = ?", (school_id,))
        db.execute("UPDATE programs SET program_status = 'inactive' WHERE school_id = ?", (school_id,))
        audit(db, user["user_id"], "DELETE", "schools", school_id,
              old_values={"school_name": row["school_name"]})
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()



@admin_bp.route("/api/users", methods=["GET"])
@admin_required
def list_users():
    search = (request.args.get("search") or "").strip()[:100]
    role_filter = (request.args.get("role") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    except (ValueError, TypeError):
        return jsonify({"error": "page and per_page must be positive integers."}), 422

    db = get_db()
    try:
        where = "WHERE u.deleted_at IS NULL"
        params = []
        if search:
            where += " AND (u.first_name LIKE ? OR u.last_name LIKE ? OR u.email LIKE ?)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        if role_filter:
            where += " AND u.role = ?"
            params.append(role_filter)

        total = db.execute(
            f"SELECT COUNT(*) AS cnt FROM users u {where}", params
        ).fetchone()["cnt"]

        offset = (page - 1) * per_page
        rows = db.execute(
            f"""SELECT u.user_id, u.role, u.first_name, u.last_name, u.email,
                       u.active_status, u.created_at,
                       sp.position_title, s.school_id, s.school_name
                FROM users u
                LEFT JOIN staff_profiles sp ON sp.user_id = u.user_id
                LEFT JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = 1
                LEFT JOIN schools s ON s.school_id = sa.school_id
                {where}
                ORDER BY u.last_name ASC, u.first_name ASC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

        users = [
            {
                "user_id": r["user_id"], "role": r["role"],
                "first_name": r["first_name"], "last_name": r["last_name"],
                "email": r["email"], "active_status": r["active_status"],
                "position_title": r["position_title"],
                "school_id": r["school_id"], "school_name": r["school_name"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return jsonify({"ok": True, "users": users, "total": total, "page": page, "per_page": per_page})
    finally:
        db.close()


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
        "head_coach", "assistant_coach", "principal", "school_staff", "parent",
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

        staff_id = None
        if role == "parent":
            db.execute(
                """INSERT INTO parents
                   (user_id, first_name, last_name, email, portal_access_status, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (new_user_id, first_name, last_name, email, ts),
            )
        else:
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


@admin_bp.route("/api/users/<int:user_id>", methods=["PATCH"])
@admin_required
def update_user(user_id: int):
    """Reset a user's password. Body: { password }"""
    admin = current_user()
    data = parse_json()
    new_password = data.get("password") or ""
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id FROM users WHERE user_id = ? AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "User not found."}), 404
        new_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        db.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
        db.commit()
        audit(db, admin["user_id"], "admin_reset_password", "users", user_id)
        return jsonify({"ok": True})
    finally:
        db.close()


@admin_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id: int):
    current = current_user()
    if current is None:
        return jsonify({"error": "Authentication required."}), 401

    if current["user_id"] == user_id:
        return jsonify({"error": "You cannot delete your own account."}), 409

    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id, role, email FROM users WHERE user_id = ? AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "User not found."}), 404

        if row["role"] == "ceo":
            remaining = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'ceo' AND deleted_at IS NULL"
            ).fetchone()[0]
            if remaining <= 1:
                return jsonify({"error": "Cannot delete the last CEO account."}), 409

        ts = now_utc()
        db.execute(
            "UPDATE users SET deleted_at = ?, active_status = 0 WHERE user_id = ?",
            (ts, user_id),
        )
        db.execute(
            "UPDATE staff_assignments SET active_status = 0 WHERE staff_id = (SELECT staff_id FROM staff_profiles WHERE user_id = ?)",
            (user_id,),
        )
        audit(db, current["user_id"], "DELETE", "users", user_id,
              old_values={"email": row["email"], "role": row["role"]})
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()



@admin_bp.route("/api/students", methods=["GET"])
@admin_required
def list_students():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    school_id = request.args.get("school_id", type=int)
    grade_filter = request.args.get("grade_level", "").strip()[:10]
    search_raw = request.args.get("search", "").strip()[:100]
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 50, type=int)))
    offset = (page - 1) * per_page

    db = get_db()
    try:
        sql = """
            SELECT s.student_id, s.student_first_name, s.student_last_name,
                   s.grade_level, s.local_student_identifier, s.active_status,
                   s.enrollment_start, sc.school_name, sc.school_id
            FROM students s
            JOIN schools sc ON sc.school_id = s.school_id
            WHERE s.deleted_at IS NULL
        """
        params = []
        if school_id:
            sql += " AND s.school_id = ?"
            params.append(school_id)
        if grade_filter:
            sql += " AND s.grade_level = ?"
            params.append(grade_filter)
        if search_raw:
            sql += " AND (LOWER(s.student_first_name) LIKE ? OR LOWER(s.student_last_name) LIKE ?)"
            p = f"%{search_raw.lower()}%"
            params.extend([p, p])

        total = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
        sql += " ORDER BY sc.school_name, s.student_last_name, s.student_first_name LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        rows = db.execute(sql, params).fetchall()

        return jsonify({
            "ok": True,
            "students": [serialize_student(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    finally:
        db.close()


@admin_bp.route("/api/students", methods=["POST"])
@admin_required
def create_student():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    first_name = (data.get("student_first_name") or data.get("first_name") or "").strip()
    last_name = (data.get("student_last_name") or data.get("last_name") or "").strip()
    grade_level = (data.get("grade_level") or "").strip()
    school_id = data.get("school_id")
    local_id = (data.get("local_student_identifier") or "").strip() or None
    gender = (data.get("gender") or "").strip() or None
    homeroom = (data.get("homeroom_teacher") or "").strip() or None
    enrollment_start = data.get("enrollment_start") or now_utc()[:10]

    if not first_name or not last_name:
        return jsonify({"error": "student_first_name and student_last_name are required."}), 400
    if not grade_level:
        return jsonify({"error": "grade_level is required."}), 400
    if not school_id or not isinstance(school_id, int):
        return jsonify({"error": "school_id is required."}), 400

    db = get_db()
    try:
        school = db.execute("SELECT school_id FROM schools WHERE school_id = ? AND deleted_at IS NULL", (school_id,)).fetchone()
        if not school:
            return jsonify({"error": "School not found."}), 404

        cur = db.execute(
            """INSERT INTO students
               (school_id, student_first_name, student_last_name, local_student_identifier,
                grade_level, homeroom_teacher, gender, active_status, enrollment_start, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (school_id, first_name, last_name, local_id,
             grade_level, homeroom, gender, enrollment_start, now_utc()),
        )
        new_id = cur.lastrowid
        audit(db, user["user_id"], "INSERT", "students", new_id,
              new_values={"school_id": school_id, "name": f"{first_name} {last_name}", "grade": grade_level})
        db.commit()

        row = db.execute(
            """SELECT s.*, sc.school_name FROM students s
               JOIN schools sc ON sc.school_id = s.school_id
               WHERE s.student_id = ?""",
            (new_id,),
        ).fetchone()
        return jsonify({"ok": True, "student": serialize_student(row)}), 201
    finally:
        db.close()


@admin_bp.route("/api/students/<int:student_id>", methods=["DELETE"])
@admin_required
def delete_student(student_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT student_id FROM students WHERE student_id = ? AND deleted_at IS NULL", (student_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Student not found."}), 404

        ts = now_utc()
        db.execute(
            "UPDATE students SET deleted_at = ?, active_status = 0 WHERE student_id = ?",
            (ts, student_id),
        )
        db.execute(
            "UPDATE student_program_enrollment SET status = 'inactive' WHERE student_id = ?",
            (student_id,),
        )
        audit(db, user["user_id"], "DELETE", "students", student_id)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()



@admin_bp.route("/api/programs", methods=["GET"])
@admin_required
def list_programs():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    school_id = request.args.get("school_id", type=int)
    active_only = request.args.get("active", "").strip()
    search_raw = request.args.get("search", "").strip()[:100]

    db = get_db()
    try:
        sql = """
            SELECT p.program_id, p.school_id, sc.school_name, p.program_name,
                   p.program_type, p.service_model, p.grade_band, p.start_date,
                   p.end_date, p.program_status, p.frequency, p.reporting_cycle, p.notes,
                   (SELECT COUNT(*) FROM staff_assignments sa WHERE sa.program_id = p.program_id AND sa.active_status = 1) AS coach_count,
                   (SELECT COUNT(*) FROM student_program_enrollment spe WHERE spe.program_id = p.program_id AND spe.status = 'active') AS student_count
            FROM programs p
            JOIN schools sc ON sc.school_id = p.school_id
            WHERE sc.deleted_at IS NULL
        """
        params = []
        if school_id:
            sql += " AND p.school_id = ?"
            params.append(school_id)
        if active_only in ("1", "true"):
            sql += " AND p.program_status = 'active'"
        if search_raw:
            sql += " AND LOWER(p.program_name) LIKE ?"
            params.append(f"%{search_raw.lower()}%")
        sql += " ORDER BY sc.school_name, p.program_name"

        rows = db.execute(sql, params).fetchall()
        return jsonify({"ok": True, "programs": [dict(r) for r in rows]})
    finally:
        db.close()


@admin_bp.route("/api/programs", methods=["POST"])
@admin_required
def create_program():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    school_id = data.get("school_id")
    program_name = (data.get("program_name") or "").strip()
    program_type = (data.get("program_type") or "pe_support").strip()
    service_model = (data.get("service_model") or "").strip() or None
    grade_band = (data.get("grade_band") or "").strip() or None
    start_date = data.get("start_date")
    end_date = data.get("end_date") or None
    frequency = (data.get("frequency") or "").strip() or None
    reporting_cycle = (data.get("reporting_cycle") or "quarterly").strip()
    notes = (data.get("notes") or "").strip() or None

    VALID_TYPES = ("pe_support", "lunch_sports", "after_school_sports", "psychomotor",
                   "middle_school_skill_development", "tournament_program", "wellness_enrichment")

    if not school_id or not isinstance(school_id, int):
        return jsonify({"error": "school_id is required."}), 400
    if not program_name:
        return jsonify({"error": "program_name is required."}), 400
    if not start_date:
        return jsonify({"error": "start_date is required."}), 400
    if program_type not in VALID_TYPES:
        return jsonify({"error": f"Invalid program_type. Must be one of: {', '.join(VALID_TYPES)}."}), 400

    db = get_db()
    try:
        school = db.execute("SELECT school_id FROM schools WHERE school_id = ? AND deleted_at IS NULL", (school_id,)).fetchone()
        if not school:
            return jsonify({"error": "School not found."}), 404

        cur = db.execute(
            """INSERT INTO programs
               (school_id, program_name, program_type, service_model, grade_band,
                start_date, end_date, frequency, program_status, reporting_cycle, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (school_id, program_name, program_type, service_model, grade_band,
             start_date, end_date, frequency, reporting_cycle, notes, now_utc()),
        )
        new_id = cur.lastrowid
        audit(db, user["user_id"], "INSERT", "programs", new_id,
              new_values={"school_id": school_id, "program_name": program_name, "program_type": program_type})
        db.commit()

        row = db.execute(
            """SELECT p.*, sc.school_name FROM programs p
               JOIN schools sc ON sc.school_id = p.school_id WHERE p.program_id = ?""",
            (new_id,),
        ).fetchone()
        return jsonify({"ok": True, "program": dict(row)}), 201
    finally:
        db.close()


@admin_bp.route("/api/programs/<int:program_id>", methods=["DELETE"])
@admin_required
def delete_program(program_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        row = db.execute("SELECT program_id, program_name FROM programs WHERE program_id = ?", (program_id,)).fetchone()
        if not row:
            return jsonify({"error": "Program not found."}), 404

        db.execute("UPDATE programs SET program_status = 'inactive' WHERE program_id = ?", (program_id,))
        db.execute("UPDATE student_program_enrollment SET status = 'inactive' WHERE program_id = ?", (program_id,))
        db.execute("UPDATE staff_assignments SET active_status = 0 WHERE program_id = ?", (program_id,))
        audit(db, user["user_id"], "DELETE", "programs", program_id,
              old_values={"program_name": row["program_name"]})
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ===========================================================================
# ASSESSMENT WINDOWS  (TABLE 14) — admin creates, coaches read
# ===========================================================================

@admin_bp.route("/api/assessment-windows", methods=["GET"])
@admin_required
def list_assessment_windows_admin():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    school_id = request.args.get("school_id", type=int)
    status_filter = request.args.get("status", "").strip()

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        sql = """
            SELECT aw.*, sc.school_name, p.program_name
            FROM assessment_windows aw
            JOIN schools sc ON sc.school_id = aw.school_id
            LEFT JOIN programs p ON p.program_id = aw.program_id
            WHERE 1=1
        """
        params = []
        if org_id is not None:
            sql += " AND sc.organization_id = ?"
            params.append(org_id)
        if school_id:
            sql += " AND aw.school_id = ?"
            params.append(school_id)
        if status_filter in ("upcoming", "active", "closed"):
            sql += " AND aw.status = ?"
            params.append(status_filter)
        sql += " ORDER BY aw.start_date DESC"
        rows = db.execute(sql, params).fetchall()
        return jsonify({"ok": True, "windows": [dict(r) for r in rows]})
    finally:
        db.close()


@admin_bp.route("/api/assessment-windows", methods=["POST"])
@admin_required
def create_assessment_window():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    school_id = data.get("school_id")
    program_id = data.get("program_id") or None
    window_name = (data.get("window_name") or "").strip()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    assessment_focus = (data.get("assessment_focus") or "").strip() or None
    status = (data.get("status") or "upcoming").strip()

    if not school_id or not isinstance(school_id, int):
        return jsonify({"error": "school_id is required."}), 400
    if not window_name:
        return jsonify({"error": "window_name is required."}), 400
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required."}), 400
    if status not in ("upcoming", "active", "closed"):
        return jsonify({"error": "status must be upcoming, active, or closed."}), 400

    try:
        s = datetime.date.fromisoformat(str(start_date))
        e = datetime.date.fromisoformat(str(end_date))
        if e < s:
            return jsonify({"error": "end_date cannot be before start_date."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    db = get_db()
    try:
        school = db.execute("SELECT school_id FROM schools WHERE school_id = ? AND deleted_at IS NULL", (school_id,)).fetchone()
        if not school:
            return jsonify({"error": "School not found."}), 404

        cur = db.execute(
            """INSERT INTO assessment_windows
               (school_id, program_id, window_name, start_date, end_date,
                assessment_focus, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, program_id, window_name, start_date, end_date,
             assessment_focus, status, now_utc()),
        )
        new_id = cur.lastrowid
        audit(db, user["user_id"], "INSERT", "assessment_windows", new_id,
              new_values={"school_id": school_id, "window_name": window_name, "status": status})
        db.commit()
        return jsonify({"ok": True, "window_id": new_id}), 201
    finally:
        db.close()


@admin_bp.route("/api/assessment-windows/<int:window_id>", methods=["PATCH"])
@admin_required
def update_assessment_window(window_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    db = get_db()
    try:
        row = db.execute("SELECT * FROM assessment_windows WHERE window_id = ?", (window_id,)).fetchone()
        if not row:
            return jsonify({"error": "Assessment window not found."}), 404

        fields = {}
        if "window_name" in data and data["window_name"]:
            fields["window_name"] = data["window_name"].strip()
        if "status" in data:
            if data["status"] not in ("upcoming", "active", "closed"):
                return jsonify({"error": "status must be upcoming, active, or closed."}), 400
            fields["status"] = data["status"]
        if "start_date" in data:
            fields["start_date"] = data["start_date"]
        if "end_date" in data:
            fields["end_date"] = data["end_date"]
        if "assessment_focus" in data:
            fields["assessment_focus"] = data["assessment_focus"]

        if not fields:
            return jsonify({"error": "No fields to update."}), 400

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [window_id]
        db.execute(f"UPDATE assessment_windows SET {set_clause} WHERE window_id = ?", vals)
        audit(db, user["user_id"], "UPDATE", "assessment_windows", window_id, new_values=fields)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()



@admin_bp.route("/api/reports", methods=["GET"])
@admin_required
def list_reports():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    report_type = request.args.get("type", "eod_compliance").strip()
    school_id = request.args.get("school_id", type=int)
    date_from = request.args.get("from", (date.today() - timedelta(days=30)).isoformat())
    date_to = request.args.get("to", date.today().isoformat())

    try:
        datetime.date.fromisoformat(date_from)
        datetime.date.fromisoformat(date_to)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        org_filter = "AND s.organization_id = ?" if org_id else ""
        org_params = [org_id] if org_id else []

        school_filter = "AND er.school_id = ?" if school_id else ""
        school_params = [school_id] if school_id else []

        if report_type == "eod_compliance":
            rows = db.execute(
                f"""
                SELECT
                    sp.staff_id,
                    u.first_name || ' ' || u.last_name AS coach_name,
                    sc.school_name,
                    COUNT(DISTINCT er.report_date) AS eod_submitted,
                    SUM(CASE WHEN er.submitted_on_time = 1 THEN 1 ELSE 0 END) AS on_time,
                    SUM(CASE WHEN er.submitted_on_time = 0 THEN 1 ELSE 0 END) AS late,
                    COUNT(DISTINCT se.session_date) AS sessions_logged
                FROM staff_profiles sp
                JOIN users u ON u.user_id = sp.user_id
                JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = 1
                JOIN schools sc ON sc.school_id = sa.school_id {org_filter}
                LEFT JOIN eod_reports er
                    ON er.staff_id = sp.staff_id
                    AND er.report_date BETWEEN ? AND ?
                    AND er.deleted_at IS NULL
                    {school_filter}
                LEFT JOIN sessions se
                    ON se.school_id = sa.school_id
                    AND se.session_date BETWEEN ? AND ?
                    AND se.deleted_at IS NULL
                WHERE u.role IN ('head_coach', 'assistant_coach')
                  AND u.active_status = 1
                  AND u.deleted_at IS NULL
                GROUP BY sp.staff_id, u.first_name, u.last_name, sc.school_name
                ORDER BY sc.school_name, coach_name
                """,
                org_params + [date_from, date_to] + school_params + [date_from, date_to],
            ).fetchall()
            return jsonify({
                "ok": True, "type": "eod_compliance",
                "from": date_from, "to": date_to,
                "rows": [dict(r) for r in rows],
            })

        elif report_type == "sessions":
            rows = db.execute(
                f"""
                SELECT
                    sc.school_name,
                    COUNT(*) AS total_sessions,
                    SUM(se.total_students_present) AS total_attendance,
                    ROUND(AVG(se.total_students_present), 1) AS avg_attendance,
                    COUNT(DISTINCT se.session_date) AS active_days
                FROM sessions se
                JOIN schools sc ON sc.school_id = se.school_id
                WHERE se.session_date BETWEEN ? AND ?
                  AND se.deleted_at IS NULL
                  {org_filter}
                  {school_filter}
                GROUP BY sc.school_id, sc.school_name
                ORDER BY sc.school_name
                """,
                [date_from, date_to] + org_params + school_params,
            ).fetchall()
            return jsonify({
                "ok": True, "type": "sessions",
                "from": date_from, "to": date_to,
                "rows": [dict(r) for r in rows],
            })

        elif report_type == "incidents":
            rows = db.execute(
                f"""
                SELECT
                    sc.school_name,
                    ir.severity_level,
                    ir.incident_type,
                    COUNT(*) AS count,
                    SUM(CASE WHEN ir.status = 'open' THEN 1 ELSE 0 END) AS open_count,
                    SUM(CASE WHEN ir.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_count
                FROM incident_reports ir
                JOIN schools sc ON sc.school_id = ir.school_id
                WHERE ir.report_date BETWEEN ? AND ?
                  {org_filter}
                  {school_filter.replace('er.school_id', 'ir.school_id')}
                GROUP BY sc.school_id, sc.school_name, ir.severity_level, ir.incident_type
                ORDER BY sc.school_name, ir.severity_level
                """,
                [date_from, date_to] + org_params + ([school_id] if school_id else []),
            ).fetchall()
            return jsonify({
                "ok": True, "type": "incidents",
                "from": date_from, "to": date_to,
                "rows": [dict(r) for r in rows],
            })

        elif report_type == "student_growth":
            rows = db.execute(
                f"""
                SELECT
                    sc.school_name,
                    COUNT(DISTINCT sos.student_id) AS students_with_scores,
                    ROUND(AVG(sos.overall_score), 1) AS avg_score,
                    ROUND(AVG(sos.growth_amount), 1) AS avg_growth,
                    SUM(CASE WHEN sos.performance_band = 'Advanced' THEN 1 ELSE 0 END) AS advanced,
                    SUM(CASE WHEN sos.performance_band = 'Proficient' THEN 1 ELSE 0 END) AS proficient,
                    SUM(CASE WHEN sos.performance_band = 'On Track' THEN 1 ELSE 0 END) AS on_track,
                    SUM(CASE WHEN sos.performance_band = 'Developing' THEN 1 ELSE 0 END) AS developing,
                    SUM(CASE WHEN sos.performance_band = 'Emerging' THEN 1 ELSE 0 END) AS emerging
                FROM student_overall_summary sos
                JOIN students st ON st.student_id = sos.student_id
                JOIN schools sc ON sc.school_id = st.school_id
                WHERE st.active_status = 1 AND st.deleted_at IS NULL
                  {org_filter}
                  {('AND sc.school_id = ?' if school_id else '')}
                GROUP BY sc.school_id, sc.school_name
                ORDER BY sc.school_name
                """,
                org_params + ([school_id] if school_id else []),
            ).fetchall()
            return jsonify({
                "ok": True, "type": "student_growth",
                "from": date_from, "to": date_to,
                "rows": [dict(r) for r in rows],
            })

        else:
            return jsonify({"error": f"Unknown report type '{report_type}'."}), 400

    finally:
        db.close()



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
                     AND ir.deleted_at IS NULL
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



@admin_bp.route("/api/admin/dashboard", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_dashboard():
    user = current_user()
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        org_filter = "AND s.organization_id = ?" if org_id else ""
        org_params = (org_id,) if org_id else ()

        active_schools = db.execute(
            f"SELECT COUNT(*) AS cnt FROM schools s WHERE s.active_status=1 AND s.deleted_at IS NULL {org_filter}",
            org_params,
        ).fetchone()["cnt"]

        active_coaches = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM users u
               JOIN staff_profiles sp ON sp.user_id = u.user_id
               JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = 1
               JOIN schools s ON s.school_id = sa.school_id
               WHERE u.role IN ('head_coach','assistant_coach')
                 AND u.active_status=1 AND u.deleted_at IS NULL
                 {org_filter}""",
            org_params,
        ).fetchone()["cnt"]

        sessions_this_week = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM sessions se
               JOIN schools s ON s.school_id = se.school_id
               WHERE se.session_date BETWEEN ? AND ? AND se.deleted_at IS NULL {org_filter}""",
            (week_start, week_end) + org_params,
        ).fetchone()["cnt"]

        # EOD compliance: expected = unique (staff_id, school_id, session_date) tuples
        # so coaches at multiple schools count once per school per day.
        expected_row = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM (
                 SELECT DISTINCT ss.staff_id, se.school_id, se.session_date
                 FROM sessions se
                 JOIN session_staff ss ON ss.session_id = se.session_id
                 JOIN schools s ON s.school_id = se.school_id
                 WHERE se.session_date BETWEEN ? AND ?
                   AND se.deleted_at IS NULL
                   {org_filter}
               )""",
            (week_start, week_end) + org_params,
        ).fetchone()
        expected = expected_row["cnt"] if expected_row else 0

        actual_row = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM eod_reports er
               JOIN schools s ON s.school_id = er.school_id
               WHERE er.report_date BETWEEN ? AND ? AND er.deleted_at IS NULL {org_filter}""",
            (week_start, week_end) + org_params,
        ).fetchone()
        actual = actual_row["cnt"] if actual_row else 0

        if expected > 0:
            eod_compliance_rate = round(min(1.0, actual / expected), 2)
        else:
            eod_compliance_rate = 0.0

        open_incidents = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.status='open' AND ir.deleted_at IS NULL {org_filter}""",
            org_params,
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
    user = current_user()
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        org_filter = "AND s.organization_id = ?" if org_id else ""
        params = [week_start, week_end]
        if org_id:
            params.append(org_id)

        rows = db.execute(
            f"""SELECT
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
               WHERE s.active_status = 1 AND s.deleted_at IS NULL {org_filter}
               ORDER BY s.school_name ASC""",
            params,
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
    user = current_user()
    week_start, week_end = _get_week_bounds()
    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        org_filter = "AND s.organization_id = ?" if org_id else ""
        params = [week_start, week_end, week_start, week_end, week_start, week_end]
        if org_id:
            params.append(org_id)

        rows = db.execute(
            f"""SELECT
                 u.user_id, u.role, u.first_name, u.last_name, u.email,
                 u.active_status, u.created_at,
                 sp.staff_id, sp.position_title,
                 sp.rolling_score, sp.rolling_band,
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
                 {org_filter}
               ORDER BY u.last_name ASC, u.first_name ASC""",
            params,
        ).fetchall()

        coaches = []
        for r in rows:
            coach = serialize_user(r)
            coach["eod_submissions_this_week"] = r["eod_submissions_this_week"]
            coach["late_submissions_this_week"] = r["late_submissions_this_week"]
            coach["incidents_filed_this_week"] = r["incidents_filed_this_week"]
            coach["rolling_score"] = r["rolling_score"]
            coach["rolling_band"] = r["rolling_band"]
            coaches.append(coach)

        return jsonify({"ok": True, "coaches": coaches, "total": len(coaches)})
    except Exception:
        return jsonify({"error": "Could not load coaches — please try again or contact support."}), 500
    finally:
        db.close()


@admin_bp.route("/api/admin/coaches/<int:staff_id>/score", methods=["GET"])
@admin_required
def get_coach_score(staff_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    from_str = request.args.get("from")
    to_str   = request.args.get("to")
    try:
        period_start = _date.fromisoformat(from_str) if from_str else rolling_period()[0]
        period_end   = _date.fromisoformat(to_str)   if to_str   else rolling_period()[1]
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        staff = db.execute(
            "SELECT sp.staff_id, sp.user_id, sa.school_id"
            " FROM staff_profiles sp"
            " JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status=1"
            " JOIN schools sc ON sc.school_id = sa.school_id"
            " WHERE sp.staff_id=? AND sp.deleted_at IS NULL"
            + (" AND sc.organization_id=?" if org_id else ""),
            (staff_id, org_id) if org_id else (staff_id,),
        ).fetchone()
        if not staff:
            return jsonify({"error": "Coach not found."}), 404

        school_id = staff["school_id"]
        scorecard = calculate_coach_score(db, staff_id, school_id, period_start, period_end)

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


@admin_bp.route("/api/admin/coaches/<int:staff_id>/score/freeze", methods=["POST"])
@admin_required
def freeze_coach_score(staff_id: int):
    """Save a point-in-time snapshot of a coach's score."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    try:
        period_start = _date.fromisoformat(data.get("period_start") or rolling_period()[0].isoformat())
        period_end   = _date.fromisoformat(data.get("period_end")   or rolling_period()[1].isoformat())
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400
    window_id = data.get("window_id")

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        staff = db.execute(
            "SELECT sp.staff_id, sa.school_id FROM staff_profiles sp"
            " JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status=1"
            " JOIN schools sc ON sc.school_id = sa.school_id"
            " WHERE sp.staff_id=? AND sp.deleted_at IS NULL"
            + (" AND sc.organization_id=?" if org_id else ""),
            (staff_id, org_id) if org_id else (staff_id,),
        ).fetchone()
        if not staff:
            return jsonify({"error": "Coach not found."}), 404

        school_id = staff["school_id"]
        sc = calculate_coach_score(db, staff_id, school_id, period_start, period_end)

        cur = db.execute(
            "INSERT INTO coach_performance_snapshots"
            " (staff_id, school_id, window_id, period_start, period_end,"
            "  compliance_score, outcomes_score, observations_score, overall_score,"
            "  performance_band, eod_ontime_rate, session_log_rate,"
            "  incident_file_rate, assessment_part_rate)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (staff_id, school_id, window_id,
             period_start.isoformat(), period_end.isoformat(),
             sc["compliance_score"], sc["outcomes_score"], sc["observations_score"],
             sc["overall_score"], sc["performance_band"],
             sc["eod_ontime_rate"], sc["session_log_rate"],
             sc["incident_file_rate"], sc["assessment_part_rate"]),
        )
        db.commit()
        return jsonify({"ok": True, "snapshot_id": cur.lastrowid, "scorecard": sc}), 201
    finally:
        db.close()


@admin_bp.route("/api/admin/incidents", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_incidents():
    user = current_user()
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
        org_id = _get_org_scope(db, user)
        org_filter = "AND s.organization_id = ?" if org_id else ""
        org_params = (org_id,) if org_id else ()

        total_row = db.execute(
            f"""SELECT COUNT(*) AS cnt FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.report_date BETWEEN ? AND ? AND ir.deleted_at IS NULL {org_filter}""",
            (window_start_str, window_end_str) + org_params,
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        severity_rows = db.execute(
            f"""SELECT ir.severity_level, COUNT(*) AS cnt
               FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.report_date BETWEEN ? AND ? AND ir.deleted_at IS NULL {org_filter}
               GROUP BY ir.severity_level
               ORDER BY cnt DESC""",
            (window_start_str, window_end_str) + org_params,
        ).fetchall()
        by_severity = [{"severity_level": r["severity_level"], "count": r["cnt"]}
                       for r in severity_rows]

        school_rows = db.execute(
            f"""SELECT ir.school_id, s.school_name, COUNT(*) AS cnt
               FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.report_date BETWEEN ? AND ? AND ir.deleted_at IS NULL {org_filter}
               GROUP BY ir.school_id, s.school_name
               ORDER BY cnt DESC""",
            (window_start_str, window_end_str) + org_params,
        ).fetchall()
        by_school = [{"school_id": r["school_id"], "school_name": r["school_name"], "count": r["cnt"]}
                     for r in school_rows]

        # Build week list — N entries, zero-fill missing weeks
        week_counts = {}
        for week_rows in db.execute(
            f"""SELECT ir.report_date, COUNT(*) AS cnt
               FROM incident_reports ir
               JOIN schools s ON s.school_id = ir.school_id
               WHERE ir.report_date BETWEEN ? AND ? AND ir.deleted_at IS NULL {org_filter}
               GROUP BY ir.report_date""",
            (window_start_str, window_end_str) + org_params,
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


@admin_bp.route("/api/admin/incidents/list", methods=["GET"])
@roles_required("ceo", "admin", "coach_overseer")
def admin_incidents_list():
    """Full paginated incident list with resolution status."""
    user = current_user()
    status_filter = request.args.get("status", "").strip()
    school_id = request.args.get("school_id", type=int)
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 25))))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid pagination params."}), 400

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        filters, params = ["ir.deleted_at IS NULL"], []
        if org_id:
            filters.append("s.organization_id = ?"); params.append(org_id)
        if status_filter in ("open", "resolved"):
            filters.append("ir.status = ?"); params.append(status_filter)
        if school_id:
            filters.append("ir.school_id = ?"); params.append(school_id)

        where = " AND ".join(filters)
        total = db.execute(
            f"SELECT COUNT(*) AS cnt FROM incident_reports ir JOIN schools s ON s.school_id = ir.school_id WHERE {where}",
            params,
        ).fetchone()["cnt"]

        rows = db.execute(
            f"""SELECT ir.incident_id, ir.report_date, ir.incident_type, ir.severity_level,
                       ir.description, ir.immediate_action_taken, ir.status,
                       ir.admin_response, ir.resolution_notes, ir.acknowledged_at,
                       ir.school_notified, ir.family_notified,
                       s.school_name,
                       u.first_name || ' ' || u.last_name AS reporter_name,
                       st.student_first_name || ' ' || st.student_last_name AS student_name
                FROM incident_reports ir
                JOIN schools s ON s.school_id = ir.school_id
                JOIN staff_profiles sp ON sp.staff_id = ir.reported_by_staff_id
                JOIN users u ON u.user_id = sp.user_id
                LEFT JOIN students st ON st.student_id = ir.student_id
                WHERE {where}
                ORDER BY
                    CASE ir.status WHEN 'open' THEN 0 ELSE 1 END,
                    CASE ir.severity_level WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    ir.report_date DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

        return jsonify({"ok": True, "total": total, "page": page, "per_page": per_page,
                        "incidents": [dict(r) for r in rows]})
    finally:
        db.close()


@admin_bp.route("/api/admin/incidents/<int:incident_id>", methods=["PATCH"])
@roles_required("ceo", "admin", "coach_overseer")
def resolve_incident(incident_id: int):
    """Resolve or reopen an incident with admin response."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    data = parse_json()
    new_status = data.get("status", "").strip()
    if new_status not in ("open", "resolved"):
        return jsonify({"error": "status must be 'open' or 'resolved'."}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT incident_id, school_id FROM incident_reports WHERE incident_id = ? AND deleted_at IS NULL",
            (incident_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Incident not found."}), 404

        org_id = _get_org_scope(db, user)
        if org_id:
            school = db.execute("SELECT organization_id FROM schools WHERE school_id = ?", (row["school_id"],)).fetchone()
            if not school or school["organization_id"] != org_id:
                return jsonify({"error": "Access denied."}), 403

        fields = {"status": new_status}
        if data.get("admin_response") is not None:
            fields["admin_response"] = str(data["admin_response"])[:2000]
        if data.get("resolution_notes") is not None:
            fields["resolution_notes"] = str(data["resolution_notes"])[:2000]
        if new_status == "resolved":
            fields["acknowledged_at"] = now_utc()
            fields["acknowledged_by"] = user["user_id"]

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        db.execute(
            f"UPDATE incident_reports SET {set_clause} WHERE incident_id = ?",
            list(fields.values()) + [incident_id],
        )
        audit(db, user["user_id"], "UPDATE", "incident_reports", incident_id,
              new_values={"status": new_status})
        db.commit()
        updated = db.execute("SELECT * FROM incident_reports WHERE incident_id = ?", (incident_id,)).fetchone()
        return jsonify({"ok": True, "incident": dict(updated)})
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

    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)

        # Build org filter fragments
        if org_id is not None:
            org_student_filter = " AND school_id IN (SELECT school_id FROM schools WHERE organization_id=?)"
            org_school_filter = " AND organization_id=?"
            org_assess_filter = (
                " AND school_id IN (SELECT school_id FROM schools WHERE organization_id=?)"
            )
            org_p = [org_id]
        else:
            org_student_filter = org_school_filter = org_assess_filter = ""
            org_p = []

        total_students = db.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE active_status=1 AND deleted_at IS NULL"
            + org_student_filter,
            org_p,
        ).fetchone()["cnt"]

        if window_id is not None:
            assessed_students = db.execute(
                "SELECT COUNT(DISTINCT student_id) AS cnt FROM assessments WHERE deleted_at IS NULL AND window_id=?"
                + org_assess_filter,
                [window_id] + org_p,
            ).fetchone()["cnt"]
        else:
            assessed_students = db.execute(
                "SELECT COUNT(DISTINCT student_id) AS cnt FROM assessments WHERE deleted_at IS NULL"
                + org_assess_filter,
                org_p,
            ).fetchone()["cnt"]

        school_rows = db.execute(
            "SELECT school_id, school_name FROM schools WHERE active_status=1 AND deleted_at IS NULL"
            + org_school_filter
            + " ORDER BY school_name ASC",
            org_p,
        ).fetchall()

        if window_id is not None:
            assessed_by_school = {
                r["school_id"]: r["cnt"]
                for r in db.execute(
                    "SELECT school_id, COUNT(DISTINCT student_id) AS cnt FROM assessments"
                    " WHERE deleted_at IS NULL AND window_id=?"
                    + org_assess_filter
                    + " GROUP BY school_id",
                    [window_id] + org_p,
                ).fetchall()
            }
        else:
            assessed_by_school = {
                r["school_id"]: r["cnt"]
                for r in db.execute(
                    "SELECT school_id, COUNT(DISTINCT student_id) AS cnt FROM assessments"
                    " WHERE deleted_at IS NULL"
                    + org_assess_filter
                    + " GROUP BY school_id",
                    org_p,
                ).fetchall()
            }

        total_by_school = {
            r["school_id"]: r["cnt"]
            for r in db.execute(
                "SELECT school_id, COUNT(*) AS cnt FROM students"
                " WHERE active_status=1 AND deleted_at IS NULL"
                + org_student_filter
                + " GROUP BY school_id",
                org_p,
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



@admin_bp.route("/api/admin/eod-alerts", methods=["POST"])
@roles_required("ceo", "admin", "coach_overseer")
def trigger_eod_alerts():
    """
    Trigger EOD compliance notifications for coaches who had sessions today
    but have not yet submitted an EOD report.

    Intended to be called at 20:00 Pacific by a scheduler (cron/Railway).
    Safe to call multiple times — idempotent per coach per calendar day.
    """
    now = _now_pacific()
    today = now.date().isoformat()          # Pacific date — used for session_date queries
    today_utc = now_utc()[:10]              # UTC date prefix — used for created_at idempotency

    db = get_db()
    try:
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
