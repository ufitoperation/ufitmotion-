"""
seed_demo.py — Creates demo data for the Ufit Motion LAUSD conference walkthrough.

Usage (local SQLite):
    UFIT_SECRET_KEY=local-dev-key python scripts/seed_demo.py

Usage (Supabase):
    DATABASE_URL=<supabase_url> UFIT_SECRET_KEY=<key> python scripts/seed_demo.py

All demo accounts use password: Demo1234!

Login credentials printed at the end.
"""

import datetime
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from werkzeug.security import generate_password_hash
from app import create_app
from app.database import get_db

DEMO_PASSWORD = "Demo1234!"
TODAY = datetime.date.today()
random.seed(42)  # reproducible


def d(days_ago: int) -> str:
    """Return ISO date string for N days ago (negative = future)."""
    return (TODAY - datetime.timedelta(days=days_ago)).isoformat()


def run():
    app = create_app()
    with app.app_context():
        db = get_db()

        # ------------------------------------------------------------------ #
        # Guard — prevent double-seeding                                       #
        # ------------------------------------------------------------------ #
        existing = db.execute(
            "SELECT organization_id FROM organizations WHERE organization_name = 'Ufit Demo Unified'"
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
               VALUES ('Ufit Demo Unified', 'school_district', 'active', ?)""",
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
                       'Dr. Patricia Moore', 'principal.lincoln@ufit.demo', 'K-5', 480,
                       1, ?, ?)""",
            (org_id, d(180), now),
        ).lastrowid

        jefferson_id = db.execute(
            """INSERT INTO schools (organization_id, school_name, school_type, city, state, zip_code,
                                    principal_name, principal_email, grade_levels_served, enrollment,
                                    active_status, start_date_with_ufit, created_at)
               VALUES (?, 'Jefferson Elementary', 'elementary', 'Inglewood', 'CA', '90301',
                       'Mr. David Chen', 'principal.jefferson@ufit.demo', 'K-5', 390,
                       1, ?, ?)""",
            (org_id, d(180), now),
        ).lastrowid

        roosevelt_id = db.execute(
            """INSERT INTO schools (organization_id, school_name, school_type, city, state, zip_code,
                                    principal_name, principal_email, grade_levels_served, enrollment,
                                    active_status, start_date_with_ufit, created_at)
               VALUES (?, 'Roosevelt Middle School', 'middle', 'Compton', 'CA', '90220',
                       'Dr. Angela Washington', 'principal.roosevelt@ufit.demo', '6-8', 520,
                       1, ?, ?)""",
            (org_id, d(180), now),
        ).lastrowid

        # ------------------------------------------------------------------ #
        # 3. Helper functions                                                  #
        # ------------------------------------------------------------------ #
        def insert_user(first, last, email, role):
            return db.execute(
                """INSERT INTO users (first_name, last_name, email, password_hash, role,
                                      active_status, email_verified, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, 1, ?)""",
                (first, last, email, pw, role, now),
            ).lastrowid

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

        # ------------------------------------------------------------------ #
        # 4. CEO + Admin (org-level, no school assignment)                     #
        # ------------------------------------------------------------------ #
        insert_user("Marcus", "James", "marcus@ufit.demo", "ceo")
        insert_user("Sarah", "Nguyen", "sarah@ufit.demo", "admin")

        # ------------------------------------------------------------------ #
        # 5. Programs (needed before staff assignments)                        #
        # ------------------------------------------------------------------ #
        lincoln_prog_id = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                      start_date, program_status, frequency, created_at)
               VALUES (?, 'Lincoln PE Program', 'pe_support', 'K-5', ?, 'active', 'daily', ?)""",
            (lincoln_id, d(180), now),
        ).lastrowid

        jefferson_prog_id = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                      start_date, program_status, frequency, created_at)
               VALUES (?, 'Jefferson PE Program', 'pe_support', 'K-5', ?, 'active', 'daily', ?)""",
            (jefferson_id, d(180), now),
        ).lastrowid

        roosevelt_prog_id = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                      start_date, program_status, frequency, created_at)
               VALUES (?, 'Roosevelt PE Program', 'pe_support', '6-8', ?, 'active', 'daily', ?)""",
            (roosevelt_id, d(180), now),
        ).lastrowid

        # ------------------------------------------------------------------ #
        # 6. Coaches                                                           #
        # ------------------------------------------------------------------ #
        # Lincoln coaches
        lincoln_head_uid = insert_user("Derek", "Thompson", "coach.lincoln@ufit.demo", "head_coach")
        lincoln_head_sid = insert_staff(lincoln_head_uid, "Head Coach")
        assign_staff(lincoln_head_sid, lincoln_id, lincoln_prog_id, "head_coach")

        lincoln_asst_uid = insert_user("Aaliyah", "Brooks", "asst.lincoln@ufit.demo", "assistant_coach")
        lincoln_asst_sid = insert_staff(lincoln_asst_uid, "Assistant Coach")
        assign_staff(lincoln_asst_sid, lincoln_id, lincoln_prog_id, "assistant_coach")

        # Jefferson coaches
        jefferson_head_uid = insert_user("Kevin", "Okafor", "coach.jefferson@ufit.demo", "head_coach")
        jefferson_head_sid = insert_staff(jefferson_head_uid, "Head Coach")
        assign_staff(jefferson_head_sid, jefferson_id, jefferson_prog_id, "head_coach")

        jefferson_asst_uid = insert_user("Priya", "Patel", "asst.jefferson@ufit.demo", "assistant_coach")
        jefferson_asst_sid = insert_staff(jefferson_asst_uid, "Assistant Coach")
        assign_staff(jefferson_asst_sid, jefferson_id, jefferson_prog_id, "assistant_coach")

        # Roosevelt coaches
        roosevelt_head_uid = insert_user("Marcus", "Rivera", "coach.roosevelt@ufit.demo", "head_coach")
        roosevelt_head_sid = insert_staff(roosevelt_head_uid, "Head Coach")
        assign_staff(roosevelt_head_sid, roosevelt_id, roosevelt_prog_id, "head_coach")

        roosevelt_asst_uid = insert_user("Tanisha", "Williams", "asst.roosevelt@ufit.demo", "assistant_coach")
        roosevelt_asst_sid = insert_staff(roosevelt_asst_uid, "Assistant Coach")
        assign_staff(roosevelt_asst_sid, roosevelt_id, roosevelt_prog_id, "assistant_coach")

        # ------------------------------------------------------------------ #
        # 7. Principals (staff_profile + site_coordinator assignment)          #
        # ------------------------------------------------------------------ #
        lincoln_prin_uid = insert_user("Patricia", "Moore", "principal.lincoln@ufit.demo", "principal")
        lincoln_prin_sid = insert_staff(lincoln_prin_uid, "Principal")
        assign_staff(lincoln_prin_sid, lincoln_id, lincoln_prog_id, "site_coordinator")

        jefferson_prin_uid = insert_user("David", "Chen", "principal.jefferson@ufit.demo", "principal")
        jefferson_prin_sid = insert_staff(jefferson_prin_uid, "Principal")
        assign_staff(jefferson_prin_sid, jefferson_id, jefferson_prog_id, "site_coordinator")

        roosevelt_prin_uid = insert_user("Angela", "Washington", "principal.roosevelt@ufit.demo", "principal")
        roosevelt_prin_sid = insert_staff(roosevelt_prin_uid, "Principal")
        assign_staff(roosevelt_prin_sid, roosevelt_id, roosevelt_prog_id, "site_coordinator")

        # ------------------------------------------------------------------ #
        # 8. Students                                                          #
        # ------------------------------------------------------------------ #
        lincoln_student_data = [
            ("Emma", "Johnson", "K"), ("Liam", "Davis", "K"), ("Sofia", "Martinez", "K"),
            ("Noah", "Wilson", "K"), ("Ava", "Brown", "K"),
            ("Carlos", "Lopez", "1"), ("Maya", "Anderson", "1"), ("Ethan", "Taylor", "1"),
            ("Zoe", "Thomas", "1"), ("Mason", "Jackson", "1"),
            ("Isabella", "White", "2"), ("Aiden", "Harris", "2"), ("Luna", "Martin", "2"),
            ("Lucas", "Garcia", "2"), ("Mia", "Rodriguez", "2"),
            ("Oliver", "Lewis", "3"), ("Emma", "Lee", "3"), ("James", "Walker", "3"),
            ("Sophia", "Hall", "3"), ("Benjamin", "Allen", "3"),
            ("Aria", "Young", "4"), ("Logan", "Hernandez", "4"), ("Chloe", "King", "4"),
            ("Elijah", "Wright", "4"), ("Riley", "Scott", "4"),
            ("Harper", "Torres", "5"), ("Sebastian", "Nguyen", "5"), ("Layla", "Hill", "5"),
            ("Grayson", "Flores", "5"), ("Nora", "Green", "5"),
        ]

        jefferson_student_data = [
            ("Andre", "Williams", "K"), ("Jasmine", "Brown", "K"), ("Marcus", "Jones", "K"),
            ("Destiny", "Davis", "K"), ("Jaylen", "Miller", "K"),
            ("Aaliyah", "Wilson", "1"), ("DeShawn", "Moore", "1"), ("Keisha", "Taylor", "1"),
            ("Darius", "Anderson", "1"), ("Brianna", "Thomas", "1"),
            ("Jaylen", "Jackson", "2"), ("Amara", "White", "2"), ("Isaiah", "Harris", "2"),
            ("Naomi", "Martin", "2"), ("Elijah", "Thompson", "2"),
            ("Zara", "Garcia", "3"), ("Jordan", "Martinez", "3"), ("Imani", "Robinson", "3"),
            ("Malik", "Clark", "3"), ("Anaya", "Rodriguez", "3"),
            ("Caleb", "Lewis", "4"), ("Faith", "Lee", "4"), ("Micah", "Walker", "4"),
            ("Nia", "Hall", "4"), ("Donovan", "Allen", "4"),
            ("Simone", "Young", "5"), ("Trevon", "King", "5"), ("Lyric", "Wright", "5"),
        ]

        roosevelt_student_data = [
            ("Diego", "Ramirez", "6"), ("Aaliyah", "Johnson", "6"), ("Kevin", "Chen", "6"),
            ("Priya", "Sharma", "6"), ("Marcus", "Brown", "6"), ("Destiny", "Williams", "6"),
            ("Jordan", "Davis", "6"), ("Camila", "Martinez", "6"), ("Jaylen", "Thompson", "6"),
            ("Sofia", "Garcia", "7"), ("Ethan", "Jones", "7"), ("Amara", "Wilson", "7"),
            ("Isaiah", "Moore", "7"), ("Maya", "Taylor", "7"), ("Darius", "Anderson", "7"),
            ("Naomi", "Thomas", "7"), ("Elijah", "Jackson", "7"),
            ("Zara", "White", "8"), ("Caleb", "Harris", "8"), ("Faith", "Martin", "8"),
            ("Micah", "Robinson", "8"), ("Nia", "Clark", "8"), ("Donovan", "Rodriguez", "8"),
            ("Simone", "Lewis", "8"), ("Trevon", "Lee", "8"),
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

        lincoln_student_ids = insert_students(lincoln_id, lincoln_prog_id, lincoln_student_data)
        jefferson_student_ids = insert_students(jefferson_id, jefferson_prog_id, jefferson_student_data)
        roosevelt_student_ids = insert_students(roosevelt_id, roosevelt_prog_id, roosevelt_student_data)

        # ------------------------------------------------------------------ #
        # 9. Sessions — Mon-Fri for 60 days, skip weekends + ~4 skip days     #
        # ------------------------------------------------------------------ #
        lincoln_activities = [
            "Locomotor Skills — Galloping & Skipping",
            "Ball Handling — Dribbling Foundations",
            "Cooperative Games & Teamwork",
            "Balance & Body Control",
            "Throwing & Catching",
            "Tag Games & Cardio Fitness",
            "Locomotor Circuit — Running & Hopping",
            "Underhand Throwing Skills",
        ]
        jefferson_activities = [
            "Jumping & Landing Skills",
            "Object Control — Kicking",
            "Partner Passing Games",
            "Fitness Stations Circuit",
            "Throwing Accuracy Drills",
            "Locomotor Combos — Skip, Slide, Gallop",
            "Catching & Tracking",
            "Cooperative Relay Races",
        ]
        roosevelt_activities = [
            "Basketball — Passing & Dribbling",
            "Soccer — Shooting & Defense",
            "Fitness Circuit & Conditioning",
            "Volleyball — Setting & Bumping",
            "Flag Football — Routes & Defense",
            "Track & Field — Sprint Technique",
            "Sport Decision-Making Drills",
            "Game Application — Multi-Sport",
        ]

        def build_sessions(school_id, prog_id, head_sid, activities, n_students, skip_count=4):
            """Generate ~60 days of Mon-Fri sessions, skipping ~skip_count random days."""
            session_ids = []
            skip_days = set(random.sample(range(1, 61), skip_count))
            act_cycle = 0
            for days_ago in range(60, 0, -1):
                date = TODAY - datetime.timedelta(days=days_ago)
                if date.weekday() >= 5:  # skip Saturday(5) and Sunday(6)
                    continue
                if days_ago in skip_days:
                    continue
                present = random.randint(
                    int(n_students * 0.80), int(n_students * 0.90)
                )
                activity = activities[act_cycle % len(activities)]
                act_cycle += 1
                sess_id = db.execute(
                    """INSERT INTO sessions (school_id, program_id, session_date, start_time, end_time,
                                             session_type, planned_activity, actual_activity,
                                             session_status, total_students_present, created_at)
                       VALUES (?, ?, ?, '08:30', '09:15', 'regular', ?, ?, 'completed', ?, ?)""",
                    (school_id, prog_id, date.isoformat(), activity, activity, present, now),
                ).lastrowid
                db.execute(
                    "INSERT INTO session_staff (session_id, staff_id, role) VALUES (?, ?, 'lead')",
                    (sess_id, head_sid),
                )
                session_ids.append((sess_id, days_ago))
            return session_ids

        lincoln_sessions = build_sessions(
            lincoln_id, lincoln_prog_id, lincoln_head_sid,
            lincoln_activities, len(lincoln_student_ids)
        )
        jefferson_sessions = build_sessions(
            jefferson_id, jefferson_prog_id, jefferson_head_sid,
            jefferson_activities, len(jefferson_student_ids)
        )
        roosevelt_sessions = build_sessions(
            roosevelt_id, roosevelt_prog_id, roosevelt_head_sid,
            roosevelt_activities, len(roosevelt_student_ids)
        )

        # ------------------------------------------------------------------ #
        # 10. Student session attendance                                       #
        # ------------------------------------------------------------------ #
        def insert_attendance(session_id_list, student_ids):
            for sess_id, _days in session_id_list:
                for stu_id in student_ids:
                    db.execute(
                        """INSERT INTO student_session_attendance
                               (session_id, student_id, attendance_status, created_at)
                           VALUES (?, ?, 'present', ?)""",
                        (sess_id, stu_id, now),
                    )

        insert_attendance(lincoln_sessions, lincoln_student_ids)
        insert_attendance(jefferson_sessions, jefferson_student_ids)
        insert_attendance(roosevelt_sessions, roosevelt_student_ids)

        # ------------------------------------------------------------------ #
        # 11. EOD Reports — one per session for head coach (~90% on-time)     #
        # ------------------------------------------------------------------ #
        eod_engagements = [
            "Students were highly engaged — 90% active participation throughout.",
            "Excellent focus today. New skill drills met with enthusiasm.",
            "Solid participation. A few students needed redirection but returned quickly.",
            "Great energy. Students demonstrated strong retention from last session.",
            "High engagement on cooperative games. SEL integration went well.",
            "Students responded well to movement stations. Low incident rate.",
            "Good session overall. 2 verbal redirects issued; no escalation needed.",
        ]

        def insert_eod_reports(session_id_list, school_id, prog_id, staff_id, on_time_rate=0.90):
            for idx, (sess_id, days_ago) in enumerate(session_id_list):
                on_time = 1 if random.random() < on_time_rate else 0
                db.execute(
                    """INSERT INTO eod_reports (school_id, staff_id, program_id, session_id,
                                                 report_date, activities_completed,
                                                 student_engagement_summary,
                                                 behavior_summary,
                                                 submitted_on_time,
                                                 coaches_clocked_in, coaches_in_uniform,
                                                 coaches_setup_ready, equipment_accounted,
                                                 transitions_orderly, yard_supervised,
                                                 curriculum_followed,
                                                 injury_incident_flag, followup_needed,
                                                 principal_communication_needed, created_at)
                       VALUES (?, ?, ?, ?, ?, 'Completed full lesson plan per curriculum guide.',
                               ?, 'No major behavior issues. Two verbal redirects at most.',
                               ?, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, ?)""",
                    (
                        school_id, staff_id, prog_id, sess_id,
                        d(days_ago),
                        eod_engagements[idx % len(eod_engagements)],
                        on_time,
                        now,
                    ),
                )

        insert_eod_reports(lincoln_sessions, lincoln_id, lincoln_prog_id, lincoln_head_sid)
        insert_eod_reports(jefferson_sessions, jefferson_id, jefferson_prog_id, jefferson_head_sid)
        insert_eod_reports(roosevelt_sessions, roosevelt_id, roosevelt_prog_id, roosevelt_head_sid)

        # ------------------------------------------------------------------ #
        # 12. Assessment Windows — Fall 2025 (closed) + Spring 2026 (closed) #
        # ------------------------------------------------------------------ #
        def make_windows(school_id, prog_id):
            fall_id = db.execute(
                """INSERT INTO assessment_windows
                   (school_id, program_id, window_name, start_date, end_date, status,
                    assessment_focus, created_at)
                   VALUES (?, ?, 'Fall 2025 Assessment', ?, ?, 'closed',
                           'Baseline locomotor and skill evaluation', ?)""",
                (school_id, prog_id, d(120), d(90), now),
            ).lastrowid
            spring_id = db.execute(
                """INSERT INTO assessment_windows
                   (school_id, program_id, window_name, start_date, end_date, status,
                    assessment_focus, created_at)
                   VALUES (?, ?, 'Spring 2026 Assessment', ?, ?, 'closed',
                           'Growth check — compare against Fall baseline', ?)""",
                (school_id, prog_id, d(30), d(-7), now),
            ).lastrowid
            return fall_id, spring_id

        lincoln_fall_wid, lincoln_spring_wid = make_windows(lincoln_id, lincoln_prog_id)
        jefferson_fall_wid, jefferson_spring_wid = make_windows(jefferson_id, jefferson_prog_id)
        roosevelt_fall_wid, roosevelt_spring_wid = make_windows(roosevelt_id, roosevelt_prog_id)

        # ------------------------------------------------------------------ #
        # 13. Assessments                                                      #
        # ------------------------------------------------------------------ #
        all_skills = db.execute(
            "SELECT skill_id, grade_band FROM skills WHERE active_status = 1"
        ).fetchall()

        k2_skills = [s for s in all_skills if s["grade_band"] in ("K-2", "K-5")]
        k5_35_skills = [s for s in all_skills if s["grade_band"] in ("3-5", "K-5")]
        ms_skills = [s for s in all_skills if s["grade_band"] in ("6-8",)]
        if not ms_skills:
            ms_skills = all_skills[:6]

        def grade_skills(grade):
            """Return skill list appropriate for a student's grade."""
            if grade in ("K", "1", "2"):
                return k2_skills if k2_skills else all_skills
            elif grade in ("3", "4", "5"):
                return k5_35_skills if k5_35_skills else all_skills
            else:
                return ms_skills if ms_skills else all_skills

        def insert_assessment(student_id, school_id, prog_id, staff_id, days_ago,
                               skill_list, scores, window_id=None):
            a_id = db.execute(
                """INSERT INTO assessments (student_id, school_id, program_id, assessed_by_staff_id,
                                            assessment_date, assessment_method, window_id,
                                            overall_assessment_notes, created_at)
                   VALUES (?, ?, ?, ?, ?, 'observational', ?,
                           'Standard observational assessment', ?)""",
                (student_id, school_id, prog_id, staff_id, d(days_ago), window_id, now),
            ).lastrowid
            for skill, score in zip(skill_list, scores):
                db.execute(
                    """INSERT INTO assessment_scores
                           (assessment_id, student_id, skill_id, raw_level, normalized_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT DO NOTHING""",
                    (a_id, student_id, skill["skill_id"], score, score * 20, now),
                )
            return a_id

        def assess_school(student_ids, student_data, school_id, prog_id, staff_id,
                          fall_wid, spring_wid, fall_days_ago=100, spring_days_ago=14):
            """Assess every student in both windows. Spring = Fall + growth."""
            assessed = []
            for stu_id, (_, _, grade) in zip(student_ids, student_data):
                skills = grade_skills(grade)
                if not skills:
                    continue
                # Use up to 6 skills per student
                skill_subset = skills[:6]
                fall_scores = [random.randint(1, 4) for _ in skill_subset]
                spring_scores = [min(5, s + random.randint(0, 1)) for s in fall_scores]
                insert_assessment(
                    stu_id, school_id, prog_id, staff_id,
                    fall_days_ago, skill_subset, fall_scores, fall_wid
                )
                insert_assessment(
                    stu_id, school_id, prog_id, staff_id,
                    spring_days_ago, skill_subset, spring_scores, spring_wid
                )
                assessed.append(stu_id)
            return assessed

        lincoln_assessed = assess_school(
            lincoln_student_ids, lincoln_student_data,
            lincoln_id, lincoln_prog_id, lincoln_head_sid,
            lincoln_fall_wid, lincoln_spring_wid
        )
        jefferson_assessed = assess_school(
            jefferson_student_ids, jefferson_student_data,
            jefferson_id, jefferson_prog_id, jefferson_head_sid,
            jefferson_fall_wid, jefferson_spring_wid
        )
        roosevelt_assessed = assess_school(
            roosevelt_student_ids, roosevelt_student_data,
            roosevelt_id, roosevelt_prog_id, roosevelt_head_sid,
            roosevelt_fall_wid, roosevelt_spring_wid
        )

        # ------------------------------------------------------------------ #
        # 14. Recalculate student summaries                                    #
        # ------------------------------------------------------------------ #
        from app.routes._scoring import recalculate_student_summaries

        for stu_id in lincoln_assessed:
            recalculate_student_summaries(db, stu_id, lincoln_id)
        for stu_id in jefferson_assessed:
            recalculate_student_summaries(db, stu_id, jefferson_id)
        for stu_id in roosevelt_assessed:
            recalculate_student_summaries(db, stu_id, roosevelt_id)

        # ------------------------------------------------------------------ #
        # 15. Coach performance snapshots                                      #
        # Maps the requested composite/attendance/eod scores onto the actual  #
        # schema columns: overall_score, eod_ontime_rate, session_log_rate.   #
        # ------------------------------------------------------------------ #
        period_start = d(30)   # 2026-04-01 approx
        period_end = d(1)      # 2026-04-30 approx

        coach_snapshot_data = [
            # (staff_id, school_id, overall, eod_ontime, session_log, compliance, outcomes, obs, band)
            (lincoln_head_sid,    lincoln_id,    87.0, 92.0, 85.0, 88.0, 86.0, 87.0, "proficient"),
            (lincoln_asst_sid,    lincoln_id,    74.0, 78.0, 70.0, 73.0, 74.0, 75.0, "developing"),
            (jefferson_head_sid,  jefferson_id,  91.0, 95.0, 89.0, 92.0, 90.0, 91.0, "exemplary"),
            (jefferson_asst_sid,  jefferson_id,  62.0, 65.0, 58.0, 60.0, 63.0, 63.0, "needs_improvement"),
            (roosevelt_head_sid,  roosevelt_id,  78.0, 82.0, 74.0, 78.0, 78.0, 78.0, "proficient"),
            (roosevelt_asst_sid,  roosevelt_id,  55.0, 60.0, 50.0, 54.0, 55.0, 56.0, "needs_improvement"),
        ]

        for (staff_id, school_id, overall, eod_rate, sess_rate,
             compliance, outcomes, observations, band) in coach_snapshot_data:
            db.execute(
                """INSERT INTO coach_performance_snapshots
                       (staff_id, school_id, period_start, period_end,
                        overall_score, compliance_score, outcomes_score, observations_score,
                        performance_band, eod_ontime_rate, session_log_rate, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, school_id, period_start, period_end,
                 overall, compliance, outcomes, observations,
                 band, eod_rate, sess_rate, now),
            )

        # ------------------------------------------------------------------ #
        # 16. Principal satisfaction surveys                                   #
        # ------------------------------------------------------------------ #
        principal_surveys = [
            (lincoln_id, lincoln_prin_uid, "Dr. Patricia Moore", "Principal", "Lincoln Elementary",
             "principal.lincoln@ufit.demo", 5, 5, 5, 5, 5,
             "Strong program with excellent student engagement.",
             "Students show measurable growth each assessment window."),
            (jefferson_id, jefferson_prin_uid, "Mr. David Chen", "Principal", "Jefferson Elementary",
             "principal.jefferson@ufit.demo", 4, 4, 4, 5, 4,
             "Would appreciate more parent communication materials.",
             "PE program has had positive impact on student behavior."),
            (roosevelt_id, roosevelt_prin_uid, "Dr. Angela Washington", "Principal", "Roosevelt Middle School",
             "principal.roosevelt@ufit.demo", 4, 5, 4, 4, 4,
             "Consider adding after-school sports programming.",
             "Coaches are professional and students respect them greatly."),
        ]

        for (school_id, user_id, name, position, school_name, email,
             sat, yard, coach_perf, comm, wellbeing, suggestions, contributions) in principal_surveys:
            db.execute(
                """INSERT INTO principal_satisfaction_surveys
                       (school_id, submitted_by_user_id, respondent_name, respondent_position,
                        school_name, email, satisfaction_rating, yard_safety_rating,
                        coach_performance_rating, communication_rating,
                        wellbeing_effectiveness_rating, improvements_suggestions,
                        contributions_description, submitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (school_id, user_id, name, position, school_name, email,
                 sat, yard, coach_perf, comm, wellbeing, suggestions, contributions, now),
            )

        # ------------------------------------------------------------------ #
        # 17. Incident reports — 2-3 per school                               #
        # ------------------------------------------------------------------ #
        # Lincoln
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'low',
                       'Student fell during relay race and scraped knee. No serious injury.',
                       'Applied first aid. Parents notified. Student returned to activity.',
                       1, 1, 0, 'resolved', ?)""",
            (lincoln_id, d(18), lincoln_head_sid, lincoln_student_ids[0], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'behavior', 'low',
                       'Student refused to participate and became verbally disruptive during cooperative game.',
                       'Verbal redirect given. Student rejoined group after 5 minutes.',
                       0, 0, 0, 'resolved', ?)""",
            (lincoln_id, d(9), lincoln_asst_sid, lincoln_student_ids[4], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'medium',
                       'Student twisted ankle during tag game. Ice pack applied. Parent called.',
                       'Stopped activity. Applied ice. Parent picked up student early.',
                       1, 1, 0, 'resolved', ?)""",
            (lincoln_id, d(3), lincoln_head_sid, lincoln_student_ids[10], now),
        )

        # Jefferson
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'behavior', 'medium',
                       'Student threw ball at another student intentionally. No injury occurred.',
                       'Student removed from activity, verbal counseling. Referred to vice principal.',
                       1, 1, 1, 'resolved', ?)""",
            (jefferson_id, d(22), jefferson_head_sid, jefferson_student_ids[2], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'low',
                       'Student bumped heads with peer during catching drill. Brief dizziness reported.',
                       'Both students seated and monitored for 15 min. School nurse evaluated.',
                       1, 1, 0, 'resolved', ?)""",
            (jefferson_id, d(7), jefferson_asst_sid, jefferson_student_ids[8], now),
        )

        # Roosevelt
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'injury', 'high',
                       'Student collision during soccer drill. Student complained of wrist pain. Sent to nurse.',
                       'Stopped drill. Escorted to nurse. Parents called. Wrist splinted. Incident documented.',
                       1, 1, 1, 'open', ?)""",
            (roosevelt_id, d(5), roosevelt_head_sid, roosevelt_student_ids[0], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'behavior', 'low',
                       'Student used inappropriate language toward teammate. First offense.',
                       'Verbal warning issued. Student apologized and class continued.',
                       0, 0, 0, 'resolved', ?)""",
            (roosevelt_id, d(12), roosevelt_asst_sid, roosevelt_student_ids[5], now),
        )
        db.execute(
            """INSERT INTO incident_reports
               (school_id, report_date, reported_by_staff_id, student_id,
                incident_type, severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, ?, ?, 'other', 'low',
                       'Student left session without permission and was found near school gate.',
                       'Student escorted back. Office notified. Parents informed.',
                       1, 1, 0, 'resolved', ?)""",
            (roosevelt_id, d(30), roosevelt_head_sid, roosevelt_student_ids[14], now),
        )

        # ------------------------------------------------------------------ #
        # 18. Commit                                                           #
        # ------------------------------------------------------------------ #
        db.commit()

        # ------------------------------------------------------------------ #
        # Print credentials table                                              #
        # ------------------------------------------------------------------ #
        lincoln_count = len(lincoln_sessions)
        jefferson_count = len(jefferson_sessions)
        roosevelt_count = len(roosevelt_sessions)
        total_students = (
            len(lincoln_student_ids) + len(jefferson_student_ids) + len(roosevelt_student_ids)
        )
        total_assessed = len(lincoln_assessed) + len(jefferson_assessed) + len(roosevelt_assessed)
        total_sessions = lincoln_count + jefferson_count + roosevelt_count

        print("\n✓ Demo data seeded successfully.\n")
        print("=" * 68)
        print("  LOGIN CREDENTIALS  —  password for all: Demo1234!")
        print("=" * 68)
        print(f"  {'Role':<22} {'Email':<38} {'School'}")
        print("-" * 68)
        print(f"  {'CEO':<22} {'marcus@ufit.demo':<38} (all orgs)")
        print(f"  {'Admin':<22} {'sarah@ufit.demo':<38} (all orgs)")
        print(f"  {'Head Coach':<22} {'coach.lincoln@ufit.demo':<38} Lincoln Elementary")
        print(f"  {'Asst Coach':<22} {'asst.lincoln@ufit.demo':<38} Lincoln Elementary")
        print(f"  {'Head Coach':<22} {'coach.jefferson@ufit.demo':<38} Jefferson Elementary")
        print(f"  {'Asst Coach':<22} {'asst.jefferson@ufit.demo':<38} Jefferson Elementary")
        print(f"  {'Head Coach':<22} {'coach.roosevelt@ufit.demo':<38} Roosevelt Middle School")
        print(f"  {'Asst Coach':<22} {'asst.roosevelt@ufit.demo':<38} Roosevelt Middle School")
        print(f"  {'Principal':<22} {'principal.lincoln@ufit.demo':<38} Lincoln Elementary")
        print(f"  {'Principal':<22} {'principal.jefferson@ufit.demo':<38} Jefferson Elementary")
        print(f"  {'Principal':<22} {'principal.roosevelt@ufit.demo':<38} Roosevelt Middle School")
        print("=" * 68)
        print(f"\n  3 schools · 11 staff accounts · {total_students} students")
        print(f"  {total_sessions} sessions  ({lincoln_count} Lincoln / {jefferson_count} Jefferson / {roosevelt_count} Roosevelt)")
        print(f"  {total_assessed * 2} assessments ({total_assessed} students × 2 windows)")
        print(f"  6 coach performance snapshots · 3 principal surveys · 8 incidents\n")


if __name__ == "__main__":
    run()
