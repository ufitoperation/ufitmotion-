"""tests/test_csv_exports.py — C10 CSV exports for admin tables."""

from __future__ import annotations


def _xhr(_):
    return {"X-Requested-With": "XMLHttpRequest"}


def test_schools_csv_export_includes_school_name(
    admin_client, make_org, make_school
):
    org = make_org(name="Lincoln USD"); make_school(org, name="Lincoln Elementary")
    resp = admin_client.get("/api/admin/schools/export.csv", headers=_xhr(admin_client))
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    body = resp.data.decode("utf-8")
    assert "School ID" in body
    assert "Lincoln Elementary" in body


def test_coaches_csv_export_includes_role(
    admin_client, make_org, make_school, make_user_with_staff
):
    org = make_org(); s = make_school(org)
    make_user_with_staff(role="head_coach", school_id=s,
                        first_name="Coach", last_name="One", email="c1@x.com")
    resp = admin_client.get("/api/admin/coaches/export.csv", headers=_xhr(admin_client))
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Email" in body
    assert "c1@x.com" in body
    assert "head_coach" in body


def test_students_csv_export_includes_grade(
    admin_client, make_org, make_school, make_student
):
    org = make_org(); s = make_school(org, name="Roosevelt ES")
    make_student(s, first="Sam", last="Quinn", grade="3")
    resp = admin_client.get("/api/admin/students/export.csv", headers=_xhr(admin_client))
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Sam" in body
    assert "Quinn" in body
    assert "Roosevelt ES" in body
    assert "3" in body


def test_csv_exports_require_admin(client):
    for path in (
        "/api/admin/schools/export.csv",
        "/api/admin/coaches/export.csv",
        "/api/admin/students/export.csv",
    ):
        resp = client.get(path)
        assert resp.status_code in (401, 403)


def test_csv_filename_in_content_disposition(admin_client):
    for path, want in (
        ("/api/admin/schools/export.csv", "schools.csv"),
        ("/api/admin/coaches/export.csv", "coaches.csv"),
        ("/api/admin/students/export.csv", "students.csv"),
    ):
        resp = admin_client.get(path, headers=_xhr(admin_client))
        cd = resp.headers.get("Content-Disposition", "")
        assert want in cd, f"{path} → {cd}"
