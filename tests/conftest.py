"""
conftest.py — pytest fixtures for Ufit Motion test suite.

Fixtures:
  app           — Flask test application backed by SQLite in-memory DB
  client        — unauthenticated Flask test client
  admin_client  — test client with an admin (role=admin) session pre-set
  coach_client  — test client with a head_coach session pre-set
"""

import os
import pytest
from werkzeug.security import generate_password_hash

# Force SQLite in-memory for all tests by clearing DATABASE_URL before imports.
os.environ.pop("DATABASE_URL", None)
os.environ["DB_PATH"] = ":memory:"
os.environ["APP_ENV"] = "test"
os.environ["UFIT_SECRET_KEY"] = "test-secret-key-not-for-production"


@pytest.fixture(scope="session")
def app():
    """
    Create a Flask application configured for testing.

    Uses SQLite in-memory so tests are fast and isolated — the DB is
    re-created fresh for each test session. The schema is applied by
    init_db() inside the app factory.
    """
    from app import create_app
    from app.config import Config

    cfg = Config(
        SECRET_KEY="test-secret-key-not-for-production",
        DATABASE_URL=None,
        DB_PATH=":memory:",
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
    """
    from app.database import _open_sqlite
    conn = _open_sqlite(":memory:")
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
                                          active_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)""",
                    ("admin", "Admin", "User", "admin@ufit.com", ph, ts, ts),
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
                                          active_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)""",
                    ("head_coach", "Test", "Coach", "coach@ufit.com", ph, ts, ts),
                )
                db.commit()
                coach_id = cur.lastrowid
            else:
                coach_id = row["user_id"]

            db.close()

        with c.session_transaction() as sess:
            sess["user_id"] = coach_id

        yield c
