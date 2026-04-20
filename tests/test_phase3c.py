"""
tests/test_phase3c.py — Phase 3C route tests.

Covers:
  POST   /api/schools
  PATCH  /api/schools/<id>
  POST   /api/users
  POST   /api/admin/eod-alerts
"""

import datetime
import pytest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FREEZE_DT = datetime.datetime(2026, 4, 20, 8, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
_TODAY = "2026-04-20"


def _freeze_today(monkeypatch):
    """Patch _now_pacific in admin_routes to return a fixed Pacific datetime."""
    monkeypatch.setattr(
        "app.routes.admin_routes._now_pacific",
        lambda: _FREEZE_DT,
    )


# ---------------------------------------------------------------------------
# POST /api/schools
# ---------------------------------------------------------------------------

class TestPostSchools:

    def test_create_school_minimal_success(self, admin_client, make_org):
        org_id = make_org("Sunrise USD")
        resp = admin_client.post("/api/schools", json={
            "organization_id": org_id,
            "school_name": "Lincoln Elementary",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert data["school"]["school_name"] == "Lincoln Elementary"
        assert "school_id" in data["school"]

    def test_create_school_all_optional_fields(self, admin_client, make_org, make_region):
        org_id = make_org("Valley USD")
        region_id = make_region()
        resp = admin_client.post("/api/schools", json={
            "organization_id": org_id,
            "school_name": "Jefferson Middle School",
            "school_type": "middle",
            "principal_name": "Jane Doe",
            "principal_email": "jane.doe@valley.edu",
            "region_id": region_id,
            "address": "123 Main St",
            "city": "Sacramento",
            "state": "CA",
            "zip_code": "95814",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert data["school"]["school_name"] == "Jefferson Middle School"

    def test_create_school_calls_principal_sync_when_both_provided(
        self, admin_client, make_org
    ):
        org_id = make_org("Sync Test USD")
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.post("/api/schools", json={
                "organization_id": org_id,
                "school_name": "Sync School",
                "principal_name": "Alice Smith",
                "principal_email": "alice@synctest.edu",
            })
        assert resp.status_code == 201
        mock_sync.assert_called_once()

    def test_create_school_no_sync_when_only_principal_name(self, admin_client, make_org):
        org_id = make_org("No Sync USD A")
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.post("/api/schools", json={
                "organization_id": org_id,
                "school_name": "No Sync School A",
                "principal_name": "Bob Jones",
            })
        assert resp.status_code == 201
        mock_sync.assert_not_called()

    def test_create_school_no_sync_when_only_principal_email(self, admin_client, make_org):
        org_id = make_org("No Sync USD B")
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.post("/api/schools", json={
                "organization_id": org_id,
                "school_name": "No Sync School B",
                "principal_email": "bob@nosync.edu",
            })
        assert resp.status_code == 201
        mock_sync.assert_not_called()

    def test_create_school_missing_organization_id_returns_400(self, admin_client):
        resp = admin_client.post("/api/schools", json={
            "school_name": "Missing Org School",
        })
        assert resp.status_code == 400

    def test_create_school_missing_school_name_returns_400(self, admin_client, make_org):
        org_id = make_org("Missing Name USD")
        resp = admin_client.post("/api/schools", json={
            "organization_id": org_id,
        })
        assert resp.status_code == 400

    def test_create_school_invalid_school_type_returns_400(self, admin_client, make_org):
        org_id = make_org("Bad Type USD")
        resp = admin_client.post("/api/schools", json={
            "organization_id": org_id,
            "school_name": "Bad Type School",
            "school_type": "university",
        })
        assert resp.status_code == 400

    def test_create_school_valid_school_types(self, admin_client, make_org):
        org_id = make_org("Valid Types USD")
        for school_type in ("elementary", "middle", "high", "k8", "other"):
            resp = admin_client.post("/api/schools", json={
                "organization_id": org_id,
                "school_name": f"School {school_type}",
                "school_type": school_type,
            })
            assert resp.status_code == 201, f"Expected 201 for school_type={school_type!r}"

    def test_create_school_nonexistent_org_returns_404(self, admin_client):
        resp = admin_client.post("/api/schools", json={
            "organization_id": 999999,
            "school_name": "Ghost School",
        })
        assert resp.status_code == 404

    def test_create_school_unauthenticated_returns_401(self, client, make_org):
        org_id = make_org("Unauth USD")
        resp = client.post("/api/schools", json={
            "organization_id": org_id,
            "school_name": "Unauth School",
        })
        assert resp.status_code == 401

    def test_create_school_non_admin_role_returns_403(
        self, app, make_org, make_user_with_staff, authenticated_client
    ):
        org_id = make_org("Non-admin USD")
        coach = make_user_with_staff(role="head_coach")
        with authenticated_client(coach["user_id"]) as c:
            resp = c.post("/api/schools", json={
                "organization_id": org_id,
                "school_name": "Forbidden School",
            })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/schools/<id>
# ---------------------------------------------------------------------------

class TestPatchSchool:

    def test_update_school_name_success(self, admin_client, make_org, make_school):
        org_id = make_org("Patch USD")
        school_id = make_school(org_id, name="Old Name School")
        resp = admin_client.patch(f"/api/schools/{school_id}", json={
            "school_name": "New Name School",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["school"]["school_name"] == "New Name School"

    def test_update_school_principal_fields_success(
        self, admin_client, make_org, make_school
    ):
        org_id = make_org("Principal Patch USD")
        school_id = make_school(org_id, name="Principal Test School")
        resp = admin_client.patch(f"/api/schools/{school_id}", json={
            "principal_name": "Dr. Carol White",
            "principal_email": "carol@patchusd.edu",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_patch_school_calls_principal_sync_when_result_has_both(
        self, admin_client, make_org, make_school
    ):
        org_id = make_org("Sync Patch USD")
        school_id = make_school(org_id, name="Sync Patch School")
        # First set both fields so the updated record has them
        admin_client.patch(f"/api/schools/{school_id}", json={
            "principal_name": "Initial Principal",
            "principal_email": "initial@syncpatch.edu",
        })
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.patch(f"/api/schools/{school_id}", json={
                "principal_name": "Updated Principal",
                "principal_email": "updated@syncpatch.edu",
            })
        assert resp.status_code == 200
        mock_sync.assert_called_once()

    def test_patch_school_no_updatable_fields_returns_400(
        self, admin_client, make_org, make_school
    ):
        org_id = make_org("No Fields USD")
        school_id = make_school(org_id, name="No Fields School")
        resp = admin_client.patch(f"/api/schools/{school_id}", json={})
        assert resp.status_code == 400

    def test_patch_school_nonexistent_returns_404(self, admin_client):
        resp = admin_client.patch("/api/schools/999999", json={
            "school_name": "Ghost",
        })
        assert resp.status_code == 404

    def test_patch_school_unauthenticated_returns_401(
        self, client, make_org, make_school
    ):
        org_id = make_org("Unauth Patch USD")
        school_id = make_school(org_id)
        resp = client.patch(f"/api/schools/{school_id}", json={
            "school_name": "No Access",
        })
        assert resp.status_code == 401

    def test_patch_school_non_admin_role_returns_403(
        self, app, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org("Non-admin Patch USD")
        school_id = make_school(org_id, name="Forbidden Patch School")
        coach = make_user_with_staff(role="head_coach")
        with authenticated_client(coach["user_id"]) as c:
            resp = c.patch(f"/api/schools/{school_id}", json={
                "school_name": "Sneaky Rename",
            })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/users
# ---------------------------------------------------------------------------

class TestPostUsers:

    def test_create_user_success(self, admin_client):
        resp = admin_client.post("/api/users", json={
            "first_name": "Test",
            "last_name": "NewUser",
            "email": "newuser_3c_001@ufit.com",
            "role": "head_coach",
            "password": "securePass1",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["ok"] is True
        assert "user_id" in data["user"]
        assert data["user"]["role"] == "head_coach"
        assert data["user"]["email"] == "newuser_3c_001@ufit.com"

    def test_create_user_missing_required_field_returns_400(self, admin_client):
        # Missing password
        resp = admin_client.post("/api/users", json={
            "first_name": "No",
            "last_name": "Password",
            "email": "nopass@ufit.com",
            "role": "head_coach",
        })
        assert resp.status_code == 400

    def test_create_user_missing_email_returns_400(self, admin_client):
        resp = admin_client.post("/api/users", json={
            "first_name": "No",
            "last_name": "Email",
            "role": "head_coach",
            "password": "securePass1",
        })
        assert resp.status_code == 400

    def test_create_user_invalid_role_returns_400(self, admin_client):
        resp = admin_client.post("/api/users", json={
            "first_name": "Bad",
            "last_name": "Role",
            "email": "badrole_3c@ufit.com",
            "role": "superhero",
            "password": "securePass1",
        })
        assert resp.status_code == 400

    def test_create_user_short_password_returns_400(self, admin_client):
        resp = admin_client.post("/api/users", json={
            "first_name": "Short",
            "last_name": "Pass",
            "email": "shortpass_3c@ufit.com",
            "role": "head_coach",
            "password": "abc",
        })
        assert resp.status_code == 400

    def test_create_user_duplicate_email_returns_409(self, admin_client):
        payload = {
            "first_name": "Dup",
            "last_name": "User",
            "email": "dup_3c_unique@ufit.com",
            "role": "head_coach",
            "password": "securePass1",
        }
        admin_client.post("/api/users", json=payload)
        resp = admin_client.post("/api/users", json=payload)
        assert resp.status_code == 409

    def test_create_user_with_nonexistent_school_id_returns_404(self, admin_client):
        resp = admin_client.post("/api/users", json={
            "first_name": "Ghost",
            "last_name": "School",
            "email": "ghostschool_3c@ufit.com",
            "role": "head_coach",
            "password": "securePass1",
            "school_id": 999999,
        })
        assert resp.status_code == 404

    def test_create_principal_with_school_calls_sync(
        self, admin_client, make_org, make_school
    ):
        org_id = make_org("Principal Sync USD")
        school_id = make_school(org_id, name="Principal Sync School")
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.post("/api/users", json={
                "first_name": "Principal",
                "last_name": "Synced",
                "email": "principal_sync_3c@ufit.com",
                "role": "principal",
                "password": "securePass1",
                "school_id": school_id,
            })
        assert resp.status_code == 201
        mock_sync.assert_called_once()

    def test_create_head_coach_with_school_does_not_call_sync(
        self, admin_client, make_org, make_school
    ):
        org_id = make_org("No Sync Coach USD")
        school_id = make_school(org_id, name="No Sync Coach School")
        mock_sync = MagicMock()
        with patch("app.routes.admin_routes.trigger_principal_sync", mock_sync):
            resp = admin_client.post("/api/users", json={
                "first_name": "Head",
                "last_name": "Coach",
                "email": "hcoach_nosync_3c@ufit.com",
                "role": "head_coach",
                "password": "securePass1",
                "school_id": school_id,
            })
        assert resp.status_code == 201
        mock_sync.assert_not_called()

    def test_create_user_unauthenticated_returns_401(self, client):
        resp = client.post("/api/users", json={
            "first_name": "Anon",
            "last_name": "User",
            "email": "anon_3c@ufit.com",
            "role": "head_coach",
            "password": "securePass1",
        })
        assert resp.status_code == 401

    def test_create_user_non_admin_role_returns_403(
        self, make_user_with_staff, authenticated_client
    ):
        coach = make_user_with_staff(role="head_coach")
        with authenticated_client(coach["user_id"]) as c:
            resp = c.post("/api/users", json={
                "first_name": "Forbidden",
                "last_name": "Create",
                "email": "forbidden_create_3c@ufit.com",
                "role": "head_coach",
                "password": "securePass1",
            })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/admin/eod-alerts
# ---------------------------------------------------------------------------

class TestEodAlerts:

    def test_eod_alerts_flags_coach_missing_report(
        self, monkeypatch, admin_client, make_org, make_school, make_program,
        make_user_with_staff, make_session
    ):
        _freeze_today(monkeypatch)
        org_id = make_org("EOD Test USD")
        school_id = make_school(org_id, name="EOD Test School")
        program_id = make_program(school_id, name="EOD Program")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        make_session(school_id, program_id, coach["staff_id"], session_date=_TODAY)

        resp = admin_client.post("/api/admin/eod-alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        flagged_ids = [c["staff_id"] for c in data["coaches_flagged"]]
        assert coach["staff_id"] in flagged_ids
        assert data["alerts_sent"] >= 1

    def test_eod_alerts_skips_coach_who_filed_report(
        self, monkeypatch, admin_client, make_org, make_school, make_program,
        make_user_with_staff, make_session, make_eod_report
    ):
        _freeze_today(monkeypatch)
        org_id = make_org("EOD Filed USD")
        school_id = make_school(org_id, name="EOD Filed School")
        program_id = make_program(school_id, name="EOD Filed Program")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        make_session(school_id, program_id, coach["staff_id"], session_date=_TODAY)
        make_eod_report(school_id, coach["staff_id"], report_date=_TODAY)

        resp = admin_client.post("/api/admin/eod-alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        flagged_ids = [c["staff_id"] for c in data["coaches_flagged"]]
        assert coach["staff_id"] not in flagged_ids

    def test_eod_alerts_idempotent_skips_already_alerted(
        self, monkeypatch, admin_client, make_org, make_school, make_program,
        make_user_with_staff, make_session
    ):
        _freeze_today(monkeypatch)
        org_id = make_org("EOD Idempotent USD")
        school_id = make_school(org_id, name="EOD Idempotent School")
        program_id = make_program(school_id, name="EOD Idempotent Program")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        make_session(school_id, program_id, coach["staff_id"], session_date=_TODAY)

        # First call — creates the notification
        resp1 = admin_client.post("/api/admin/eod-alerts")
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        first_alerts_sent = data1["alerts_sent"]

        # Second call — should be idempotent: same coach already alerted today
        resp2 = admin_client.post("/api/admin/eod-alerts")
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        # The coach should now appear in skipped_already_alerted, not re-sent
        assert data2["skipped_already_alerted"] >= first_alerts_sent

    def test_eod_alerts_returns_expected_shape(
        self, monkeypatch, admin_client
    ):
        _freeze_today(monkeypatch)
        resp = admin_client.post("/api/admin/eod-alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ok" in data
        assert "alerts_sent" in data
        assert "skipped_already_alerted" in data
        assert "coaches_flagged" in data
        assert isinstance(data["coaches_flagged"], list)

    def test_eod_alerts_coach_overseer_is_allowed(
        self, monkeypatch, make_user_with_staff, authenticated_client
    ):
        _freeze_today(monkeypatch)
        overseer = make_user_with_staff(role="coach_overseer")
        with authenticated_client(overseer["user_id"]) as c:
            resp = c.post("/api/admin/eod-alerts")
        assert resp.status_code == 200

    def test_eod_alerts_unauthenticated_returns_401(self, monkeypatch, client):
        _freeze_today(monkeypatch)
        resp = client.post("/api/admin/eod-alerts")
        assert resp.status_code == 401

    def test_eod_alerts_head_coach_role_returns_403(
        self, monkeypatch, make_user_with_staff, authenticated_client
    ):
        _freeze_today(monkeypatch)
        coach = make_user_with_staff(role="head_coach")
        with authenticated_client(coach["user_id"]) as c:
            resp = c.post("/api/admin/eod-alerts")
        assert resp.status_code == 403

    def test_eod_alerts_no_sessions_today_flags_nobody(
        self, monkeypatch, admin_client, make_org, make_school, make_program,
        make_user_with_staff, make_session
    ):
        _freeze_today(monkeypatch)
        org_id = make_org("Past Session USD")
        school_id = make_school(org_id, name="Past Session School")
        program_id = make_program(school_id, name="Past Session Program")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        # Session is on a different day — should not trigger an alert
        make_session(school_id, program_id, coach["staff_id"], session_date="2026-04-19")

        resp = admin_client.post("/api/admin/eod-alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        flagged_ids = [c["staff_id"] for c in data["coaches_flagged"]]
        assert coach["staff_id"] not in flagged_ids
