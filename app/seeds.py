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
        _seed_default_admin(db)
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
    is_sqlite = getattr(db, "backend", "sqlite") == "sqlite"
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
        return

    from app.routes._helpers import now_utc

    password_hash = generate_password_hash("admin123", method="pbkdf2:sha256")
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
            "[seeds] Dev admin created: admin@ufit.com / admin123 — development only.",
            flush=True,
        )
    except Exception as exc:
        db.rollback()
        print(f"[seeds] Could not create default admin: {exc}", file=sys.stderr, flush=True)


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
    for key, value, is_public in _DEFAULT_SETTINGS:
        try:
            db.execute(
                """INSERT OR IGNORE INTO app_settings (key, value, updated_at)
                   VALUES (?, ?, ?)""",
                (key, value, ts),
            )
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
