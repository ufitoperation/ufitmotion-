"""
test_incidents.py — Phase 2C: Incident Reporting

POST /api/incidents  — file an incident report
GET  /api/incidents  — list incident reports (role-scoped)

Today frozen at 2026-04-20.  All date-sensitive tests monkeypatch
app.routes.coach_routes._get_today so they don't drift as time passes.
"""

import datetime
import json
import pytest

TODAY = datetime.date(2026, 4, 20)

_VALID_TYPES = ("injury", "behavior", "property", "medical", "safety", "other")
_VALID_SEVERITIES = ("low", "medium", "high", "critical")


def _post(client, payload):
    return client.post(
        "/api/incidents",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get(client, params=None):
    return client.get("/api/incidents", query_string=params or {})


def _json(resp):
    return json.loads(resp.data)


def _freeze(monkeypatch, today=TODAY):
    monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: today)


def _minimal_body(school_id, report_date=None):
    return {
        "school_id": school_id,
        "report_date": (report_date or TODAY).isoformat(),
        "incident_type": "injury",
        "severity_level": "low",
        "description": "Student fell during warm-up.",
        "immediate_action_taken": "Applied first aid, student rested.",
    }


# ===========================================================================
# POST /api/incidents
# ===========================================================================

class TestCreateIncident:

    def test_create_incident_minimal_success(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Minimal Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, _minimal_body(school_id))

        assert resp.status_code == 201
        data = _json(resp)
        assert data["ok"] is True
        inc = data["incident"]
        assert inc["incident_id"] is not None
        assert inc["school_id"] == school_id
        assert inc["report_date"] == TODAY.isoformat()
        assert inc["incident_type"] == "injury"
        assert inc["severity_level"] == "low"
        assert inc["status"] == "open"
        assert inc["school_notified"] is False
        assert inc["family_notified"] is False
        assert inc["escalated_to_supervisor"] is False

    def test_create_incident_full_success(
        self, monkeypatch, app, authenticated_client, make_org, make_region, make_school,
        make_program, make_session, make_student, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Full Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        session_id = make_session(school_id, program_id, coach["staff_id"], session_date=TODAY.isoformat())
        student_id = make_student(school_id, first="Jordan", last="Smith")

        body = {
            "school_id": school_id,
            "report_date": TODAY.isoformat(),
            "incident_type": "behavior",
            "severity_level": "high",
            "description": "Student disrupted class repeatedly.",
            "immediate_action_taken": "Removed student from activity.",
            "session_id": session_id,
            "student_id": student_id,
            "school_notified": True,
            "family_notified": True,
            "escalated_to_supervisor": False,
            "resolution_notes": "Parent meeting scheduled.",
        }

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 201
        inc = _json(resp)["incident"]
        assert inc["session_id"] == session_id
        assert inc["student_id"] == student_id
        assert inc["school_notified"] is True
        assert inc["family_notified"] is True
        assert inc["resolution_notes"] == "Parent meeting scheduled."
        assert inc["school_name"] is not None
        assert inc["coach_name"] is not None

    def test_create_incident_critical_notifies_admins(
        self, monkeypatch, app, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff,
    ):
        """severity=critical → notification rows inserted for admin/ceo/overseer in same org."""
        _freeze(monkeypatch)
        org_id = make_org("Critical Notify Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        admin = make_user_with_staff(role="admin", school_id=school_id)

        body = _minimal_body(school_id)
        body["severity_level"] = "critical"

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 201
        incident_id = _json(resp)["incident"]["incident_id"]

        with app.app_context():
            from app.database import get_db
            db = get_db()
            notif = db.execute(
                "SELECT * FROM notifications WHERE related_table = 'incident_reports' AND related_id = ?",
                (incident_id,),
            ).fetchall()
            db.close()

        assert len(notif) >= 1
        notif_user_ids = [n["user_id"] for n in notif]
        assert admin["user_id"] in notif_user_ids

    def test_create_incident_site_coordinator_403(
        self, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        org_id = make_org("SC 403 Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        sc = make_user_with_staff(role="site_coordinator", school_id=school_id)

        with authenticated_client(sc["user_id"]) as c:
            resp = _post(c, _minimal_body(school_id))

        assert resp.status_code == 403
        assert "coach" in _json(resp)["error"].lower()

    def test_create_incident_coach_overseer_403(
        self, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        org_id = make_org("Overseer 403 Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post(c, _minimal_body(school_id))

        assert resp.status_code == 403

    def test_create_incident_missing_school_id(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing School Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["school_id"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "school_id" in _json(resp)["error"]

    def test_create_incident_missing_report_date(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing Date Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["report_date"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "report_date" in _json(resp)["error"]

    def test_create_incident_invalid_date_format(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Bad Date Format Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["report_date"] = "20-04-2026"

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "report_date" in _json(resp)["error"]

    def test_create_incident_future_date(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Future Date Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id, report_date=TODAY + datetime.timedelta(days=1))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "future" in _json(resp)["error"].lower()

    def test_create_incident_past_8_days(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("8 Days Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id, report_date=TODAY - datetime.timedelta(days=8))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "7 days" in _json(resp)["error"].lower()

    def test_create_incident_past_7_days_ok(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("7 Days Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id, report_date=TODAY - datetime.timedelta(days=7))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 201

    def test_create_incident_missing_incident_type(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing Type Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["incident_type"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "incident_type" in _json(resp)["error"]

    def test_create_incident_invalid_incident_type(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Invalid Type Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["incident_type"] = "earthquake"

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "incident_type" in _json(resp)["error"]

    def test_create_incident_missing_severity_level(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing Severity Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["severity_level"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "severity_level" in _json(resp)["error"]

    def test_create_incident_invalid_severity_level(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Invalid Severity Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["severity_level"] = "extreme"

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "severity_level" in _json(resp)["error"]

    def test_create_incident_missing_description(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing Desc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["description"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "description" in _json(resp)["error"]

    def test_create_incident_description_too_long(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Long Desc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["description"] = "x" * 2001

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "2000" in _json(resp)["error"]

    def test_create_incident_missing_immediate_action(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Missing Action Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        del body["immediate_action_taken"]

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "immediate_action_taken" in _json(resp)["error"]

    def test_create_incident_immediate_action_too_long(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Long Action Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["immediate_action_taken"] = "y" * 1001

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "1000" in _json(resp)["error"]

    def test_create_incident_resolution_notes_too_long(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Long Notes Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["resolution_notes"] = "z" * 1001

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "resolution_notes" in _json(resp)["error"]

    def test_create_incident_boolean_not_bool(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Bool Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["school_notified"] = "yes"

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "boolean" in _json(resp)["error"].lower()

    def test_create_incident_wrong_school_403(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Wrong School Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Coach School")
        school_b = make_school(org_id, region_id=region_id, name="Other School")
        coach = make_user_with_staff(role="head_coach", school_id=school_a)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, _minimal_body(school_b))

        assert resp.status_code == 403
        assert "not assigned" in _json(resp)["error"].lower()

    def test_create_incident_invalid_session_id(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school,
        make_program, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Invalid Session Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["session_id"] = 999999

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "session_id" in _json(resp)["error"]

    def test_create_incident_invalid_student_id(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Invalid Student Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        body = _minimal_body(school_id)
        body["student_id"] = 999999

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, body)

        assert resp.status_code == 400
        assert "student_id" in _json(resp)["error"]

    def test_create_incident_all_valid_types(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        """All incident_type values are accepted."""
        _freeze(monkeypatch)
        org_id = make_org("All Types Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        for itype in _VALID_TYPES:
            body = _minimal_body(school_id)
            body["incident_type"] = itype
            with authenticated_client(coach["user_id"]) as c:
                resp = _post(c, body)
            assert resp.status_code == 201, f"Expected 201 for type={itype}, got {resp.status_code}"

    def test_create_incident_assistant_coach_can_post(
        self, monkeypatch, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        _freeze(monkeypatch)
        org_id = make_org("Asst Coach Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="assistant_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post(c, _minimal_body(school_id))

        assert resp.status_code == 201


# ===========================================================================
# GET /api/incidents
# ===========================================================================

class TestListIncidents:

    def test_list_incidents_head_coach_own_only(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        """head_coach sees only their own incidents at their school."""
        org_id = make_org("HC List Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach_a = make_user_with_staff(role="head_coach", school_id=school_id)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_id)

        inc_a = make_incident(school_id, coach_a["staff_id"])
        make_incident(school_id, coach_b["staff_id"])

        with authenticated_client(coach_a["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        data = _json(resp)
        assert data["ok"] is True
        ids = [i["incident_id"] for i in data["incidents"]]
        assert inc_a in ids
        for inc in data["incidents"]:
            assert inc["staff_id"] == coach_a["staff_id"]

    def test_list_incidents_site_coordinator_assigned_schools(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        """site_coordinator sees all incidents from their assigned schools."""
        org_id = make_org("SC List Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="SC School A")
        school_b = make_school(org_id, region_id=region_id, name="SC School B")
        coach_a = make_user_with_staff(role="head_coach", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)
        sc = make_user_with_staff(role="site_coordinator", school_id=school_a)

        inc_a = make_incident(school_a, coach_a["staff_id"])
        inc_b = make_incident(school_b, coach_b["staff_id"])

        with authenticated_client(sc["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert inc_a in ids
        assert inc_b not in ids

    def test_list_incidents_overseer_full_org(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        """coach_overseer sees all incidents in their org."""
        org_id = make_org("Overseer List Org")
        org_b_id = make_org("Other Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Overseer School A")
        school_b = make_school(org_id, region_id=region_id, name="Overseer School B")
        school_c = make_school(org_b_id, region_id=region_id, name="Other Org School")
        coach_a = make_user_with_staff(role="head_coach", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)
        coach_c = make_user_with_staff(role="head_coach", school_id=school_c)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)

        inc_a = make_incident(school_a, coach_a["staff_id"])
        inc_b = make_incident(school_b, coach_b["staff_id"])
        inc_c = make_incident(school_c, coach_c["staff_id"])

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert inc_a in ids
        assert inc_b in ids
        assert inc_c not in ids

    def test_list_incidents_filter_status(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        org_id = make_org("Status Filter Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        inc_open = make_incident(school_id, coach["staff_id"], status="open")
        inc_resolved = make_incident(school_id, coach["staff_id"], status="resolved")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"status": "resolved"})

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert inc_resolved in ids
        assert inc_open not in ids

    def test_list_incidents_filter_severity(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        org_id = make_org("Severity Filter Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        inc_low = make_incident(school_id, coach["staff_id"], severity_level="low")
        inc_critical = make_incident(school_id, coach["staff_id"], severity_level="critical")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"severity": "critical"})

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert inc_critical in ids
        assert inc_low not in ids

    def test_list_incidents_date_range(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        org_id = make_org("Date Range Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        inc_apr1 = make_incident(school_id, coach["staff_id"], report_date="2026-04-01")
        inc_apr15 = make_incident(school_id, coach["staff_id"], report_date="2026-04-15")
        inc_apr20 = make_incident(school_id, coach["staff_id"], report_date="2026-04-20")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-10", "to": "2026-04-16"})

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert inc_apr15 in ids
        assert inc_apr1 not in ids
        assert inc_apr20 not in ids

    def test_list_incidents_pagination(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        org_id = make_org("Pagination Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        for _ in range(5):
            make_incident(school_id, coach["staff_id"])

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"page": 1, "per_page": 3})

        assert resp.status_code == 200
        data = _json(resp)
        assert data["per_page"] == 3
        assert len(data["incidents"]) <= 3
        assert data["total"] >= 5

    def test_list_incidents_invalid_page(
        self, authenticated_client, make_org, make_region, make_school, make_user_with_staff,
    ):
        org_id = make_org("Invalid Page Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"page": "abc"})

        assert resp.status_code == 400
        assert "page" in _json(resp)["error"]

    def test_list_incidents_excludes_soft_deleted(
        self, authenticated_client, make_org, make_region, make_school,
        make_user_with_staff, make_incident,
    ):
        org_id = make_org("Soft Delete Inc Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        live_id = make_incident(school_id, coach["staff_id"])
        dead_id = make_incident(school_id, coach["staff_id"], deleted_at="2026-04-01T00:00:00+00:00")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        ids = [i["incident_id"] for i in _json(resp)["incidents"]]
        assert live_id in ids
        assert dead_id not in ids
