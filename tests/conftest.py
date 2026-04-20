"""
conftest.py — pytest fixtures for Ufit Motion test suite.

Fixtures (original):
  app           — Flask test application backed by SQLite in-memory DB
  client        — unauthenticated Flask test client
  admin_client  — test client with an admin (role=admin) session pre-set
  coach_client  — test client with a head_coach session pre-set

Fixtures (Phase 2A — Session Logging):
  make_user_with_staff   — factory: create a user + staff_profile + optional staff_assignment
  make_org               — factory: create an organization row
  make_region            — factory: create a region row
  make_school            — factory: create a school (requires org; region optional)
  make_program           — factory: create a program at a given school
  make_student           — factory: create an active student at a given school
  make_session           — factory: create a sessions row + session_staff (lead) row
  make_eod_report        — factory: create an eod_reports row for a given staff/school/date
  authenticated_client   — factory: return a test client with a given user_id in the session

All factory fixtures are function-scoped.  Each factory creates rows inside the
shared Flask in-memory DB (via get_db() inside an app_context), matching the
pattern used by the existing admin_client / coach_client fixtures.
"""

import os
import pytest
from werkzeug.security import generate_password_hash

# Force SQLite in-memory for all tests by clearing DATABASE_URL before imports.
# Use the shared-cache URI form so every connection in this process opens the
# same in-memory database.  The named database "ufit_test" is local to this
# process and vanishes when all connections close.
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = "file:ufit_test?mode=memory&cache=shared"
os.environ["APP_ENV"] = "test"
os.environ["UFIT_SECRET_KEY"] = "test-secret-key-not-for-production"


# ===========================================================================
# Core app / client fixtures (unchanged from original)
# ===========================================================================

_SHARED_DB_URI = "file:ufit_test?mode=memory&cache=shared"


@pytest.fixture(scope="session")
def _anchor_conn():
    """
    Hold one open connection to the shared-cache in-memory database for the
    entire test session.

    SQLite drops a named in-memory shared-cache database when the last
    connection to it closes.  The Flask app's teardown hook closes its
    connection after create_app() finishes — which would destroy the schema
    before any test runs.  Keeping this connection open prevents that.
    Must be listed before the `app` fixture so it is created first.
    """
    from app.database import _open_sqlite
    conn = _open_sqlite(_SHARED_DB_URI)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def app(_anchor_conn):
    """
    Create a Flask application configured for testing.

    Uses a named SQLite shared-cache in-memory database so every connection
    in the process (Flask g, factories, verification queries) sees the same
    schema and data.  The anchor connection keeps the DB alive for the full
    session.
    """
    from app import create_app
    from app.config import Config

    cfg = Config(
        SECRET_KEY="test-secret-key-not-for-production",
        DATABASE_URL=None,
        DB_PATH=_SHARED_DB_URI,
        APP_ENV="test",
        APP_BASE_URL="http://localhost:5000",
    )

    flask_app = create_app(config=cfg)
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app


@pytest.fixture(scope="session")
def _db(app):
    """
    Return a long-lived database connection for the test session.
    Used by fixture helpers that need to pre-populate data.
    Connects to the same shared in-memory database as the Flask app.
    """
    from app.database import _open_sqlite
    conn = _open_sqlite("file:ufit_test?mode=memory&cache=shared")
    yield conn
    conn.close()


@pytest.fixture()
def client(app):
    """Unauthenticated Flask test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture()
def admin_client(app):
    """
    Flask test client with an admin user pre-authenticated in the session.

    Creates the admin user directly in the database if it doesn't already
    exist (the seeds.py default admin satisfies this in most runs).
    """
    with app.test_client() as c:
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc

            db = get_db()
            row = db.execute(
                "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL",
                ("admin@ufit.com",),
            ).fetchone()

            if row is None:
                ph = generate_password_hash("admin123")
                ts = now_utc()
                cur = db.execute(
                    """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                          active_status, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    ("admin", "Admin", "User", "admin@ufit.com", ph, ts),
                )
                db.commit()
                admin_id = cur.lastrowid
            else:
                admin_id = row["user_id"]

            db.close()

        with c.session_transaction() as sess:
            sess["user_id"] = admin_id

        yield c


@pytest.fixture()
def coach_client(app):
    """
    Flask test client with a head_coach user pre-authenticated in the session.

    Creates a test coach user if one doesn't already exist.
    """
    with app.test_client() as c:
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc

            db = get_db()
            row = db.execute(
                "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL",
                ("coach@ufit.com",),
            ).fetchone()

            if row is None:
                ph = generate_password_hash("coach123")
                ts = now_utc()
                cur = db.execute(
                    """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                          active_status, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    ("head_coach", "Test", "Coach", "coach@ufit.com", ph, ts),
                )
                db.commit()
                coach_id = cur.lastrowid
            else:
                coach_id = row["user_id"]

            db.close()

        with c.session_transaction() as sess:
            sess["user_id"] = coach_id

        yield c


# ===========================================================================
# Phase 2A factory fixtures
# ===========================================================================

@pytest.fixture()
def make_org(app):
    """
    Factory: create an organization row.

    Usage:
        org_id = make_org("Downtown USD")

    Returns the new organization_id (integer).
    """
    created_ids = []

    def _make(name="Test Organization"):
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            cur = db.execute(
                """INSERT INTO organizations
                   (organization_name, organization_type, contract_status, created_at)
                   VALUES (?, 'school_district', 'active', ?)""",
                (name, now_utc()),
            )
            db.commit()
            org_id = cur.lastrowid
            db.close()
        created_ids.append(org_id)
        return org_id

    yield _make

    # Cleanup: delete in reverse to respect FK constraints.
    with app.app_context():
        from app.database import get_db
        db = get_db()
        for oid in reversed(created_ids):
            db.execute("DELETE FROM organizations WHERE organization_id = ?", (oid,))
        db.commit()
        db.close()


@pytest.fixture()
def make_region(app):
    """
    Factory: create a region row.

    Usage:
        region_id = make_region("Bay Area")

    Returns the new region_id (integer).
    """
    created_ids = []

    def _make(name=None):
        import time
        unique_name = name or f"Test Region {time.time_ns()}"
        with app.app_context():
            from app.database import get_db
            db = get_db()
            cur = db.execute(
                "INSERT INTO regions (region_name, state) VALUES (?, 'CA')",
                (unique_name,),
            )
            db.commit()
            rid = cur.lastrowid
            db.close()
        created_ids.append(rid)
        return rid

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for rid in reversed(created_ids):
            db.execute("DELETE FROM regions WHERE region_id = ?", (rid,))
        db.commit()
        db.close()


@pytest.fixture()
def make_school(app):
    """
    Factory: create a school row.

    Usage:
        school_id = make_school(org_id, region_id=region_id, name="Lincoln ES")

    Arguments:
        org_id     — required, must exist in organizations
        region_id  — optional; if None the school has no region
        name       — optional, defaults to a unique generated name

    Returns the new school_id (integer).
    """
    created_ids = []

    def _make(org_id, region_id=None, name=None):
        import time
        unique_name = name or f"Test School {time.time_ns()}"
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            cur = db.execute(
                """INSERT INTO schools
                   (organization_id, region_id, school_name, active_status, created_at)
                   VALUES (?, ?, ?, 1, ?)""",
                (org_id, region_id, unique_name, now_utc()),
            )
            db.commit()
            sid = cur.lastrowid
            db.close()
        created_ids.append(sid)
        return sid

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for sid in reversed(created_ids):
            db.execute("DELETE FROM schools WHERE school_id = ?", (sid,))
        db.commit()
        db.close()


@pytest.fixture()
def make_program(app):
    """
    Factory: create a programs row at a given school.

    Usage:
        program_id = make_program(school_id, name="PE Support 2025-26")

    Arguments:
        school_id      — required
        name           — optional
        status         — optional, defaults to 'active'

    Returns the new program_id (integer).
    """
    created_ids = []

    def _make(school_id, name="PE Support — 2025-26", status="active"):
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            cur = db.execute(
                """INSERT INTO programs
                   (school_id, program_name, program_type, start_date, program_status, created_at)
                   VALUES (?, ?, 'pe_support', '2025-08-01', ?, ?)""",
                (school_id, name, status, now_utc()),
            )
            db.commit()
            pid = cur.lastrowid
            db.close()
        created_ids.append(pid)
        return pid

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for pid in reversed(created_ids):
            db.execute("DELETE FROM programs WHERE program_id = ?", (pid,))
        db.commit()
        db.close()


@pytest.fixture()
def make_student(app):
    """
    Factory: create an active student at a given school.

    Usage:
        student_id = make_student(school_id, first="Alex", last="Smith")

    Returns the new student_id (integer).
    """
    created_ids = []

    def _make(school_id, first="Test", last="Student", grade="3", active=True):
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            cur = db.execute(
                """INSERT INTO students
                   (school_id, student_first_name, student_last_name,
                    grade_level, active_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (school_id, first, last, grade, 1 if active else 0, now_utc()),
            )
            db.commit()
            stud_id = cur.lastrowid
            db.close()
        created_ids.append(stud_id)
        return stud_id

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for stud_id in reversed(created_ids):
            db.execute("DELETE FROM students WHERE student_id = ?", (stud_id,))
        db.commit()
        db.close()


@pytest.fixture()
def make_user_with_staff(app):
    """
    Factory: create a user row + staff_profiles row + optional staff_assignments row.

    Usage:
        result = make_user_with_staff(
            role="head_coach",
            school_id=4,            # if provided, creates a staff_assignment
            assigned_region_id=None,  # sets staff_profiles.assigned_region_id
            email="coach1@ufit.com",
        )
        # result["user_id"], result["staff_id"], result["assignment_id"]

    Arguments:
        role               — user role string (e.g. 'head_coach')
        school_id          — if provided, an active staff_assignment is created
        assigned_region_id — if provided, sets staff_profiles.assigned_region_id
        email              — optional, auto-generated if omitted
        first_name         — optional
        last_name          — optional
        no_staff_profile   — if True, skips staff_profiles row (for test_no_staff_profile)

    Returns a dict with keys: user_id, staff_id (or None), assignment_id (or None).
    """
    created_user_ids = []

    def _make(
        role="head_coach",
        school_id=None,
        assigned_region_id=None,
        email=None,
        first_name="Test",
        last_name="Coach",
        no_staff_profile=False,
    ):
        import time
        unique_email = email or f"testuser_{time.time_ns()}@ufit.com"

        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc

            db = get_db()
            ts = now_utc()
            ph = generate_password_hash("testpass123", method="pbkdf2:sha256")

            # Create user
            cur = db.execute(
                """INSERT INTO users
                   (role, first_name, last_name, email, password_hash, active_status, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (role, first_name, last_name, unique_email, ph, ts),
            )
            db.commit()
            user_id = cur.lastrowid

            staff_id = None
            assignment_id = None

            if not no_staff_profile:
                # Create staff_profile
                cur = db.execute(
                    """INSERT INTO staff_profiles
                       (user_id, employee_type, assigned_region_id, status, created_at)
                       VALUES (?, 'full_time', ?, 'active', ?)""",
                    (user_id, assigned_region_id, ts),
                )
                db.commit()
                staff_id = cur.lastrowid

                if school_id is not None:
                    # Create active staff_assignment
                    cur = db.execute(
                        """INSERT INTO staff_assignments
                           (staff_id, school_id, assignment_role, start_date, active_status, created_at)
                           VALUES (?, ?, ?, '2025-08-01', 1, ?)""",
                        (staff_id, school_id, role, ts),
                    )
                    db.commit()
                    assignment_id = cur.lastrowid

            db.close()

        created_user_ids.append(user_id)
        return {
            "user_id": user_id,
            "staff_id": staff_id,
            "assignment_id": assignment_id,
            "email": unique_email,
        }

    yield _make

    # Cleanup — cascading deletes via FK: deleting the user removes staff_profile
    # and staff_assignments via ON DELETE CASCADE.
    with app.app_context():
        from app.database import get_db
        db = get_db()
        for uid in reversed(created_user_ids):
            db.execute("DELETE FROM users WHERE user_id = ?", (uid,))
        db.commit()
        db.close()


@pytest.fixture()
def make_session(app):
    """
    Factory: create a sessions row + one session_staff row (lead).

    Usage:
        session_id = make_session(
            school_id=4,
            program_id=7,
            staff_id=2,
            session_date="2026-04-19",
        )

    Returns the new session_id (integer).
    """
    created_ids = []

    def _make(
        school_id,
        program_id,
        staff_id,
        session_date="2026-04-15",
        session_type="regular",
        session_status="completed",
        total_students_present=0,
    ):
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc

            db = get_db()
            ts = now_utc()

            cur = db.execute(
                """INSERT INTO sessions
                   (school_id, program_id, session_date, session_type,
                    session_status, total_students_present, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (school_id, program_id, session_date, session_type,
                 session_status, total_students_present, ts),
            )
            db.commit()
            sess_id = cur.lastrowid

            # Insert session_staff (lead)
            db.execute(
                """INSERT INTO session_staff (session_id, staff_id, role)
                   VALUES (?, ?, 'lead')""",
                (sess_id, staff_id),
            )
            db.commit()
            db.close()

        created_ids.append(sess_id)
        return sess_id

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for sess_id in reversed(created_ids):
            # session_staff cascades on delete
            db.execute("DELETE FROM sessions WHERE session_id = ?", (sess_id,))
        db.commit()
        db.close()


@pytest.fixture()
def make_eod_report(app):
    """
    Factory: create an eod_reports row.

    Usage:
        eod_id = make_eod_report(
            school_id=4,
            staff_id=2,
            report_date="2026-04-19",
        )

    Returns the new eod_id (integer).

    Note: eod_filed logic in GET /api/sessions keys on
          (staff_id, school_id, report_date) — not session_id.
    """
    created_ids = []

    def _make(school_id, staff_id, report_date="2026-04-15", deleted_at=None):
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc

            db = get_db()
            ts = now_utc()
            cur = db.execute(
                """INSERT INTO eod_reports
                   (school_id, staff_id, report_date, activities_completed,
                    student_engagement_summary, created_at, deleted_at)
                   VALUES (?, ?, ?, 'Test activities', 'Good engagement', ?, ?)""",
                (school_id, staff_id, report_date, ts, deleted_at),
            )
            db.commit()
            eod_id = cur.lastrowid
            db.close()

        created_ids.append(eod_id)
        return eod_id

    yield _make

    with app.app_context():
        from app.database import get_db
        db = get_db()
        for eod_id in reversed(created_ids):
            db.execute("DELETE FROM eod_reports WHERE eod_id = ?", (eod_id,))
        db.commit()
        db.close()


@pytest.fixture()
def authenticated_client(app):
    """
    Factory: return a Flask test client with the given user_id in the session.

    Usage:
        with authenticated_client(user_id) as c:
            resp = c.post("/api/sessions", json={...})

    Yields a context manager — use as `with authenticated_client(uid) as c`.
    """
    import contextlib

    @contextlib.contextmanager
    def _make(user_id):
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess["user_id"] = user_id
            yield c

    return _make
