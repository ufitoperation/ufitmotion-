"""tests/test_bulk_invite.py — POST /api/admin/coaches/bulk-invite

Bulk-create pending coach users (one per row), each with an invite token
and an emailed set-password link. Per-row try/except so a single bad row
doesn't kill the whole batch.
"""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def _silence_email(monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)


def test_bulk_invite_requires_admin(client, make_org, make_school):
    org = make_org(); s = make_school(org)
    resp = client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": [{"first_name": "A", "last_name": "X",
                        "email": "a@x.com", "role": "head_coach",
                        "school_ids": [s]}]},
        headers=_xhr(client),
    )
    assert resp.status_code in (401, 403)


def test_bulk_invite_creates_pending_users(admin_client, make_org, make_school, monkeypatch):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    rows = [
        {"first_name": "A", "last_name": "X", "email": "a@x.com",
         "role": "head_coach", "school_ids": [s]},
        {"first_name": "B", "last_name": "Y", "email": "b@y.com",
         "role": "assistant_coach", "school_ids": [s]},
    ]
    resp = admin_client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": rows},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["summary"]["created"] == 2
    assert body["summary"]["errors"] == 0
    assert body["summary"]["duplicates"] == 0


def test_bulk_invite_skips_duplicates_continues_batch(admin_client, make_org, make_school, monkeypatch):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    # Pre-create a user with the same email to trigger duplicate path.
    admin_client.post(
        "/api/users",
        json={"first_name": "A", "last_name": "X", "email": "dup@x.com",
              "role": "head_coach", "school_id": s},
        headers=_xhr(admin_client),
    )
    rows = [
        {"first_name": "A", "last_name": "X", "email": "dup@x.com",
         "role": "head_coach", "school_ids": [s]},
        {"first_name": "C", "last_name": "Z", "email": "fresh@z.com",
         "role": "head_coach", "school_ids": [s]},
    ]
    resp = admin_client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": rows},
        headers=_xhr(admin_client),
    )
    body = resp.get_json()
    assert body["summary"]["duplicates"] == 1
    assert body["summary"]["created"] == 1


def test_bulk_invite_per_row_validation_doesnt_kill_batch(admin_client, make_org, make_school, monkeypatch):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    rows = [
        {"first_name": "D", "last_name": "W", "email": "not-an-email",
         "role": "head_coach", "school_ids": [s]},  # invalid email
        {"first_name": "E", "last_name": "Q", "email": "good@q.com",
         "role": "head_coach", "school_ids": [s]},
    ]
    resp = admin_client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": rows},
        headers=_xhr(admin_client),
    )
    body = resp.get_json()
    assert body["summary"]["errors"] == 1
    assert body["summary"]["created"] == 1
    # Per-row results show which row failed.
    err_row = next(r for r in body["results"] if r["status"] == "error")
    assert "email" in (err_row.get("message") or "").lower()


def test_bulk_invite_blocks_admin_role_escalation(admin_client, make_org, make_school, monkeypatch):
    _silence_email(monkeypatch)
    org = make_org(); s = make_school(org)
    rows = [
        {"first_name": "Z", "last_name": "Z", "email": "bad@z.com",
         "role": "admin", "school_ids": [s]},
    ]
    resp = admin_client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": rows},
        headers=_xhr(admin_client),
    )
    body = resp.get_json()
    # admin/ceo are not bulk-invitable from this endpoint — must error.
    assert body["summary"]["errors"] == 1


def test_bulk_invite_caps_batch_size(admin_client, monkeypatch):
    _silence_email(monkeypatch)
    huge = [{"first_name": "x", "last_name": "y", "email": f"a{i}@x.com",
             "role": "head_coach", "school_ids": []} for i in range(250)]
    resp = admin_client.post(
        "/api/admin/coaches/bulk-invite",
        json={"rows": huge},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 400
