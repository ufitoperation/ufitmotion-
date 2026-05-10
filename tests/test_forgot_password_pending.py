"""tests/test_forgot_password_pending.py — C13.

Pending-invite users (no password_hash, active_status=FALSE) must be able
to recover via /api/auth/forgot-password — they get a fresh invite link
instead of a password-reset link.
"""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def test_forgot_password_for_pending_user_emits_invite(
    app, client, monkeypatch
):
    sent = []
    monkeypatch.setattr(
        "app.email.send_invite_email",
        lambda to, fn, role, token: sent.append({"to": to, "kind": "invite", "token": token}) or True,
    )
    monkeypatch.setattr(
        "app.email.send_password_reset_email",
        lambda to, fn, token: sent.append({"to": to, "kind": "reset", "token": token}) or True,
    )

    # Insert a pending user (no password_hash, active_status=FALSE).
    from app.database import get_db
    from app.routes._helpers import now_utc
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO users (role, first_name, last_name, email, active_status, created_at)
               VALUES ('head_coach', 'Pen', 'Ding', ?, 0, ?)""",
            ("pending@x.com", now_utc()),
        )
        db.commit()

    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "pending@x.com"},
        headers=_xhr(client),
    )
    assert resp.status_code == 200
    assert sent and sent[0]["kind"] == "invite"
    assert sent[0]["to"] == "pending@x.com"


def test_forgot_password_for_active_user_emits_reset(app, client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.email.send_invite_email",
        lambda to, fn, role, token: sent.append({"to": to, "kind": "invite"}) or True,
    )
    monkeypatch.setattr(
        "app.email.send_password_reset_email",
        lambda to, fn, token: sent.append({"to": to, "kind": "reset"}) or True,
    )
    # admin@ufit.com is created by the admin_client fixture / seeds with a password.
    # We won't use admin_client itself; just trigger forgot-password directly.
    from app.database import get_db
    from app.routes._helpers import now_utc
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                  active_status, created_at)
               VALUES ('head_coach', 'Act', 'Ive', ?, ?, 1, ?)""",
            ("active@x.com", generate_password_hash("p@ssw0rd!", method="pbkdf2:sha256"),
             now_utc()),
        )
        db.commit()

    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "active@x.com"},
        headers=_xhr(client),
    )
    assert resp.status_code == 200
    assert sent and sent[0]["kind"] == "reset"


def test_forgot_password_unknown_email_still_200(client):
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody@nowhere.com"},
        headers=_xhr(client),
    )
    # Always 200 to avoid email enumeration.
    assert resp.status_code == 200
