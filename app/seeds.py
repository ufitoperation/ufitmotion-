"""
seeds.py — Database initialization and default data seeding for Ufit Motion.

init_db() is called once per app startup (from the app factory). It is safe
to re-run: the SQL migration uses IF NOT EXISTS throughout, and the default
admin check prevents duplicate seeding.

Execution order:
  1. Read migrations/001_initial_schema.sql and execute it (creates all tables).
  2. Check for any existing admin/ceo user — if none, create the default admin.
  3. Seed default app_settings rows if the table is empty.
  4. Print confirmation to stdout.
"""

import os
import sys
from typing import Optional

from werkzeug.security import generate_password_hash


def init_db() -> None:
    """Initialize the database schema and seed required default data."""
    from app.database import get_db, ensure_column

    db = get_db()
    try:
        _run_migration(db)
        # Patch existing databases missing columns added after initial migration.
        ensure_column(db, "schools", "region_id", "INTEGER DEFAULT NULL")
        ensure_column(db, "schools", "city", "TEXT DEFAULT NULL")
        ensure_column(db, "schools", "state", "TEXT DEFAULT NULL")
        ensure_column(db, "schools", "zip_code", "TEXT DEFAULT NULL")
        ensure_column(db, "staff_profiles", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "staff_profiles", "rolling_score", "NUMERIC(5,2) DEFAULT NULL")
        ensure_column(db, "staff_profiles", "rolling_band", "TEXT DEFAULT NULL")
        ensure_column(db, "staff_profiles", "score_last_updated", "TEXT DEFAULT NULL")
        ensure_column(db, "assessment_windows", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "sessions", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "sessions", "duration_minutes", "INTEGER DEFAULT NULL")
        ensure_column(db, "programs", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "coach_observations", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "behavior_observations", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        ensure_column(db, "staff_assignments", "deleted_at", "TIMESTAMPTZ DEFAULT NULL")
        # EOD extended fields (step2 migration)
        for col in [
            ("incident_report_filed", "INTEGER DEFAULT NULL"),
            ("school_concerns", "TEXT DEFAULT NULL"),
            ("school_concerns_resolved", "INTEGER DEFAULT NULL"),
            ("school_concerns_notes", "TEXT DEFAULT NULL"),
            ("schedule_changes", "TEXT DEFAULT NULL"),
            ("coaches_clocked_in", "INTEGER DEFAULT NULL"),
            ("late_arrivals", "TEXT DEFAULT NULL"),
            ("coaches_in_uniform", "INTEGER DEFAULT NULL"),
            ("verbal_warnings", "TEXT DEFAULT NULL"),
            ("hr_app_issues", "TEXT DEFAULT NULL"),
            ("coaches_setup_ready", "INTEGER DEFAULT NULL"),
            ("equipment_accounted", "INTEGER DEFAULT NULL"),
            ("transitions_orderly", "INTEGER DEFAULT NULL"),
            ("safety_hazards", "TEXT DEFAULT NULL"),
            ("yard_supervised", "INTEGER DEFAULT NULL"),
            ("curriculum_followed", "INTEGER DEFAULT NULL"),
            ("equipment_requests", "TEXT DEFAULT NULL"),
            ("principal_communication_notes", "TEXT DEFAULT NULL"),
            ("ufit_standards_notes", "TEXT DEFAULT NULL"),
        ]:
            ensure_column(db, "eod_reports", col[0], col[1])
        _seed_default_admin(db)
        _seed_demo_users(db)
        _seed_app_settings(db)
        print("Database initialized.", flush=True)
    except Exception as exc:
        print(f"[seeds] init_db error: {exc}", file=sys.stderr, flush=True)
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

def _run_migration(db) -> None:
    """Read and execute the correct schema migration for the current backend."""
    # Use SQLite-compatible schema for local dev, Postgres schema for production.
    is_sqlite = getattr(db, "backend", "postgres") == "sqlite"
    filename = "001_sqlite_dev.sql" if is_sqlite else "001_initial_schema.sql"
    migration_path = _find_migration_file(filename)
    if migration_path is None:
        print(
            f"[seeds] Warning: migrations/{filename} not found. "
            "Skipping schema migration.",
            file=sys.stderr,
            flush=True,
        )
        return

    with open(migration_path, "r", encoding="utf-8") as fh:
        sql = fh.read()

    try:
        db.executescript(sql)
        db.commit()
        print(f"[seeds] Schema migration applied: {migration_path}", flush=True)
    except Exception as exc:
        db.rollback()
        print(
            f"[seeds] Migration warning: {exc}",
            file=sys.stderr,
            flush=True,
        )

    # Run skills seed — route to the correct dialect file.
    # 002_seed_skills.sql uses SQLite-only INSERT OR IGNORE syntax.
    # supabase/step3_seed_skills.sql uses ON CONFLICT DO NOTHING (Postgres).
    skills_filename = "002_seed_skills.sql" if is_sqlite else "supabase/step3_seed_skills.sql"
    skills_path = _find_migration_file(skills_filename)
    if skills_path:
        try:
            with open(skills_path, "r", encoding="utf-8") as fh:
                db.executescript(fh.read())
            db.commit()
            print("[seeds] Skills seed applied.", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"[seeds] Skills seed warning: {exc}", file=sys.stderr, flush=True)


def _find_migration_file(filename: str = "001_initial_schema.sql") -> Optional[str]:
    """
    Locate migrations/001_initial_schema.sql relative to the project root.
    Tries several candidate paths to be robust against different CWDs.
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "migrations", filename),
        os.path.join("migrations", filename),
        os.path.join(os.environ.get("UFIT_APP_ROOT", ""), "migrations", filename),
    ]
    for path in candidates:
        normalized = os.path.normpath(path)
        if os.path.isfile(normalized):
            return normalized
    return None


# ---------------------------------------------------------------------------
# Default admin user
# ---------------------------------------------------------------------------

def _seed_default_admin(db) -> None:
    """
    Create a default admin account if no admin or ceo user exists.
    Skipped in production — use POST /api/auth/setup-admin to create the first account.

    Default credentials (development only):
      email:    admin@ufit.com
      password: admin123
    """
    env = os.environ.get("APP_ENV", "development")
    if env == "production":
        return

    try:
        existing = db.execute(
            "SELECT user_id FROM users WHERE role IN ('ceo', 'admin') AND deleted_at IS NULL LIMIT 1"
        ).fetchone()
    except Exception:
        # Table may not exist yet if migration failed; skip seeding.
        return

    if existing:
        # Already have an admin/ceo — make sure Miss A's CEO account exists too.
        _ensure_missa_ceo(db)
        return

    from app.routes._helpers import now_utc

    dev_password = os.environ.get("UFIT_SEED_PASSWORD", "changeme-dev-only")
    password_hash = generate_password_hash(dev_password, method="pbkdf2:sha256")
    ts = now_utc()

    try:
        db.execute(
            """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                  active_status, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            ("admin", "Admin", "User", "admin@ufit.com", password_hash, ts),
        )
        db.commit()
        print(
            "[seeds] Dev admin created: admin@ufit.com — set UFIT_SEED_PASSWORD for password.",
            flush=True,
        )
    except Exception as exc:
        db.rollback()
        print(f"[seeds] Could not create default admin: {exc}", file=sys.stderr, flush=True)

    _ensure_missa_ceo(db)


def _ensure_missa_ceo(db) -> None:
    """
    Seed Miss A's CEO account (Ufit founder) if it doesn't already exist.
    Email: missa@ufitonline.com  Password: from UFIT_SEED_PASSWORD or default 'UfitDemo2026!'
    """
    from app.routes._helpers import now_utc
    try:
        exists = db.execute(
            "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL",
            ("missa@ufitonline.com",),
        ).fetchone()
        if exists:
            return
        ceo_password = os.environ.get("UFIT_SEED_PASSWORD", "UfitDemo2026!")
        ceo_hash = generate_password_hash(ceo_password, method="pbkdf2:sha256")
        db.execute(
            """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                  active_status, email_verified, created_at)
               VALUES ('ceo', 'Miss', 'A', 'missa@ufitonline.com', ?, TRUE, TRUE, ?)""",
            (ceo_hash, now_utc()),
        )
        db.commit()
        print("[seeds] Miss A CEO account seeded: missa@ufitonline.com", flush=True)
    except Exception as exc:
        db.rollback()
        print(f"[seeds] Could not seed Miss A CEO: {exc}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Demo users (development only)
# ---------------------------------------------------------------------------

def _seed_demo_users(db) -> None:
    """
    Create demo accounts + full demo school data (development only).
    Never runs outside APP_ENV=development.
    """
    env = os.environ.get("APP_ENV", "development")
    if env != "development":
        return

    # Skip entirely if demo school already exists
    try:
        existing = db.execute(
            "SELECT school_id FROM schools WHERE school_name = 'Lincoln Elementary' AND deleted_at IS NULL LIMIT 1"
        ).fetchone()
        if existing:
            return
    except Exception:
        return

    from app.routes._helpers import now_utc
    import datetime

    ts = now_utc()
    today = datetime.date.today()
    demo_pw = os.environ.get("UFIT_SEED_PASSWORD", "changeme-dev-only")
    pw_hash = generate_password_hash(demo_pw, method="pbkdf2:sha256")

    try:
        # ── 1. Organization ──────────────────────────────────────────────────
        cur = db.execute(
            """INSERT INTO organizations (organization_name, organization_type, created_at)
               VALUES ('Ufit Demo District', 'school_district', ?)""",
            (ts,),
        )
        org_id = cur.lastrowid

        # ── 2. School ────────────────────────────────────────────────────────
        cur = db.execute(
            """INSERT INTO schools (organization_id, school_name, school_type, address, city,
                                    state, zip_code, principal_name, principal_email,
                                    active_status, created_at)
               VALUES (?, 'Lincoln Elementary', 'elementary', '100 Demo St', 'Springfield',
                       'CA', '90210', 'Alex Rivera', 'principal@demo.com', 1, ?)""",
            (org_id, ts),
        )
        school_id = cur.lastrowid

        # ── 3. Program ───────────────────────────────────────────────────────
        cur = db.execute(
            """INSERT INTO programs (school_id, program_name, program_type, grade_band,
                                     start_date, program_status, reporting_cycle, created_at)
               VALUES (?, 'Lincoln PE Support', 'pe_support', 'K-8',
                       ?, 'active', 'weekly', ?)""",
            (school_id, (today - datetime.timedelta(days=60)).isoformat(), ts),
        )
        program_id = cur.lastrowid

        # ── 4. Demo users ────────────────────────────────────────────────────
        def insert_user(role, first, last, email):
            c = db.execute(
                """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                      active_status, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (role, first, last, email, pw_hash, ts),
            )
            return c.lastrowid

        principal_uid  = insert_user("principal",       "Alex",   "Rivera",  "principal@demo.com")
        staff_uid      = insert_user("school_staff",    "Sam",    "Chen",    "staff@demo.com")
        parent_uid     = insert_user("parent",          "Maria",  "Johnson", "parent@demo.com")
        coach_uid      = insert_user("head_coach",      "Jordan", "Davis",   "coach@demo.com")
        asst_uid       = insert_user("assistant_coach", "Marcus", "Wright",  "assistant@demo.com")

        # ── 5. Staff profiles + assignments (principal, school_staff, coaches) ─
        start_date = (today - datetime.timedelta(days=60)).isoformat()
        coach_sp_id = None
        asst_sp_id = None
        for uid, assign_role, title in [
            (principal_uid, "observer",       "Principal"),
            (staff_uid,     "observer",       "School Staff"),
            (coach_uid,     "head_coach",     "Head Coach"),
            (asst_uid,      "assistant_coach","Assistant Coach"),
        ]:
            cur = db.execute(
                """INSERT INTO staff_profiles (user_id, employee_type, position_title,
                                               status, created_at)
                   VALUES (?, 'full_time', ?, 'active', ?)""",
                (uid, title, ts),
            )
            sp_id = cur.lastrowid
            db.execute(
                """INSERT INTO staff_assignments (staff_id, school_id, assignment_role,
                                                  start_date, active_status, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (sp_id, school_id, assign_role, start_date, ts),
            )
            if uid == coach_uid:
                coach_sp_id = sp_id
            if uid == asst_uid:
                asst_sp_id = sp_id

        # ── 6. Parent record ─────────────────────────────────────────────────
        cur = db.execute(
            """INSERT INTO parents (user_id, first_name, last_name, email,
                                    portal_access_status, created_at)
               VALUES (?, 'Maria', 'Johnson', 'parent@demo.com', 1, ?)""",
            (parent_uid, ts),
        )
        parent_id = cur.lastrowid

        # ── 7. Students ──────────────────────────────────────────────────────
        student_data = [
            ("Emma",    "Johnson",  "3", parent_id),
            ("Liam",    "Torres",   "4", None),
            ("Sofia",   "Nguyen",   "5", None),
            ("Aiden",   "Patel",    "2", None),
            ("Mia",     "Williams", "6", None),
            ("Noah",    "Brown",    "7", None),
            ("Olivia",  "Garcia",   "1", None),
            ("Ethan",   "Martinez", "3", None),
            ("Ava",     "Anderson", "5", None),
            ("Lucas",   "Wilson",   "8", None),
        ]
        student_ids = []
        for first, last, grade, pid in student_data:
            cur = db.execute(
                """INSERT INTO students (school_id, student_first_name, student_last_name,
                                         grade_level, active_status, parent_primary_id, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (school_id, first, last, grade, pid, ts),
            )
            student_ids.append(cur.lastrowid)

        # ── 8. Sessions (last 10 days) ────────────────────────────────────────
        session_times = [
            ("13:30", "14:30"), ("14:00", "15:00"), ("12:00", "13:00"),
            ("14:30", "15:30"), ("13:00", "14:00"), ("14:00", "15:00"),
            ("13:30", "14:30"), ("12:30", "13:30"), ("14:00", "15:00"), ("13:00", "14:00"),
        ]
        activities = [
            "Warm-up, locomotor circuits, 3v3 soccer, cool-down stretching",
            "Agility ladder drills, dribbling relays, 5v5 basketball scrimmage",
            "Jump rope, balance beam stations, tag games, group reflection",
            "Cone agility course, passing accuracy drills, team handball game",
            "Dynamic stretching, SEL circle, skill-based stations, cool-down",
            "Warm-up jog, striking and catching drills, modified kickball",
            "Yoga flow warm-up, defensive positioning practice, small-sided game",
            "Sprint intervals, passing under pressure, 4v4 flag football",
            "Balance challenges, sport decision-making drills, full game",
            "Cooperative games, leadership challenge, cool-down reflection circle",
        ]
        student_counts = [9, 10, 8, 10, 9, 10, 8, 9, 10, 10]
        session_ids = []
        for i, ((start_t, end_t), activity, count) in enumerate(
            zip(session_times, activities, student_counts)
        ):
            session_date = (today - datetime.timedelta(days=10 - i)).isoformat()
            cur = db.execute(
                """INSERT INTO sessions (school_id, program_id, session_date, start_time, end_time,
                                          session_type, location, actual_activity,
                                          session_status, total_students_present, created_at)
                   VALUES (?, ?, ?, ?, ?, 'regular', 'Main Gymnasium', ?, 'completed', ?, ?)""",
                (school_id, program_id, session_date, start_t, end_t, activity, count, ts),
            )
            session_ids.append(cur.lastrowid)

        # ── 9. EOD reports for each session ──────────────────────────────────
        engagements = [
            "Students were highly engaged. Great energy throughout.",
            "Solid participation. A few students needed redirection.",
            "Excellent focus today — best session this week.",
            "Moderate engagement. Weather affected outdoor activity.",
            "Students responded well to new skill drills.",
        ]
        for idx, (sid, i) in enumerate(zip(session_ids, range(10, 0, -1))):
            session_date = (today - datetime.timedelta(days=i)).isoformat()
            db.execute(
                """INSERT INTO eod_reports (school_id, staff_id, program_id, session_id,
                                             report_date, activities_completed,
                                             student_engagement_summary, attendance_summary,
                                             behavior_summary, submitted_on_time,
                                             coaches_clocked_in, coaches_in_uniform,
                                             coaches_setup_ready, equipment_accounted,
                                             transitions_orderly, yard_supervised,
                                             curriculum_followed, injury_incident_flag,
                                             followup_needed, principal_communication_needed,
                                             created_at)
                   VALUES (?, ?, ?, ?, ?, 'Warm-up, locomotor skills, team game, cool-down',
                           ?, 'All students present and accounted for.',
                           'Good behavior overall. 1 verbal reminder issued.',
                           1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, ?)""",
                (school_id, coach_sp_id, program_id, sid, session_date,
                 engagements[idx % len(engagements)], ts),
            )

        # ── 10. Assessment windows ────────────────────────────────────────────
        baseline_start = (today - datetime.timedelta(days=45)).isoformat()
        baseline_end   = (today - datetime.timedelta(days=31)).isoformat()
        midyear_start  = (today - datetime.timedelta(days=20)).isoformat()
        midyear_end    = (today - datetime.timedelta(days=4)).isoformat()

        cur = db.execute(
            """INSERT INTO assessment_windows (school_id, program_id, window_name,
                                               start_date, end_date, assessment_focus, status, created_at)
               VALUES (?, ?, 'Baseline Assessment', ?, ?, 'Initial skill evaluation for all students', 'closed', ?)""",
            (school_id, program_id, baseline_start, baseline_end, ts),
        )
        baseline_window = cur.lastrowid

        cur = db.execute(
            """INSERT INTO assessment_windows (school_id, program_id, window_name,
                                               start_date, end_date, assessment_focus, status, created_at)
               VALUES (?, ?, 'Mid-Year Assessment', ?, ?, 'Progress check — physical skills + SEL growth', 'active', ?)""",
            (school_id, program_id, midyear_start, midyear_end, ts),
        )
        midyear_window = cur.lastrowid

        # ── 11. Assessments + scores per student ─────────────────────────────
        # Grade-band → physical skill names
        grade_to_band = {
            "1": "K-2", "2": "K-2",
            "3": "3-5", "4": "3-5", "5": "3-5",
            "6": "6-8", "7": "6-8", "8": "6-8",
        }
        phys_skills_by_band = {
            "K-2": ["run_with_control", "hop_on_one_foot", "skip_with_rhythm",
                    "throw_underhand", "catch_two_hands", "balance_on_one_foot"],
            "3-5": ["dribble_with_control", "pass_to_target", "strike_with_accuracy",
                    "defensive_positioning_basic", "change_direction_with_control"],
            "6-8": ["sport_decision_making", "offensive_spacing", "defensive_recovery",
                    "combination_skills", "game_application"],
        }
        sel_skills = ["teamwork", "effort", "self_control",
                      "listening_following_directions", "sportsmanship", "confidence_participation"]

        # Fetch all needed skill IDs in one query
        skill_id_map = {}
        for row in db.execute("SELECT skill_id, skill_name FROM skills").fetchall():
            skill_id_map[row["skill_name"]] = row["skill_id"]

        # Per-student baseline + growth scores
        student_scores = [
            # (name, grade, baseline_phys, midyear_phys, baseline_sel, midyear_sel)
            ("Emma",   "3", [2, 3, 2, 2, 3],    [3, 4, 3, 3, 4],    [3, 4, 3, 4, 3, 4], [4, 4, 4, 4, 4, 4]),
            ("Liam",   "4", [3, 3, 2, 3, 2],    [4, 4, 3, 4, 3],    [4, 3, 4, 3, 4, 3], [4, 4, 4, 4, 4, 4]),
            ("Sofia",  "5", [4, 4, 3, 3, 4],    [5, 5, 4, 4, 5],    [5, 4, 5, 4, 5, 4], [5, 5, 5, 5, 5, 5]),
            ("Aiden",  "2", [2, 2, 1, 2, 2, 2], [3, 3, 2, 3, 3, 3], [3, 3, 2, 3, 3, 3], [4, 4, 3, 4, 3, 4]),
            ("Mia",    "6", [3, 3, 2, 2, 3],    [4, 4, 3, 3, 4],    [4, 3, 4, 3, 3, 4], [5, 4, 4, 4, 4, 5]),
            ("Noah",   "7", [2, 2, 3, 2, 2],    [3, 3, 4, 3, 3],    [3, 4, 3, 3, 4, 3], [4, 4, 4, 4, 4, 4]),
            ("Olivia", "1", [1, 2, 1, 2, 1, 2], [2, 3, 2, 3, 2, 3], [2, 3, 2, 2, 3, 2], [3, 4, 3, 3, 4, 3]),
            ("Ethan",  "3", [3, 2, 3, 2, 3],    [4, 3, 4, 3, 4],    [2, 3, 3, 2, 3, 3], [3, 4, 4, 3, 4, 4]),
            ("Ava",    "5", [4, 3, 4, 3, 4],    [5, 4, 5, 4, 5],    [4, 5, 4, 5, 4, 5], [5, 5, 5, 5, 5, 5]),
            ("Lucas",  "8", [3, 4, 3, 4, 3],    [4, 5, 4, 5, 4],    [4, 4, 3, 4, 4, 3], [5, 5, 4, 5, 5, 4]),
        ]

        baseline_date = (today - datetime.timedelta(days=38)).isoformat()
        midyear_date  = (today - datetime.timedelta(days=10)).isoformat()
        # Use assessment_date-based timestamps so the scoring engine can
        # correctly identify baseline (oldest) vs. current (most recent).
        baseline_ts = (today - datetime.timedelta(days=38)).strftime("%Y-%m-%dT12:00:00+00:00")
        midyear_ts  = (today - datetime.timedelta(days=10)).strftime("%Y-%m-%dT12:00:00+00:00")

        for sid, (name, grade, b_phys, m_phys, b_sel, m_sel) in zip(student_ids, student_scores):
            band = grade_to_band.get(grade, "3-5")
            phys_skill_names = phys_skills_by_band[band]

            for window_id, assess_date, score_ts, phys_scores, sel_scores in [
                (baseline_window, baseline_date, baseline_ts, b_phys, b_sel),
                (midyear_window,  midyear_date,  midyear_ts,  m_phys, m_sel),
            ]:
                cur = db.execute(
                    """INSERT INTO assessments (student_id, school_id, program_id, window_id,
                                                assessed_by_staff_id, assessment_date,
                                                assessment_method, overall_assessment_notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'observational', 'Standard observational assessment', ?)""",
                    (sid, school_id, program_id, window_id, coach_sp_id, assess_date, score_ts),
                )
                assessment_id = cur.lastrowid

                # Physical skills
                for skill_name, score in zip(phys_skill_names, phys_scores):
                    skill_id = skill_id_map.get(skill_name)
                    if skill_id:
                        db.execute(
                            """INSERT INTO assessment_scores
                               (assessment_id, student_id, skill_id, raw_level, normalized_score, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)
                               ON CONFLICT DO NOTHING""",
                            (assessment_id, sid, skill_id, score, score * 20, score_ts),
                        )

                # SEL skills
                for skill_name, score in zip(sel_skills, sel_scores):
                    skill_id = skill_id_map.get(skill_name)
                    if skill_id:
                        db.execute(
                            """INSERT INTO assessment_scores
                               (assessment_id, student_id, skill_id, raw_level, normalized_score, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)
                               ON CONFLICT DO NOTHING""",
                            (assessment_id, sid, skill_id, score, score * 20, score_ts),
                        )

        # ── 12. session_staff — link coach as lead for every session ─────────
        for sess_id in session_ids:
            db.execute(
                """INSERT INTO session_staff (session_id, staff_id, role)
                   VALUES (?, ?, 'lead')
                   ON CONFLICT DO NOTHING""",
                (sess_id, coach_sp_id),
            )

        # ── 13. student_session_attendance ───────────────────────────────────
        # Each session has 8-10 students; distribute all 10 students across sessions.
        for i, sess_id in enumerate(session_ids):
            # Rotate which students attend each session (8-10 out of 10)
            present_count = student_counts[i]
            for j, sid in enumerate(student_ids):
                status = "present" if j < present_count else "absent"
                level = "high" if j < 5 else "medium"
                db.execute(
                    """INSERT INTO student_session_attendance
                       (session_id, student_id, attendance_status, participation_level, created_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT DO NOTHING""",
                    (sess_id, sid, status, level if status == "present" else None, ts),
                )

        # ── 14. behavior_observations — SEL observations for recent sessions ─
        sel_score_sets = [
            (4, 4, 3, 4, 4, 3), (3, 4, 4, 3, 4, 4), (5, 5, 4, 5, 5, 4),
            (3, 3, 3, 4, 3, 3), (4, 4, 3, 4, 4, 3), (3, 4, 3, 3, 4, 3),
            (2, 3, 2, 3, 3, 3), (4, 3, 4, 4, 3, 4), (5, 4, 5, 5, 4, 5),
            (4, 5, 4, 4, 5, 4),
        ]
        for i, sess_id in enumerate(session_ids):
            session_date = (today - datetime.timedelta(days=10 - i)).isoformat()
            for j, sid in enumerate(student_ids[:6]):
                t, ef, sc, li, sp, co = sel_score_sets[(i + j) % len(sel_score_sets)]
                db.execute(
                    """INSERT INTO behavior_observations
                       (student_id, school_id, session_id, observed_by_staff_id,
                        observation_date, teamwork_score, effort_score, self_control_score,
                        listening_score, sportsmanship_score, confidence_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sid, school_id, sess_id, coach_sp_id, session_date, t, ef, sc, li, sp, co, ts),
                )

        # ── 15. coach_observations — admin evaluates the coach ───────────────
        # Use principal's staff profile as evaluator (or a proxy staff_id)
        principal_sp_row = db.execute(
            "SELECT staff_id FROM staff_profiles WHERE user_id = ? LIMIT 1", (principal_uid,)
        ).fetchone()
        evaluator_sp_id = principal_sp_row["staff_id"] if principal_sp_row else coach_sp_id

        coach_obs_dates = [
            (today - datetime.timedelta(days=25)).isoformat(),
            (today - datetime.timedelta(days=12)).isoformat(),
            (today - datetime.timedelta(days=3)).isoformat(),
        ]
        coach_obs_scores = [
            (4, 4, 4, 3, 5, 4, "Strong lesson delivery. Good transitions.", None),
            (4, 5, 4, 4, 5, 4, "Excellent engagement. Students clearly motivated.", "Continue integrating SEL language into transitions."),
            (5, 5, 5, 4, 5, 5, "Outstanding session. Model-level delivery.", None),
        ]
        for obs_date, (tr, en, lf, sl, sf, og, notes, action) in zip(coach_obs_dates, coach_obs_scores):
            db.execute(
                """INSERT INTO coach_observations
                   (observed_staff_id, evaluator_staff_id, school_id, observation_date,
                    transitions_score, engagement_score, lesson_fidelity_score,
                    sel_language_score, safety_score, organization_score, notes, action_plan, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (coach_sp_id, evaluator_sp_id, school_id, obs_date, tr, en, lf, sl, sf, og, notes, action, ts),
            )

        # ── 16. Coach evaluation (head coach evaluates assistant coach) ─────────
        if asst_sp_id and coach_sp_id:
            eval_date = (today - datetime.timedelta(days=14)).isoformat()
            db.execute(
                """INSERT INTO coach_evaluations
                   (school_id, evaluator_staff_id, evaluated_staff_id, email,
                    same_day_calloff,
                    shows_up_consistently, reports_on_time, processes_consistently,
                    follows_sop, problem_solves, demonstrates_improvement,
                    apprises_lead_coach, provides_feedback_to_lead, follows_up_timely, communicates_regularly,
                    practices_restorative_justice, creates_inclusive_environment, teaches_transferable_skills,
                    maintains_positive_atmosphere, uses_reward_systems, implements_activities_fidelity,
                    learns_student_names, provides_student_feedback, uses_positive_language,
                    provides_supervision, uses_designated_spaces, ensures_safe_areas, determines_best_areas,
                    follows_safety_procedures, maintains_equipment, maintains_orderly_flow,
                    implements_rules_safeguards,
                    coach_strengths, coach_weaknesses, improvement_plan, submitted_at)
                   VALUES (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?,?,?,?)""",
                (
                    school_id, coach_sp_id, asst_sp_id, "coach@demo.com",
                    0,          # no same-day calloff
                    4, 4, 4,   # attendance
                    4, 3, 4,   # continuous skill
                    4, 3, 4, 4, # communication
                    4, 4, 3, 4, 3, 4,  # school & team
                    4, 4, 4,   # student interaction
                    4, 4, 4, 3, 4, 4, 4, 4,  # safety & compliance
                    "Strong rapport with students. Transitions are smooth and consistent.",
                    "Needs to communicate more proactively with the lead coach about student concerns.",
                    "Check in daily with lead coach before sessions. Review UFIT SOPs for equipment setup.",
                    eval_date,
                ),
            )

        # ── 18. Incident report ───────────────────────────────────────────────
        incident_date = (today - datetime.timedelta(days=5)).isoformat()
        db.execute(
            """INSERT INTO incident_reports
               (school_id, reported_by_staff_id, incident_type, report_date,
                severity_level, description, immediate_action_taken,
                school_notified, family_notified, escalated_to_supervisor, status, created_at)
               VALUES (?, ?, 'minor_injury', ?, 'low',
                       'Student tripped during agility drill; minor scrape on knee.',
                       'First aid applied. Student returned to activity within 5 minutes.',
                       1, 1, 0, 'open', ?)""",
            (school_id, coach_sp_id, incident_date, ts),
        )

        db.commit()

        # ── 17. Recalculate student score summaries ───────────────────────────
        # Must run after commit so the scoring engine sees the inserted scores.
        try:
            from app.routes._scoring import recalculate_student_summaries
            for sid in student_ids:
                recalculate_student_summaries(db, sid, school_id)
            db.commit()
            print("[seeds] Student score summaries recalculated.", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"[seeds] Warning: could not recalculate student summaries: {exc}", file=sys.stderr, flush=True)

        # ── 18. Compute and store coach rolling score ─────────────────────────
        try:
            from app.routes._coach_scoring import calculate_coach_score, rolling_period
            period_start, period_end = rolling_period()
            scorecard = calculate_coach_score(db, coach_sp_id, school_id, period_start, period_end)
            db.execute(
                """UPDATE staff_profiles
                   SET rolling_score = ?, rolling_band = ?, score_last_updated = ?
                   WHERE staff_id = ?""",
                (scorecard["overall_score"], scorecard["performance_band"], ts, coach_sp_id),
            )
            db.commit()
            print(f"[seeds] Coach rolling score computed: {scorecard['overall_score']} ({scorecard['performance_band']}).", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"[seeds] Warning: could not compute coach score: {exc}", file=sys.stderr, flush=True)

        print("[seeds] Demo school data created: Lincoln Elementary + 10 students + 10 sessions + 20 assessments.", flush=True)
        print("[seeds] Demo logins: principal@demo.com / staff@demo.com / parent@demo.com / coach@demo.com / assistant@demo.com", flush=True)

    except Exception as exc:
        db.rollback()
        print(f"[seeds] Could not create demo data: {exc}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Default app settings
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS = [
    ("app_name", "Ufit Motion", True),
    ("app_version", "1.0.0", True),
    ("support_email", "support@ufitonline.net", True),
    ("eod_report_deadline_hour", "20", False),   # 8 PM local time cutoff
    ("max_session_duration_hours", "4", False),
    ("assessment_window_weeks", "6", False),
    ("allow_parent_portal", "true", True),
]


def _seed_app_settings(db) -> None:
    """Insert default app_settings rows if the table is empty."""
    try:
        count_row = db.execute("SELECT COUNT(*) AS cnt FROM app_settings").fetchone()
        if count_row and (count_row.get("cnt") or 0) > 0:
            return
    except Exception:
        return

    from app.routes._helpers import now_utc

    ts = now_utc()
    inserted = 0
    is_sqlite = getattr(db, "backend", "postgres") == "sqlite"
    upsert_sql = (
        "INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)"
        if is_sqlite else
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT (key) DO NOTHING"
    )
    for key, value, is_public in _DEFAULT_SETTINGS:
        try:
            db.execute(upsert_sql, (key, value, ts))
            inserted += 1
        except Exception as exc:
            print(f"[seeds] Could not insert setting '{key}': {exc}", file=sys.stderr, flush=True)

    if inserted:
        try:
            db.commit()
            print(f"[seeds] Seeded {inserted} default app_settings rows.", flush=True)
        except Exception as exc:
            db.rollback()
            print(f"[seeds] Could not commit app_settings: {exc}", file=sys.stderr, flush=True)
