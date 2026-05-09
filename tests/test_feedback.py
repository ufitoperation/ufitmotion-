"""tests/test_feedback.py — /api/feedback emails ops + audit-logs the message."""

from __future__ import annotations


def _xhr(client):
    """Helper: the CSRF guard requires X-Requested-With: XMLHttpRequest on POST /api/."""
    return {"X-Requested-With": "XMLHttpRequest"}


def test_feedback_requires_auth(client):
    resp = client.post(
        "/api/feedback",
        json={"subject": "x", "message": "y"},
        headers=_xhr(client),
    )
    assert resp.status_code == 401


def test_feedback_validates_required_fields(admin_client, monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)
    resp = admin_client.post(
        "/api/feedback",
        json={"subject": "", "message": ""},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 400


def test_feedback_emails_operations_and_audits(admin_client, monkeypatch):
    sent = []

    def fake_send(to, subject, html):
        sent.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr("app.email._send", fake_send)
    resp = admin_client.post(
        "/api/feedback",
        json={
            "subject": "login broken",
            "message": "I cannot log in this morning.",
            "page_url": "/login",
        },
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200, resp.data
    assert sent and sent[0]["to"] == "operations@ufitonline.net"
    assert "login broken" in sent[0]["subject"]
    assert "I cannot log in this morning." in sent[0]["html"]
    assert "/login" in sent[0]["html"]

    # Audit row written.
    from app import create_app
    from app.database import get_db
    with create_app().app_context():
        db = get_db()
        row = db.execute(
            """SELECT new_values FROM audit_log
               WHERE action = 'feedback_submitted'
               ORDER BY log_id DESC LIMIT 1"""
        ).fetchone()
    assert row is not None


def test_feedback_truncates_oversized_input(admin_client, monkeypatch):
    """Long inputs must be truncated to defend against abuse — server caps
    subject @ 200 chars and message @ 5000 chars."""
    sent = []
    monkeypatch.setattr(
        "app.email._send",
        lambda to, subj, html: sent.append({"subject": subj, "html": html}) or True,
    )
    long_subject = "S" * 600
    long_message = "M" * 9000
    resp = admin_client.post(
        "/api/feedback",
        json={"subject": long_subject, "message": long_message, "page_url": "/x"},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200
    # Subject in the email is "[Ufit Feedback] " + first 200 chars of subject.
    assert sent[0]["subject"] == "[Ufit Feedback] " + ("S" * 200)
    assert ("M" * 5000) in sent[0]["html"]
    assert ("M" * 5001) not in sent[0]["html"]
