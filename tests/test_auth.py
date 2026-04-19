"""
test_auth.py — Tests for the /api/auth/* endpoints.

Covers:
  1. Login with wrong password returns 401.
  2. Login with correct password but wrong portal returns 403.
  3. POST /api/auth/setup-admin creates a new admin user when none exists.
  4. GET /api/auth/session returns 401 when not logged in.
"""

import json
import pytest
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_json(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Fixture: ensure a test user exists for login tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=False)
def login_test_user(app):
    """
    Create a known test user (head_coach) for login tests.
    Tears down by soft-deleting after the test so state doesn't leak.
    """
    email = "logintest@ufit.com"
    password = "correctpassword"

    with app.app_context():
        from app.database import get_db
        from app.routes._helpers import now_utc

        db = get_db()
        # Remove any previous test remnant.
        db.execute("DELETE FROM users WHERE email = ?", (email,))
        db.commit()

        ph = generate_password_hash(password)
        ts = now_utc()
        cur = db.execute(
            """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                  active_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)""",
            ("head_coach", "Login", "Tester", email, ph, ts, ts),
        )
        db.commit()
        user_id = cur.lastrowid
        db.close()

    yield {"email": email, "password": password, "user_id": user_id}

    # Cleanup
    with app.app_context():
        from app.database import get_db
        db = get_db()
        db.execute("DELETE FROM users WHERE email = ?", (email,))
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# TEST 1: Login with wrong password returns 401
# ---------------------------------------------------------------------------

def test_login_wrong_password_returns_401(client, login_test_user):
    """
    Submitting a valid email to the correct portal but wrong password
    must return HTTP 401 with an error message.
    """
    response = _post_json(client, "/api/auth/login", {
        "email": login_test_user["email"],
        "password": "wrongpassword",
        "portal": "coach",
    })
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "error" in data


# ---------------------------------------------------------------------------
# TEST 2: Login with wrong portal returns 403
# ---------------------------------------------------------------------------

def test_login_wrong_portal_returns_403(client, login_test_user):
    """
    Submitting correct credentials but for the wrong portal (a head_coach
    trying to log in via the admin portal) must return HTTP 403.
    """
    response = _post_json(client, "/api/auth/login", {
        "email": login_test_user["email"],
        "password": login_test_user["password"],
        "portal": "admin",   # head_coach is not allowed here
    })
    assert response.status_code == 403
    data = json.loads(response.data)
    assert "error" in data


# ---------------------------------------------------------------------------
# TEST 3: setup-admin creates user when no admin exists
# ---------------------------------------------------------------------------

def test_setup_admin_creates_user(app, client):
    """
    POST /api/auth/setup-admin should create an admin user and return 201
    when no admin/ceo users currently exist.

    We use a unique email to avoid conflicting with the default seeded admin.
    If the default admin already exists, setup-admin correctly returns 409 —
    in that case we verify that behaviour instead.
    """
    unique_email = "firstceo@ufit.com"

    with app.app_context():
        from app.database import get_db
        db = get_db()
        # Check whether any admin already exists.
        existing = db.execute(
            "SELECT user_id FROM users WHERE role IN ('ceo', 'admin') AND deleted_at IS NULL LIMIT 1"
        ).fetchone()
        db.close()

    if existing:
        # The default seeded admin exists — confirm setup-admin returns 409.
        response = _post_json(client, "/api/auth/setup-admin", {
            "first_name": "First",
            "last_name": "CEO",
            "email": unique_email,
            "password": "securepass123",
            "role": "ceo",
        })
        assert response.status_code == 409
        data = json.loads(response.data)
        assert "error" in data
    else:
        # No admin exists — setup-admin should succeed.
        response = _post_json(client, "/api/auth/setup-admin", {
            "first_name": "First",
            "last_name": "CEO",
            "email": unique_email,
            "password": "securepass123",
            "role": "ceo",
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data.get("ok") is True
        assert "user" in data
        assert data["user"]["role"] == "ceo"
        assert data["user"]["email"] == unique_email
        # Sensitive fields must NOT be present.
        assert "password_hash" not in data["user"]
        assert "auth_uid" not in data["user"]

        # Cleanup: remove the test CEO so other tests aren't affected.
        with app.app_context():
            from app.database import get_db
            db = get_db()
            db.execute("DELETE FROM users WHERE email = ?", (unique_email,))
            db.commit()
            db.close()


# ---------------------------------------------------------------------------
# TEST 4: session endpoint returns 401 when not logged in
# ---------------------------------------------------------------------------

def test_session_returns_401_when_not_logged_in(client):
    """
    GET /api/auth/session must return HTTP 401 for an unauthenticated client.
    """
    response = client.get("/api/auth/session")
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "error" in data
