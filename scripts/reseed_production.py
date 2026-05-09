"""
reseed_production.py — Wipes and re-seeds the Supabase Postgres DB
from the local SQLite snapshot.

Run from project root:
  DATABASE_URL="postgresql://..." python3 scripts/reseed_production.py
"""
import os
import sys
import sqlite3

SQLITE_PATH = "ufit_motion.db"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL env var not set.")

# --------------------------------------------------------------------------
# Connect to Postgres
# --------------------------------------------------------------------------
try:
    import psycopg
except ImportError:
    sys.exit("pip install psycopg[binary]")


def make_pg_conn():
    c = psycopg.connect(DATABASE_URL, autocommit=False, connect_timeout=30)
    c.prepare_threshold = None
    return c


print("Connecting to Postgres…")
conn_pg = make_pg_conn()
print("Connected.")

# --------------------------------------------------------------------------
# Connect to SQLite
# --------------------------------------------------------------------------
conn_sq = sqlite3.connect(SQLITE_PATH)
conn_sq.row_factory = sqlite3.Row


def sq(sql, params=()):
    return conn_sq.execute(sql, params).fetchall()


def pg_exec(sql, params=()):
    global conn_pg
    try:
        cur = conn_pg.cursor()
        cur.execute(sql, params)
        return cur
    except psycopg.OperationalError:
        print("  [reconnecting…]")
        try:
            conn_pg.close()
        except Exception:
            pass
        conn_pg = make_pg_conn()
        cur = conn_pg.cursor()
        cur.execute(sql, params)
        return cur


# Boolean columns per table (stored as 0/1 in SQLite → TRUE/FALSE in PG)
BOOL_COLS = {
    "schools": {"active_status"},
    "users": {"active_status", "email_verified"},
    "staff_assignments": {"active_status"},
    "students": {"active_status"},
    "skill_domains": {"active_status"},
    "skills": {"active_status"},
    "benchmarks": {"active_status"},
    "parents": {"portal_access_status"},
    "assessment_scores": {
        "growth_flag", "observed_independence", "observed_consistency", "observed_accuracy",
    },
    "eod_reports": {
        "injury_incident_flag", "followup_needed", "principal_communication_needed",
        "submitted_on_time", "incident_report_filed", "school_concerns_resolved",
        "equipment_accounted", "transitions_orderly", "yard_supervised",
        "curriculum_followed", "coaches_in_uniform", "coaches_setup_ready", "coaches_clocked_in",
    },
    "incident_reports": {
        "school_notified", "family_notified", "escalated_to_supervisor",
    },
    "notifications": {"is_read"},
    "role_permissions": {"allowed"},
}


def convert_row(table, row_dict):
    """Convert SQLite 0/1 booleans to Python bool for psycopg3."""
    bool_set = BOOL_COLS.get(table, set())
    result = {}
    for k, v in row_dict.items():
        if k in bool_set:
            result[k] = bool(v) if v is not None else None
        else:
            result[k] = v
    return result


BATCH_SIZE = 50


def insert_table(table, rows, skip_cols=None):
    """Insert all rows into a Postgres table in batches, skipping generated cols."""
    global conn_pg
    if not rows:
        print(f"  {table}: 0 rows (skipping)")
        return
    skip_cols = skip_cols or set()
    sample = dict(rows[0])
    cols = [c for c in sample.keys() if c not in skip_cols]
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    count = 0
    converted = [convert_row(table, dict(r)) for r in rows]

    for batch_start in range(0, len(converted), BATCH_SIZE):
        batch = converted[batch_start:batch_start + BATCH_SIZE]
        for attempt in range(3):
            try:
                for d in batch:
                    pg_exec(sql, [d[c] for c in cols])
                conn_pg.commit()
                count += len(batch)
                break
            except psycopg.OperationalError as e:
                print(f"  [reconnect attempt {attempt+1} for {table} batch {batch_start}…]")
                try:
                    conn_pg.close()
                except Exception:
                    pass
                conn_pg = make_pg_conn()
            except Exception as e:
                print(f"  WARN {table} batch at {batch_start}: {e}")
                try:
                    conn_pg.rollback()
                except Exception:
                    pass
                break

    print(f"  {table}: {count} rows inserted")


# --------------------------------------------------------------------------
# STEP 1: Truncate all tables (CASCADE handles FK deps)
# --------------------------------------------------------------------------
print("\n[1] Truncating all tables…")
TRUNCATE_ORDER = [
    "audit_log", "notifications",
    "principal_satisfaction_surveys",
    "coach_performance_snapshots", "coach_evaluations",
    "behavior_observations", "incident_reports", "eod_reports",
    "student_session_attendance", "session_staff", "sessions",
    "assessment_scores", "assessments", "assessment_windows",
    "student_skill_summary", "student_domain_summary", "student_overall_summary",
    "student_program_enrollment", "students",
    "staff_assignments", "staff_profiles",
    "benchmarks", "skills", "skill_domains",
    "programs", "schools",
    "parents", "users",
    "organizations",
    "app_settings",
]
for t in TRUNCATE_ORDER:
    try:
        pg_exec(f"TRUNCATE TABLE {t} CASCADE")
        print(f"  truncated {t}")
    except Exception as e:
        print(f"  WARN truncate {t}: {e}")
        conn_pg.rollback()
conn_pg.commit()

# --------------------------------------------------------------------------
# STEP 2: Only insert org 2 (demo district) and its data
# Old org 1 and school 1 are legacy/deleted — skip them.
# --------------------------------------------------------------------------
print("\n[2] Inserting seed data…")

# Organizations — only org 2 (Ufit Demo Unified)
orgs = [r for r in sq("SELECT * FROM organizations WHERE organization_id = 2")]
insert_table("organizations", orgs)

# Schools — only org 2 schools (schools 2, 3, 4)
schools = [r for r in sq("SELECT * FROM schools WHERE organization_id = 2 AND deleted_at IS NULL")]
insert_table("schools", schools)

# Skill domains
insert_table("skill_domains", sq("SELECT * FROM skill_domains"))

# Skills
insert_table("skills", sq("SELECT * FROM skills"))

# Benchmarks
insert_table("benchmarks", sq("SELECT * FROM benchmarks"))

# Programs — only for schools 2-4
insert_table("programs", sq("SELECT * FROM programs WHERE school_id IN (2,3,4)"))

# Users — only demo users (user_id 7-17), defer linked_ FKs by inserting with NULLs first
demo_user_ids = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
users_raw = sq(f"SELECT * FROM users WHERE user_id IN ({','.join(str(i) for i in demo_user_ids)})")
# Insert users without linked FK cols first (circular deps)
cols_no_link = [c for c in dict(users_raw[0]).keys() if c not in ("linked_staff_id", "linked_parent_id")]
col_list = ", ".join(cols_no_link)
placeholders = ", ".join(["%s"] * len(cols_no_link))
sql_user = f"INSERT INTO users ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
for row in users_raw:
    d = convert_row("users", dict(row))
    pg_exec(sql_user, [d[c] for c in cols_no_link])
conn_pg.commit()
print(f"  users: {len(users_raw)} rows inserted")

# Parents
parents = sq("SELECT * FROM parents WHERE user_id IN (SELECT user_id FROM users WHERE user_id BETWEEN 7 AND 17)")
insert_table("parents", parents)

# Staff profiles — for demo users
staff = sq(f"SELECT * FROM staff_profiles WHERE user_id IN ({','.join(str(i) for i in demo_user_ids)})")
insert_table("staff_profiles", staff)

# Staff assignments
insert_table("staff_assignments", sq("SELECT * FROM staff_assignments WHERE school_id IN (2,3,4)"))

# Students — only schools 2-4, active
students = sq("SELECT * FROM students WHERE school_id IN (2,3,4) AND deleted_at IS NULL")
insert_table("students", students)

# Student program enrollment
student_ids = [r["student_id"] for r in students]
if student_ids:
    placeholders = ",".join(str(i) for i in student_ids)
    enroll = sq(f"SELECT * FROM student_program_enrollment WHERE student_id IN ({placeholders})")
    insert_table("student_program_enrollment", enroll)

# Sessions
sessions = sq("SELECT * FROM sessions WHERE school_id IN (2,3,4) AND deleted_at IS NULL")
insert_table("sessions", sessions)

# Session staff
session_ids = [r["session_id"] for r in sessions]
if session_ids:
    placeholders = ",".join(str(i) for i in session_ids)
    insert_table("session_staff", sq(f"SELECT * FROM session_staff WHERE session_id IN ({placeholders})"))

# Student session attendance
if session_ids and student_ids:
    s_ph = ",".join(str(i) for i in session_ids)
    stu_ph = ",".join(str(i) for i in student_ids)
    ssa = sq(f"SELECT * FROM student_session_attendance WHERE session_id IN ({s_ph}) AND student_id IN ({stu_ph})")
    insert_table("student_session_attendance", ssa)

# Assessment windows
insert_table("assessment_windows", sq("SELECT * FROM assessment_windows WHERE school_id IN (2,3,4)"))

# Assessments
if student_ids:
    stu_ph = ",".join(str(i) for i in student_ids)
    assessments = sq(f"SELECT * FROM assessments WHERE student_id IN ({stu_ph}) AND deleted_at IS NULL")
    insert_table("assessments", assessments, skip_cols=set())

    # Assessment scores — skip normalized_score (generated column in Postgres)
    assessment_ids = [r["assessment_id"] for r in assessments]
    if assessment_ids:
        a_ph = ",".join(str(i) for i in assessment_ids)
        scores = sq(f"SELECT * FROM assessment_scores WHERE assessment_id IN ({a_ph})")
        insert_table("assessment_scores", scores, skip_cols={"normalized_score"})

# Student skill summary
if student_ids:
    stu_ph = ",".join(str(i) for i in student_ids)
    insert_table("student_skill_summary", sq(f"SELECT * FROM student_skill_summary WHERE student_id IN ({stu_ph})"), skip_cols={"growth_amount"})
    insert_table("student_domain_summary", sq(f"SELECT * FROM student_domain_summary WHERE student_id IN ({stu_ph})"), skip_cols={"growth_amount"})
    insert_table("student_overall_summary", sq(f"SELECT * FROM student_overall_summary WHERE student_id IN ({stu_ph})"))

# EOD reports
if session_ids:
    s_ph = ",".join(str(i) for i in session_ids)
    insert_table("eod_reports", sq(f"SELECT * FROM eod_reports WHERE session_id IN ({s_ph})"))

# Incident reports — session_id can be NULL so filter by school only
insert_table("incident_reports", sq("SELECT * FROM incident_reports WHERE school_id IN (2,3,4)"))

# Behavior observations
if student_ids and session_ids:
    stu_ph = ",".join(str(i) for i in student_ids)
    s_ph = ",".join(str(i) for i in session_ids)
    insert_table("behavior_observations", sq(f"SELECT * FROM behavior_observations WHERE student_id IN ({stu_ph}) AND session_id IN ({s_ph})"))

# Staff-level tables
staff_ids = [r["staff_id"] for r in staff]
if staff_ids:
    s_ph = ",".join(str(i) for i in staff_ids)
    insert_table("coach_evaluations", sq(f"SELECT * FROM coach_evaluations WHERE evaluated_staff_id IN ({s_ph})"))
    insert_table("coach_performance_snapshots", sq(f"SELECT * FROM coach_performance_snapshots WHERE staff_id IN ({s_ph})"))

# Principal satisfaction surveys
insert_table("principal_satisfaction_surveys", sq("SELECT * FROM principal_satisfaction_surveys WHERE school_id IN (2,3,4)"))

# --------------------------------------------------------------------------
# STEP 3: Reset Postgres sequences so next INSERT gets a valid ID
# --------------------------------------------------------------------------
print("\n[3] Resetting sequences…")
SEQ_TABLES = [
    ("organizations", "organization_id"),
    ("schools", "school_id"),
    ("users", "user_id"),
    ("staff_profiles", "staff_id"),
    ("staff_assignments", "assignment_id"),
    ("parents", "parent_id"),
    ("students", "student_id"),
    ("programs", "program_id"),
    ("student_program_enrollment", "enrollment_id"),
    ("sessions", "session_id"),
    ("session_staff", "session_staff_id"),
    ("student_session_attendance", "attendance_id"),
    ("skill_domains", "domain_id"),
    ("skills", "skill_id"),
    ("benchmarks", "benchmark_id"),
    ("assessment_windows", "window_id"),
    ("assessments", "assessment_id"),
    ("assessment_scores", "score_id"),
    ("student_skill_summary", "student_skill_summary_id"),
    ("student_domain_summary", "student_domain_summary_id"),
    ("student_overall_summary", "student_overall_summary_id"),
    ("eod_reports", "eod_id"),
    ("incident_reports", "incident_id"),
    ("behavior_observations", "behavior_observation_id"),
    ("coach_evaluations", "evaluation_id"),
    ("coach_performance_snapshots", "snapshot_id"),
    ("principal_satisfaction_surveys", "survey_id"),
]

for table, pk in SEQ_TABLES:
    try:
        cur = conn_pg.cursor()
        cur.execute(f"SELECT MAX({pk}) FROM {table}")
        row = cur.fetchone()
        max_id = row[0] if row and row[0] else 0
        if max_id > 0:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), %s)",
                (max_id,)
            )
            conn_pg.commit()
            print(f"  {table}.{pk} → {max_id}")
    except Exception as e:
        print(f"  WARN seq {table}: {e}")
        conn_pg.rollback()

# --------------------------------------------------------------------------
# STEP 4: Verify counts
# --------------------------------------------------------------------------
print("\n[4] Verification counts in Postgres:")
VERIFY = [
    "organizations", "schools", "users", "staff_profiles",
    "students", "sessions", "assessments", "assessment_scores",
    "student_skill_summary", "student_domain_summary", "student_overall_summary",
    "eod_reports", "behavior_observations",
]
for t in VERIFY:
    cur = conn_pg.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t}: {count}")

print("\nDone! Production DB re-seeded.")
conn_pg.close()
conn_sq.close()
