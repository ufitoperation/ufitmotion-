"""tests/test_static_pages.py — Privacy + Terms must be reachable
without authentication and contain the required boilerplate."""

from __future__ import annotations


def test_privacy_returns_200_with_ferpa_content(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Privacy Policy" in body
    assert "FERPA" in body
    assert "operations@ufitonline.net" in body


def test_terms_returns_200(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Terms of Service" in body
    assert "operations@ufitonline.net" in body


def test_privacy_and_terms_link_back_home(client):
    for path in ("/privacy", "/terms"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert b'href="/"' in resp.data


def test_privacy_does_not_leak_session_cookie(client):
    resp = client.get("/privacy")
    assert "Set-Cookie" not in resp.headers or "__ufit_sess" not in resp.headers.get("Set-Cookie", "")
