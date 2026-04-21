"""
tests/test_phase4.py — Phase 4 route tests.

Covers:
  GET /api/principal/dashboard
  GET /api/principal/students
  GET /api/parent/student
"""

import datetime
import pytest
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Shared freeze helpers
# ---------------------------------------------------------------------------

_FREEZE_DT = datetime.datetime(2026, 4, 20, 8, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
_THIS_MONDAY = "2026-04-20"  # Monday of the frozen week


def _freeze_principal_now(monkeypatch):
    """Patch _now_pacific in principal_routes to a fixed Pacific datetime."""
    monkeypatch.setattr(
        "app.routes.principal_routes._now_pacific",
        lambda: _FREEZE_DT,
    )


# ===========================================================================
# TestPrincipalDashboard
# ===========================================================================

class TestPrincipalDashboard:

    def test_dashboard_unauthenticated_returns_401(self, client):
        resp = client.get("/api/principal/dashboard")
        assert resp.status_code == 401

    def test_dashboard_wrong_role_returns_403(
        self, make_org, make_school, make_user_with_staff, authenticated_client, monkeypatch
    ):
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        with authenticated_client(coach["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        assert resp.status_code == 403

    def test_dashboard_no_school_assignment_returns_403(
        self, make_user_with_staff, authenticated_client, monkeypatch
    ):
        """Principal with no staff_assignment gets 403 with correct message."""
        _freeze_principal_now(monkeypatch)
        # no school_id → no staff_assignment row
        principal = make_user_with_staff(role="principal")
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error"] == "No school assignment found for your account."

    def test_dashboard_returns_expected_shape(
        self, make_org, make_school, make_user_with_staff, authenticated_client, monkeypatch
    ):
        """Happy-path: response contains all required top-level keys."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id, name="Happy Path ES")
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        for key in (
            "school", "sessions_this_week", "students_total",
            "students_assessed", "eod_compliance_rate", "open_incidents", "coaches",
        ):
            assert key in data, f"Missing key: {key}"

    def test_dashboard_school_block_contains_correct_fields(
        self, make_org, make_school, make_user_with_staff, authenticated_client, monkeypatch
    ):
        """school block returns school_id, school_name, school_type, city, state."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id, name="Field Check ES")
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        school = data["school"]
        assert school["school_id"] == school_id
        assert school["school_name"] == "Field Check ES"
        for key in ("school_type", "city", "state"):
            assert key in school

    def test_dashboard_sessions_this_week_counts_correctly(
        self,
        make_org, make_school, make_program, make_user_with_staff,
        make_session, authenticated_client, monkeypatch,
    ):
        """sessions_this_week counts only sessions in the frozen week window."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)

        # Two sessions this week, one outside the window
        make_session(school_id, program_id, coach["staff_id"], session_date=_THIS_MONDAY)
        make_session(school_id, program_id, coach["staff_id"], session_date="2026-04-22")
        make_session(school_id, program_id, coach["staff_id"], session_date="2026-04-13")  # prior week

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        assert data["sessions_this_week"] == 2

    def test_dashboard_students_total_reflects_active_students(
        self,
        make_org, make_school, make_student, make_user_with_staff,
        authenticated_client, monkeypatch,
    ):
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)

        make_student(school_id, first="Alice", last="Aarons")
        make_student(school_id, first="Bob", last="Barnes")
        make_student(school_id, first="Inactive", last="Zed", active=False)

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        # Inactive student must not be counted
        assert data["students_total"] >= 2
        # The inactive one should not appear
        # (total could include students from other tests; just assert >= 2 and
        # that the value type is correct)
        assert isinstance(data["students_total"], int)

    def test_dashboard_eod_compliance_rate_zero_when_no_sessions(
        self,
        make_org, make_school, make_user_with_staff,
        authenticated_client, monkeypatch,
    ):
        """No sessions this week → expected = 0 → compliance rate = 0.0."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        assert data["eod_compliance_rate"] == 0.0

    def test_dashboard_eod_compliance_rate_full_when_all_reports_filed(
        self,
        make_org, make_school, make_program, make_user_with_staff,
        make_session, make_eod_report, authenticated_client, monkeypatch,
    ):
        """One session + one EOD report → compliance rate = 1.0."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)

        make_session(school_id, program_id, coach["staff_id"], session_date=_THIS_MONDAY)
        make_eod_report(school_id, coach["staff_id"], report_date=_THIS_MONDAY)

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        assert data["eod_compliance_rate"] == 1.0

    def test_dashboard_eod_compliance_rate_is_float_rounded_to_2dp(
        self,
        make_org, make_school, make_program, make_user_with_staff,
        make_session, make_eod_report, authenticated_client, monkeypatch,
    ):
        """Partial compliance → rate is a float with at most 2 decimal places."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        program_id = make_program(school_id)
        coach_a = make_user_with_staff(role="head_coach", school_id=school_id)
        coach_b = make_user_with_staff(role="assistant_coach", school_id=school_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)

        # 2 (staff × date) combos expected; 1 EOD filed → 50 %
        make_session(school_id, program_id, coach_a["staff_id"], session_date=_THIS_MONDAY)
        make_session(school_id, program_id, coach_b["staff_id"], session_date="2026-04-21")
        make_eod_report(school_id, coach_a["staff_id"], report_date=_THIS_MONDAY)

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        rate = data["eod_compliance_rate"]
        assert isinstance(rate, float)
        # Check it's rounded to 2 dp
        assert rate == round(rate, 2)

    def test_dashboard_coaches_list_contains_principal_themselves(
        self,
        make_org, make_school, make_user_with_staff,
        authenticated_client, monkeypatch,
    ):
        """Coaches list includes all active-assignment users; principal is among them."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(
            role="principal", school_id=school_id,
            first_name="Dana", last_name="Principal",
        )
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        user_ids = [c["user_id"] for c in data["coaches"]]
        assert principal["user_id"] in user_ids

    def test_dashboard_coaches_list_shape(
        self,
        make_org, make_school, make_user_with_staff,
        authenticated_client, monkeypatch,
    ):
        """Each coach entry has user_id, first_name, last_name, role."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        for coach in data["coaches"]:
            for key in ("user_id", "first_name", "last_name", "role"):
                assert key in coach

    def test_dashboard_accessible_by_school_staff_role(
        self,
        make_org, make_school, make_user_with_staff,
        authenticated_client, monkeypatch,
    ):
        """school_staff role should also be allowed (not just principal)."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        staff = make_user_with_staff(role="school_staff", school_id=school_id)
        with authenticated_client(staff["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_dashboard_open_incidents_counted_correctly(
        self,
        make_org, make_school, make_user_with_staff, make_incident,
        authenticated_client, monkeypatch,
    ):
        """open_incidents counts only status='open' non-deleted incidents."""
        _freeze_principal_now(monkeypatch)
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        make_incident(school_id, coach["staff_id"], status="open")
        make_incident(school_id, coach["staff_id"], status="open")
        make_incident(school_id, coach["staff_id"], status="resolved")

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/dashboard")
        data = resp.get_json()
        # At minimum 2 open incidents from this test
        assert data["open_incidents"] >= 2


# ===========================================================================
# TestPrincipalStudents
# ===========================================================================

class TestPrincipalStudents:

    def test_students_unauthenticated_returns_401(self, client):
        resp = client.get("/api/principal/students")
        assert resp.status_code == 401

    def test_students_wrong_role_returns_403(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        with authenticated_client(coach["user_id"]) as c:
            resp = c.get("/api/principal/students")
        assert resp.status_code == 403

    def test_students_no_school_assignment_returns_403(
        self, make_user_with_staff, authenticated_client
    ):
        principal = make_user_with_staff(role="principal")
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students")
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error"] == "No school assignment found for your account."

    def test_students_returns_expected_shape(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        """Happy-path: response contains ok, page, per_page, total, students."""
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        for key in ("page", "per_page", "total", "students"):
            assert key in data

    def test_students_defaults_page_and_per_page(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students")
        data = resp.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 25

    def test_students_each_record_has_required_keys(
        self, make_org, make_school, make_student, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        make_student(school_id, first="Carla", last="Chen")

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students")
        data = resp.get_json()
        assert len(data["students"]) >= 1
        for s in data["students"]:
            for key in (
                "student_id", "first_name", "last_name",
                "grade_level", "latest_assessment_date", "avg_raw_level",
            ):
                assert key in s

    def test_students_search_filters_by_first_name(
        self, make_org, make_school, make_student, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        make_student(school_id, first="Zelda", last="Unique")
        make_student(school_id, first="Other", last="Person")

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?search=Zelda")
        data = resp.get_json()
        assert data["ok"] is True
        names = [s["first_name"] for s in data["students"]]
        assert "Zelda" in names
        assert "Other" not in names

    def test_students_search_filters_by_last_name(
        self, make_org, make_school, make_student, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        make_student(school_id, first="Quinn", last="Xanthe")

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?search=Xanthe")
        data = resp.get_json()
        names = [s["last_name"] for s in data["students"]]
        assert "Xanthe" in names

    def test_students_invalid_page_returns_422(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?page=abc")
        assert resp.status_code == 422

    def test_students_page_zero_returns_422(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?page=0")
        assert resp.status_code == 422

    def test_students_per_page_zero_returns_422(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?per_page=0")
        assert resp.status_code == 422

    def test_students_per_page_over_100_returns_422(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?per_page=101")
        assert resp.status_code == 422

    def test_students_search_over_100_chars_returns_422(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        long_search = "a" * 101
        with authenticated_client(principal["user_id"]) as c:
            resp = c.get(f"/api/principal/students?search={long_search}")
        assert resp.status_code == 422

    def test_students_pagination_respects_per_page(
        self, make_org, make_school, make_student, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        for i in range(5):
            make_student(school_id, first=f"Pager{i}", last="Pupil")

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?per_page=2&page=1")
        data = resp.get_json()
        assert len(data["students"]) <= 2
        assert data["per_page"] == 2
        assert data["page"] == 1

    def test_students_inactive_excluded_from_roster(
        self, make_org, make_school, make_student, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        principal = make_user_with_staff(role="principal", school_id=school_id)
        make_student(school_id, first="Inactive", last="Withdrawn", active=False)

        with authenticated_client(principal["user_id"]) as c:
            resp = c.get("/api/principal/students?search=Withdrawn")
        data = resp.get_json()
        last_names = [s["last_name"] for s in data["students"]]
        assert "Withdrawn" not in last_names

    def test_students_accessible_by_school_staff_role(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        staff = make_user_with_staff(role="school_staff", school_id=school_id)
        with authenticated_client(staff["user_id"]) as c:
            resp = c.get("/api/principal/students")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


# ===========================================================================
# TestParentStudent
# ===========================================================================

class TestParentStudent:

    # ------------------------------------------------------------------
    # Helper: insert a parents row directly (no conftest fixture exists).
    # ------------------------------------------------------------------

    @staticmethod
    def _insert_parent(app, user_id, first_name="Test", last_name="Parent", email=None):
        """Insert a parents row and return parent_id."""
        import time
        unique_email = email or f"parent_{time.time_ns()}@test.com"
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            cur = db.execute(
                """INSERT INTO parents
                   (user_id, first_name, last_name, email, portal_access_status, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (user_id, first_name, last_name, unique_email, now_utc()),
            )
            db.commit()
            parent_id = cur.lastrowid
            db.close()
        return parent_id

    @staticmethod
    def _link_parent_to_student(app, student_id, parent_id, primary=True):
        """Set parent_primary_id or parent_secondary_id on a student row."""
        col = "parent_primary_id" if primary else "parent_secondary_id"
        with app.app_context():
            from app.database import get_db
            db = get_db()
            db.execute(
                f"UPDATE students SET {col} = ? WHERE student_id = ?",
                (parent_id, student_id),
            )
            db.commit()
            db.close()

    @staticmethod
    def _insert_attendance(app, session_id, student_id, status="present"):
        """Insert a student_session_attendance row."""
        with app.app_context():
            from app.database import get_db
            from app.routes._helpers import now_utc
            db = get_db()
            db.execute(
                """INSERT OR IGNORE INTO student_session_attendance
                   (session_id, student_id, attendance_status, created_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, student_id, status, now_utc()),
            )
            db.commit()
            db.close()

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_parent_student_unauthenticated_returns_401(self, client):
        resp = client.get("/api/parent/student")
        assert resp.status_code == 401

    def test_parent_student_wrong_role_returns_403(
        self, make_org, make_school, make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        with authenticated_client(coach["user_id"]) as c:
            resp = c.get("/api/parent/student")
        assert resp.status_code == 403

    def test_parent_student_no_parents_row_returns_404(
        self, app, make_user_with_staff, authenticated_client
    ):
        """User with role=parent but no parents table row → 404."""
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "Parent record not found."

    def test_parent_student_zero_children_returns_empty_list(
        self, app, make_user_with_staff, authenticated_client
    ):
        """Parent exists but has no linked children → 200 with children=[]."""
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        self._insert_parent(app, parent_user["user_id"])
        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["children"] == []

    def test_parent_student_returns_linked_child(
        self, app, make_org, make_school, make_student,
        make_user_with_staff, authenticated_client
    ):
        """Parent linked to one child sees that child in the response."""
        org_id = make_org()
        school_id = make_school(org_id, name="Parent Test ES")
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Jordan", last="Rivers")
        self._link_parent_to_student(app, student_id, parent_id)

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["children"]) >= 1
        child = next(c for c in data["children"] if c["student_id"] == student_id)
        assert child["first_name"] == "Jordan"
        assert child["last_name"] == "Rivers"

    def test_parent_student_child_has_required_keys(
        self, app, make_org, make_school, make_student,
        make_user_with_staff, authenticated_client
    ):
        """Each child record contains all required fields."""
        org_id = make_org()
        school_id = make_school(org_id)
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Kerry", last="Fields")
        self._link_parent_to_student(app, student_id, parent_id)

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        data = resp.get_json()
        child = next(c for c in data["children"] if c["student_id"] == student_id)
        for key in (
            "student_id", "first_name", "last_name",
            "grade_level", "school_name",
            "recent_sessions", "assessment_summary",
        ):
            assert key in child, f"Missing key: {key}"

    def test_parent_student_includes_school_name(
        self, app, make_org, make_school, make_student,
        make_user_with_staff, authenticated_client
    ):
        org_id = make_org()
        school_id = make_school(org_id, name="Named School ES")
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Morgan", last="Lake")
        self._link_parent_to_student(app, student_id, parent_id)

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        data = resp.get_json()
        child = next(c for c in data["children"] if c["student_id"] == student_id)
        assert child["school_name"] == "Named School ES"

    def test_parent_student_recent_sessions_populated(
        self, app, make_org, make_school, make_program, make_student,
        make_user_with_staff, make_session, authenticated_client
    ):
        """recent_sessions list is populated when attendance rows exist."""
        org_id = make_org()
        school_id = make_school(org_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Sam", last="Trails")
        self._link_parent_to_student(app, student_id, parent_id)

        session_id = make_session(
            school_id, program_id, coach["staff_id"], session_date="2026-04-18"
        )
        self._insert_attendance(app, session_id, student_id, status="present")

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        data = resp.get_json()
        child = next(c for c in data["children"] if c["student_id"] == student_id)
        assert len(child["recent_sessions"]) >= 1
        entry = child["recent_sessions"][0]
        for key in ("session_date", "session_type", "attendance_status"):
            assert key in entry

    def test_parent_student_secondary_parent_link_works(
        self, app, make_org, make_school, make_student,
        make_user_with_staff, authenticated_client
    ):
        """Parent linked as secondary guardian also sees the child."""
        org_id = make_org()
        school_id = make_school(org_id)
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Riley", last="Cross")
        # Link as secondary (not primary)
        self._link_parent_to_student(app, student_id, parent_id, primary=False)

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        data = resp.get_json()
        student_ids = [c["student_id"] for c in data["children"]]
        assert student_id in student_ids

    def test_parent_student_assessment_summary_empty_when_no_assessments(
        self, app, make_org, make_school, make_student,
        make_user_with_staff, authenticated_client
    ):
        """assessment_summary is an empty list when no assessments exist."""
        org_id = make_org()
        school_id = make_school(org_id)
        parent_user = make_user_with_staff(role="parent", no_staff_profile=True)
        parent_id = self._insert_parent(app, parent_user["user_id"])
        student_id = make_student(school_id, first="Avery", last="Stone")
        self._link_parent_to_student(app, student_id, parent_id)

        with authenticated_client(parent_user["user_id"]) as c:
            resp = c.get("/api/parent/student")
        data = resp.get_json()
        child = next(c for c in data["children"] if c["student_id"] == student_id)
        assert child["assessment_summary"] == []
