"""
parent_routes.py — Parent portal endpoints.

Parents can only see their own children's data (FERPA).
All student queries are scoped via parents.user_id → students.parent_primary_id / parent_secondary_id.
"""

import logging

from flask import Blueprint, jsonify

from app.auth import current_user, roles_required
from app.database import get_db
from app.routes._helpers import audit

parent_bp = Blueprint("parent", __name__)



@parent_bp.route("/api/parent/student", methods=["GET"])
@roles_required("parent")
def parent_student():
    """
    Return all children linked to the authenticated parent, with recent session
    attendance and assessment summary per skill domain.
    Returns 200 with children=[] if the parent has no enrolled children.
    Returns 404 if no parents row exists for this user.
    """
    user = current_user()
    db = get_db()
    try:
        parent_row = db.execute(
            "SELECT parent_id FROM parents WHERE user_id = ?",
            (user["user_id"],),
        ).fetchone()
        if not parent_row:
            return jsonify({"error": "Parent record not found."}), 404

        parent_id = parent_row["parent_id"]

        child_rows = db.execute(
            """SELECT
                   s.student_id,
                   s.student_first_name,
                   s.student_last_name,
                   s.grade_level,
                   sc.school_name
               FROM students s
               JOIN schools sc ON sc.school_id = s.school_id
               WHERE (s.parent_primary_id = ? OR s.parent_secondary_id = ?)
                 AND s.active_status = 1
                 AND s.deleted_at IS NULL
               ORDER BY s.student_last_name ASC, s.student_first_name ASC""",
            (parent_id, parent_id),
        ).fetchall()

        if not child_rows:
            return jsonify({"ok": True, "children": []})

        # student_ids is always non-empty here — the guard above ensures child_rows is non-empty.
        student_ids = [r["student_id"] for r in child_rows]
        placeholders = ",".join("?" * len(student_ids))

        # Cap at 10 sessions per child × max children per parent (guard: 10 children × 10 sessions = 100 rows max).
        # Python-side trimming below enforces the per-student cap after the DB fetch.
        attendance_rows = db.execute(
            "SELECT ssa.student_id, s.session_date, s.session_type, ssa.attendance_status"
            " FROM student_session_attendance ssa"
            " JOIN sessions s ON s.session_id = ssa.session_id"
            " WHERE ssa.student_id IN (" + ",".join(["?"] * len(student_ids)) + ")"
            " AND s.deleted_at IS NULL"
            " ORDER BY ssa.student_id ASC, s.session_date DESC LIMIT 200",
            student_ids,
        ).fetchall()

        score_rows = db.execute(
            "SELECT asco.student_id, sd.domain_name, ROUND(AVG(asco.raw_level), 1) AS avg_raw_level"
            " FROM assessment_scores asco"
            " JOIN assessments a ON a.assessment_id = asco.assessment_id"
            " JOIN skills sk ON sk.skill_id = asco.skill_id"
            " JOIN skill_domains sd ON sd.domain_id = sk.domain_id"
            " WHERE asco.student_id IN (" + ",".join(["?"] * len(student_ids)) + ")"
            " AND a.deleted_at IS NULL"
            " GROUP BY asco.student_id, sd.domain_name"
            " ORDER BY asco.student_id ASC, sd.domain_name ASC",
            student_ids,
        ).fetchall()

        overall_rows = db.execute(
            "SELECT student_id, overall_ufit_score, readiness_band"
            " FROM student_overall_summary"
            " WHERE student_id IN (" + ",".join(["?"] * len(student_ids)) + ")",
            student_ids,
        ).fetchall()
        overall_by_student = {r["student_id"]: r for r in overall_rows}

        # keep first 10 sessions per student
        attendance_by_student = {}
        for row in attendance_rows:
            sid = row["student_id"]
            if sid not in attendance_by_student:
                attendance_by_student[sid] = []
            if len(attendance_by_student[sid]) < 10:
                attendance_by_student[sid].append({
                    "session_date": row["session_date"],
                    "session_type": row["session_type"],
                    "attendance_status": row["attendance_status"],
                })

        summary_by_student = {}
        for row in score_rows:
            sid = row["student_id"]
            if sid not in summary_by_student:
                summary_by_student[sid] = []
            summary_by_student[sid].append({
                "domain_name": row["domain_name"],
                "avg_raw_level": row["avg_raw_level"],
            })

        children = []
        for r in child_rows:
            sid = r["student_id"]
            overall = overall_by_student.get(sid)
            children.append({
                "student_id": sid,
                "first_name": r["student_first_name"],
                "last_name": r["student_last_name"],
                "grade_level": r["grade_level"],
                "school_name": r["school_name"],
                "overall_ufit_score": overall["overall_ufit_score"] if overall else None,
                "readiness_band": overall["readiness_band"] if overall else None,
                "recent_sessions": attendance_by_student.get(sid, []),
                "assessment_summary": summary_by_student.get(sid, []),
            })

        audit(db, user["user_id"], "READ", "students", None,
              new_values={"scope": "parent_children", "count": len(children)})
        db.commit()
        return jsonify({"ok": True, "children": children})
    except Exception:
        logging.exception("parent_student route error")
        return jsonify({"error": "Could not load student data — please try again or contact support."}), 500
    finally:
        db.close()
