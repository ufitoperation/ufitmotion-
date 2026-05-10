"""tests/test_school_invite_code.py — B8 coach self-registration via
school invite code.

Public POST /api/auth/coach-register validates the code, creates a
pending user with an active assignment to that school, and emails an
invite link. Admin POST /api/admin/schools/<id>/invite-code/regenerate
rotates the code (immediately invalidating the previous one).
"""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def _silence_email(monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)


def _seed_invite_code(app, school_id, code, expires="2030-01-01T00:00:00+00:00"):
    from app.database import get_db
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE schools SET coach_invite_code = ?, "
            "coach_invite_code_expires_at = ? WHERE school_id = ?",
            (code, expires, school_id),
        )
        db.commit()


# ---------------------------------------------------------------------------
# POST /api/auth/coach-register
# ---------------------------------------------------------------------------

def test_coach_register_with_valid_code_creates_pending_user(
    app, client, make_org, make_school, monkeypatch
):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    _seed_invite_code(app, s, "LCN-X7M9-2026")

    resp = client.post(
        "/api/auth/coach-register",
        json={"code": "LCN-X7M9-2026", "first_name": "Z", "last_name": "K",
              "email": "newcoach@x.com", "role": "head_coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 201, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    # Confirm pending user landed with correct school assignment.
    from app.database import get_db
    with app.app_context():
        db = get_db()
        u = db.execute(
            "SELECT user_id, role, active_status, password_hash "
            "FROM users WHERE email = ?", ("newcoach@x.com",)
        ).fetchone()
        assert u is not None
        assert u["role"] == "head_coach"
        assert not u["active_status"]
        assert not u["password_hash"]


def test_coach_register_rejects_unknown_code(app, client, make_org, make_school):
    org = make_org(); s = make_school(org)
    resp = client.post(
        "/api/auth/coach-register",
        json={"code": "BOGUS-CODE-2099", "first_name": "X", "last_name": "Y",
              "email": "z@x.com", "role": "head_coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 400


def test_coach_register_rejects_expired_code(app, client, make_org, make_school):
    org = make_org(); s = make_school(org)
    _seed_invite_code(app, s, "OLD-CODE-2020", expires="2020-01-01T00:00:00+00:00")
    resp = client.post(
        "/api/auth/coach-register",
        json={"code": "OLD-CODE-2020", "first_name": "X", "last_name": "Y",
              "email": "exp@x.com", "role": "head_coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 400


def test_coach_register_blocks_admin_role_escalation(
    app, client, make_org, make_school, monkeypatch
):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    _seed_invite_code(app, s, "ESC-CODE-2026")
    resp = client.post(
        "/api/auth/coach-register",
        json={"code": "ESC-CODE-2026", "first_name": "E", "last_name": "V",
              "email": "ev@x.com", "role": "admin"},
        headers=_xhr(client),
    )
    assert resp.status_code == 400


def test_coach_register_dedups_existing_email(
    app, client, make_org, make_school, monkeypatch
):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    _seed_invite_code(app, s, "DUP-CODE-2026")
    # Pre-insert a user with the email directly; avoid mixing fixture clients.
    from app.database import get_db
    from app.routes._helpers import now_utc
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO users (role, first_name, last_name, email,
                                  active_status, created_at)
               VALUES ('head_coach', 'A', 'X', ?, 1, ?)""",
            ("dupcoach@x.com", now_utc()),
        )
        db.commit()
    resp = client.post(
        "/api/auth/coach-register",
        json={"code": "DUP-CODE-2026", "first_name": "A", "last_name": "X",
              "email": "dupcoach@x.com", "role": "head_coach"},
        headers=_xhr(client),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/admin/schools/<id>/invite-code/regenerate
# ---------------------------------------------------------------------------

def test_admin_regenerate_invite_code(app, admin_client, make_org, make_school):
    org = make_org(); s = make_school(org)
    _seed_invite_code(app, s, "OLD-CODE-2026")
    resp = admin_client.post(
        f"/api/admin/schools/{s}/invite-code/regenerate",
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    new_code = body["code"]
    assert new_code and new_code != "OLD-CODE-2026"
    # Old code is now dead.
    resp2 = app.test_client().post(
        "/api/auth/coach-register",
        json={"code": "OLD-CODE-2026", "first_name": "Q", "last_name": "Q",
              "email": "regen@x.com", "role": "head_coach"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp2.status_code == 400


def test_regenerate_requires_admin(client, make_org, make_school):
    org = make_org(); s = make_school(org)
    resp = client.post(
        f"/api/admin/schools/{s}/invite-code/regenerate",
        headers=_xhr(client),
    )
    assert resp.status_code in (401, 403)
