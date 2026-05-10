"""tests/test_email_transport.py — coverage for the dual transport.

Strategy:
  - Tries Resend (HTTP) first if RESEND_API_KEY is set.
  - Falls back to Gmail SMTP if RESEND_API_KEY is unset and GMAIL_APP_PASSWORD is set.
  - Otherwise no-ops to stdout (dev mode).

We patch `app.email` module attributes (RESEND_API_KEY, GMAIL_APP_PASSWORD,
FROM_ADDRESS) directly because they are read at module-import time.
"""

from __future__ import annotations

import email as stdlib_email
import pytest


def _decoded_html(raw_msg_str: str) -> str:
    """Parse a wire-format multipart MIME message and return the decoded
    text of the text/html part."""
    msg = stdlib_email.message_from_string(raw_msg_str)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return ""


# ---------------------------------------------------------------------------
# DEV MODE — no creds at all
# ---------------------------------------------------------------------------

def test_no_op_when_no_creds_configured(monkeypatch, capsys):
    from app import email as email_mod
    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "")
    ok = email_mod.send_invite_email(
        "ada@example.com", "Ada", "head_coach", "tok-abc"
    )
    assert ok is True
    out = capsys.readouterr().out
    assert "DEV MODE" in out
    assert "ada@example.com" in out


# ---------------------------------------------------------------------------
# RESEND PATH (preferred when RESEND_API_KEY is set)
# ---------------------------------------------------------------------------

def test_send_via_resend_when_api_key_set(monkeypatch):
    from app import email as email_mod

    captured = {}

    class FakeResp:
        status_code = 200
        text = "{}"

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResp()

    class FakeHttpx:
        post = staticmethod(fake_post)

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "re_test_key_123")
    monkeypatch.setattr(email_mod, "FROM_ADDRESS",
                        "Ufit Motion <noreply@x.com>")
    monkeypatch.setitem(__import__("sys").modules, "httpx", FakeHttpx)

    ok = email_mod.send_invite_email(
        "dst@example.com", "Bo", "head_coach", "tok-x9"
    )
    assert ok is True
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key_123"
    assert captured["json"]["from"] == "Ufit Motion <noreply@x.com>"
    assert captured["json"]["to"] == ["dst@example.com"]
    assert "Set My Password" in captured["json"]["html"]
    assert "tok-x9" in captured["json"]["html"]
    # Plaintext alternative is sent so spam scores stay low.
    assert "Set My Password" in captured["json"]["text"]


def test_resend_returns_false_on_4xx(monkeypatch):
    from app import email as email_mod

    class FakeResp:
        status_code = 401
        text = "Unauthorized"

    class FakeHttpx:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return FakeResp()

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "bad_key")
    monkeypatch.setitem(__import__("sys").modules, "httpx", FakeHttpx)

    ok = email_mod.send_password_reset_email("a@b.com", "A", "tok-1")
    assert ok is False


def test_resend_returns_false_on_network_error(monkeypatch):
    from app import email as email_mod

    class FakeHttpx:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            raise RuntimeError("network unreachable")

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "test_key")
    monkeypatch.setitem(__import__("sys").modules, "httpx", FakeHttpx)

    ok = email_mod.send_invite_email("a@b.com", "A", "head_coach", "t")
    assert ok is False


# ---------------------------------------------------------------------------
# GMAIL FALLBACK (only when RESEND_API_KEY is empty)
# ---------------------------------------------------------------------------

def test_falls_back_to_gmail_when_no_resend_key(monkeypatch):
    from app import email as email_mod

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, user, pw): sent["login"] = (user, pw)
        def sendmail(self, frm, to, msg_str):
            sent["msg"] = msg_str
            sent["frm"] = frm
            sent["to"] = to

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "")
    monkeypatch.setattr(email_mod, "GMAIL_USER", "ops@x.com")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(email_mod, "FROM_ADDRESS",
                        "Ufit Motion <ops@x.com>")
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    ok = email_mod.send_invite_email("dst@x.com", "Bo", "head_coach", "tok-y")
    assert ok is True
    assert sent["host"] == "smtp.gmail.com"
    assert sent["port"] == 465
    assert sent["timeout"] == 15
    assert sent["login"] == ("ops@x.com", "abcd efgh ijkl mnop")
    assert sent["frm"] == "ops@x.com"  # SMTP envelope sender is GMAIL_USER
    assert sent["to"] == ["dst@x.com"]
    html = _decoded_html(sent["msg"])
    assert "Set My Password" in html
    assert "tok-y" in html


def test_gmail_returns_false_on_smtp_exception(monkeypatch):
    from app import email as email_mod

    class BoomSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): raise RuntimeError("boom")
        def __exit__(self, *a): pass

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr("smtplib.SMTP_SSL", BoomSMTP)

    ok = email_mod.send_invite_email("a@b.com", "A", "head_coach", "t")
    assert ok is False


# ---------------------------------------------------------------------------
# PRECEDENCE — Resend wins when both are configured
# ---------------------------------------------------------------------------

def test_resend_takes_precedence_over_gmail(monkeypatch):
    from app import email as email_mod

    smtp_called = {"hit": False}
    resend_called = {"hit": False}

    class FakeSMTP:
        def __init__(self, *a, **kw): smtp_called["hit"] = True
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, *a): pass
        def sendmail(self, *a): pass

    class FakeResp:
        status_code = 200
        text = "{}"

    class FakeHttpx:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            resend_called["hit"] = True
            return FakeResp()

    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "test_key")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)
    monkeypatch.setitem(__import__("sys").modules, "httpx", FakeHttpx)

    email_mod.send_invite_email("a@b.com", "A", "head_coach", "t")
    assert resend_called["hit"] is True
    assert smtp_called["hit"] is False
