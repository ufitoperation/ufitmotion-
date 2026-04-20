"""
test_eod_reports.py — Phase 2B: EOD Reports — RED-phase test suite.

All 39 test cases from §8 of docs/specs/phase-2b-eod-reports.md.
Tests are RED: routes return stubs until implementation is written.

Test organisation:
  POST /api/eod-reports — TestCreateEodReport  (25 tests)
  GET  /api/eod-reports — TestListEodReports   (14 tests)

Implementation requirements for time mocking:
  The implementation must expose a module-level _now_pacific() function
  in app.routes.coach_routes (parallel to _get_today()) that returns
  datetime.datetime.now(tz=ZoneInfo("America/Los_Angeles")).
  Tests monkeypatch this function to freeze Pacific wall-clock time.
"""

import json
import datetime
import pytest
from zoneinfo import ZoneInfo

TODAY = datetime.date(2026, 4, 19)
_PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


# ===========================================================================
# Helpers
# ===========================================================================

def _post_json(client, payload):
    return client.post(
        "/api/eod-reports",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get(client, params=None):
    return client.get(
        "/api/eod-reports",
        query_string=params or {},
    )


def _json(resp):
    return json.loads(resp.data)


def _minimal_body(school_id):
    """Minimal valid POST body — only the three required fields."""
    return {
        "school_id": school_id,
        "report_date": TODAY.isoformat(),
        "activities_completed": "Locomotor skills — galloping, skipping, hopping.",
        "student_engagement_summary": "High energy. 3rd graders very engaged.",
    }


def _freeze_pacific(monkeypatch, dt: datetime.datetime):
    """Patch both _now_pacific and _get_today so time is fully frozen."""
    monkeypatch.setattr("app.routes.coach_routes._now_pacific", lambda: dt)
    monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: dt.date())


# ===========================================================================
# POST /api/eod-reports
# ===========================================================================

class TestCreateEodReport:

    def test_create_eod_minimal_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """
        201, only required fields. Optional fields null in response and DB.
        Both eod_reports and audit_log rows exist after commit.
        """
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 19:45 Pacific — before the 20:00 deadline
        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 19, 45, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(school_id))

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("ok") is True
        eod = data.get("eod_report", {})

        assert eod.get("eod_id") is not None
        assert eod.get("school_id") == school_id
        assert eod.get("school_name") is not None
        assert eod.get("staff_id") == coach["staff_id"]
        assert eod.get("coach_name") is not None
        assert eod.get("report_date") == TODAY.isoformat()
        assert eod.get("submitted_on_time") is True
        assert eod.get("created_at") is not None

        for field in ["attendance_summary", "behavior_summary", "success_story",
                      "challenge_summary", "notes", "program_id", "session_id"]:
            assert eod.get(field) is None, f"Expected {field} to be null, got {eod.get(field)!r}"

        with app.app_context():
            from app.database import get_db
            db = get_db()
            eod_id = eod["eod_id"]
            row = db.execute("SELECT * FROM eod_reports WHERE eod_id = ?", (eod_id,)).fetchone()
            assert row is not None, "eod_reports row not found in DB"
            assert row["school_id"] == school_id
            assert row["staff_id"] == coach["staff_id"]
            audit = db.execute(
                "SELECT * FROM audit_log WHERE table_name = 'eod_reports' AND record_id = ?",
                (eod_id,),
            ).fetchone()
            assert audit is not None, "audit_log row not found"
            assert audit["action"] == "INSERT"
            db.close()

    def test_create_eod_full_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
        monkeypatch,
    ):
        """201, all optional fields provided and saved correctly in response."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        session_id = make_session(
            school_id, program_id, coach["staff_id"], session_date=TODAY.isoformat()
        )

        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 18, 0, 0, tzinfo=_PACIFIC_TZ))

        body = {
            "school_id": school_id,
            "report_date": TODAY.isoformat(),
            "activities_completed": "Locomotor skills.",
            "student_engagement_summary": "High energy.",
            "attendance_summary": "28 of 30 present.",
            "behavior_summary": "No major issues.",
            "success_story": "Jordan completed gallop sequence.",
            "challenge_summary": "Lighting issue on east side.",
            "notes": "3 hula hoops cracked.",
            "injury_incident_flag": False,
            "followup_needed": False,
            "principal_communication_needed": True,
            "program_id": program_id,
            "session_id": session_id,
        }

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, body)

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        eod = _json(resp).get("eod_report", {})
        assert eod.get("attendance_summary") == "28 of 30 present."
        assert eod.get("behavior_summary") == "No major issues."
        assert eod.get("success_story") == "Jordan completed gallop sequence."
        assert eod.get("challenge_summary") == "Lighting issue on east side."
        assert eod.get("notes") == "3 hula hoops cracked."
        assert eod.get("principal_communication_needed") is True
        assert eod.get("program_id") == program_id
        assert eod.get("session_id") == session_id
        assert eod.get("injury_incident_flag") is False
        assert eod.get("followup_needed") is False

    def test_create_eod_submitted_on_time_true(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """submitted_on_time=True when Pacific wall-clock is before 20:00 on report_date."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 19:45 Pacific on 2026-04-19 — before the 20:00 deadline
        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 19, 45, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(school_id))

        assert resp.status_code == 201
        assert _json(resp)["eod_report"]["submitted_on_time"] is True

    def test_create_eod_submitted_on_time_false_after_deadline(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """submitted_on_time=False when Pacific wall-clock is after 20:00 on report_date."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 20:01 Pacific on 2026-04-19 — past the deadline
        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 20, 1, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(school_id))

        assert resp.status_code == 201
        assert _json(resp)["eod_report"]["submitted_on_time"] is False

    def test_create_eod_submitted_on_time_false_backdated(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """submitted_on_time=False when report_date is a prior Pacific calendar date."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 10:00 Pacific on 2026-04-20 — submitting for 2026-04-19 (yesterday in Pacific)
        frozen = datetime.datetime(2026, 4, 20, 10, 0, 0, tzinfo=_PACIFIC_TZ)
        monkeypatch.setattr("app.routes.coach_routes._now_pacific", lambda: frozen)
        # UTC date is also 2026-04-20 here; rule 4 range check uses _get_today()
        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: datetime.date(2026, 4, 20))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                **_minimal_body(school_id),
                "report_date": "2026-04-19",  # yesterday in Pacific
            })

        assert resp.status_code == 201
        assert _json(resp)["eod_report"]["submitted_on_time"] is False, (
            "Backdated report (prior Pacific calendar date) must always be False"
        )

    def test_create_eod_submitted_on_time_true_after_midnight_utc(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """
        01:00 UTC on 2026-04-20 = 18:00 Pacific on 2026-04-19.
        Pacific date is still 2026-04-19; 18:00 is before the 20:00 deadline.
        submitted_on_time must be True.
        """
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 18:00 Pacific on 2026-04-19 (= 01:00 UTC 2026-04-20)
        frozen_pacific = datetime.datetime(2026, 4, 19, 18, 0, 0, tzinfo=_PACIFIC_TZ)
        monkeypatch.setattr("app.routes.coach_routes._now_pacific", lambda: frozen_pacific)
        # _get_today() returns UTC date (2026-04-20); report_date 2026-04-19 is 1 day past → OK
        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: datetime.date(2026, 4, 20))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                **_minimal_body(school_id),
                "report_date": "2026-04-19",
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        assert _json(resp)["eod_report"]["submitted_on_time"] is True, (
            "18:00 Pacific on 2026-04-19 is before the 20:00 deadline — must be on time"
        )

    def test_create_eod_injury_forces_followup(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """injury_incident_flag=True forces followup_needed=True, overriding coach's False."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 15, 0, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                **_minimal_body(school_id),
                "injury_incident_flag": True,
                "followup_needed": False,  # coach says no — injury overrides
            })

        assert resp.status_code == 201
        eod = _json(resp)["eod_report"]
        assert eod["injury_incident_flag"] is True
        assert eod["followup_needed"] is True, (
            "injury_incident_flag=True must override followup_needed to True regardless of coach input"
        )

    def test_create_eod_duplicate_returns_409(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
        monkeypatch,
    ):
        """409 with existing_eod_id when same staff+school+date already has a non-deleted EOD."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        existing_id = make_eod_report(school_id, coach["staff_id"], report_date=TODAY.isoformat())

        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 15, 0, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(school_id))

        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert "existing_eod_id" in data, "409 body must include existing_eod_id"
        assert data["existing_eod_id"] == existing_id
        assert "already been submitted" in data.get("error", "")

    def test_create_eod_site_coordinator_blocked(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
    ):
        """site_coordinator cannot POST EOD reports — 403 blocked at rule 1 before body parsing."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_id)

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, _minimal_body(school_id))

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "You do not have permission to submit EOD reports."

    def test_create_eod_wrong_school_head_coach(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """head_coach submitting for a school they are not assigned to — 403."""
        org_id = make_org()
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Coach's School")
        school_b = make_school(org_id, region_id=region_id, name="Other School")
        coach = make_user_with_staff(role="head_coach", school_id=school_a)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_a), "school_id": school_b})

        assert resp.status_code == 403
        assert _json(resp)["error"] == "You are not assigned to this school."

    def test_create_eod_overseer_cross_school_in_org(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """coach_overseer can POST EOD at any school in their org — 201."""
        org_id = make_org()
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Overseer Home")
        school_b = make_school(org_id, region_id=region_id, name="Cross School")
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)

        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 15, 0, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_a), "school_id": school_b})

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"

    def test_create_eod_overseer_wrong_org(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """coach_overseer submitting for a school in a different org — 403."""
        org_a = make_org("Overseer Org A")
        org_b = make_org("Overseer Org B")
        region_id = make_region()
        school_a = make_school(org_a, region_id=region_id)
        school_b = make_school(org_b, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_a), "school_id": school_b})

        assert resp.status_code == 403
        assert _json(resp)["error"] == "School is not in your organization."

    def test_create_eod_future_date(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """report_date one day in the future — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        future = (TODAY + datetime.timedelta(days=1)).isoformat()
        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "report_date": future})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Report date cannot be in the future."

    def test_create_eod_past_8_days(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """report_date 8 days ago (beyond the 7-day window) — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        eight_days_ago = (TODAY - datetime.timedelta(days=8)).isoformat()
        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "report_date": eight_days_ago})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Report date cannot be more than 7 days in the past."

    def test_create_eod_missing_activities_completed(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """Missing activities_completed — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        body = _minimal_body(school_id)
        del body["activities_completed"]
        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, body)

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Missing required field: activities_completed."

    def test_create_eod_missing_student_engagement_summary(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """Missing student_engagement_summary — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        body = _minimal_body(school_id)
        del body["student_engagement_summary"]
        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, body)

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Missing required field: student_engagement_summary."

    def test_create_eod_field_too_long(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """activities_completed of 2001 chars exceeds the 2000-char limit — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "activities_completed": "x" * 2001})

        assert resp.status_code == 400
        assert _json(resp)["error"] == (
            "Field 'activities_completed' exceeds maximum length of 2000 characters."
        )

    def test_create_eod_invalid_session_id(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """session_id 999999 does not exist at this school on this date — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "session_id": 999999})

        assert resp.status_code == 400
        assert _json(resp)["error"] == (
            "session_id does not match a session at this school on this date."
        )

    def test_create_eod_boolean_field_wrong_type(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """injury_incident_flag sent as JSON string "true" (not bool) — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        # Build raw JSON so the string "true" arrives instead of boolean true
        raw = (
            f'{{"school_id": {school_id}, "report_date": "{TODAY.isoformat()}", '
            f'"activities_completed": "Test", "student_engagement_summary": "Test", '
            f'"injury_incident_flag": "true"}}'
        )
        with authenticated_client(coach["user_id"]) as c:
            resp = c.post("/api/eod-reports", data=raw, content_type="application/json")

        assert resp.status_code == 400
        assert _json(resp)["error"] == "injury_incident_flag must be a boolean."

    def test_create_eod_whitespace_only_activities(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        """activities_completed of only whitespace fails the non-empty strip check — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "activities_completed": "   "})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Missing required field: activities_completed."

    def test_create_eod_program_id_valid(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        monkeypatch,
    ):
        """program_id pointing to an active program at school — 201, program_id in response."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        _freeze_pacific(monkeypatch, datetime.datetime(2026, 4, 19, 15, 0, 0, tzinfo=_PACIFIC_TZ))

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "program_id": program_id})

        assert resp.status_code == 201
        assert _json(resp)["eod_report"]["program_id"] == program_id

    def test_create_eod_program_id_wrong_school(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        monkeypatch,
    ):
        """program_id belonging to a different school — 400."""
        org_id = make_org()
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id)
        school_b = make_school(org_id, region_id=region_id)
        program_at_b = make_program(school_b)
        coach = make_user_with_staff(role="head_coach", school_id=school_a)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_a), "program_id": program_at_b})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "Program not found at this school."

    def test_create_eod_session_id_deleted_session(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
        monkeypatch,
    ):
        """session_id referencing a soft-deleted session — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        session_id = make_session(
            school_id, program_id, coach["staff_id"], session_date=TODAY.isoformat()
        )

        # Soft-delete the session
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            db.execute(
                "UPDATE sessions SET deleted_at = ? WHERE session_id = ?",
                (now_utc(), session_id),
            )
            db.commit()
            db.close()

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {**_minimal_body(school_id), "session_id": session_id})

        assert resp.status_code == 400
        assert _json(resp)["error"] == (
            "session_id does not match a session at this school on this date."
        )

    def test_create_eod_overseer_no_school_assignment(
        self,
        authenticated_client,
        make_user_with_staff,
        monkeypatch,
    ):
        """coach_overseer with no school_id in current_user() — 403 at rule 12."""
        overseer = make_user_with_staff(role="coach_overseer", school_id=None)

        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": 99999,
                "report_date": TODAY.isoformat(),
                "activities_completed": "Test.",
                "student_engagement_summary": "Test.",
            })

        assert resp.status_code == 403
        assert _json(resp)["error"] == (
            "You have no active school assignment. Contact your administrator."
        )

    def test_create_eod_unauthenticated(self, client):
        """No session cookie — 401."""
        resp = _post_json(client, {
            "school_id": 1,
            "report_date": TODAY.isoformat(),
            "activities_completed": "Test.",
            "student_engagement_summary": "Test.",
        })
        assert resp.status_code == 401
        assert _json(resp)["error"] == "Authentication required."


# ===========================================================================
# GET /api/eod-reports
# ===========================================================================

class TestListEodReports:

    def test_list_eod_head_coach_sees_own_reports(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """head_coach sees their own report. Response includes all required fields."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        eod_id = make_eod_report(school_id, coach["staff_id"], report_date="2026-04-15")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True
        reports = data.get("eod_reports", [])
        ids = [r["eod_id"] for r in reports]
        assert eod_id in ids

        target = next(r for r in reports if r["eod_id"] == eod_id)
        required_fields = [
            "eod_id", "school_id", "school_name", "staff_id", "coach_name",
            "report_date", "submitted_on_time", "program_id", "session_id",
            "activities_completed", "student_engagement_summary", "created_at",
        ]
        for field in required_fields:
            assert field in target, f"Field '{field}' missing from GET response item"

    def test_list_eod_head_coach_own_only(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """head_coach does NOT see EOD reports filed by other coaches at the same school."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach_a = make_user_with_staff(role="head_coach", school_id=school_id)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_id)

        make_eod_report(school_id, coach_a["staff_id"], report_date="2026-04-15")
        other_eod_id = make_eod_report(school_id, coach_b["staff_id"], report_date="2026-04-15")

        with authenticated_client(coach_a["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = [r["eod_id"] for r in _json(resp).get("eod_reports", [])]
        assert other_eod_id not in ids, (
            "EOD reports are coach-scoped — head_coach must not see other coaches' reports"
        )

    def test_list_eod_site_coordinator_region_scope(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """
        site_coordinator sees reports from schools they are staff-assigned to.
        Reports from unassigned schools are excluded.
        """
        org_id = make_org()
        region_1 = make_region()
        region_3 = make_region()
        school_4 = make_school(org_id, region_id=region_1, name="SC School 4")
        school_5 = make_school(org_id, region_id=region_1, name="SC School 5")
        school_20 = make_school(org_id, region_id=region_3, name="SC School 20")

        coordinator = make_user_with_staff(
            role="site_coordinator", school_id=school_4, assigned_region_id=region_1
        )

        # Assign coordinator to school_5 as well
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            db.execute(
                """INSERT INTO staff_assignments
                   (staff_id, school_id, assignment_role, start_date, active_status, created_at)
                   VALUES (?, ?, 'site_coordinator', '2025-08-01', 1, ?)""",
                (coordinator["staff_id"], school_5, now_utc()),
            )
            db.commit()
            db.close()

        coach_b = make_user_with_staff(role="head_coach", school_id=school_5)
        coach_c = make_user_with_staff(role="head_coach", school_id=school_20)

        eod_4 = make_eod_report(school_4, coordinator["staff_id"], report_date="2026-04-15")
        eod_5 = make_eod_report(school_5, coach_b["staff_id"], report_date="2026-04-15")
        eod_20 = make_eod_report(school_20, coach_c["staff_id"], report_date="2026-04-15")

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = {r["eod_id"] for r in _json(resp).get("eod_reports", [])}
        assert eod_4 in ids, "Coordinator's own school report should appear"
        assert eod_5 in ids, "Report from assigned school_5 should appear"
        assert eod_20 not in ids, "Report from unassigned school_20 must NOT appear"

    def test_list_eod_overseer_org_scope(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """coach_overseer sees all EOD reports in their org. Cross-org reports excluded."""
        org_a = make_org("Overseer Org A")
        org_b = make_org("Overseer Org B")
        region_id = make_region()
        school_a = make_school(org_a, region_id=region_id)
        school_b = make_school(org_a, region_id=region_id)
        school_other = make_school(org_b, region_id=region_id)

        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)
        coach_other = make_user_with_staff(role="head_coach", school_id=school_other)

        eod_a = make_eod_report(school_a, overseer["staff_id"], report_date="2026-04-15")
        eod_b = make_eod_report(school_b, coach_b["staff_id"], report_date="2026-04-15")
        eod_other = make_eod_report(school_other, coach_other["staff_id"], report_date="2026-04-15")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = {r["eod_id"] for r in _json(resp).get("eod_reports", [])}
        assert eod_a in ids
        assert eod_b in ids
        assert eod_other not in ids, "Cross-org EOD must not appear for overseer"

    def test_list_eod_pagination(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """Pagination fields correct. Items ordered by report_date DESC, eod_id DESC."""
        import math

        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        for d in ["2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14", "2026-04-15"]:
            make_eod_report(school_id, coach["staff_id"], report_date=d)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat(), "per_page": 3, "page": 1})

        assert resp.status_code == 200
        data = _json(resp)
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["eod_reports"]) <= 3
        assert data["total"] >= 5
        assert data["pages"] == math.ceil(data["total"] / 3)

        reports = data["eod_reports"]
        for i in range(len(reports) - 1):
            curr, nxt = reports[i]["report_date"], reports[i + 1]["report_date"]
            assert curr >= nxt, f"Not ordered by report_date DESC: {curr} < {nxt}"
            if curr == nxt:
                assert reports[i]["eod_id"] >= reports[i + 1]["eod_id"], "eod_id tiebreaker violated"

    def test_list_eod_school_filter_in_scope(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """school_id filter narrows results for coach_overseer to that school only."""
        org_id = make_org()
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id)
        school_b = make_school(org_id, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)

        eod_a = make_eod_report(school_a, overseer["staff_id"], report_date="2026-04-15")
        eod_b = make_eod_report(school_b, coach_b["staff_id"], report_date="2026-04-15")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"school_id": school_b, "from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = {r["eod_id"] for r in _json(resp).get("eod_reports", [])}
        assert eod_b in ids
        assert eod_a not in ids, "school_id filter should exclude other schools"

    def test_list_eod_school_filter_out_of_scope(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
    ):
        """school_id filter pointing to a school outside overseer's org — 403."""
        org_a = make_org()
        org_b = make_org()
        region_id = make_region()
        school_a = make_school(org_a, region_id=region_id)
        school_other = make_school(org_b, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"school_id": school_other, "from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 403
        assert _json(resp)["error"] == "You do not have access to this school."

    def test_list_eod_program_id_filter(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_eod_report,
    ):
        """?program_id=N returns only reports linked to that program."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_a = make_program(school_id, name="Program A")
        make_program(school_id, name="Program B")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        eod_with_prog = make_eod_report(
            school_id, coach["staff_id"], report_date="2026-04-15", program_id=prog_a
        )
        eod_no_prog = make_eod_report(school_id, coach["staff_id"], report_date="2026-04-14")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"program_id": prog_a, "from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = {r["eod_id"] for r in _json(resp).get("eod_reports", [])}
        assert eod_with_prog in ids
        assert eod_no_prog not in ids, "program_id filter should exclude unlinked reports"

    def test_list_eod_coach_name_null_deleted_user(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """coach_name is null in GET when the coach's user record is soft-deleted."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)
        ghost = make_user_with_staff(role="head_coach", school_id=school_id)

        eod_id = make_eod_report(school_id, ghost["staff_id"], report_date="2026-04-15")

        # Soft-delete the ghost coach's user record
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            db.execute(
                "UPDATE users SET deleted_at = ? WHERE user_id = ?",
                (now_utc(), ghost["user_id"]),
            )
            db.commit()
            db.close()

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        reports = _json(resp).get("eod_reports", [])
        target = next((r for r in reports if r["eod_id"] == eod_id), None)
        assert target is not None, f"EOD {eod_id} not found in overseer response"
        assert target.get("coach_name") is None, (
            "coach_name must be null for soft-deleted user — not an error"
        )

    def test_list_eod_no_school_assignment_head_coach(
        self,
        authenticated_client,
        make_user_with_staff,
    ):
        """head_coach with no active school assignment — 403."""
        coach = make_user_with_staff(role="head_coach", school_id=None)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 403
        assert _json(resp)["error"] == (
            "You have no active school assignment. Contact your administrator."
        )

    def test_list_eod_school_id_not_integer(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
    ):
        """?school_id=abc (non-integer) — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_id)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"school_id": "abc"})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "school_id must be a positive integer."

    def test_list_eod_program_id_not_integer(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
    ):
        """?program_id=xyz (non-integer) — 400."""
        org_id = make_org()
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"program_id": "xyz"})

        assert resp.status_code == 400
        assert _json(resp)["error"] == "program_id must be a positive integer."

    def test_list_eod_head_coach_excludes_prior_school_reports(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
        make_eod_report,
    ):
        """
        head_coach sees only reports at their CURRENT assigned school.
        An EOD they filed at a prior school (no current assignment there) is excluded.
        """
        org_id = make_org()
        region_id = make_region()
        school_old = make_school(org_id, region_id=region_id, name="Old School")
        school_new = make_school(org_id, region_id=region_id, name="New School")

        # Coach is currently assigned to school_new only
        coach = make_user_with_staff(role="head_coach", school_id=school_new)

        # EOD at old school — no current assignment there
        old_eod = make_eod_report(school_old, coach["staff_id"], report_date="2026-04-15")
        new_eod = make_eod_report(school_new, coach["staff_id"], report_date="2026-04-16")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200
        ids = {r["eod_id"] for r in _json(resp).get("eod_reports", [])}
        assert new_eod in ids, "Current school report should appear"
        assert old_eod not in ids, "Prior school report must NOT appear for head_coach"

    def test_list_eod_unauthenticated(self, client):
        """No session cookie — 401."""
        resp = _get(client)
        assert resp.status_code == 401
        assert _json(resp)["error"] == "Authentication required."
