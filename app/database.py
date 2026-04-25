"""
database.py — SQLite + Postgres abstraction layer for Ufit Motion.

Dev:  DATABASE_URL unset  → SQLite at DB_PATH
Prod: DATABASE_URL set    → Supabase Postgres via psycopg3 (psycopg)

Both backends expose the same interface:
    execute(sql, params=()) → cursor-like with .fetchone() / .fetchall() / .rowcount
    executescript(sql)      → run a multi-statement SQL block
    commit()
    rollback()
    close()

Per-request sharing: get_db() stores the connection in Flask g._pg_conn so the
same object is reused throughout a request and properly torn down in teardown.
"""

import re
import sqlite3
import os
from typing import Optional
from flask import g

# ---------------------------------------------------------------------------
# Tables that need RETURNING id appended on INSERT (Postgres only).
# SQLite uses lastrowid; Postgres needs the explicit clause.
# ---------------------------------------------------------------------------
POSTGRES_ID_TABLES: set[str] = {
    "organizations",
    "regions",
    "contracts",
    "schools",
    "users",
    "staff_profiles",
    "staff_assignments",
    "parents",
    "students",
    "programs",
    "student_program_enrollment",
    "sessions",
    "session_staff",
    "student_session_attendance",
    "skill_domains",
    "skills",
    "benchmarks",
    "assessment_windows",
    "assessments",
    "assessment_scores",
    "behavior_observations",
    "eod_reports",
    "incident_reports",
    "coach_observations",
    "school_reports",
    "student_skill_summary",
    "student_domain_summary",
    "student_overall_summary",
    "notifications",
    "role_permissions",
    "audit_log",
    "app_settings",
}

# ---------------------------------------------------------------------------
# Supabase pooler DSN builder
# ---------------------------------------------------------------------------
_SUPABASE_REGIONS = [
    "aws-0-us-east-1",
    "aws-0-us-west-1",
    "aws-0-eu-west-1",
    "aws-0-ap-southeast-1",
]


def _supabase_pooler_dsns(base_url: str) -> list[str]:
    """
    Given a standard Supabase DATABASE_URL (direct connection), return a list
    of transaction-pooler DSNs to try, one per known AWS region.

    Supabase pooler hostnames follow the pattern:
        aws-0-<region>.pooler.supabase.com

    The pooler uses port 6543 for transaction mode.
    """
    # Parse out user/password/dbname from the direct connection URL.
    # Expected format: postgresql://user:password@host:port/dbname[?options]
    pattern = re.compile(
        r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@[^/]+/([^?]+)"
    )
    m = pattern.match(base_url)
    if not m:
        # Cannot parse — return the original URL unchanged in a single-item list.
        return [base_url]

    user, password, dbname = m.group(1), m.group(2), m.group(3)
    dsns = []
    for region in _SUPABASE_REGIONS:
        dsns.append(
            f"postgresql://{user}:{password}@{region}.pooler.supabase.com:6543/{dbname}?sslmode=require"
        )
    return dsns


# ---------------------------------------------------------------------------
# Placeholder conversion: SQLite uses ? while psycopg3 uses %s
# ---------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(r"\?")


def _to_pg(sql: str) -> str:
    """Convert ? placeholders to %s for psycopg3."""
    return _PLACEHOLDER_RE.sub("%s", sql)


# ---------------------------------------------------------------------------
# INSERT → RETURNING id injection (Postgres only)
# ---------------------------------------------------------------------------
_INSERT_INTO_RE = re.compile(
    r"\bINSERT\s+INTO\s+(\w+)\b", re.IGNORECASE
)


def _maybe_add_returning(sql: str) -> str:
    """
    If the SQL is an INSERT into a known table and doesn't already have a
    RETURNING clause, append RETURNING <pk_column>.
    """
    stripped = sql.strip().rstrip(";")
    if not re.match(r"\s*INSERT\b", stripped, re.IGNORECASE):
        return sql
    if re.search(r"\bRETURNING\b", stripped, re.IGNORECASE):
        return sql
    m = _INSERT_INTO_RE.search(stripped)
    if not m:
        return sql
    table = m.group(1).lower()
    if table not in POSTGRES_ID_TABLES:
        return sql
    # Determine primary key column name (convention: <table_singular>_id or id).
    # Most tables use <table>_id; use a small lookup for irregular ones.
    pk_map = {
        "organizations": "organization_id",
        "regions": "region_id",
        "contracts": "contract_id",
        "schools": "school_id",
        "users": "user_id",
        "staff_profiles": "staff_id",
        "staff_assignments": "assignment_id",
        "parents": "parent_id",
        "students": "student_id",
        "programs": "program_id",
        "student_program_enrollment": "enrollment_id",
        "sessions": "session_id",
        "session_staff": "session_staff_id",
        "student_session_attendance": "attendance_id",
        "skill_domains": "domain_id",
        "skills": "skill_id",
        "benchmarks": "benchmark_id",
        "assessment_windows": "window_id",
        "assessments": "assessment_id",
        "assessment_scores": "score_id",
        "behavior_observations": "behavior_observation_id",
        "eod_reports": "eod_id",
        "incident_reports": "incident_id",
        "coach_observations": "coach_observation_id",
        "school_reports": "report_id",
        "student_skill_summary": "student_skill_summary_id",
        "student_domain_summary": "student_domain_summary_id",
        "student_overall_summary": "student_overall_summary_id",
        "notifications": "notification_id",
        "role_permissions": "permission_id",
        "audit_log": "log_id",
        "app_settings": "key",
    }
    pk = pk_map.get(table, "id")
    return f"{stripped} RETURNING {pk}"


# ---------------------------------------------------------------------------
# Postgres connection wrapper
# ---------------------------------------------------------------------------
class PostgresConnection:
    """
    Thin wrapper around a psycopg3 connection that provides the same interface
    as SQLiteConnection, including ? → %s conversion and RETURNING injection.
    """

    backend = "postgres"

    def __init__(self, conn):
        self._conn = conn
        self._closed = False

    def execute(self, sql: str, params=()):
        sql_pg = _to_pg(sql)
        sql_pg = _maybe_add_returning(sql_pg)
        cur = self._conn.cursor()
        cur.execute(sql_pg, params)
        return _PGCursor(cur)

    def executescript(self, sql: str):
        """
        Execute a multi-statement SQL block. psycopg3 doesn't have executescript,
        so we split on semicolons and execute each statement individually.
        """
        cur = self._conn.cursor()
        # Split into individual statements, skip empty ones.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            cur.execute(stmt)
        return _PGCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._conn.close()
            self._closed = True


class _PGCursor:
    """Wraps a psycopg3 cursor to provide fetchone/fetchall returning dicts."""

    def __init__(self, cur):
        self._cur = cur
        self._lastrowid_fetched = False
        self._cached_lastrow = None

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        """Return the id from a RETURNING clause, if present. Cached after first call."""
        if not self._lastrowid_fetched:
            row = self._cur.fetchone()  # consumes the cursor — don't also call fetchone()
            self._cached_lastrow = row[0] if row else None
            self._lastrowid_fetched = True
        return self._cached_lastrow

    def fetchone(self):
        if self._lastrowid_fetched:
            return None  # cursor already consumed by lastrowid
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return dict(zip(cols, row))

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cur.description]
        return [dict(zip(cols, row)) for row in rows]


# ---------------------------------------------------------------------------
# Borrowed-connection wrapper (per-request sharing)
# ---------------------------------------------------------------------------
class _BorrowedConnection:
    """
    A connection borrowed from Flask g. commit/rollback/close are no-ops
    because the real connection is managed by teardown_appcontext.
    """

    def __init__(self, real_conn):
        self._real = real_conn

    @property
    def backend(self):
        return self._real.backend

    def execute(self, sql: str, params=()):
        return self._real.execute(sql, params)

    def executescript(self, sql: str):
        return self._real.executescript(sql)

    def commit(self):
        self._real.commit()

    def rollback(self):
        self._real.rollback()

    def close(self):
        # Do NOT close — the teardown hook owns this connection.
        pass


# ---------------------------------------------------------------------------
# SQLite connection wrapper (dev)
# ---------------------------------------------------------------------------
class _SQLiteConnection:
    """
    Wraps sqlite3.Connection to provide the same interface as PostgresConnection.
    Rows are returned as dicts via sqlite3.Row.
    """

    backend = "sqlite"

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._closed = False

    def execute(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        return _SQLiteCursor(cur)

    def executescript(self, sql: str):
        # sqlite3.executescript doesn't support parameterised queries but is fine
        # for schema migrations.
        self._conn.executescript(sql)
        return _SQLiteCursor(None)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._conn.close()
            self._closed = True


class _SQLiteCursor:
    def __init__(self, cur):
        self._cur = cur

    @property
    def rowcount(self):
        return self._cur.rowcount if self._cur else 0

    @property
    def lastrowid(self):
        return self._cur.lastrowid if self._cur else None

    def fetchone(self):
        if self._cur is None:
            return None
        row = self._cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        if self._cur is None:
            return []
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_db():
    """
    Return a database connection for this request.

    If called inside a Flask request context, the connection is stored in
    g._pg_conn and reused for the lifetime of the request (teardown closes it).

    If called outside a request context (e.g. init_db), a fresh connection is
    returned that the caller is responsible for closing.
    """
    try:
        # Inside a request context — share the connection.
        if "_pg_conn" in g:
            return _BorrowedConnection(g._pg_conn)
        conn = _open_connection()
        g._pg_conn = conn
        return _BorrowedConnection(conn)
    except RuntimeError:
        # Outside request context (e.g., seeds/init_db called from app factory).
        return _open_connection()


def _open_connection():
    """Open a fresh database connection based on environment configuration."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _open_postgres(database_url)
    # Fall back to config object if available.
    try:
        from flask import current_app
        cfg = current_app.config.get("UFIT_CONFIG")
        if cfg and cfg.DATABASE_URL:
            return _open_postgres(cfg.DATABASE_URL)
        db_path = cfg.DB_PATH if cfg else "ufit_motion.db"
    except RuntimeError:
        db_path = os.environ.get("DB_PATH", "ufit_motion.db")
    return _open_sqlite(db_path)


def _open_postgres(database_url: str) -> PostgresConnection:
    """
    Open a Postgres connection, trying the Supabase pooler DSNs first and
    falling back to the original URL on failure.
    """
    try:
        import psycopg
    except ImportError:
        raise RuntimeError(
            "psycopg (psycopg3) is required for Postgres support. "
            "Install it with: pip install psycopg[binary]"
        )

    dsns = _supabase_pooler_dsns(database_url)
    last_error: Optional[Exception] = None
    for dsn in dsns:
        try:
            conn = psycopg.connect(dsn, autocommit=False)
            return PostgresConnection(conn)
        except Exception as e:
            last_error = e
            continue

    # Try the original URL as final fallback.
    try:
        conn = psycopg.connect(database_url, autocommit=False)
        return PostgresConnection(conn)
    except Exception as e:
        last_error = e

    raise RuntimeError(
        f"Could not connect to Postgres. Last error: {last_error}"
    )


def _open_sqlite(db_path: str) -> _SQLiteConnection:
    # Detect SQLite URI format (e.g. "file:name?mode=memory&cache=shared") so
    # tests can share a single in-memory database across connections.
    is_uri = db_path.startswith("file:")
    conn = sqlite3.connect(db_path, uri=is_uri, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return _SQLiteConnection(conn)


# ---------------------------------------------------------------------------
# Helper: safe ALTER TABLE ADD COLUMN IF NOT EXISTS (SQLite compat)
# ---------------------------------------------------------------------------

_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def ensure_column(conn, table: str, column: str, column_def: str) -> None:
    """
    Add `column` to `table` with `column_def` if it doesn't already exist.
    Works for both SQLite (no IF NOT EXISTS on ALTER TABLE ADD COLUMN in older
    versions) and Postgres.

    Usage:
        ensure_column(db, "users", "avatar_url", "TEXT DEFAULT NULL")
    """
    if not _SAFE_IDENTIFIER.match(table) or not _SAFE_IDENTIFIER.match(column):
        raise ValueError(f"Invalid identifier in ensure_column: table={table!r} column={column!r}")

    database_url = os.environ.get("DATABASE_URL")
    is_postgres = bool(database_url)

    if is_postgres:
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_def}"
            )
            conn.commit()
        except Exception:
            conn.rollback()
    else:
        # SQLite: check information_schema equivalent via PRAGMA.
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {r["name"] for r in rows}
        if column not in existing:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {column_def}"
                )
                conn.commit()
            except Exception:
                conn.rollback()
