"""
principal_routes.py — Principal & school_staff portal endpoints.

All routes resolve the principal's school_id server-side from staff_assignments.
No school_id is ever trusted from request params — FERPA hard requirement.
"""

import datetime
import logging
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request

from app.auth import current_user, roles_required
from app.database import get_db
from app.routes._helpers import audit

_PACIFIC = ZoneInfo("America/Los_Angeles")

principal_bp = Blueprint("principal", __name__)


def _now_pacific() -> datetime.datetime:
    """Return current Pacific wall-clock datetime. Monkeypatchable in tests."""
    return datetime.datetime.now(tz=_PACIFIC)


def _get_week_bounds() -> tuple:
    today = _now_pacific().date()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _resolve_school_id(db, user_id: int):
    row = db.execute(
        """SELECT sa.school_id
           FROM staff_assignments sa
           JOIN staff_profiles sp ON sp.staff_id = sa.staff_id
           WHERE sp.user_id = ?
             AND sa.active_status = 1
             AND sa.deleted_at IS NULL
             AND sp.deleted_at IS NULL
           ORDER BY sa.created_at DESC
           LIMIT 1""",
        (user_id,),
    ).fetchone()
    return row["school_id"] if row else None



@principal_bp.route("/api/principal/dashboard", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_dashboard():
    """
    School-level dashboard stats for the authenticated principal.
    Scoped to the principal's assigned school.
    """
    user = current_user()
    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        week_start, week_end = _get_week_bounds()

        school_row = db.execute(
            """SELECT school_id, school_name, school_type, city, state
               FROM schools
               WHERE school_id = ? AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()

        sessions_this_week = db.execute(
            """SELECT COUNT(*) AS cnt FROM sessions
               WHERE school_id = ?
                 AND session_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (school_id, week_start, week_end),
        ).fetchone()["cnt"]

        students_total = db.execute(
            """SELECT COUNT(*) AS cnt FROM students
               WHERE school_id = ?
                 AND active_status = 1
                 AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        students_assessed = db.execute(
            """SELECT COUNT(DISTINCT a.student_id) AS cnt
               FROM assessments a
               WHERE a.school_id = ?
                 AND a.deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        expected_row = db.execute(
            """SELECT COUNT(*) AS cnt
               FROM (
                 SELECT DISTINCT ss.staff_id, s.session_date
                 FROM sessions s
                 JOIN session_staff ss ON ss.session_id = s.session_id
                 WHERE s.school_id = ?
                   AND s.session_date BETWEEN ? AND ?
                   AND s.deleted_at IS NULL
               ) AS _expected""",
            (school_id, week_start, week_end),
        ).fetchone()
        expected = expected_row["cnt"] if expected_row else 0

        actual = db.execute(
            """SELECT COUNT(*) AS cnt FROM eod_reports
               WHERE school_id = ?
                 AND report_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (school_id, week_start, week_end),
        ).fetchone()["cnt"]

        eod_compliance_rate = round(min(1.0, actual / expected), 2) if expected > 0 else 0.0

        open_incidents = db.execute(
            """SELECT COUNT(*) AS cnt FROM incident_reports
               WHERE school_id = ?
                 AND status = 'open'
                 AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        coach_rows = db.execute(
            """SELECT DISTINCT u.user_id, u.first_name, u.last_name, u.role
               FROM users u
               JOIN staff_profiles sp ON sp.user_id = u.user_id AND sp.deleted_at IS NULL
               JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
               WHERE sa.school_id = ?
                 AND sa.active_status = 1
                 AND sa.deleted_at IS NULL
                 AND u.active_status = 1
                 AND u.deleted_at IS NULL
               ORDER BY u.last_name ASC, u.first_name ASC""",
            (school_id,),
        ).fetchall()
        coaches = [
            {"user_id": r["user_id"], "first_name": r["first_name"],
             "last_name": r["last_name"], "role": r["role"]}
            for r in coach_rows
        ]

        audit(db, user["user_id"], "READ", "students", None,
              new_values={"scope": "principal_dashboard", "school_id": school_id})
        db.commit()
        return jsonify({
            "ok": True,
            "school": {
                "school_id": school_row["school_id"],
                "school_name": school_row["school_name"],
                "school_type": school_row["school_type"],
                "city": school_row["city"],
                "state": school_row["state"],
            },
            "sessions_this_week": sessions_this_week,
            "students_total": students_total,
            "students_assessed": students_assessed,
            "eod_compliance_rate": eod_compliance_rate,
            "open_incidents": open_incidents,
            "coaches": coaches,
        })
    except Exception:
        logging.exception("principal_dashboard route error")
        return jsonify({"error": "Could not load dashboard — please try again or contact support."}), 500
    finally:
        db.close()



@principal_bp.route("/api/principal/students", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_students():
    """
    Paginated student roster for the principal's school with assessment summaries.
    Query params: page (default 1), per_page (default 25, max 100), search (optional).
    """
    user = current_user()

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "page must be a positive integer."}), 422

    try:
        per_page = int(request.args.get("per_page", 25))
        if not (1 <= per_page <= 100):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "per_page must be an integer between 1 and 100."}), 422

    search = (request.args.get("search") or "").strip()
    if len(search) > 100:
        return jsonify({"error": "search must be 100 characters or fewer."}), 422

    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        search_pattern = f"%{search.lower()}%" if search else "%"
        offset = (page - 1) * per_page

        total_row = db.execute(
            """SELECT COUNT(*) AS cnt FROM students
               WHERE school_id = ?
                 AND active_status = 1
                 AND deleted_at IS NULL
                 AND (LOWER(student_first_name) LIKE ? OR LOWER(student_last_name) LIKE ?)""",
            (school_id, search_pattern, search_pattern),
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        rows = db.execute(
            """SELECT
                   s.student_id,
                   s.student_first_name,
                   s.student_last_name,
                   s.grade_level,
                   latest_a.latest_assessment_date,
                   ROUND(AVG(asco.raw_level), 1) AS avg_raw_level
               FROM students s
               LEFT JOIN (
                   SELECT student_id, MAX(assessment_date) AS latest_assessment_date
                   FROM assessments
                   WHERE school_id = ?
                     AND deleted_at IS NULL
                   GROUP BY student_id
               ) AS latest_a ON latest_a.student_id = s.student_id
               LEFT JOIN assessments a
                   ON a.student_id = s.student_id
                   AND a.school_id = ?
                   AND a.assessment_date = latest_a.latest_assessment_date
                   AND a.deleted_at IS NULL
               LEFT JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               WHERE s.school_id = ?
                 AND s.active_status = 1
                 AND s.deleted_at IS NULL
                 AND (LOWER(s.student_first_name) LIKE ? OR LOWER(s.student_last_name) LIKE ?)
               GROUP BY s.student_id, s.student_first_name, s.student_last_name,
                        s.grade_level, latest_a.latest_assessment_date
               ORDER BY s.student_last_name ASC, s.student_first_name ASC
               LIMIT ? OFFSET ?""",
            (school_id, school_id, school_id, search_pattern, search_pattern, per_page, offset),
        ).fetchall()

        students = [
            {
                "student_id": r["student_id"],
                "first_name": r["student_first_name"],
                "last_name": r["student_last_name"],
                "grade_level": r["grade_level"],
                "latest_assessment_date": r["latest_assessment_date"],
                "avg_raw_level": r["avg_raw_level"],
            }
            for r in rows
        ]

        audit(db, user["user_id"], "READ", "students", None,
              new_values={"scope": "principal_roster", "school_id": school_id, "total": total})
        db.commit()
        return jsonify({
            "ok": True,
            "page": page,
            "per_page": per_page,
            "total": total,
            "students": students,
        })
    except Exception:
        logging.exception("principal_students route error")
        return jsonify({"error": "Could not load students — please try again or contact support."}), 500
    finally:
        db.close()
