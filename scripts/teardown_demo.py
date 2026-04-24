"""
teardown_demo.py — Removes all demo data created by seed_demo.py.

Usage (local SQLite):
    UFIT_SECRET_KEY=local-dev-key python scripts/teardown_demo.py

Usage (Supabase):
    DATABASE_URL=<supabase_url> UFIT_SECRET_KEY=<key> python scripts/teardown_demo.py

Safe to run multiple times. Does nothing if demo data doesn't exist.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.database import get_db


def run():
    app = create_app()
    with app.app_context():
        db = get_db()

        org = db.execute(
            "SELECT organization_id FROM organizations WHERE organization_name = 'Ufit Demo District'"
        ).fetchone()

        # Always clean up stale demo users regardless of org state
        db.execute("DELETE FROM users WHERE email LIKE '%@ufit.demo'")

        if not org:
            db.commit()
            print("No demo data found — nothing to remove.")
            return

        org_id = org["organization_id"]

        # Collect school IDs before deleting
        school_ids = [
            r["school_id"]
            for r in db.execute(
                "SELECT school_id FROM schools WHERE organization_id = ?", (org_id,)
            ).fetchall()
        ]

        if school_ids:
            placeholders = ",".join("?" * len(school_ids))

            # Collect staff IDs via assignments for these schools
            staff_ids = [
                r["staff_id"]
                for r in db.execute(
                    f"SELECT DISTINCT staff_id FROM staff_assignments WHERE school_id IN ({placeholders})",
                    school_ids,
                ).fetchall()
            ]

            # Collect user IDs for those staff
            user_ids = []
            if staff_ids:
                sp = ",".join("?" * len(staff_ids))
                user_ids = [
                    r["user_id"]
                    for r in db.execute(
                        f"SELECT user_id FROM staff_profiles WHERE staff_id IN ({sp})",
                        staff_ids,
                    ).fetchall()
                ]

            # Delete in reverse dependency order
            # assessment_scores → assessments → sessions/eod_reports → students → programs
            # → staff_assignments → staff_profiles → users → schools → organization

            session_ids = [
                r["session_id"]
                for r in db.execute(
                    f"SELECT session_id FROM sessions WHERE school_id IN ({placeholders})",
                    school_ids,
                ).fetchall()
            ]
            if session_ids:
                sp2 = ",".join("?" * len(session_ids))
                db.execute(f"DELETE FROM student_session_attendance WHERE session_id IN ({sp2})", session_ids)
                db.execute(f"DELETE FROM session_staff WHERE session_id IN ({sp2})", session_ids)
                db.execute(f"DELETE FROM behavior_observations WHERE session_id IN ({sp2})", session_ids)

            assessment_ids = [
                r["assessment_id"]
                for r in db.execute(
                    f"SELECT assessment_id FROM assessments WHERE school_id IN ({placeholders})",
                    school_ids,
                ).fetchall()
            ]
            if assessment_ids:
                ap = ",".join("?" * len(assessment_ids))
                db.execute(f"DELETE FROM assessment_scores WHERE assessment_id IN ({ap})", assessment_ids)
                db.execute(f"DELETE FROM assessments WHERE assessment_id IN ({ap})", assessment_ids)

            student_ids = [
                r["student_id"]
                for r in db.execute(
                    f"SELECT student_id FROM students WHERE school_id IN ({placeholders})",
                    school_ids,
                ).fetchall()
            ]
            if student_ids:
                stp = ",".join("?" * len(student_ids))
                db.execute(f"DELETE FROM student_skill_summary WHERE student_id IN ({stp})", student_ids)
                db.execute(f"DELETE FROM student_domain_summary WHERE student_id IN ({stp})", student_ids)
                db.execute(f"DELETE FROM student_overall_summary WHERE student_id IN ({stp})", student_ids)
                db.execute(f"DELETE FROM student_program_enrollment WHERE student_id IN ({stp})", student_ids)
                db.execute(f"DELETE FROM behavior_observations WHERE student_id IN ({stp})", student_ids)
                db.execute(f"DELETE FROM students WHERE student_id IN ({stp})", student_ids)

            db.execute(f"DELETE FROM sessions WHERE school_id IN ({placeholders})", school_ids)
            db.execute(f"DELETE FROM eod_reports WHERE school_id IN ({placeholders})", school_ids)
            db.execute(f"DELETE FROM incident_reports WHERE school_id IN ({placeholders})", school_ids)
            db.execute(f"DELETE FROM assessment_windows WHERE school_id IN ({placeholders})", school_ids)
            db.execute(f"DELETE FROM programs WHERE school_id IN ({placeholders})", school_ids)
            db.execute(f"DELETE FROM staff_assignments WHERE school_id IN ({placeholders})", school_ids)

            if staff_ids:
                sp = ",".join("?" * len(staff_ids))
                db.execute(f"DELETE FROM staff_profiles WHERE staff_id IN ({sp})", staff_ids)

            if user_ids:
                up = ",".join("?" * len(user_ids))
                db.execute(f"DELETE FROM users WHERE user_id IN ({up})", user_ids)

            db.execute(f"DELETE FROM schools WHERE school_id IN ({placeholders})", school_ids)

        # Remove any remaining demo users (CEO/admin have no staff_profile)
        db.execute("DELETE FROM users WHERE email LIKE '%@ufit.demo'")

        # Clean up orphaned audit_log entries that reference deleted demo records
        if school_ids:
            sp_al = ",".join("?" * len(school_ids))
            db.execute(
                f"DELETE FROM audit_log WHERE table_name='schools' AND record_id IN ({sp_al})",
                school_ids,
            )
        if student_ids:
            stp_al = ",".join("?" * len(student_ids))
            db.execute(
                f"DELETE FROM audit_log WHERE table_name='students' AND record_id IN ({stp_al})",
                student_ids,
            )
        if user_ids:
            up_al = ",".join("?" * len(user_ids))
            db.execute(
                f"DELETE FROM audit_log WHERE table_name='users' AND record_id IN ({up_al})",
                user_ids,
            )

        db.execute("DELETE FROM organizations WHERE organization_id = ?", (org_id,))
        db.commit()

        print("\n✓ Demo data removed successfully.\n")


if __name__ == "__main__":
    run()
