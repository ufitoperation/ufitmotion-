"""
production_wipe.py — Atomic production reset + first super-admin bootstrap.

Run via Render Job (or any environment with DATABASE_URL set):

    APP_ENV=production \\
    SUPER_ADMIN_EMAIL=ceo@ufitonline.net \\
    SUPER_ADMIN_PASSWORD='strong-12+chars' \\
    SUPER_ADMIN_FIRST=Boss \\
    SUPER_ADMIN_LAST=Lady \\
    python -m scripts.production_wipe --yes-really

Behavior:
  1. TRUNCATE all operational tables (Postgres) / DELETE FROM (SQLite tests).
     Static reference data — skill_domains, skills, benchmarks, app_settings,
     role_permissions — is left intact.
  2. INSERT the first CEO from the SUPER_ADMIN_* env vars in the same
     transaction. No window of "zero admins".

Guards:
  - Refuses to run unless APP_ENV == "production" OR --allow-non-prod is passed.
  - Requires --yes-really to confirm destructive intent.
  - Requires all four SUPER_ADMIN_* env vars; password must be 12+ chars.

Exit codes:
  0  success
  2  APP_ENV guard failed (and --allow-non-prod not passed)
  3  missing required env var(s)
  4  password too short
  5  --yes-really not passed
  1  database error
"""

from __future__ import annotations

import argparse
import os
import sys

from werkzeug.security import generate_password_hash

# Order doesn't matter for Postgres TRUNCATE … CASCADE; for the SQLite test path
# we run with foreign_keys OFF so order is also irrelevant. Listed roughly
# leaf-to-root for readability.
OPERATIONAL_TABLES = [
    "audit_log",
    "notifications",
    "principal_satisfaction_surveys",
    "coach_performance_snapshots",
    "coach_evaluations",
    "coach_observations",
    "incident_reports",
    "eod_reports",
    "behavior_observations",
    "student_overall_summary",
    "student_domain_summary",
    "student_skill_summary",
    "school_reports",
    "assessment_scores",
    "assessments",
    "assessment_windows",
    "student_session_attendance",
    "session_staff",
    "sessions",
    "student_program_enrollment",
    "programs",
    "parent_student_links",
    "parents",
    "staff_assignments",
    "staff_profiles",
    "students",
    "schools",
    "contracts",
    "regions",
    "organizations",
    "users",
]

PRESERVED_TABLES = (
    "skill_domains",
    "skills",
    "benchmarks",
    "app_settings",
    "role_permissions",
)

REQUIRED_ENV = (
    "SUPER_ADMIN_EMAIL",
    "SUPER_ADMIN_PASSWORD",
    "SUPER_ADMIN_FIRST",
    "SUPER_ADMIN_LAST",
)


def _check_env(allow_non_prod: bool) -> dict:
    env = (os.environ.get("APP_ENV") or "").strip().lower()
    if env != "production" and not allow_non_prod:
        sys.stderr.write(
            f"REFUSING: APP_ENV={env!r} is not 'production'. "
            "Pass --allow-non-prod to override (staging dry-runs only).\n"
        )
        sys.exit(2)

    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.stderr.write(f"Missing required env vars: {missing}\n")
        sys.exit(3)

    pw = os.environ["SUPER_ADMIN_PASSWORD"]
    if len(pw) < 12:
        sys.stderr.write(
            "SUPER_ADMIN_PASSWORD must be at least 12 characters.\n"
        )
        sys.exit(4)

    return {k: os.environ[k] for k in REQUIRED_ENV}


def _wipe_and_seed(creds: dict) -> None:
    """Run inside a Flask app context. Truncates operational tables, inserts CEO."""
    # Lazy-import: tests need to set APP_ENV/DB_PATH before app modules load.
    from app import create_app
    from app.database import get_db
    from app.routes._helpers import now_utc

    app = create_app()
    with app.app_context():
        db = get_db()
        try:
            is_postgres = getattr(db, "backend", "postgres") == "postgres"

            if is_postgres:
                # Single statement, all tables, CASCADE handles FK chains.
                # RESTART IDENTITY resets sequences so new IDs start at 1.
                tables_csv = ", ".join(OPERATIONAL_TABLES)
                db.execute(
                    f"TRUNCATE {tables_csv} RESTART IDENTITY CASCADE"
                )
            else:
                # SQLite test path. Disable FKs while we delete to avoid
                # ordering hazards. Skip tables that don't exist in the
                # SQLite dialect schema rather than failing the whole wipe.
                db.execute("PRAGMA foreign_keys = OFF")
                for tbl in OPERATIONAL_TABLES:
                    try:
                        db.execute(f"DELETE FROM {tbl}")
                    except Exception as exc:
                        sys.stderr.write(
                            f"[wipe] skipping {tbl}: {exc}\n"
                        )
                db.execute("PRAGMA foreign_keys = ON")

            password_hash = generate_password_hash(
                creds["SUPER_ADMIN_PASSWORD"], method="pbkdf2:sha256"
            )
            ts = now_utc()
            email = creds["SUPER_ADMIN_EMAIL"].strip().lower()

            # active_status: TRUE works on both backends (SQLite ≥ 3.23 accepts
            # TRUE/FALSE keywords; Postgres native boolean).
            db.execute(
                """INSERT INTO users
                   (role, first_name, last_name, email, password_hash,
                    active_status, created_at)
                   VALUES (?, ?, ?, ?, ?, TRUE, ?)""",
                (
                    "ceo",
                    creds["SUPER_ADMIN_FIRST"],
                    creds["SUPER_ADMIN_LAST"],
                    email,
                    password_hash,
                    ts,
                ),
            )

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="production_wipe",
        description="Wipe operational data and seed the first CEO from env vars.",
    )
    parser.add_argument(
        "--allow-non-prod",
        action="store_true",
        help="Permit running when APP_ENV != 'production' (staging dry-runs).",
    )
    parser.add_argument(
        "--yes-really",
        action="store_true",
        help="Required to confirm destructive intent.",
    )
    args = parser.parse_args(argv)

    creds = _check_env(args.allow_non_prod)

    if not args.yes_really:
        sys.stderr.write(
            "Pass --yes-really to confirm destructive wipe.\n"
        )
        sys.exit(5)

    sys.stderr.write(
        f"[wipe] truncating {len(OPERATIONAL_TABLES)} operational tables, "
        f"preserving {list(PRESERVED_TABLES)}.\n"
    )
    try:
        _wipe_and_seed(creds)
    except Exception as exc:
        sys.stderr.write(f"[wipe] FAILED: {exc}\n")
        sys.exit(1)

    sys.stderr.write(
        f"[wipe] complete. CEO seeded as {creds['SUPER_ADMIN_EMAIL']}.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
