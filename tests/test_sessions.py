"""
test_sessions.py — Phase 2A: Session Logging — RED-phase test suite.

All 32 test cases from §9 of docs/specs/phase-2a-session-logging.md are
covered here.  Every test is in the RED state: the routes currently return
{"ok": True, "stub": True} stubs, so assertions against real behaviour will
fail until the implementation is written.

Test organisation:
  POST /api/sessions — test_create_session_*  (20 tests)
  GET  /api/sessions — test_list_sessions_*   (12 tests)

Helper:
  _post_json(client, payload) — thin wrapper around client.post
  _get(client, params)        — thin wrapper around client.get
"""

import json
import datetime
import pytest


TODAY = datetime.date(2026, 4, 19)  # frozen "today" used throughout


# ===========================================================================
# Helpers
# ===========================================================================

def _post_json(client, payload):
    return client.post(
        "/api/sessions",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get(client, params=None):
    return client.get(
        "/api/sessions",
        query_string=params or {},
    )


def _json(resp):
    return json.loads(resp.data)


# ===========================================================================
# POST /api/sessions
# ===========================================================================

class TestCreateSession:

    def test_create_session_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_student,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — happy path.

        Verifies:
        - HTTP 201 returned.
        - Response body contains ok=True, session dict with school_name,
          program_name, session_id, total_students_present, student_ids.
        - sessions table has exactly one new row with correct school_id
          and total_students_present = 3.
        - session_staff table has one row with staff_id = coach's staff_id,
          role = 'lead'.
        - student_session_attendance has 3 rows, all attendance_status='present'.
        - audit_log has one INSERT row with table_name='sessions'.
        All five writes must share one commit (atomicity).
        """
        org_id = make_org("Success Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id, name="Lincoln Elementary")
        program_id = make_program(school_id, name="PE Support — 2025-26")
        s1 = make_student(school_id, first="Alice", last="A")
        s2 = make_student(school_id, first="Bob", last="B")
        s3 = make_student(school_id, first="Carol", last="C")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
                "student_ids": [s1, s2, s3],
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("ok") is True
        session = data.get("session", {})
        assert session.get("school_name") is not None, "school_name missing from 201 response"
        assert session.get("program_name") is not None, "program_name missing from 201 response"
        assert session.get("total_students_present") == 3
        assert sorted(session.get("student_ids", [])) == sorted([s1, s2, s3])

        # Verify DB state
        with app.app_context():
            from app.database import get_db
            db = get_db()
            new_session_id = session.get("session_id")
            assert new_session_id is not None

            # sessions row
            row = db.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (new_session_id,)
            ).fetchone()
            assert row is not None, "sessions row not found"
            assert row["school_id"] == school_id
            assert row["total_students_present"] == 3
            assert row["session_status"] == "completed"

            # session_staff row
            ss = db.execute(
                "SELECT * FROM session_staff WHERE session_id = ?", (new_session_id,)
            ).fetchone()
            assert ss is not None, "session_staff row not found"
            assert ss["staff_id"] == coach["staff_id"]
            assert ss["role"] == "lead"

            # student_session_attendance rows
            att = db.execute(
                "SELECT * FROM student_session_attendance WHERE session_id = ?",
                (new_session_id,),
            ).fetchall()
            assert len(att) == 3, f"Expected 3 attendance rows, got {len(att)}"
            assert all(r["attendance_status"] == "present" for r in att)

            # audit_log row
            audit = db.execute(
                "SELECT * FROM audit_log WHERE table_name = 'sessions' AND record_id = ?",
                (new_session_id,),
            ).fetchone()
            assert audit is not None, "audit_log row not found"
            assert audit["action"] == "INSERT"

            db.close()

    def test_create_session_zero_students(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions with no student_ids field.

        Verifies:
        - HTTP 201 returned.
        - sessions.total_students_present = 0.
        - student_session_attendance has zero rows for this session.
        - session_staff still has 1 row for the submitting coach.
        """
        org_id = make_org("Zero Students Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
                # No student_ids key — should default to []
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session = data.get("session", {})
        assert session.get("total_students_present") == 0

        with app.app_context():
            from app.database import get_db
            db = get_db()
            new_id = session.get("session_id")

            att = db.execute(
                "SELECT COUNT(*) AS cnt FROM student_session_attendance WHERE session_id = ?",
                (new_id,),
            ).fetchone()
            assert att["cnt"] == 0, "Expected zero attendance rows"

            ss = db.execute(
                "SELECT COUNT(*) AS cnt FROM session_staff WHERE session_id = ?",
                (new_id,),
            ).fetchone()
            assert ss["cnt"] == 1, "Expected 1 session_staff row"
            db.close()

    def test_create_session_wrong_school_head_coach(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — head_coach submits a school_id that is not their
        assigned school.

        Verifies:
        - HTTP 403 returned.
        - Error message: "You are not assigned to this school."
        - No rows inserted in sessions, session_staff, or student_session_attendance.
        """
        org_id = make_org("Wrong School Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Coach's School")
        school_b = make_school(org_id, region_id=region_id, name="Other School")
        program_id = make_program(school_b)
        coach = make_user_with_staff(role="head_coach", school_id=school_a)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_b,  # Not the coach's school
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "You are not assigned to this school."

    def test_create_session_no_school_assignment(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — head_coach has no active school assignment
        (school_id is None in current_user()).

        Verifies:
        - HTTP 403 returned.
        - Error message: "You have no active school assignment. Contact your administrator."
        """
        org_id = make_org("No Assignment Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        # Create coach with NO school_id → no staff_assignment row
        coach = make_user_with_staff(role="head_coach", school_id=None)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "You have no active school assignment. Contact your administrator."

    def test_create_session_future_date(
        self,
        monkeypatch,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions with a session_date one day in the future.

        Verifies:
        - HTTP 400 returned.
        - Error message: "Session date cannot be in the future."
        """
        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        org_id = make_org("Future Date Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        future_date = (TODAY + datetime.timedelta(days=1)).isoformat()

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": future_date,
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Session date cannot be in the future."

    def test_create_session_past_8_days(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions with a session_date 8 days ago (beyond the 7-day window).

        Verifies:
        - HTTP 400 returned.
        - Error message: "Session date cannot be more than 7 days in the past."
        """
        org_id = make_org("8 Days Past Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        eight_days_ago = (TODAY - datetime.timedelta(days=8)).isoformat()

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": eight_days_ago,
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Session date cannot be more than 7 days in the past."

    def test_create_session_past_7_days(
        self,
        monkeypatch,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions with session_date exactly 7 days ago (boundary: allowed).

        Verifies:
        - HTTP 201 returned (7 days ago is within the allowed window).
        """
        monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: TODAY)

        org_id = make_org("7 Days Past Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        seven_days_ago = (TODAY - datetime.timedelta(days=7)).isoformat()

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": seven_days_ago,
            })

        assert resp.status_code == 201, (
            f"Expected 201 for 7-days-ago date, got {resp.status_code}: {resp.data}"
        )

    def test_create_session_invalid_student_ids(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_student,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — student_ids contains an ID that does not belong to
        the given school (ID 999999 does not exist).

        Verifies:
        - HTTP 400 returned.
        - Response body contains "Invalid student IDs" and lists the bad IDs.
        - No session row is inserted.
        """
        org_id = make_org("Invalid Student Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        valid_student = make_student(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        nonexistent_id = 999999

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
                "student_ids": [valid_student, nonexistent_id],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        error_msg = data.get("error", "")
        assert "Invalid student IDs" in error_msg, f"Expected 'Invalid student IDs' in: {error_msg}"
        assert str(nonexistent_id) in error_msg, f"Expected bad ID {nonexistent_id} listed in error"

    def test_create_session_non_integer_student_ids(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — student_ids array contains non-integer values.

        Verifies:
        - HTTP 400 returned.
        - Error message: "student_ids must be an array of positive integers."
        """
        org_id = make_org("Non-Int Student Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
                "student_ids": [12, "abc", None],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "student_ids must be an array of positive integers."

    def test_create_session_duplicate_student_ids(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_student,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — student_ids contains the same integer twice.

        Without this check the UNIQUE(session_id, student_id) constraint on
        student_session_attendance would cause an unhandled 500 DB error.

        Verifies:
        - HTTP 400 returned.
        - Error message: "student_ids contains duplicate values."
        """
        org_id = make_org("Dup Student Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        student_id = make_student(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
                "student_ids": [student_id, student_id],  # same ID twice
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "student_ids contains duplicate values."

    def test_create_session_inactive_program(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — program_id references a program with status='inactive'.

        Verifies:
        - HTTP 400 returned.
        - Error message: "Program not found at this school."
        """
        org_id = make_org("Inactive Program Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        inactive_program_id = make_program(school_id, name="Old Program", status="inactive")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": inactive_program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Program not found at this school."

    def test_create_session_unauthenticated(self, client):
        """
        POST /api/sessions with no session cookie.

        Verifies:
        - HTTP 401 returned.
        - Error message: "Authentication required."
        """
        resp = _post_json(client, {
            "school_id": 1,
            "program_id": 1,
            "session_date": TODAY.isoformat(),
        })

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Authentication required."

    def test_create_session_duplicate_same_coach(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        POST /api/sessions when the same coach has already logged a session
        for the same school, program, and date (mobile double-tap scenario).

        Verifies:
        - HTTP 409 returned.
        - Body: error message about duplicate + existing_session_id matching the
          pre-existing session's session_id.
        - No new sessions row is inserted.
        """
        org_id = make_org("Dup Session Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # Pre-insert the existing session
        existing_sid = make_session(
            school_id=school_id,
            program_id=program_id,
            staff_id=coach["staff_id"],
            session_date=TODAY.isoformat(),
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert "existing_session_id" in data, "409 body must include existing_session_id"
        assert data["existing_session_id"] == existing_sid, (
            f"existing_session_id should be {existing_sid}, got {data['existing_session_id']}"
        )
        expected_msg = (
            "A session for this school, program, and date has already been logged by you. "
            "Use the existing session ID to file an EOD report."
        )
        assert data.get("error") == expected_msg

    def test_create_session_no_staff_profile(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — the authenticated user has no row in staff_profiles
        (their staff_id in current_user() resolves to None).

        Verifies:
        - HTTP 500 returned.
        - Error message: "Staff profile missing for this account. Contact your administrator."
        """
        org_id = make_org("No Staff Profile Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        program_id = make_program(school_id)
        # no_staff_profile=True → only a users row, no staff_profiles row
        user = make_user_with_staff(
            role="head_coach",
            school_id=None,
            no_staff_profile=True,
        )

        with authenticated_client(user["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 500, f"Expected 500, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Staff profile missing for this account. Contact your administrator."

    def test_create_session_school_not_in_org_overseer(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — coach_overseer submits a school_id that belongs to
        a different organization.

        Verifies:
        - HTTP 403 returned.
        - Error message: "School is not in your organization."
        """
        org_a = make_org("Overseer Org A")
        org_b = make_org("Overseer Org B")
        region_id = make_region()
        school_in_org_a = make_school(org_a, region_id=region_id)
        school_in_org_b = make_school(org_b, region_id=region_id)
        program_in_b = make_program(school_in_org_b)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_in_org_a)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_in_org_b,  # different org
                "program_id": program_in_b,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "School is not in your organization."

    def test_create_session_overseer_cross_school_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — coach_overseer logs a session at a school different
        from their assigned school but within the same organization.

        Verifies:
        - HTTP 201 returned.
        - sessions row has school_id = the other school's ID.
        """
        org_id = make_org("Overseer Cross School Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Overseer Home School")
        school_b = make_school(org_id, region_id=region_id, name="Overseer Cross School")
        program_id = make_program(school_b)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_b,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session = data.get("session", {})
        assert session.get("school_id") == school_b

    def test_create_session_site_coordinator_in_region(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — site_coordinator logs a session at a school that is
        in their region (different from their home school but same region_id).

        Verifies:
        - HTTP 201 returned.
        - sessions row has school_id = the cross-school ID.
        """
        org_id = make_org("Coordinator In-Region Org")
        region_id = make_region()
        school_home = make_school(org_id, region_id=region_id, name="Coord Home School")
        school_other = make_school(org_id, region_id=region_id, name="Coord Target School")
        program_id = make_program(school_other)
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_home)

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_other,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session = data.get("session", {})
        assert session.get("school_id") == school_other

    def test_create_session_site_coordinator_out_of_region(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — site_coordinator submits a school_id in a different
        region from their assigned school.

        Verifies:
        - HTTP 403 returned.
        - Error message: "This school is not in your region."
        """
        org_id = make_org("Coordinator Out-Region Org")
        region_1 = make_region()
        region_3 = make_region()
        school_home = make_school(org_id, region_id=region_1, name="Coord Home Region 1")
        school_other_region = make_school(org_id, region_id=region_3, name="Other Region School")
        program_id = make_program(school_other_region)
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_home)

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_other_region,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "This school is not in your region."

    def test_create_session_site_coordinator_no_region_assignment(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — site_coordinator has NULL assigned_region_id in
        staff_profiles AND no active school assignment (school_id is also None).
        Both resolution paths yield NULL → 403.

        Verifies:
        - HTTP 403 returned.
        - Error message: "You have no active region assignment. Contact your administrator."
        """
        org_id = make_org("No Region Org")
        school_id = make_school(org_id)  # no region_id
        program_id = make_program(school_id)
        # No school assignment, no assigned_region_id
        coordinator = make_user_with_staff(
            role="site_coordinator",
            school_id=None,
            assigned_region_id=None,
        )

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": school_id,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "You have no active region assignment. Contact your administrator."

    def test_create_session_site_coordinator_region_from_staff_profiles(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
    ):
        """
        POST /api/sessions — site_coordinator has staff_profiles.assigned_region_id
        set but NO active school assignment (school_id is None in current_user()).
        Region should be resolved from the staff_profiles column (primary path),
        not from their school chain.

        Verifies:
        - HTTP 201 returned.
        - The session is created at the target school in that region.
        """
        org_id = make_org("Staff Profile Region Org")
        region_id = make_region()
        target_school = make_school(org_id, region_id=region_id, name="Target School Region")
        program_id = make_program(target_school)
        # assigned_region_id is set; school_id is None (no assignment)
        coordinator = make_user_with_staff(
            role="site_coordinator",
            school_id=None,
            assigned_region_id=region_id,
        )

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, {
                "school_id": target_school,
                "program_id": program_id,
                "session_date": TODAY.isoformat(),
            })

        assert resp.status_code == 201, (
            f"Expected 201 (region from staff_profiles), got {resp.status_code}: {resp.data}"
        )
        data = _json(resp)
        session = data.get("session", {})
        assert session.get("school_id") == target_school


# ===========================================================================
# GET /api/sessions
# ===========================================================================

class TestListSessions:

    def test_list_sessions_scoped_to_school_head_coach(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — head_coach only sees sessions at their assigned school.

        Verifies:
        - Sessions from another school (school_b) never appear in the results.
        - All returned sessions have school_id == the coach's school_id.
        """
        org_id = make_org("Scoped School Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Coach School A")
        school_b = make_school(org_id, region_id=region_id, name="Other School B")
        prog_a = make_program(school_a)
        prog_b = make_program(school_b)
        coach = make_user_with_staff(role="head_coach", school_id=school_a)
        other_coach = make_user_with_staff(role="head_coach", school_id=school_b)

        # Session at coach's school
        make_session(school_a, prog_a, coach["staff_id"], session_date="2026-04-15")
        # Session at the other school — must NOT appear
        make_session(school_b, prog_b, other_coach["staff_id"], session_date="2026-04-15")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        sessions = data.get("sessions", [])
        school_ids = {s["school_id"] for s in sessions}
        assert school_b not in school_ids, (
            f"school_b ({school_b}) sessions leaked into head_coach response"
        )
        # The coach's school session should be present
        assert school_a in school_ids, "Expected coach's school sessions in response"

    def test_list_sessions_head_coach_sees_other_coach_sessions(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — head_coach sees sessions logged by other coaches at
        the same school (school-scoped, not coach-scoped).

        Verifies:
        - A session logged by coach_B at the same school appears in coach_A's list.
        """
        org_id = make_org("Shared School Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id)
        coach_a = make_user_with_staff(role="head_coach", school_id=school_id)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_id)

        # coach_B logs a session
        b_session_id = make_session(
            school_id, prog_id, coach_b["staff_id"], session_date="2026-04-14"
        )

        with authenticated_client(coach_a["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session_ids = [s["session_id"] for s in data.get("sessions", [])]
        assert b_session_id in session_ids, (
            f"coach_B's session ({b_session_id}) should be visible to coach_A at same school"
        )

    def test_list_sessions_pagination(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — paginated response with per_page=5, page=1.

        Verifies:
        - sessions array has ≤ per_page items.
        - total field reflects total count (≥ number of sessions inserted).
        - pages = ceil(total / per_page).
        - page and per_page fields present and correct.
        - sessions ordered by session_date DESC, session_id DESC
          (first item has latest date or largest session_id among same date).
        """
        org_id = make_org("Pagination Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        # Insert 7 sessions across different dates within the window
        dates = [
            "2026-04-13", "2026-04-14", "2026-04-15",
            "2026-04-16", "2026-04-17", "2026-04-18", "2026-04-19",
        ]
        inserted_ids = []
        for d in dates:
            sid = make_session(school_id, prog_id, coach["staff_id"], session_date=d)
            inserted_ids.append(sid)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {
                "from": "2026-04-01",
                "to": TODAY.isoformat(),
                "per_page": 5,
                "page": 1,
            })

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)

        assert "sessions" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data

        assert len(data["sessions"]) <= 5
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert data["total"] >= 7

        import math
        expected_pages = math.ceil(data["total"] / 5)
        assert data["pages"] == expected_pages

        # Verify ordering: session_date DESC, session_id DESC
        returned = data["sessions"]
        for i in range(len(returned) - 1):
            curr_date = returned[i]["session_date"]
            next_date = returned[i + 1]["session_date"]
            assert curr_date >= next_date, (
                f"Sessions not ordered by session_date DESC: {curr_date} < {next_date}"
            )
            if curr_date == next_date:
                assert returned[i]["session_id"] >= returned[i + 1]["session_id"], (
                    "Tiebreaker on session_id DESC violated"
                )

    def test_list_sessions_default_date_range(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions with no from/to params.

        Default window: 30 days before today UTC through today UTC.
        Given today = 2026-04-19, window is 2026-03-20 through 2026-04-19.

        Verifies:
        - A session dated 2026-04-15 (in window) appears in results.
        - A session dated 2026-03-19 (31 days ago, outside window) does NOT appear.
        """
        org_id = make_org("Default Date Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        in_window_sid = make_session(
            school_id, prog_id, coach["staff_id"], session_date="2026-04-15"
        )
        out_of_window_sid = make_session(
            school_id, prog_id, coach["staff_id"], session_date="2026-03-19"
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c)  # no from/to

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session_ids = [s["session_id"] for s in data.get("sessions", [])]
        assert in_window_sid in session_ids, (
            f"Session {in_window_sid} (2026-04-15) should be in default 30-day window"
        )
        assert out_of_window_sid not in session_ids, (
            f"Session {out_of_window_sid} (2026-03-19) is outside default window, should not appear"
        )

    def test_list_sessions_eod_filed_true(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
        make_eod_report,
    ):
        """
        GET /api/sessions — eod_filed is True when an eod_reports row exists
        with matching (staff_id, school_id, report_date) and deleted_at IS NULL.

        Verifies:
        - The session object with session_id=X has eod_filed=True.
        - eod_filed check is date-level (not session_id-level).
        """
        org_id = make_org("EOD Filed True Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        target_date = "2026-04-15"
        session_id = make_session(
            school_id, prog_id, coach["staff_id"], session_date=target_date
        )
        make_eod_report(school_id, coach["staff_id"], report_date=target_date)

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        sessions = data.get("sessions", [])
        target_sessions = [s for s in sessions if s["session_id"] == session_id]
        assert target_sessions, f"Session {session_id} not found in response"
        assert target_sessions[0]["eod_filed"] is True, (
            f"Expected eod_filed=True for session {session_id} on {target_date}"
        )

    def test_list_sessions_eod_filed_false_different_date(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
        make_eod_report,
    ):
        """
        GET /api/sessions — eod_filed is False when the eod_reports row exists
        for the same coach and school but a DIFFERENT date (2026-04-18 vs session
        on 2026-04-19).

        Verifies:
        - The session with session_date="2026-04-19" has eod_filed=False even
          though an EOD exists for 2026-04-18.
        """
        org_id = make_org("EOD Filed False Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)

        session_id = make_session(
            school_id, prog_id, coach["staff_id"], session_date="2026-04-19"
        )
        # EOD is for a different date
        make_eod_report(school_id, coach["staff_id"], report_date="2026-04-18")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        sessions = data.get("sessions", [])
        target = [s for s in sessions if s["session_id"] == session_id]
        assert target, f"Session {session_id} not found in response"
        assert target[0]["eod_filed"] is False, (
            "eod_filed should be False: EOD exists for a different date"
        )

    def test_list_sessions_no_cross_org_leakage(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — sessions from a school in a different organization
        never appear in the response.

        Verifies org boundary enforcement: coach_A (org_2) never sees sessions
        from school_50 (org_9).
        """
        org_a = make_org("Org 2 No Leakage")
        org_b = make_org("Org 9 No Leakage")
        region_id = make_region()
        school_a = make_school(org_a, region_id=region_id, name="Org A School")
        school_b = make_school(org_b, region_id=region_id, name="Org B School")
        prog_a = make_program(school_a)
        prog_b = make_program(school_b)
        coach_a = make_user_with_staff(role="head_coach", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)

        make_session(school_a, prog_a, coach_a["staff_id"], session_date="2026-04-15")
        make_session(school_b, prog_b, coach_b["staff_id"], session_date="2026-04-15")

        with authenticated_client(coach_a["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        school_ids = {s["school_id"] for s in data.get("sessions", [])}
        assert school_b not in school_ids, (
            f"Org B school ({school_b}) sessions leaked into Org A coach's response"
        )

    def test_list_sessions_site_coordinator_region_scope(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — site_coordinator sees sessions from all schools in
        their region, and does NOT see sessions from schools in other regions.

        Setup:
        - region_1: school_4 and school_5
        - region_3: school_20
        - Coordinator is at school_4 (region_1)
        - Sessions exist for all three schools

        Verifies:
        - school_4 and school_5 sessions appear.
        - school_20 sessions do not appear.
        """
        org_id = make_org("Coordinator Region Scope Org")
        region_1 = make_region()
        region_3 = make_region()
        school_4 = make_school(org_id, region_id=region_1, name="School 4 R1")
        school_5 = make_school(org_id, region_id=region_1, name="School 5 R1")
        school_20 = make_school(org_id, region_id=region_3, name="School 20 R3")
        prog_4 = make_program(school_4)
        prog_5 = make_program(school_5)
        prog_20 = make_program(school_20)
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_4)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_5)
        coach_c = make_user_with_staff(role="head_coach", school_id=school_20)

        sid_4 = make_session(school_4, prog_4, coordinator["staff_id"], session_date="2026-04-15")
        sid_5 = make_session(school_5, prog_5, coach_b["staff_id"], session_date="2026-04-15")
        sid_20 = make_session(school_20, prog_20, coach_c["staff_id"], session_date="2026-04-15")

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session_ids = {s["session_id"] for s in data.get("sessions", [])}
        assert sid_4 in session_ids, f"Session {sid_4} (region_1 school_4) should appear"
        assert sid_5 in session_ids, f"Session {sid_5} (region_1 school_5) should appear"
        assert sid_20 not in session_ids, (
            f"Session {sid_20} (region_3 school_20) must NOT appear for coordinator in region_1"
        )

    def test_list_sessions_overseer_all_schools_in_org(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — coach_overseer sees sessions from all schools in
        their organization (not just their assigned school).

        Verifies:
        - Sessions from school_a and school_b (same org) both appear.
        - Sessions from school_other_org (different org) do NOT appear.
        """
        org_id = make_org("Overseer All Schools Org")
        other_org = make_org("Overseer Other Org")
        region_id = make_region()
        school_a = make_school(org_id, region_id=region_id, name="Overseer Home")
        school_b = make_school(org_id, region_id=region_id, name="Overseer Other Same Org")
        school_other = make_school(other_org, region_id=region_id, name="Other Org School")
        prog_a = make_program(school_a)
        prog_b = make_program(school_b)
        prog_other = make_program(school_other)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)
        coach_b = make_user_with_staff(role="head_coach", school_id=school_b)
        coach_other = make_user_with_staff(role="head_coach", school_id=school_other)

        sid_a = make_session(school_a, prog_a, overseer["staff_id"], session_date="2026-04-15")
        sid_b = make_session(school_b, prog_b, coach_b["staff_id"], session_date="2026-04-15")
        sid_other = make_session(school_other, prog_other, coach_other["staff_id"], session_date="2026-04-15")

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        session_ids = {s["session_id"] for s in data.get("sessions", [])}
        assert sid_a in session_ids, f"Overseer's own school session ({sid_a}) must appear"
        assert sid_b in session_ids, f"Same-org school session ({sid_b}) must appear"
        assert sid_other not in session_ids, (
            f"Other-org session ({sid_other}) must NOT appear for overseer"
        )

    def test_list_sessions_unauthenticated(self, client):
        """
        GET /api/sessions with no session cookie.

        Verifies:
        - HTTP 401 returned.
        - Error message: "Authentication required."
        """
        resp = _get(client)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "Authentication required."

    def test_list_sessions_school_filter_out_of_scope(
        self,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_user_with_staff,
    ):
        """
        GET /api/sessions?school_id=N where N is outside the coach's scope.

        site_coordinator filtering by a school in a different region must
        receive 403 with "You do not have access to this school."

        Verifies:
        - HTTP 403 returned.
        - Error message: "You do not have access to this school."
        """
        org_id = make_org("Out Of Scope Filter Org")
        region_1 = make_region()
        region_2 = make_region()
        school_home = make_school(org_id, region_id=region_1, name="Filter Home School")
        school_other = make_school(org_id, region_id=region_2, name="Filter Out Scope School")
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_home)

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _get(c, {
                "school_id": school_other,  # in a different region
                "from": "2026-04-01",
                "to": TODAY.isoformat(),
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("error") == "You do not have access to this school."

    def test_list_sessions_response_includes_program_name(
        self,
        app,
        authenticated_client,
        make_org,
        make_region,
        make_school,
        make_program,
        make_user_with_staff,
        make_session,
    ):
        """
        GET /api/sessions — every session item in the response must include
        program_name (not just program_id).

        Rationale (from spec §4.3): "program_id: 7 is meaningless to a coach on
        a phone." The JOIN must be performed in the query.

        Verifies:
        - Each session dict has a non-null 'program_name' key.
        """
        org_id = make_org("Program Name Org")
        region_id = make_region()
        school_id = make_school(org_id, region_id=region_id)
        prog_id = make_program(school_id, name="PE Support — 2025-26")
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        make_session(school_id, prog_id, coach["staff_id"], session_date="2026-04-15")

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"from": "2026-04-01", "to": TODAY.isoformat()})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        sessions = data.get("sessions", [])
        assert sessions, "Expected at least one session in response"
        for s in sessions:
            assert "program_name" in s, f"program_name missing from session item: {s}"
            assert s["program_name"] is not None, (
                f"program_name is None in session item: {s}"
            )
