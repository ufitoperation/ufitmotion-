"""
Run all Supabase migrations in order.
Usage: DATABASE_URL="postgresql://..." python3 run_migrations.py
"""
import os
import sys
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    sys.exit(1)

MIGRATIONS = [
    "step1_schema.sql",
    "step2_eod_fields.sql",
    "step3_seed_skills.sql",
    "step4_schema_gaps.sql",
    "step5_rls.sql",
    "step6_sessions_soft_delete.sql",
    "step7_coach_scoring.sql",
    "step8_staff_profiles_soft_delete.sql",
    "step9_assessment_windows_soft_delete.sql",
    "step10_sessions_duration.sql",
    "step11_obs_soft_delete.sql",
    # step12 deliberately skipped (file not present in repo)
    "step13_coach_evaluations.sql",
    "step14_staff_assignment_role_principal.sql",
    "step15_audit_log_action_freeform.sql",
]

MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "supabase"

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

def run_migration(conn, name: str, sql: str):
    print(f"  Running {name}...", end=" ", flush=True)
    try:
        conn.execute(sql)
        conn.commit()
        print("OK")
    except Exception as e:
        conn.rollback()
        print(f"FAILED\n  Error: {e}")
        raise

def main():
    print(f"Connecting to database...")
    try:
        conn = psycopg.connect(DATABASE_URL, autocommit=False)
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        sys.exit(1)

    print(f"Connected. Running {len(MIGRATIONS)} migrations:\n")
    try:
        for name in MIGRATIONS:
            path = MIGRATIONS_DIR / name
            if not path.exists():
                print(f"  SKIP {name} (file not found)")
                continue
            sql = path.read_text()
            run_migration(conn, name, sql)
    except Exception:
        print("\nMigration failed — see error above. All changes in that step rolled back.")
        conn.close()
        sys.exit(1)

    conn.close()
    print("\nAll migrations completed successfully.")

if __name__ == "__main__":
    main()
