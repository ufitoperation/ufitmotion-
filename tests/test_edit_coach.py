"""tests/test_edit_coach.py — PATCH /api/admin/users/<id>/role.

Edits a non-CEO/admin user's role and replaces their staff_assignments
atomically. Audit row 'role_changed' captures old + new state.
"""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def test_admin_can_change_coach_role(
    admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="assistant_coach", school_id=s, email="ac@x.com")
    resp = admin_client.patch(
        f"/api/admin/users/{u['user_id']}/role",
        json={"role": "head_coach", "school_ids": [s]},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200, resp.data


def test_admin_cannot_promote_to_ceo(
    admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="head_coach", school_id=s, email="hc@x.com")
    resp = admin_client.patch(
        f"/api/admin/users/{u['user_id']}/role",
        json={"role": "ceo", "school_ids": [s]},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 403


def test_admin_cannot_promote_to_admin(
    admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="head_coach", school_id=s, email="hc2@x.com")
    resp = admin_client.patch(
        f"/api/admin/users/{u['user_id']}/role",
        json={"role": "admin", "school_ids": [s]},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 403


def test_self_role_change_blocked(admin_client):
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        uid = db.execute(
            "SELECT user_id FROM users WHERE email = ?", ("admin@ufit.com",)
        ).fetchone()["user_id"]
    resp = admin_client.patch(
        f"/api/admin/users/{uid}/role",
        json={"role": "head_coach", "school_ids": []},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 409


def test_role_change_replaces_assignments_atomically(
    app, admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org()
    s1 = make_school(org); s2 = make_school(org); s3 = make_school(org)
    u = make_user_with_staff(role="head_coach", school_id=s1, email="hc3@x.com")

    resp = admin_client.patch(
        f"/api/admin/users/{u['user_id']}/role",
        json={"role": "assistant_coach", "school_ids": [s2, s3]},
        headers=_xhr(admin_client),
    )
    assert resp.status_code == 200

    from app.database import get_db
    with app.app_context():
        db = get_db()
        active = db.execute(
            """SELECT sa.school_id FROM staff_assignments sa
               JOIN staff_profiles sp ON sp.staff_id = sa.staff_id
               WHERE sp.user_id = ? AND sa.active_status = TRUE
               ORDER BY sa.school_id""",
            (u["user_id"],),
        ).fetchall()
        active_ids = sorted([r["school_id"] for r in active])
        # The original s1 assignment is now inactive; s2 + s3 are active.
        assert active_ids == sorted([s2, s3])

        role = db.execute(
            "SELECT role FROM users WHERE user_id = ?", (u["user_id"],)
        ).fetchone()["role"]
        assert role == "assistant_coach"


def test_role_change_writes_audit_log(
    app, admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="assistant_coach", school_id=s, email="ac2@x.com")
    admin_client.patch(
        f"/api/admin/users/{u['user_id']}/role",
        json={"role": "head_coach", "school_ids": [s]},
        headers=_xhr(admin_client),
    )

    from app.database import get_db
    with app.app_context():
        db = get_db()
        row = db.execute(
            """SELECT old_values, new_values FROM audit_log
               WHERE action = 'role_changed' AND record_id = ?
               ORDER BY log_id DESC LIMIT 1""",
            (u["user_id"],),
        ).fetchone()
    assert row is not None
    # SQLite returns these as text JSON — just check substrings.
    assert "assistant_coach" in (row["old_values"] or "")
    assert "head_coach" in (row["new_values"] or "")
