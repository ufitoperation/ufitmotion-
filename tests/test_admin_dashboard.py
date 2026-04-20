"""
test_admin_dashboard.py — Phase 3A: Admin Dashboard Routes — RED-phase test suite.

All test cases from §10 of docs/specs/phase-3a-admin-dashboard.md.

Routes under test:
  GET /api/admin/dashboard
  GET /api/admin/schools
  GET /api/admin/coaches
  GET /api/admin/incidents
  GET /api/admin/students/growth

Authorized roles: ceo, admin, coach_overseer
All other roles → 403
"""

import datetime
import json
import math
import pytest

# Frozen "today" — Monday 2026-04-20 — used by all week-sensitive tests.
# Pacific time: this is week Mon 2026-04-20 → Sun 2026-04-26.
TODAY_MON = datetime.date(2026, 4, 20)  # Monday


# ===========================================================================
# Helpers
# ===========================================================================

def _get(client, path, params=None):
    return client.get(path, query_string=params or {})


def _json(resp):
    return json.loads(resp.data)


def _freeze_week(monkeypatch):
    """Freeze _now_pacific to TODAY_MON (Monday 2026-04-20 at 08:00 Pacific)."""
    from zoneinfo import ZoneInfo
    _PACIFIC = ZoneInfo("America/Los_Angeles")
    frozen = datetime.datetime(2026, 4, 20, 8, 0, 0, tzinfo=_PACIFIC)
    monkeypatch.setattr("app.routes.admin_routes._now_pacific", lambda: frozen)


def _week_start():
    """Return week_start ISO string matching the frozen week (Mon 2026-04-20)."""
    return "2026-04-20"


def _week_end():
    """Return week_end ISO string matching the frozen week (Sun 2026-04-26)."""
    return "2026-04-26"


# ===========================================================================
# Fixtures — admin and overseer clients
# ===========================================================================

@pytest.fixture()
def ceo_client(app, make_user_with_staff):
    """Test client authenticated as a ceo user."""
    u = make_user_with_staff(role="ceo")
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = u["user_id"]
        yield c


@pytest.fixture()
def overseer_client(app, make_user_with_staff, make_org, make_school):
    """Test client authenticated as a coach_overseer with a school assignment."""
    org_id = make_org()
    school_id = make_school(org_id)
    u = make_user_with_staff(role="coach_overseer", school_id=school_id)
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = u["user_id"]
        yield c


# ===========================================================================
# GET /api/admin/dashboard
# ===========================================================================

class TestAdminDashboard:

    def test_dashboard_unauthenticated(self, client):
        resp = _get(client, "/api/admin/dashboard")
        assert resp.status_code == 401
        assert "error" in _json(resp)

    def test_dashboard_wrong_role_head_coach(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="head_coach")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/dashboard")
        assert resp.status_code == 403
        assert "error" in _json(resp)

    def test_dashboard_wrong_role_site_coordinator(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="site_coordinator")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/dashboard")
        assert resp.status_code == 403

    def test_dashboard_admin_allowed(self, admin_client):
        resp = _get(admin_client, "/api/admin/dashboard")
        assert resp.status_code == 200

    def test_dashboard_coach_overseer_allowed(self, overseer_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(overseer_client, "/api/admin/dashboard")
        assert resp.status_code == 200

    def test_dashboard_active_school_count(
        self,
        admin_client,
        make_org,
        make_school,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        s1 = make_school(org_id, name="Active School A")
        s2 = make_school(org_id, name="Active School B")

        resp = _get(admin_client, "/api/admin/dashboard")
        assert resp.status_code == 200
        data = _json(resp)
        assert "active_schools" in data
        assert data["active_schools"] >= 2

    def test_dashboard_active_coach_count(
        self,
        admin_client,
        make_org,
        make_school,
        make_user_with_staff,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        make_user_with_staff(role="head_coach", school_id=school_id)
        make_user_with_staff(role="assistant_coach", school_id=school_id)

        resp = _get(admin_client, "/api/admin/dashboard")
        data = _json(resp)
        assert data["active_coaches"] >= 2

    def test_dashboard_sessions_this_week(
        self,
        admin_client,
        make_org,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        prog_id = make_program(school_id)
        u = make_user_with_staff(role="head_coach", school_id=school_id)
        # Session during the frozen week
        make_session(school_id, prog_id, u["staff_id"], session_date=_week_start())

        resp = _get(admin_client, "/api/admin/dashboard")
        data = _json(resp)
        assert "sessions_this_week" in data
        assert data["sessions_this_week"] >= 1

    def test_dashboard_eod_compliance_rate_shape(
        self,
        admin_client,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/dashboard")
        data = _json(resp)
        assert "eod_compliance_rate" in data
        rate = data["eod_compliance_rate"]
        assert isinstance(rate, (float, int))
        assert 0.0 <= rate <= 1.0

    def test_dashboard_compliance_zero_sessions_returns_zero(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        monkeypatch,
    ):
        """When no sessions exist this week, compliance rate is 0.0."""
        _freeze_week(monkeypatch)
        # Use a far-future frozen week with no sessions
        from zoneinfo import ZoneInfo
        _PACIFIC = ZoneInfo("America/Los_Angeles")
        frozen = datetime.datetime(2099, 6, 2, 8, 0, 0, tzinfo=_PACIFIC)  # A Monday
        monkeypatch.setattr("app.routes.admin_routes._now_pacific", lambda: frozen)

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/dashboard")
        data = _json(resp)
        assert data["eod_compliance_rate"] == 0.0

    def test_dashboard_open_incidents(
        self,
        admin_client,
        make_org,
        make_school,
        make_user_with_staff,
        make_incident,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        u = make_user_with_staff(role="head_coach", school_id=school_id)
        make_incident(school_id, u["staff_id"], status="open")

        resp = _get(admin_client, "/api/admin/dashboard")
        data = _json(resp)
        assert "open_incidents" in data
        assert data["open_incidents"] >= 1

    def test_dashboard_response_shape(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/dashboard")
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True
        for key in ("active_schools", "active_coaches", "sessions_this_week",
                    "eod_compliance_rate", "open_incidents"):
            assert key in data, f"Missing key: {key}"


# ===========================================================================
# GET /api/admin/schools
# ===========================================================================

class TestAdminSchools:

    def test_schools_unauthenticated(self, client):
        resp = _get(client, "/api/admin/schools")
        assert resp.status_code == 401

    def test_schools_wrong_role(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="head_coach")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/schools")
        assert resp.status_code == 403

    def test_schools_returns_200(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/schools")
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True
        assert "schools" in data
        assert "total" in data

    def test_schools_enrichment_fields(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_program,
        make_session,
        make_eod_report,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id, name=f"Enrichment Test School {datetime.datetime.now().timestamp()}")
        prog_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 1 session this week
        make_session(school_id, prog_id, coach["staff_id"], session_date=_week_start())
        # 1 EOD on a known date
        make_eod_report(school_id, coach["staff_id"], report_date="2026-04-19")

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/schools")
        data = _json(resp)
        # Find our school
        school_row = next((s for s in data["schools"] if s["school_id"] == school_id), None)
        assert school_row is not None
        assert school_row["coach_count"] >= 1
        assert school_row["session_count_this_week"] >= 1
        assert school_row["last_eod_date"] == "2026-04-19"

    def test_schools_no_eod_null(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id, name=f"No EOD School {datetime.datetime.now().timestamp()}")

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/schools")
        data = _json(resp)
        school_row = next((s for s in data["schools"] if s["school_id"] == school_id), None)
        assert school_row is not None
        assert school_row["last_eod_date"] is None

    def test_schools_ordered_by_name(self, admin_client, make_org, make_school, monkeypatch):
        _freeze_week(monkeypatch)
        org_id = make_org()
        make_school(org_id, name="ZZZZZ Last School")
        make_school(org_id, name="AAAAA First School")

        resp = _get(admin_client, "/api/admin/schools")
        data = _json(resp)
        names = [s["school_name"] for s in data["schools"]]
        assert names == sorted(names)

    def test_schools_total_matches_list(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/schools")
        data = _json(resp)
        assert data["total"] == len(data["schools"])


# ===========================================================================
# GET /api/admin/coaches
# ===========================================================================

class TestAdminCoaches:

    def test_coaches_unauthenticated(self, client):
        resp = _get(client, "/api/admin/coaches")
        assert resp.status_code == 401

    def test_coaches_wrong_role(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="head_coach")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/coaches")
        assert resp.status_code == 403

    def test_coaches_returns_200(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/coaches")
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True
        assert "coaches" in data
        assert "total" in data

    def test_coaches_compliance_metrics(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_incident,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # Insert 2 EODs (on-time + late) and 1 incident in a single context
        eod_ids = []
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            ts = now_utc()
            cur1 = db.execute(
                """INSERT INTO eod_reports
                   (school_id, staff_id, report_date, activities_completed,
                    student_engagement_summary, submitted_on_time, created_at)
                   VALUES (?, ?, ?, 'act', 'eng', 1, ?)""",
                (school_id, coach["staff_id"], _week_start(), ts),
            )
            db.commit()
            eod_ids.append(cur1.lastrowid)
            cur2 = db.execute(
                """INSERT INTO eod_reports
                   (school_id, staff_id, report_date, activities_completed,
                    student_engagement_summary, submitted_on_time, created_at)
                   VALUES (?, ?, ?, 'act', 'eng', 0, ?)""",
                (school_id, coach["staff_id"], _week_end(), ts),
            )
            db.commit()
            eod_ids.append(cur2.lastrowid)
            db.close()

        make_incident(school_id, coach["staff_id"], report_date=_week_start(), status="open")

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/coaches")
        data = _json(resp)
        coach_row = next((x for x in data["coaches"] if x["staff_id"] == coach["staff_id"]), None)
        assert coach_row is not None
        assert coach_row["eod_submissions_this_week"] >= 2
        assert coach_row["late_submissions_this_week"] >= 1
        assert coach_row["incidents_filed_this_week"] >= 1

        # cleanup
        with app.app_context():
            from app.database import get_db
            db = get_db()
            for eid in eod_ids:
                db.execute("DELETE FROM eod_reports WHERE eod_id = ?", (eid,))
            db.commit()
            db.close()

    def test_coaches_inactive_excluded(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        # Create an inactive coach
        inactive = make_user_with_staff(role="head_coach")
        with app.app_context():
            from app.database import get_db
            db = get_db()
            db.execute("UPDATE users SET active_status=0 WHERE user_id=?", (inactive["user_id"],))
            db.commit()
            db.close()

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/coaches")
        data = _json(resp)
        user_ids = [x["user_id"] for x in data["coaches"]]
        assert inactive["user_id"] not in user_ids

    def test_coaches_ordered_by_last_name(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        make_user_with_staff(role="head_coach", school_id=school_id,
                             first_name="Zoe", last_name="Zimmerman")
        make_user_with_staff(role="assistant_coach", school_id=school_id,
                             first_name="Amy", last_name="Anderson")

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/coaches")
        data = _json(resp)
        last_names = [x["last_name"] for x in data["coaches"]]
        assert last_names == sorted(last_names)

    def test_coaches_has_required_fields(self, admin_client, make_org, make_school,
                                          make_user_with_staff, monkeypatch):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        make_user_with_staff(role="head_coach", school_id=school_id)

        resp = _get(admin_client, "/api/admin/coaches")
        data = _json(resp)
        if data["coaches"]:
            row = data["coaches"][0]
            for key in ("user_id", "role", "first_name", "last_name",
                        "eod_submissions_this_week", "late_submissions_this_week",
                        "incidents_filed_this_week"):
                assert key in row, f"Missing key: {key}"


# ===========================================================================
# GET /api/admin/incidents
# ===========================================================================

class TestAdminIncidents:

    def test_incidents_unauthenticated(self, client):
        resp = _get(client, "/api/admin/incidents")
        assert resp.status_code == 401

    def test_incidents_wrong_role(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="head_coach")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/incidents")
        assert resp.status_code == 403

    def test_incidents_default_4_weeks(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents")
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True
        assert data["weeks"] == 4

    def test_incidents_custom_weeks(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "6"})
        assert resp.status_code == 200
        data = _json(resp)
        assert data["weeks"] == 6
        assert len(data["by_week"]) == 6

    def test_incidents_invalid_weeks_non_integer(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "abc"})
        assert resp.status_code == 422
        assert "error" in _json(resp)

    def test_incidents_invalid_weeks_zero(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "0"})
        assert resp.status_code == 422

    def test_incidents_invalid_weeks_too_large(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "13"})
        assert resp.status_code == 422

    def test_incidents_by_week_has_n_entries(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        for n in (1, 4, 8, 12):
            resp = _get(admin_client, "/api/admin/incidents", {"weeks": str(n)})
            data = _json(resp)
            assert len(data["by_week"]) == n, f"Expected {n} week entries, got {len(data['by_week'])}"

    def test_incidents_zero_fill_empty_weeks(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_incident,
        monkeypatch,
    ):
        """All N week slots present even if some weeks have no incidents."""
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        u_coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # Only 1 incident in the 4-week window
        # week_start for frozen week = 2026-04-20, so 4 weeks back starts 2026-03-23
        make_incident(school_id, u_coach["staff_id"], report_date="2026-03-23", status="open")

        u_admin = make_user_with_staff(role="admin")
        with authenticated_client(u_admin["user_id"]) as c:
            resp = _get(c, "/api/admin/incidents", {"weeks": "4"})
        data = _json(resp)
        assert len(data["by_week"]) == 4
        counts = [w["count"] for w in data["by_week"]]
        assert 0 in counts  # some weeks are zero

    def test_incidents_by_severity_sorted_desc(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_incident,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        u_coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # 3 low, 1 high in window (2026-04-06 is in the 4-week window before 2026-04-20)
        for _ in range(3):
            make_incident(school_id, u_coach["staff_id"],
                          report_date="2026-04-06", severity_level="low")
        make_incident(school_id, u_coach["staff_id"],
                      report_date="2026-04-06", severity_level="high")

        u_admin = make_user_with_staff(role="admin")
        with authenticated_client(u_admin["user_id"]) as c:
            resp = _get(c, "/api/admin/incidents", {"weeks": "4"})
        data = _json(resp)
        counts = [x["count"] for x in data["by_severity"]]
        assert counts == sorted(counts, reverse=True)

    def test_incidents_total_equals_sum_of_weeks(
        self,
        admin_client,
        monkeypatch,
    ):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "4"})
        data = _json(resp)
        assert data["total"] == sum(w["count"] for w in data["by_week"])

    def test_incidents_response_shape(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents")
        data = _json(resp)
        assert data.get("ok") is True
        for key in ("weeks", "window_start", "window_end", "total",
                    "by_severity", "by_school", "by_week"):
            assert key in data, f"Missing key: {key}"

    def test_incidents_by_week_sorted_asc(self, admin_client, monkeypatch):
        _freeze_week(monkeypatch)
        resp = _get(admin_client, "/api/admin/incidents", {"weeks": "4"})
        data = _json(resp)
        dates = [w["week_start"] for w in data["by_week"]]
        assert dates == sorted(dates)


# ===========================================================================
# GET /api/admin/students/growth
# ===========================================================================

class TestAdminStudentsGrowth:

    def test_growth_unauthenticated(self, client):
        resp = _get(client, "/api/admin/students/growth")
        assert resp.status_code == 401

    def test_growth_wrong_role(self, app, make_user_with_staff, authenticated_client):
        u = make_user_with_staff(role="head_coach")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/students/growth")
        assert resp.status_code == 403

    def test_growth_returns_200(self, admin_client):
        resp = _get(admin_client, "/api/admin/students/growth")
        assert resp.status_code == 200
        data = _json(resp)
        assert data.get("ok") is True

    def test_growth_response_shape_no_filter(self, admin_client):
        resp = _get(admin_client, "/api/admin/students/growth")
        data = _json(resp)
        assert data.get("ok") is True
        for key in ("window_id", "assessed_students", "total_students",
                    "by_school", "by_skill_domain"):
            assert key in data, f"Missing key: {key}"
        assert data["window_id"] is None

    def test_growth_invalid_window_id_string(self, admin_client):
        resp = _get(admin_client, "/api/admin/students/growth", {"window_id": "abc"})
        assert resp.status_code == 400
        assert "error" in _json(resp)

    def test_growth_invalid_window_id_zero(self, admin_client):
        resp = _get(admin_client, "/api/admin/students/growth", {"window_id": "0"})
        assert resp.status_code == 400

    def test_growth_nonexistent_window_returns_zeroes(self, admin_client):
        resp = _get(admin_client, "/api/admin/students/growth", {"window_id": "99999"})
        assert resp.status_code == 200
        data = _json(resp)
        assert data["assessed_students"] == 0
        assert data["by_skill_domain"] == []

    def test_growth_total_students_counts_active(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_student,
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        make_student(school_id, active=True)
        make_student(school_id, active=True)
        # inactive student — should not be counted
        make_student(school_id, active=False)

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/students/growth")
        data = _json(resp)
        assert data["total_students"] >= 2

    def test_growth_window_filter_applied(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        student_id = make_student(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        win_a = make_assessment_window(school_id, name="Window A", status="active")
        win_b = make_assessment_window(school_id, name="Window B", status="active")
        # 1 assessment in each window
        make_assessment(student_id, school_id, win_a, coach["staff_id"],
                        scores=[(skill_id, 3)])
        make_assessment(student_id, school_id, win_b, coach["staff_id"],
                        scores=[(skill_id, 4)])

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            # filter to win_a only
            resp = _get(c, "/api/admin/students/growth", {"window_id": str(win_a)})
        data = _json(resp)
        assert data["window_id"] == win_a
        assert data["assessed_students"] >= 1

    def test_growth_by_school_includes_zero_assessed(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_student,
    ):
        org_id = make_org()
        # School with students but no assessments
        school_id = make_school(org_id, name=f"Zero Assessed School {datetime.datetime.now().timestamp()}")
        make_student(school_id)

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/students/growth")
        data = _json(resp)
        school_row = next((s for s in data["by_school"] if s["school_id"] == school_id), None)
        assert school_row is not None
        assert school_row["assessed_count"] == 0
        assert school_row["total_students"] >= 1

    def test_growth_by_skill_domain_avg_raw_level(
        self,
        app,
        make_user_with_staff,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        student_id = make_student(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        domain_id = make_skill_domain(name=f"Domain Avg Test {datetime.datetime.now().timestamp()}")
        skill_a = make_skill(domain_id)
        skill_b = make_skill(domain_id)
        win = make_assessment_window(school_id, status="active")
        # Two scores: 2 and 4 → avg = 3.0
        make_assessment(student_id, school_id, win, coach["staff_id"],
                        scores=[(skill_a, 2), (skill_b, 4)])

        u = make_user_with_staff(role="admin")
        with authenticated_client(u["user_id"]) as c:
            resp = _get(c, "/api/admin/students/growth")
        data = _json(resp)
        domain_row = next((d for d in data["by_skill_domain"]
                           if d["skill_domain_id"] == domain_id), None)
        assert domain_row is not None
        assert domain_row["avg_raw_level"] == 3.0

    def test_growth_coach_overseer_allowed(self, overseer_client):
        resp = _get(overseer_client, "/api/admin/students/growth")
        assert resp.status_code == 200
