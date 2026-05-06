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
from app.extensions import limiter
from app.routes._helpers import audit, now_utc, parse_json

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
             AND sa.active_status = TRUE
             AND sa.deleted_at IS NULL
             AND sp.deleted_at IS NULL
           ORDER BY sa.created_at DESC
           LIMIT 1""",
        (user_id,),
    ).fetchone()
    return row["school_id"] if row else None



def _reliability_badge(score):
    """Convert composite score to badge label."""
    if score is None:
        return "unscored"
    if score >= 80:
        return "strong"
    if score >= 60:
        return "developing"
    return "needs_support"


@principal_bp.route("/api/principal/dashboard", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_dashboard():
    """
    School-level dashboard stats for the authenticated principal.
    Scoped to the principal's assigned school — no school_id trusted from client.
    """
    user = current_user()
    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        week_start, week_end = _get_week_bounds()
        today = _now_pacific().date()
        thirty_ago = (today - datetime.timedelta(days=30)).isoformat()
        today_iso = today.isoformat()

        school_row = db.execute(
            """SELECT school_id, school_name, school_type, city, state
               FROM schools WHERE school_id = ? AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()

        sessions_this_week = db.execute(
            """SELECT COUNT(*) AS cnt FROM sessions
               WHERE school_id = ? AND session_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (school_id, week_start, week_end),
        ).fetchone()["cnt"]

        students_total = db.execute(
            """SELECT COUNT(*) AS cnt FROM students
               WHERE school_id = ? AND active_status = TRUE AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        students_assessed = db.execute(
            """SELECT COUNT(DISTINCT a.student_id) AS cnt
               FROM assessments a WHERE a.school_id = ? AND a.deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        open_incidents = db.execute(
            """SELECT COUNT(*) AS cnt FROM incident_reports
               WHERE school_id = ? AND status = 'open' AND deleted_at IS NULL""",
            (school_id,),
        ).fetchone()["cnt"]

        # Session compliance: % of calendar days in last 30 with at least one session
        session_days_row = db.execute(
            """SELECT COUNT(DISTINCT session_date) AS cnt FROM sessions
               WHERE school_id = ? AND session_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (school_id, thirty_ago, today_iso),
        ).fetchone()
        session_days = session_days_row["cnt"] if session_days_row else 0
        # 22 working days is a reasonable month approximation for display
        session_compliance = round(min(1.0, session_days / 22), 2)

        # EOD compliance (weekly, existing metric)
        expected_row = db.execute(
            """SELECT COUNT(*) AS cnt FROM (
                 SELECT DISTINCT ss.staff_id, s.session_date
                 FROM sessions s
                 JOIN session_staff ss ON ss.session_id = s.session_id
                 WHERE s.school_id = ? AND s.session_date BETWEEN ? AND ?
                   AND s.deleted_at IS NULL
               ) AS _exp""",
            (school_id, week_start, week_end),
        ).fetchone()
        expected = expected_row["cnt"] if expected_row else 0
        actual_eod = db.execute(
            """SELECT COUNT(*) AS cnt FROM eod_reports
               WHERE school_id = ? AND report_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (school_id, week_start, week_end),
        ).fetchone()["cnt"]
        eod_compliance_rate = round(min(1.0, actual_eod / expected), 2) if expected > 0 else 0.0

        # Coaches with latest performance snapshot
        coach_rows = db.execute(
            """SELECT DISTINCT u.user_id, u.first_name, u.last_name, u.role,
                      sp.staff_id,
                      cps.overall_score,
                      cps.performance_band,
                      cps.period_start
               FROM users u
               JOIN staff_profiles sp ON sp.user_id = u.user_id AND sp.deleted_at IS NULL
               JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
               LEFT JOIN coach_performance_snapshots cps
                   ON cps.staff_id = sp.staff_id
                   AND cps.snapshot_id = (
                       SELECT snapshot_id FROM coach_performance_snapshots
                       WHERE staff_id = sp.staff_id
                       ORDER BY created_at DESC LIMIT 1
                   )
               WHERE sa.school_id = ? AND sa.active_status = TRUE
                 AND sa.deleted_at IS NULL
                 AND u.active_status = TRUE AND u.deleted_at IS NULL
                 AND u.role IN ('head_coach', 'assistant_coach', 'site_coordinator', 'coach_overseer')
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
                "composite_score": r["overall_score"],
                "performance_band": r["performance_band"],
                "period_label": r["period_start"],
                "reliability_badge": _reliability_badge(r["overall_score"]),
            }
            for r in coach_rows
        ]

        # Skill domain averages (latest assessment per student)
        domain_rows = db.execute(
            """SELECT sd.domain_name,
                      ROUND(AVG(asco.normalized_score), 1) AS avg_score,
                      COUNT(DISTINCT a.student_id) AS student_count
               FROM assessments a
               JOIN (
                   SELECT student_id, MAX(assessment_date) AS latest_date
                   FROM assessments
                   WHERE school_id = ? AND deleted_at IS NULL
                   GROUP BY student_id
               ) latest ON latest.student_id = a.student_id
                       AND latest.latest_date = a.assessment_date
               JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               JOIN skills sk ON sk.skill_id = asco.skill_id
               JOIN skill_domains sd ON sd.domain_id = sk.domain_id
               WHERE a.school_id = ? AND a.deleted_at IS NULL
               GROUP BY sd.domain_id, sd.domain_name
               ORDER BY sd.domain_name""",
            (school_id, school_id),
        ).fetchall()
        domain_averages = [
            {"domain_name": r["domain_name"], "avg_score": r["avg_score"],
             "student_count": r["student_count"]}
            for r in domain_rows
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
            "session_compliance_monthly": session_compliance,
            "session_days_monthly": session_days,
            "students_total": students_total,
            "students_assessed": students_assessed,
            "eod_compliance_rate": eod_compliance_rate,
            "open_incidents": open_incidents,
            "coaches": coaches,
            "domain_averages": domain_averages,
        })
    except Exception:
        logging.exception("principal_dashboard route error")
        return jsonify({"error": "Could not load dashboard — please try again or contact support."}), 500
    finally:
        db.close()



@principal_bp.route("/api/principal/coaches/<int:staff_id>/score", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_coach_score(staff_id: int):
    """
    Returns the latest performance score breakdown for a coach at the principal's school.
    Principal can only view coaches assigned to their school — FERPA hard scope.
    """
    user = current_user()
    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        # Verify coach is at this principal's school
        coach_row = db.execute(
            """SELECT u.user_id, u.first_name, u.last_name, u.role, sp.staff_id
               FROM users u
               JOIN staff_profiles sp ON sp.user_id = u.user_id AND sp.deleted_at IS NULL
               JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
               WHERE sp.staff_id = ?
                 AND sa.school_id = ?
                 AND sa.active_status = TRUE
                 AND sa.deleted_at IS NULL
                 AND u.active_status = TRUE
                 AND u.deleted_at IS NULL
                 AND u.role IN ('head_coach', 'assistant_coach', 'site_coordinator', 'coach_overseer')""",
            (staff_id, school_id),
        ).fetchone()
        if not coach_row:
            return jsonify({"error": "Coach not found at your school."}), 404

        # Latest snapshot
        snap = db.execute(
            """SELECT overall_score, compliance_score, outcomes_score, observations_score,
                      performance_band, eod_ontime_rate, session_log_rate,
                      incident_file_rate, assessment_part_rate, period_start, period_end
               FROM coach_performance_snapshots
               WHERE staff_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (staff_id,),
        ).fetchone()

        # Recent activity counts (last 30 days)
        today = _now_pacific().date()
        thirty_ago = (today - datetime.timedelta(days=30)).isoformat()
        today_iso = today.isoformat()

        sessions_logged = db.execute(
            """SELECT COUNT(*) AS cnt FROM sessions s
               JOIN session_staff ss ON ss.session_id = s.session_id
               WHERE ss.staff_id = ? AND s.school_id = ?
                 AND s.session_date BETWEEN ? AND ?
                 AND s.deleted_at IS NULL""",
            (staff_id, school_id, thirty_ago, today_iso),
        ).fetchone()["cnt"]

        eods_filed = db.execute(
            """SELECT COUNT(*) AS cnt FROM eod_reports
               WHERE staff_id = ? AND school_id = ?
                 AND report_date BETWEEN ? AND ?
                 AND deleted_at IS NULL""",
            (staff_id, school_id, thirty_ago, today_iso),
        ).fetchone()["cnt"]

        eods_ontime = db.execute(
            """SELECT COUNT(*) AS cnt FROM eod_reports
               WHERE staff_id = ? AND school_id = ?
                 AND report_date BETWEEN ? AND ?
                 AND submitted_on_time = TRUE
                 AND deleted_at IS NULL""",
            (staff_id, school_id, thirty_ago, today_iso),
        ).fetchone()["cnt"]

        audit(db, user["user_id"], "READ", "coach_performance_snapshots", staff_id,
              new_values={"scope": "principal_coach_score", "school_id": school_id})
        db.commit()

        return jsonify({
            "ok": True,
            "coach": {
                "staff_id": staff_id,
                "first_name": coach_row["first_name"],
                "last_name": coach_row["last_name"],
                "role": coach_row["role"],
            },
            "snapshot": dict(snap) if snap else None,
            "activity": {
                "sessions_logged_30d": sessions_logged,
                "eods_filed_30d": eods_filed,
                "eods_ontime_30d": eods_ontime,
            },
        })
    except Exception:
        logging.exception("principal_coach_score error")
        return jsonify({"error": "Could not load coach score."}), 500
    finally:
        db.close()


@principal_bp.route("/api/principal/skill-averages", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_skill_averages():
    """
    School-wide skill domain averages broken down by grade level.
    Uses latest assessment per student. Scoped to principal's school.
    """
    user = current_user()
    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        # Grade-level breakdown by domain
        grade_rows = db.execute(
            """SELECT s.grade_level,
                      sd.domain_name,
                      ROUND(AVG(asco.normalized_score), 1) AS avg_score,
                      COUNT(DISTINCT a.student_id) AS student_count
               FROM assessments a
               JOIN (
                   SELECT student_id, MAX(assessment_date) AS latest_date
                   FROM assessments
                   WHERE school_id = ? AND deleted_at IS NULL
                   GROUP BY student_id
               ) latest ON latest.student_id = a.student_id
                       AND latest.latest_date = a.assessment_date
               JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               JOIN skills sk ON sk.skill_id = asco.skill_id
               JOIN skill_domains sd ON sd.domain_id = sk.domain_id
               JOIN students s ON s.student_id = a.student_id
               WHERE a.school_id = ? AND a.deleted_at IS NULL
               GROUP BY s.grade_level, sd.domain_id, sd.domain_name
               ORDER BY s.grade_level, sd.domain_name""",
            (school_id, school_id),
        ).fetchall()

        # Overall domain averages
        domain_rows = db.execute(
            """SELECT sd.domain_name,
                      ROUND(AVG(asco.normalized_score), 1) AS avg_score,
                      COUNT(DISTINCT a.student_id) AS student_count
               FROM assessments a
               JOIN (
                   SELECT student_id, MAX(assessment_date) AS latest_date
                   FROM assessments
                   WHERE school_id = ? AND deleted_at IS NULL
                   GROUP BY student_id
               ) latest ON latest.student_id = a.student_id
                       AND latest.latest_date = a.assessment_date
               JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               JOIN skills sk ON sk.skill_id = asco.skill_id
               JOIN skill_domains sd ON sd.domain_id = sk.domain_id
               WHERE a.school_id = ? AND a.deleted_at IS NULL
               GROUP BY sd.domain_id, sd.domain_name
               ORDER BY sd.domain_name""",
            (school_id, school_id),
        ).fetchall()

        # Restructure grade data into {grade: [{domain, avg_score, student_count}]}
        by_grade = {}
        for r in grade_rows:
            g = r["grade_level"] or "Unknown"
            by_grade.setdefault(g, []).append({
                "domain_name": r["domain_name"],
                "avg_score": r["avg_score"],
                "student_count": r["student_count"],
            })

        # Per-skill averages using raw_level (1-5 scale) for student-page skill card
        skill_rows = db.execute(
            """SELECT sk.skill_id, sk.skill_name, sd.domain_id, sd.domain_name,
                      ROUND(AVG(CAST(asco.raw_level AS NUMERIC)), 2) AS avg_raw_level,
                      COUNT(DISTINCT a.student_id) AS student_count
               FROM assessments a
               JOIN (
                   SELECT student_id, MAX(assessment_date) AS latest_date
                   FROM assessments
                   WHERE school_id = ? AND deleted_at IS NULL
                   GROUP BY student_id
               ) latest ON latest.student_id = a.student_id
                       AND latest.latest_date = a.assessment_date
               JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               JOIN skills sk ON sk.skill_id = asco.skill_id
               JOIN skill_domains sd ON sd.domain_id = sk.domain_id
               WHERE a.school_id = ? AND a.deleted_at IS NULL
               GROUP BY sk.skill_id, sd.domain_id
               ORDER BY sd.domain_name, sk.skill_name""",
            (school_id, school_id),
        ).fetchall()

        audit(db, user["user_id"], "READ", "students", None,
              new_values={"scope": "principal_skill_averages", "school_id": school_id})
        db.commit()
        return jsonify({
            "ok": True,
            "domain_averages": [
                {"domain_name": r["domain_name"], "avg_score": r["avg_score"],
                 "student_count": r["student_count"]}
                for r in domain_rows
            ],
            "by_grade": [
                {"grade_level": g, "domains": domains}
                for g, domains in sorted(by_grade.items())
            ],
            "by_skill": [
                {"skill_id": r["skill_id"], "skill_name": r["skill_name"],
                 "domain_id": r["domain_id"], "domain_name": r["domain_name"],
                 "avg_raw_level": r["avg_raw_level"], "student_count": r["student_count"]}
                for r in skill_rows
            ],
        })
    except Exception:
        logging.exception("principal_skill_averages error")
        return jsonify({"error": "Could not load skill averages."}), 500
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
                 AND active_status = TRUE
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
                 AND s.active_status = TRUE
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


@principal_bp.route("/api/principal/incidents", methods=["GET"])
@roles_required("principal", "school_staff")
def principal_incidents():
    """List incidents for the principal's school, newest first."""
    user = current_user()
    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        status_filter = (request.args.get("status") or "").strip()
        if status_filter and status_filter not in ("open", "under_review", "resolved", "closed"):
            return jsonify({"error": "Invalid status filter."}), 400

        sql = """
            SELECT ir.incident_id, ir.report_date, ir.incident_type, ir.severity_level,
                   ir.description, ir.immediate_action_taken, ir.status,
                   ir.admin_response, ir.resolution_notes, ir.acknowledged_at,
                   ir.school_notified, ir.family_notified, ir.escalated_to_supervisor,
                   (u.first_name || ' ' || u.last_name) AS reporter_name,
                   CASE WHEN su.student_id IS NOT NULL
                        THEN (su.student_first_name || ' ' || su.student_last_name)
                        ELSE NULL END AS student_name
            FROM incident_reports ir
            LEFT JOIN staff_profiles sp ON sp.staff_id = ir.reported_by_staff_id
            LEFT JOIN users u ON u.user_id = sp.user_id
            LEFT JOIN students su ON su.student_id = ir.student_id
            WHERE ir.school_id = ? AND ir.deleted_at IS NULL
        """
        params = [school_id]
        if status_filter:
            sql += " AND ir.status = ?"
            params.append(status_filter)
        sql += " ORDER BY ir.report_date DESC, ir.incident_id DESC LIMIT 100"

        rows = db.execute(sql, params).fetchall()
        incidents = [dict(r) for r in rows]

        audit(db, user["user_id"], "READ", "incident_reports", None,
              new_values={"scope": "principal_incidents", "school_id": school_id})
        db.commit()
        return jsonify({"ok": True, "incidents": incidents})
    except Exception:
        logging.exception("principal_incidents error")
        return jsonify({"error": "Could not load incidents."}), 500
    finally:
        db.close()


@principal_bp.route("/api/principal/incidents/<int:incident_id>", methods=["PATCH"])
@roles_required("principal", "school_staff")
def principal_resolve_incident(incident_id: int):
    """Allow principal to update status and add response notes on their school's incidents."""
    user = current_user()
    data = parse_json()
    new_status = (data.get("status") or "").strip()
    if new_status not in ("open", "under_review", "resolved", "closed"):
        return jsonify({"error": "status must be open, under_review, resolved, or closed."}), 400

    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        row = db.execute(
            "SELECT incident_id, school_id FROM incident_reports WHERE incident_id = ? AND deleted_at IS NULL",
            (incident_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Incident not found."}), 404
        if row["school_id"] != school_id:
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
              new_values={"status": new_status, "updated_by_role": user["role"]})
        db.commit()
        return jsonify({"ok": True})
    except Exception:
        logging.exception("principal_resolve_incident error")
        return jsonify({"error": "Could not update incident."}), 500
    finally:
        db.close()


@principal_bp.route("/api/principal/survey", methods=["POST"])
@roles_required("principal", "school_staff")
@limiter.limit("10 per minute")
def principal_submit_survey():
    """Submit a principal satisfaction survey. One submission per call; no dedup enforced."""
    user = current_user()
    data = parse_json()

    def _int_field(key, required=True):
        v = data.get(key)
        if v is None:
            if required:
                return None, f"{key} is required."
            return None, None
        try:
            v = int(v)
            if not (1 <= v <= 5):
                raise ValueError
            return v, None
        except (ValueError, TypeError):
            return None, f"{key} must be an integer between 1 and 5."

    respondent_name = str(data.get("respondent_name") or "").strip()[:200]
    respondent_position = str(data.get("respondent_position") or "").strip()[:200]
    school_name_input = str(data.get("school_name") or "").strip()[:200]
    email = str(data.get("email") or "").strip()[:200] or None

    if not respondent_name:
        return jsonify({"error": "respondent_name is required."}), 422
    if not respondent_position:
        return jsonify({"error": "respondent_position is required."}), 422
    if not school_name_input:
        return jsonify({"error": "school_name is required."}), 422

    satisfaction_rating, err = _int_field("satisfaction_rating")
    if err: return jsonify({"error": err}), 422
    yard_safety_rating, err = _int_field("yard_safety_rating")
    if err: return jsonify({"error": err}), 422
    coach_performance_rating, err = _int_field("coach_performance_rating")
    if err: return jsonify({"error": err}), 422
    communication_rating, err = _int_field("communication_rating")
    if err: return jsonify({"error": err}), 422
    wellbeing_effectiveness_rating, err = _int_field("wellbeing_effectiveness_rating", required=False)
    if err: return jsonify({"error": err}), 422

    improvements_suggestions = str(data.get("improvements_suggestions") or "").strip()[:5000] or None
    contributions_description = str(data.get("contributions_description") or "").strip()[:5000] or None
    additional_services = str(data.get("additional_services") or "").strip()[:5000] or None

    db = get_db()
    try:
        school_id = _resolve_school_id(db, user["user_id"])
        if not school_id:
            return jsonify({"error": "No school assignment found for your account."}), 403

        db.execute(
            """INSERT INTO principal_satisfaction_surveys
               (school_id, submitted_by_user_id, respondent_name, respondent_position,
                school_name, email,
                satisfaction_rating, yard_safety_rating, coach_performance_rating,
                communication_rating, wellbeing_effectiveness_rating,
                improvements_suggestions, contributions_description, additional_services,
                submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                school_id,
                user["user_id"],
                respondent_name,
                respondent_position,
                school_name_input,
                email,
                satisfaction_rating,
                yard_safety_rating,
                coach_performance_rating,
                communication_rating,
                wellbeing_effectiveness_rating,
                improvements_suggestions,
                contributions_description,
                additional_services,
                now_utc(),
            ),
        )
        audit(db, user["user_id"], "CREATE", "principal_satisfaction_surveys", None,
              new_values={"school_id": school_id, "respondent_name": respondent_name})
        db.commit()
        return jsonify({"ok": True}), 201
    except Exception:
        logging.exception("principal_submit_survey error")
        return jsonify({"error": "Could not submit survey — please try again."}), 500
    finally:
        db.close()
