"""
test_assessments.py — Phase 2D: Assessments — RED-phase test suite.

All test cases from §8 of docs/specs/phase-2d-assessments.md.
Tests are RED: routes return stubs until implementation is written.

Test organisation:
  POST /api/assessments — TestCreateAssessment  (17 tests)
  GET  /api/assessments — TestListAssessments   (7 tests)

Column names from schema (001_sqlite_dev.sql):
  assessments.assessed_by_staff_id  — not assessor_id or staff_id
  assessment_scores.raw_level       — not raw_score (raw_score is the POST body field name)
  assessment_scores.normalized_score
  assessment_windows.status         — 'active', 'upcoming', 'closed'
"""

import json
import datetime
import math
import pytest

TODAY = datetime.date(2026, 4, 20)


# ===========================================================================
# Helpers
# ===========================================================================

def _post_json(client, payload):
    return client.post(
        "/api/assessments",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _get(client, params=None):
    return client.get(
        "/api/assessments",
        query_string=params or {},
    )


def _json(resp):
    return json.loads(resp.data)


def _minimal_body(student_id, window_id, skill_id):
    """Minimal valid POST body — required fields only."""
    return {
        "student_id": student_id,
        "window_id": window_id,
        "scores": [{"skill_id": skill_id, "raw_score": 3}],
    }


def _freeze_today(monkeypatch, d: datetime.date):
    monkeypatch.setattr("app.routes.coach_routes._get_today", lambda: d)


# ===========================================================================
# POST /api/assessments
# ===========================================================================

class TestCreateAssessment:

    def test_create_assessment_minimal_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """
        201 with minimal required fields.
        Verifies: response shape, assessments row, assessment_scores row, audit_log row.
        """
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_id, window_id, skill_id))

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("ok") is True

        a = data.get("assessment", {})
        assert a.get("assessment_id") is not None
        assert a.get("student_id") == student_id
        assert a.get("school_id") == school_id
        assert a.get("school_name") is not None
        assert a.get("window_id") == window_id
        assert a.get("window_name") is not None
        assert a.get("assessed_by_staff_id") == coach["staff_id"]
        assert a.get("assessor_name") is not None
        assert a.get("assessment_date") is not None
        assert a.get("assessment_method") == "observational"
        assert a.get("overall_assessment_notes") is None
        assert a.get("created_at") is not None

        scores = a.get("scores", [])
        assert len(scores) == 1
        assert scores[0].get("score_id") is not None
        assert scores[0].get("skill_id") == skill_id
        assert scores[0].get("raw_level") == 3
        assert scores[0].get("normalized_score") == 3
        assert scores[0].get("skill_name") is not None

        # Verify DB rows exist
        with app.app_context():
            from app.database import get_db
            db = get_db()
            assessment_id = a["assessment_id"]

            a_row = db.execute(
                "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
            ).fetchone()
            assert a_row is not None, "assessments row not found in DB"
            assert a_row["student_id"] == student_id
            assert a_row["school_id"] == school_id
            assert a_row["window_id"] == window_id
            assert a_row["assessed_by_staff_id"] == coach["staff_id"]

            score_row = db.execute(
                "SELECT * FROM assessment_scores WHERE assessment_id = ?", (assessment_id,)
            ).fetchone()
            assert score_row is not None, "assessment_scores row not found in DB"
            assert score_row["raw_level"] == 3
            assert score_row["normalized_score"] == 3

            audit_row = db.execute(
                "SELECT * FROM audit_log WHERE table_name = 'assessments' AND record_id = ?",
                (assessment_id,),
            ).fetchone()
            assert audit_row is not None, "audit_log row not found"
            assert audit_row["action"] == "INSERT"

            db.close()

    def test_create_assessment_full_success(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """
        201 with all optional fields: assessor_staff_id, assessment_date,
        assessment_method, overall_assessment_notes, two skills.
        """
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        assessor = make_user_with_staff(role="assistant_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_1 = make_skill(domain_id, name="Galloping skill")
        skill_2 = make_skill(domain_id, name="Skipping skill")
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        body = {
            "student_id": student_id,
            "window_id": window_id,
            "assessor_staff_id": assessor["staff_id"],
            "assessment_date": TODAY.isoformat(),
            "assessment_method": "observational",
            "overall_assessment_notes": "Strong improvement in locomotor skills.",
            "scores": [
                {"skill_id": skill_1, "raw_score": 3},
                {"skill_id": skill_2, "raw_score": 5},
            ],
        }

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, body)

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        a = _json(resp).get("assessment", {})

        assert a.get("assessed_by_staff_id") == assessor["staff_id"]
        assert a.get("assessment_date") == TODAY.isoformat()
        assert a.get("assessment_method") == "observational"
        assert a.get("overall_assessment_notes") == "Strong improvement in locomotor skills."
        assert len(a.get("scores", [])) == 2

        raw_levels = {s["skill_id"]: s["raw_level"] for s in a["scores"]}
        assert raw_levels[skill_1] == 3
        assert raw_levels[skill_2] == 5

    def test_create_assessment_site_coordinator_blocked(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_user_with_staff,
    ):
        """site_coordinator cannot POST assessments — 403 at rule 1 before body parsing."""
        org_id = make_org()
        school_id = make_school(org_id)
        coordinator = make_user_with_staff(role="site_coordinator", school_id=school_id)

        with authenticated_client(coordinator["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": 1,
                "window_id": 1,
                "scores": [{"skill_id": 1, "raw_score": 3}],
            })

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "You do not have permission to submit assessments."

    def test_create_assessment_student_not_at_coaches_school(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """head_coach submitting assessment for a student at a different school — 403."""
        org_id = make_org()
        school_a = make_school(org_id, name="Coach School A")
        school_b = make_school(org_id, name="Other School B")
        coach = make_user_with_staff(role="head_coach", school_id=school_a)
        student_at_b = make_student(school_b)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_b, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_at_b, window_id, skill_id))

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "Student does not belong to your school."

    def test_create_assessment_invalid_window_id(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        monkeypatch,
    ):
        """window_id that does not exist in the DB — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_id, 999999, skill_id))

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "Assessment window not found."

    def test_create_assessment_window_not_active(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """window_id exists but has status='closed' — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="closed")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_id, window_id, skill_id))

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "Assessment window is not active."

    def test_create_assessment_raw_score_too_high(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """raw_score=6 exceeds the allowed 1–5 range — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "window_id": window_id,
                "scores": [{"skill_id": skill_id, "raw_score": 6}],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == (
            "Each score must have skill_id (integer) and raw_score (integer 1-5)."
        )

    def test_create_assessment_raw_score_too_low(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """raw_score=0 is below the allowed range of 1–5 — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "window_id": window_id,
                "scores": [{"skill_id": skill_id, "raw_score": 0}],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == (
            "Each score must have skill_id (integer) and raw_score (integer 1-5)."
        )

    def test_create_assessment_duplicate_returns_409(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
        monkeypatch,
    ):
        """
        409 with existing_assessment_id when the same (student_id, window_id) already has
        a non-deleted assessment.
        """
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        existing_id = make_assessment(
            student_id, school_id, window_id, coach["staff_id"],
            scores=[(skill_id, 3)],
        )

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_id, window_id, skill_id))

        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert "existing_assessment_id" in data, "409 body must include existing_assessment_id"
        assert data["existing_assessment_id"] == existing_id
        assert "already exists" in data.get("error", "")

    def test_create_assessment_missing_student_id(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """Missing student_id — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "window_id": window_id,
                "scores": [{"skill_id": skill_id, "raw_score": 3}],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "Missing required field: student_id."

    def test_create_assessment_without_window_id(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        monkeypatch,
    ):
        """window_id is optional — omitting it should succeed with 201."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "scores": [{"skill_id": skill_id, "raw_score": 3}],
            })

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        assert _json(resp).get("ok") is True

    def test_create_assessment_missing_scores(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_assessment_window,
        monkeypatch,
    ):
        """Missing scores field entirely — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "window_id": window_id,
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "Missing required field: scores."

    def test_create_assessment_empty_scores_array(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_assessment_window,
        monkeypatch,
    ):
        """scores is an empty array [] — 400 (at least one score is required)."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "window_id": window_id,
                "scores": [],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == "scores must be a non-empty array."

    def test_create_assessment_invalid_skill_id(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_assessment_window,
        monkeypatch,
    ):
        """skill_id 999999 does not exist in the skills table — 400."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        window_id = make_assessment_window(school_id, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(coach["user_id"]) as c:
            resp = _post_json(c, {
                "student_id": student_id,
                "window_id": window_id,
                "scores": [{"skill_id": 999999, "raw_score": 3}],
            })

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert "Invalid or inactive skill_id" in data["error"], (
            f"Expected error mentioning 'Invalid or inactive skill_id', got: {data['error']!r}"
        )
        assert "999999" in data["error"]

    def test_create_assessment_overseer_cross_school_in_org(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """coach_overseer can submit an assessment for a student at any school in their org."""
        org_id = make_org()
        school_a = make_school(org_id, name="Overseer Home")
        school_b = make_school(org_id, name="Cross School")
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)
        student_at_b = make_student(school_b)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_b, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_at_b, window_id, skill_id))

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
        assert _json(resp)["ok"] is True

    def test_create_assessment_overseer_student_outside_org(
        self,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        monkeypatch,
    ):
        """coach_overseer cannot assess a student at a school in a different org — 403."""
        org_a = make_org("Org A")
        org_b = make_org("Org B")
        school_a = make_school(org_a)
        school_b = make_school(org_b)
        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a)
        student_at_b = make_student(school_b)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_b, status="active")

        _freeze_today(monkeypatch, TODAY)

        with authenticated_client(overseer["user_id"]) as c:
            resp = _post_json(c, _minimal_body(student_at_b, window_id, skill_id))

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.data}"
        assert _json(resp)["error"] == (
            "Student does not belong to a school in your organization."
        )

    def test_create_assessment_unauthenticated(self, client):
        """No session cookie — 401."""
        resp = _post_json(client, {
            "student_id": 1,
            "window_id": 1,
            "scores": [{"skill_id": 1, "raw_score": 3}],
        })
        assert resp.status_code == 401
        assert _json(resp)["error"] == "Authentication required."


# ===========================================================================
# GET /api/assessments
# ===========================================================================

class TestListAssessments:

    def test_list_assessments_head_coach_sees_own_school(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """
        head_coach sees assessments at their school.
        Response includes required fields: assessment_id, student_id, school_id,
        school_name, window_id, window_name, assessed_by_staff_id, assessor_name,
        assessment_date, assessment_method, scores array, created_at.
        """
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_id = make_student(school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_id = make_assessment_window(school_id, status="active")

        assessment_id = make_assessment(
            student_id, school_id, window_id, coach["staff_id"],
            scores=[(skill_id, 3)],
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = _json(resp)
        assert data.get("ok") is True

        ids = [a["assessment_id"] for a in data.get("assessments", [])]
        assert assessment_id in ids, f"assessment_id {assessment_id} not in response"

        target = next(a for a in data["assessments"] if a["assessment_id"] == assessment_id)
        required_fields = [
            "assessment_id", "student_id", "school_id", "school_name",
            "window_id", "window_name", "assessed_by_staff_id", "assessor_name",
            "assessment_date", "assessment_method", "scores", "created_at",
        ]
        for field in required_fields:
            assert field in target, f"Field '{field}' missing from GET response item"

        assert isinstance(target["scores"], list), "scores must be a list"

    def test_list_assessments_head_coach_excludes_other_schools(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """
        head_coach does NOT see assessments from a different school.
        """
        org_id = make_org()
        school_a = make_school(org_id, name="Coach School A")
        school_b = make_school(org_id, name="Other School B")

        coach = make_user_with_staff(role="head_coach", school_id=school_a)
        other_coach = make_user_with_staff(role="head_coach", school_id=school_b)
        student_a = make_student(school_a)
        student_b = make_student(school_b)

        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_a = make_assessment_window(school_a, status="active")
        window_b = make_assessment_window(school_b, status="active")

        assessment_a = make_assessment(
            student_a, school_a, window_a, coach["staff_id"], scores=[(skill_id, 3)]
        )
        assessment_b = make_assessment(
            student_b, school_b, window_b, other_coach["staff_id"], scores=[(skill_id, 4)]
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        ids = {a["assessment_id"] for a in _json(resp).get("assessments", [])}
        assert assessment_a in ids, "Own school's assessment must appear"
        assert assessment_b not in ids, "Other school's assessment must NOT appear for head_coach"

    def test_list_assessments_overseer_org_scope(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """
        coach_overseer sees assessments from all schools in their org.
        Assessments from a different org are excluded.
        """
        org_a = make_org("Overseer Org A")
        org_b = make_org("Overseer Org B")
        school_a1 = make_school(org_a)
        school_a2 = make_school(org_a)
        school_other = make_school(org_b)

        overseer = make_user_with_staff(role="coach_overseer", school_id=school_a1)
        coach_a2 = make_user_with_staff(role="head_coach", school_id=school_a2)
        coach_other = make_user_with_staff(role="head_coach", school_id=school_other)

        student_a1 = make_student(school_a1)
        student_a2 = make_student(school_a2)
        student_other = make_student(school_other)

        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_a1 = make_assessment_window(school_a1, status="active")
        window_a2 = make_assessment_window(school_a2, status="active")
        window_other = make_assessment_window(school_other, status="active")

        assessment_a1 = make_assessment(
            student_a1, school_a1, window_a1, overseer["staff_id"], scores=[(skill_id, 3)]
        )
        assessment_a2 = make_assessment(
            student_a2, school_a2, window_a2, coach_a2["staff_id"], scores=[(skill_id, 4)]
        )
        assessment_other = make_assessment(
            student_other, school_other, window_other, coach_other["staff_id"],
            scores=[(skill_id, 5)]
        )

        with authenticated_client(overseer["user_id"]) as c:
            resp = _get(c)

        assert resp.status_code == 200
        ids = {a["assessment_id"] for a in _json(resp).get("assessments", [])}
        assert assessment_a1 in ids, "Own org school_a1 assessment must appear"
        assert assessment_a2 in ids, "Own org school_a2 assessment must appear"
        assert assessment_other not in ids, "Cross-org assessment must NOT appear"

    def test_list_assessments_pagination(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """
        Pagination fields are correct.
        Items are ordered by assessment_date DESC, assessment_id DESC.
        """
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)

        # Create 5 assessments across different dates
        dates = ["2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14", "2026-04-15"]
        for d in dates:
            student_id = make_student(school_id)
            window_id = make_assessment_window(school_id, status="active")
            make_assessment(
                student_id, school_id, window_id, coach["staff_id"],
                scores=[(skill_id, 3)],
                assessment_date=d,
            )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"per_page": 3, "page": 1})

        assert resp.status_code == 200
        data = _json(resp)
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["assessments"]) <= 3
        assert data["total"] >= 5
        assert data["pages"] == math.ceil(data["total"] / 3)

        assessments = data["assessments"]
        for i in range(len(assessments) - 1):
            curr_date = assessments[i]["assessment_date"]
            next_date = assessments[i + 1]["assessment_date"]
            assert curr_date >= next_date, (
                f"Not ordered by assessment_date DESC: {curr_date} < {next_date}"
            )
            if curr_date == next_date:
                assert assessments[i]["assessment_id"] >= assessments[i + 1]["assessment_id"], (
                    "assessment_id tiebreaker DESC violated"
                )

    def test_list_assessments_student_id_filter(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """?student_id=N returns only assessments for that student."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_a = make_student(school_id, first="Alice")
        student_b = make_student(school_id, first="Bob")

        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_a = make_assessment_window(school_id, status="active")
        window_b = make_assessment_window(school_id, status="active")

        assessment_a = make_assessment(
            student_a, school_id, window_a, coach["staff_id"], scores=[(skill_id, 3)]
        )
        assessment_b = make_assessment(
            student_b, school_id, window_b, coach["staff_id"], scores=[(skill_id, 4)]
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"student_id": student_a})

        assert resp.status_code == 200
        ids = {a["assessment_id"] for a in _json(resp).get("assessments", [])}
        assert assessment_a in ids, "Filtered student's assessment must appear"
        assert assessment_b not in ids, "Other student's assessment must NOT appear"

    def test_list_assessments_window_id_filter(
        self,
        app,
        authenticated_client,
        make_org,
        make_school,
        make_student,
        make_user_with_staff,
        make_skill_domain,
        make_skill,
        make_assessment_window,
        make_assessment,
    ):
        """?window_id=N returns only assessments in that window."""
        org_id = make_org()
        school_id = make_school(org_id)
        coach = make_user_with_staff(role="head_coach", school_id=school_id)
        student_1 = make_student(school_id)
        student_2 = make_student(school_id)

        domain_id = make_skill_domain()
        skill_id = make_skill(domain_id)
        window_1 = make_assessment_window(school_id, status="active")
        window_2 = make_assessment_window(school_id, status="active")

        assessment_1 = make_assessment(
            student_1, school_id, window_1, coach["staff_id"], scores=[(skill_id, 3)]
        )
        assessment_2 = make_assessment(
            student_2, school_id, window_2, coach["staff_id"], scores=[(skill_id, 4)]
        )

        with authenticated_client(coach["user_id"]) as c:
            resp = _get(c, {"window_id": window_1})

        assert resp.status_code == 200
        ids = {a["assessment_id"] for a in _json(resp).get("assessments", [])}
        assert assessment_1 in ids, "Assessment in the filtered window must appear"
        assert assessment_2 not in ids, "Assessment in a different window must NOT appear"

    def test_list_assessments_unauthenticated(self, client):
        """No session cookie — 401."""
        resp = _get(client)
        assert resp.status_code == 401
        assert _json(resp)["error"] == "Authentication required."
