"""tests/test_audit_log_viewer.py — C11 GET /api/admin/audit-log."""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def test_audit_log_requires_admin(client):
    resp = client.get("/api/admin/audit-log")
    assert resp.status_code in (401, 403)


def test_audit_log_returns_recent_entries(admin_client, app):
    # Trigger an audit-write via a known endpoint (admin login via fixture
    # doesn't always emit audit; create a school to guarantee an audit row).
    from app.database import get_db
    from app.routes._helpers import audit, now_utc
    with app.app_context():
        db = get_db()
        audit(db, None, "TEST_ACTION", "schools", 42,
              new_values={"foo": "bar"})
        db.commit()
    resp = admin_client.get(
        "/api/admin/audit-log?limit=10",
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["entries"], list)
    actions = [e["action"] for e in body["entries"]]
    assert "TEST_ACTION" in actions


def test_audit_log_filters_by_action(admin_client, app):
    from app.database import get_db
    from app.routes._helpers import audit
    with app.app_context():
        db = get_db()
        audit(db, None, "FILTER_ME_PLEASE", "schools", 7,
              new_values={"k": "v"})
        db.commit()
    resp = admin_client.get(
        "/api/admin/audit-log?action=FILTER_ME_PLEASE",
        headers=_xhr(admin_client),
    )
    body = resp.get_json()
    assert all(e["action"] == "FILTER_ME_PLEASE" for e in body["entries"])
    assert len(body["entries"]) >= 1


def test_audit_log_filters_by_record_id(admin_client, app):
    from app.database import get_db
    from app.routes._helpers import audit
    with app.app_context():
        db = get_db()
        audit(db, None, "WIDGET_TOUCHED", "widgets", 9999, new_values={})
        audit(db, None, "WIDGET_TOUCHED", "widgets", 8888, new_values={})
        db.commit()
    resp = admin_client.get(
        "/api/admin/audit-log?record_id=9999&action=WIDGET_TOUCHED",
        headers=_xhr(admin_client),
    )
    body = resp.get_json()
    assert all(e["record_id"] == 9999 for e in body["entries"])


def test_audit_log_caps_limit_at_500(admin_client):
    resp = admin_client.get(
        "/api/admin/audit-log?limit=10000",
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["limit"] == 500
