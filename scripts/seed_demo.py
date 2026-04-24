"""
seed_demo.py — Creates demo data for the Ufit Motion Loom walkthrough.

Usage (local SQLite):
    UFIT_SECRET_KEY=local-dev-key python scripts/seed_demo.py

Usage (Supabase):
    DATABASE_URL=<supabase_url> UFIT_SECRET_KEY=<key> python scripts/seed_demo.py

All demo accounts use password: Demo1234!

Login credentials printed at the end.
"""

import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from app import create_app
from app.database import get_db

DEMO_PASSWORD = "Demo1234!"
TODAY = datetime.date.today()


def d(days_ago: int) -> str:
    return (TODAY - datetime.timedelta(days=days_ago)).isoformat()


def run():
    app = create_app()
    with app.app_context():
        db = get_db()

        # ------------------------------------------------------------------ #
        # Guard — prevent double-seeding                                       #
        # ------------------------------------------------------------------ #
        existing = db.execute(
            "SELECT organization_id FROM organizations WHERE organization_name = 'Ufit Demo District'"
        ).fetchone()
        if existing:
            print("Demo data already exists. Run teardown_demo.py first if you want to re-seed.")
            return

        pw = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")
        now = datetime.datetime.utcnow().isoformat()

        # ------------------------------------------------------------------ #
        # 1. Organization                                                      #
        # ------------------------------------------------------------------ #
        org_id = db.execute(
            """INSERT INTO organizations (organization_name, organization_type, contract_status, created_at)
               VALUES ('Ufit Demo District', 'school_district', 'active', ?)""",
            (now,),
        ).lastrowid

        # ------------------------------------------------------------------ #
        # 2. Schools                                                           #
        # ------------------------------------------------------------------ #
        lincoln_id = db.execute(
            """INSERT INTO schools (organization_id, school_name, school_type, city, state, zip_code,
                                    principal_name, principal_email, grade_levels_served, enrollment,
                                    active_status, start_date_with_ufit, created_at)
               VALUES (?, 'Lincoln Elementary', 'elementary', 'Los Angeles', 'CA', '90001',
                       'Dr. Patricia Moore', 'p.moore@lincoln.demo', 'K-5', 420,
                       1, ?, ?)""",
            (org_id, d(180), now),
        ).lastrowid

        washington_id = db.execute(
            """INSERT INTO schools (organization_id, school_name, school_type, city, state, zip_code,
                                    principal_name, principal_email, grade_levels_served, enrollment,
                                    active_status, start_date_with_ufit, created_at)
               VALUES (?, 'Washington Middle School', 'middle', 'Los Angeles', 'CA', '90002',
                       'Mr. David Chen', 'd.chen@washington.demo', '6-8', 380,
                       1, ?, ?)""",
            (org_id, d(120), now),
        ).lastrowid

        # ------------------------------------------------------------------ #
        # 3. Users + Staff Profiles                                            #
        # ------------------------------------------------------------------ #
        def insert_user(first, last, email, role):
            uid = db.execute(
                """INSERT INTO users (first_name, last_name, email, password_hash, role,
                                      active_status, email_verified, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, 1, ?)""",
                (first, last, email, pw, role, now),
            ).lastrowid
            return uid

        def insert_staff(user_id, title="Coach"):
            return db.execute(
                """INSERT INTO staff_profiles (user_id, position_title, employee_type, status, created_at)
                   VALUES (?, ?, 'full_time', 'active', ?)""",
                (user_id, title, now),
            ).lastrowid

        def assign_staff(staff_id, school_id, program_id, role):
            db.execute(
                """INSERT INTO staff_assignments (staff_id, school_id, program_id, assignment_role,
                                                   start_date, active_status, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (staff_id, school_id, program_id, role, d(180), now),
            )

        # CEO + Admin (no school assignment)
        ceo_id = insert_user("Marcus", "James", "marcus@ufit.demo", "ceo")
        admin_id = insert_user("Sarah", "Nguyen", "sarah@ufit.demo", "admin")

        # Programs (need before staff assignments that reference program_id)
        lincoln_prog_id = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                      start_date, program_status, frequency, created_at)
               VALUES (?, 'Lincoln PE Program', 'pe_support', 'K-5', ?, 'active', 'daily', ?)""",
            (lincoln_id, d(180), now),
        ).lastrowid

        washington_prog_id = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                      start_date, program_status, frequency, created_at)
               VALUES (?, 'Washington PE Program', 'pe_support', '6-8', ?, 'active', 'daily', ?)""",
            (washington_id, d(120), now),
        ).lastrowid

        # Coaches — Lincoln
        coach1_uid = insert_user("Derek", "Thompson", "coach.lincoln@ufit.demo", "head_coach")
        coach1_sid = insert_staff(coach1_uid, "Head Coach")
        assign_staff(coach1_sid, lincoln_id, lincoln_prog_id, "head_coach")

        coach2_uid = insert_user("Aaliyah", "Brooks", "asst.lincoln@ufit.demo", "assistant_coach")
        coach2_sid = insert_staff(coach2_uid, "Assistant Coach")
        assign_staff(coach2_sid, lincoln_id, lincoln_prog_id, "assistant_coach")

        # Coaches — Washington
        coach3_uid = insert_user("Marcus", "Rivera", "coach.washington@ufit.demo", "head_coach")
        coach3_sid = insert_staff(coach3_uid, "Head Coach")
        assign_staff(coach3_sid, washington_id, washington_prog_id, "head_coach")

        # Principal — Lincoln
        prin_uid = insert_user("Patricia", "Moore", "principal@ufit.demo", "principal")
        # Principal doesn't need staff_profile, but needs school association via linked field
        # We handle this through a direct school_id on the session — principals use school lookup
        # Store school association in a separate lightweight way by inserting a staff stub
        prin_staff_id = insert_staff(prin_uid, "Principal")
        assign_staff(prin_staff_id, lincoln_id, lincoln_prog_id, "site_coordinator")

        # ------------------------------------------------------------------ #
        # 4. Students                                                          #
        # ------------------------------------------------------------------ #
        lincoln_students = [
            ("Emma", "Johnson", "K"),
            ("Liam", "Davis", "1"),
            ("Sofia", "Martinez", "2"),
            ("Noah", "Wilson", "3"),
            ("Ava", "Brown", "2"),
        ]
        washington_students = [
            ("James", "Garcia", "6"),
            ("Isabella", "Lee", "7"),
            ("Oliver", "Thomas", "8"),
            ("Mia", "Jackson", "6"),
            ("Ethan", "White", "7"),
        ]

        def insert_students(school_id, prog_id, students):
            ids = []
            for first, last, grade in students:
                sid = db.execute(
                    """INSERT INTO students (school_id, student_first_name, student_last_name,
                                             grade_level, active_status, enrollment_start, created_at)
                       VALUES (?, ?, ?, ?, 1, ?, ?)""",
                    (school_id, first, last, grade, d(180), now),
                ).lastrowid
                db.execute(
                    """INSERT INTO student_program_enrollment (student_id, program_id, status, created_at)
                       VALUES (?, ?, 'active', ?)""",
                    (sid, prog_id, now),
                )
                ids.append(sid)
            return ids

        lincoln_student_ids = insert_students(lincoln_id, lincoln_prog_id, lincoln_students)
        washington_student_ids = insert_students(washington_id, washington_prog_id, washington_students)

        # ------------------------------------------------------------------ #
        # 5. Sessions                                                          #
        # ------------------------------------------------------------------ #
        def insert_session(school_id, prog_id, staff_id, days_ago, activity, present):
            sess_id = db.execute(
                """INSERT INTO sessions (school_id, program_id, session_date, start_time, end_time,
                                         session_type, planned_activity, actual_activity,
                                         session_status, total_students_present, created_at)
                   VALUES (?, ?, ?, '08:30', '09:15', 'regular', ?, ?, 'completed', ?, ?)""",
                (school_id, prog_id, d(days_ago), activity, activity, present, now),
            ).lastrowid
            db.execute(
                "INSERT INTO session_staff (session_id, staff_id, role) VALUES (?, ?, 'lead')",
                (sess_id, staff_id),
            )
            return sess_id

        lincoln_activities = [
            "Locomotor Skills — Galloping & Skipping",
            "Ball Handling — Dribbling",
            "Cooperative Games",
            "Balance & Body Control",
            "Throwing & Catching",
            "Tag Games & Cardio",
        ]
        washington_activities = [
            "Basketball — Passing & Dribbling",
            "Soccer — Shooting & Defense",
            "Fitness Circuit",
            "Volleyball — Setting & Bumping",
        ]

        lincoln_sessions = []
        for i, act in enumerate(lincoln_activities):
            sid = insert_session(lincoln_id, lincoln_prog_id, coach1_sid, i + 1, act, 18)
            lincoln_sessions.append(sid)

        washington_sessions = []
        for i, act in enumerate(washington_activities):
            sid = insert_session(washington_id, washington_prog_id, coach3_sid, i + 1, act, 22)
            washington_sessions.append(sid)

        # Attendance
        for sess_id in lincoln_sessions:
            for stu_id in lincoln_student_ids:
                db.execute(
                    """INSERT INTO student_session_attendance (session_id, student_id, attendance_status, created_at)
                       VALUES (?, ?, 'present', ?)""",
                    (sess_id, stu_id, now),
                )
        for sess_id in washington_sessions:
            for stu_id in washington_student_ids:
                db.execute(
                    """INSERT INTO student_session_attendance (session_id, student_id, attendance_status, created_at)
                       VALUES (?, ?, 'present', ?)""",
                    (sess_id, stu_id, now),
                )

        # ------------------------------------------------------------------ #
        # 6. EOD Reports                                                       #
        # ------------------------------------------------------------------ #
        def insert_eod(school_id, prog_id, staff_id, days_ago, on_time=1):
            db.execute(
                """INSERT INTO eod_reports (school_id, staff_id, program_id, report_date,
                                             activities_completed, student_engagement_summary,
                                             behavior_summary, submitted_on_time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (school_id, staff_id, prog_id, d(days_ago),
                 "Completed full lesson plan per curriculum guide.",
                 "Students were highly engaged — 90% participation rate.",
                 "No major behavior issues. Two verbal redirects.",
                 on_time, now),
            )

        insert_eod(lincoln_id, lincoln_prog_id, coach1_sid, 1, on_time=1)
        insert_eod(lincoln_id, lincoln_prog_id, coach1_sid, 2, on_time=1)
        insert_eod(lincoln_id, lincoln_prog_id, coach1_sid, 3, on_time=0)  # one late
        insert_eod(lincoln_id, lincoln_prog_id, coach1_sid, 4, on_time=1)
        insert_eod(washington_id, washington_prog_id, coach3_sid, 1, on_time=1)
        insert_eod(washington_id, washington_prog_id, coach3_sid, 2, on_time=1)
        insert_eod(washington_id, washington_prog_id, coach3_sid, 3, on_time=1)

        # ------------------------------------------------------------------ #
        # 7. Assessments + Scores                                             #
        # ------------------------------------------------------------------ #
        skills = db.execute(
            "SELECT skill_id, grade_band FROM skills WHERE active_status = 1 LIMIT 20"
        ).fetchall()

        k5_skills = [s for s in skills if s["grade_band"] in ("K-2", "3-5", "K-5")][:4]
        ms_skills = [s for s in skills if s["grade_band"] in ("6-8",)][:4]
        if not ms_skills:
            ms_skills = skills[:4]

        def insert_assessment(student_id, school_id, prog_id, staff_id, days_ago, skill_list, scores):
            a_id = db.execute(
                """INSERT INTO assessments (student_id, school_id, program_id, assessed_by_staff_id,
                                            assessment_date, assessment_method, created_at)
                   VALUES (?, ?, ?, ?, ?, 'observational', ?)""",
                (student_id, school_id, prog_id, staff_id, d(days_ago), now),
            ).lastrowid
            for skill, score in zip(skill_list, scores):
                db.execute(
                    """INSERT INTO assessment_scores (assessment_id, student_id, skill_id,
                                                       raw_level, normalized_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (a_id, student_id, skill["skill_id"], score, score * 20, now),
                )
            return a_id

        # Assess 3 Lincoln students
        assessed_lincoln = []
        if k5_skills:
            assessed_lincoln = [
                (lincoln_student_ids[0], [3, 4, 2, 3]),
                (lincoln_student_ids[1], [4, 4, 3, 5]),
                (lincoln_student_ids[2], [2, 3, 2, 3]),
            ]
            for stu_id, scores in assessed_lincoln:
                insert_assessment(stu_id, lincoln_id, lincoln_prog_id, coach1_sid, 7, k5_skills, scores)

        # Assess 2 Washington students
        assessed_washington = []
        if ms_skills:
            assessed_washington = [
                (washington_student_ids[0], [3, 3, 4, 3]),
                (washington_student_ids[1], [4, 5, 4, 4]),
            ]
            for stu_id, scores in assessed_washington:
                insert_assessment(stu_id, washington_id, washington_prog_id, coach3_sid, 5, ms_skills, scores)

        # ------------------------------------------------------------------ #
        # 8. Populate summary tables via scoring engine                       #
        # ------------------------------------------------------------------ #
        from app.routes._scoring import recalculate_student_summaries
        for stu_id, _ in assessed_lincoln:
            recalculate_student_summaries(db, stu_id, lincoln_id)
        for stu_id, _ in assessed_washington:
            recalculate_student_summaries(db, stu_id, washington_id)

        # ------------------------------------------------------------------ #
        # 9. Incident Reports                                                  #
        # ------------------------------------------------------------------ #
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'medium',
                       'Student fell during relay race and scraped knee. No serious injury.',
                       'Applied first aid. Parents notified. Student returned to activity.',
                       1, 1, 'resolved', ?)""",
            (lincoln_id, d(5), coach1_sid, lincoln_student_ids[0], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, status, created_at)
               VALUES (?, ?, ?, ?, 'behavior', 'low',
                       'Student refused to participate and became verbally disruptive.',
                       'Verbal redirect given. Student rejoined group after 5 minutes.',
                       0, 0, 'resolved', ?)""",
            (lincoln_id, d(3), coach2_sid, lincoln_student_ids[2], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'high',
                       'Student collision during soccer drill. Student complained of wrist pain. Sent to school nurse.',
                       'Stopped activity. Escorted student to nurse. Parents called. Incident documented.',
                       1, 1, 'open', ?)""",
            (washington_id, d(2), coach3_sid, washington_student_ids[0], now),
        )

        db.commit()

        print("\n✓ Demo data seeded successfully.\n")
        print("=" * 50)
        print("LOGIN CREDENTIALS (password for all: Demo1234!)")
        print("=" * 50)
        print(f"  CEO         marcus@ufit.demo")
        print(f"  Admin       sarah@ufit.demo")
        print(f"  Head Coach  coach.lincoln@ufit.demo   (Lincoln Elementary)")
        print(f"  Asst Coach  asst.lincoln@ufit.demo    (Lincoln Elementary)")
        print(f"  Head Coach  coach.washington@ufit.demo (Washington Middle)")
        print(f"  Principal   principal@ufit.demo       (Lincoln Elementary)")
        print("=" * 50)
        print(f"\n  2 schools · 4 coaches · 10 students")
        print(f"  10 sessions · 7 EODs · 5 assessments · 3 incidents\n")


if __name__ == "__main__":
    run()
