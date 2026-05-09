"""
tests/test_email_transport.py — coverage for the Gmail SMTP transport in
`app/email.py`. Replaces the old Resend/httpx code path.

Strategy:
  - The two public callers (`send_invite_email`, `send_password_reset_email`)
    keep their signatures. We test through them so any future internal
    refactor doesn't bypass coverage.
  - `_send` is the single network point — we monkeypatch `smtplib.SMTP_SSL`
    so no real network calls are made.
  - The graceful no-op when GMAIL_APP_PASSWORD is unset is preserved from
    the prior Resend implementation; tests guard it.
"""

from __future__ import annotations

import email as stdlib_email
import pytest


def _decoded_html(raw_msg_str: str) -> str:
    """Parse a wire-format multipart MIME message and return the decoded
    text of the text/html part. Necessary because Python's email library
    base64-encodes utf-8 bodies that contain non-ASCII chars (em-dash, etc.)."""
    msg = stdlib_email.message_from_string(raw_msg_str)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return ""


def test_no_op_without_gmail_password(monkeypatch, capsys):
    """Without credentials, _send must log to stdout and return True (dev mode)."""
    from app import email as email_mod
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "")
    ok = email_mod.send_invite_email(
        "ada@example.com", "Ada", "head_coach", "tok-abc123"
    )
    assert ok is True
    out = capsys.readouterr().out
    assert "DEV MODE" in out
    assert "ada@example.com" in out


def test_send_invite_uses_smtplib_when_configured(monkeypatch):
    """With GMAIL_APP_PASSWORD set, _send must call smtplib.SMTP_SSL with
    the right host/port, login, and sendmail args."""
    from app import email as email_mod

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def login(self, user, password):
            sent["login"] = (user, password)

        def sendmail(self, frm, to, msg_str):
            sent["sendmail_from"] = frm
            sent["sendmail_to"] = to
            sent["sendmail_msg"] = msg_str

    monkeypatch.setattr(email_mod, "GMAIL_USER", "ops@ufitonline.net")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(email_mod, "FROM_ADDRESS",
                        "Ufit Motion <ops@ufitonline.net>")
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    ok = email_mod.send_invite_email(
        "dst@example.com", "Bo", "head_coach", "tok-x9"
    )
    assert ok is True
    assert sent["host"] == "smtp.gmail.com"
    assert sent["port"] == 465
    assert sent["login"] == ("ops@ufitonline.net", "abcd efgh ijkl mnop")
    assert sent["sendmail_from"] == "Ufit Motion <ops@ufitonline.net>"
    assert sent["sendmail_to"] == ["dst@example.com"]
    # Decode the multipart payload and assert against the actual HTML body.
    html = _decoded_html(sent["sendmail_msg"])
    assert "UFIT MOTION" in html
    assert "Set My Password" in html
    assert "tok-x9" in html


def test_send_password_reset_uses_smtplib(monkeypatch):
    """Same path for password reset — different subject/body, same transport."""
    from app import email as email_mod

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg_str):
            sent["msg"] = msg_str

    monkeypatch.setattr(email_mod, "GMAIL_USER", "ops@ufitonline.net")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr(email_mod, "FROM_ADDRESS",
                        "Ufit Motion <ops@ufitonline.net>")
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    ok = email_mod.send_password_reset_email("ada@x.com", "Ada", "tok-rst")
    assert ok is True
    html = _decoded_html(sent["msg"])
    assert "Reset Password" in html
    assert "tok-rst" in html


def test_send_returns_false_on_smtp_exception(monkeypatch):
    """Network or auth failures must not crash callers — they get False."""
    from app import email as email_mod

    class BoomSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): raise RuntimeError("boom")
        def __exit__(self, *a): pass

    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr("smtplib.SMTP_SSL", BoomSMTP)
    ok = email_mod.send_invite_email("a@b.com", "A", "head_coach", "t1")
    assert ok is False


def test_message_includes_plaintext_alternative(monkeypatch):
    """MIMEMultipart('alternative') with both text/plain and text/html so
    spam scores stay low and screen readers have a fallback."""
    from app import email as email_mod

    captured = {}

    class CaptureSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg_str):
            captured["msg"] = msg_str

    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "x" * 16)
    monkeypatch.setattr("smtplib.SMTP_SSL", CaptureSMTP)
    email_mod.send_invite_email("c@d.com", "C", "head_coach", "t2")

    msg = captured["msg"]
    assert "multipart/alternative" in msg
    assert "Content-Type: text/plain" in msg
    assert "Content-Type: text/html" in msg
