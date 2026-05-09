"""tests/test_multi_school_picker.py — login returns assignments[],
new POST /api/auth/select-school sets session.current_school_id."""

from __future__ import annotations

from werkzeug.security import generate_password_hash


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def _set_password(app, user_id: int, plaintext: str):
    """Helper: directly set a known password on a user row."""
    from app.database import get_db
    with app.app_context():
        db = get_db()
        ph = generate_password_hash(plaintext, method="pbkdf2:sha256")
        db.execute(
            "UPDATE users SET password_hash = ?, active_status = TRUE WHERE user_id = ?",
            (ph, user_id),
        )
        db.commit()


def _add_assignment(app, staff_id: int, school_id: int, role: str = "head_coach"):
    """Helper: add a second active staff_assignment for an existing staff."""
    from app.database import get_db
    from app.routes._helpers import now_utc
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO staff_assignments
               (staff_id, school_id, assignment_role, start_date, active_status, created_at)
               VALUES (?, ?, ?, ?, TRUE, ?)""",
            (staff_id, school_id, role, "2025-08-01", now_utc()),
        )
        db.commit()


# ---------------------------------------------------------------------------
# Login response shape
# ---------------------------------------------------------------------------

def test_login_returns_assignments_array_for_multi_school_coach(
    app, client, make_org, make_school, make_user_with_staff
):
    org = make_org()
    s1 = make_school(org, name="Lincoln ES")
    s2 = make_school(org, name="Roosevelt ES")
    info = make_user_with_staff(role="head_coach", school_id=s1, email="multi@x.com")
    _add_assignment(app, info["staff_id"], s2, role="head_coach")
    _set_password(app, info["user_id"], "p@ssw0rd!")

    resp = client.post(
        "/api/auth/login",
        json={"email": "multi@x.com", "password": "p@ssw0rd!", "portal": "coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert "assignments" in body["user"]
    school_ids = {a["school_id"] for a in body["user"]["assignments"]}
    assert school_ids == {s1, s2}
    assert body.get("needs_school_selection") is True


def test_login_single_school_auto_selects(
    app, client, make_org, make_school, make_user_with_staff
):
    org = make_org()
    s1 = make_school(org, name="Lincoln ES")
    info = make_user_with_staff(role="head_coach", school_id=s1, email="solo@x.com")
    _set_password(app, info["user_id"], "p@ssw0rd!")

    resp = client.post(
        "/api/auth/login",
        json={"email": "solo@x.com", "password": "p@ssw0rd!", "portal": "coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    # Single assignment auto-selected — no picker needed.
    assert body.get("needs_school_selection") is False
    assert len(body["user"]["assignments"]) == 1


# ---------------------------------------------------------------------------
# POST /api/auth/select-school
# ---------------------------------------------------------------------------

def test_select_school_writes_session_for_assigned_school(
    app, client, make_org, make_school, make_user_with_staff
):
    org = make_org()
    s1 = make_school(org)
    s2 = make_school(org)
    info = make_user_with_staff(role="head_coach", school_id=s1, email="sel@x.com")
    _add_assignment(app, info["staff_id"], s2, role="head_coach")
    _set_password(app, info["user_id"], "p@ssw0rd!")

    # Log in first.
    client.post(
        "/api/auth/login",
        json={"email": "sel@x.com", "password": "p@ssw0rd!", "portal": "coach"},
        headers=_xhr(client),
    )
    # Switch to s2.
    resp = client.post(
        "/api/auth/select-school",
        json={"school_id": s2},
        headers=_xhr(client),
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["school"]["school_id"] == s2


def test_select_school_rejects_unassigned(
    app, client, make_org, make_school, make_user_with_staff
):
    org = make_org()
    s1 = make_school(org)
    s_other = make_school(org)
    info = make_user_with_staff(role="head_coach", school_id=s1, email="x1@x.com")
    _set_password(app, info["user_id"], "p@ssw0rd!")
    client.post(
        "/api/auth/login",
        json={"email": "x1@x.com", "password": "p@ssw0rd!", "portal": "coach"},
        headers=_xhr(client),
    )
    resp = client.post(
        "/api/auth/select-school",
        json={"school_id": s_other},
        headers=_xhr(client),
    )
    assert resp.status_code == 403


def test_select_school_requires_auth(client):
    resp = client.post(
        "/api/auth/select-school",
        json={"school_id": 1},
        headers=_xhr(client),
    )
    assert resp.status_code == 401
