"""
email.py — Transactional email via Resend.

Set RESEND_API_KEY in your environment. If unset, emails are logged to
stdout (development mode) so the app never crashes due to missing config.

Usage:
    from app.email import send_invite_email, send_password_reset_email
"""

import os
import sys
from html import escape as _html_escape

APP_BASE_URL = os.environ.get("UFIT_APP_BASE_URL", "http://localhost:5000")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_ADDRESS = os.environ.get("EMAIL_FROM", "Ufit Motion <noreply@ufitonline.net>")


def _send(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success, False on failure."""
    if not RESEND_API_KEY:
        print(
            f"[email] DEV MODE — would send to {to}\n  Subject: {subject}\n  (Set RESEND_API_KEY to enable real delivery)",
            flush=True,
        )
        return True

    try:
        import httpx
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": FROM_ADDRESS, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"[email] Resend error {resp.status_code}: {resp.text}", file=sys.stderr, flush=True)
            return False
        return True
    except Exception as exc:
        print(f"[email] Send failed: {exc}", file=sys.stderr, flush=True)
        return False


def send_invite_email(to: str, first_name: str, role: str, token: str) -> bool:
    """Send a welcome / account-setup invite with a password-set link."""
    reset_url = f"{APP_BASE_URL}/?reset_token={token}"
    role_label = _html_escape((role or "").replace("_", " ").title())
    safe_first = _html_escape(first_name or "there")
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111;">
      <div style="background:#1E40AF;padding:24px;border-radius:8px 8px 0 0;">
        <span style="color:#fff;font-size:22px;font-weight:700;">UFIT MOTION</span>
      </div>
      <div style="border:1px solid #e5e7eb;border-top:none;padding:32px;border-radius:0 0 8px 8px;">
        <h2 style="margin:0 0 8px;">Welcome, {safe_first}!</h2>
        <p style="color:#6b7280;margin:0 0 24px;">Your <strong>{role_label}</strong> account on Ufit Motion has been created. Click below to set your password and get started.</p>
        <a href="{reset_url}" style="display:inline-block;background:#1E40AF;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:600;font-size:15px;">Set My Password</a>
        <p style="margin:24px 0 0;font-size:13px;color:#9ca3af;">This link expires in 24 hours. If you didn't expect this email, you can safely ignore it.</p>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;" />
        <p style="font-size:12px;color:#9ca3af;margin:0;">Ufit Motion &mdash; School Fitness Platform &mdash; <a href="{APP_BASE_URL}" style="color:#1E40AF;">ufitmotion.onrender.com</a></p>
      </div>
    </div>
    """
    return _send(to, "You're invited to Ufit Motion — set your password", html)


def send_password_reset_email(to: str, first_name: str, token: str) -> bool:
    """Send a password reset link."""
    reset_url = f"{APP_BASE_URL}/?reset_token={token}"
    safe_first = _html_escape(first_name or "there")
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111;">
      <div style="background:#1E40AF;padding:24px;border-radius:8px 8px 0 0;">
        <span style="color:#fff;font-size:22px;font-weight:700;">UFIT MOTION</span>
      </div>
      <div style="border:1px solid #e5e7eb;border-top:none;padding:32px;border-radius:0 0 8px 8px;">
        <h2 style="margin:0 0 8px;">Reset your password</h2>
        <p style="color:#6b7280;margin:0 0 24px;">Hi {safe_first}, we received a request to reset your Ufit Motion password.</p>
        <a href="{reset_url}" style="display:inline-block;background:#1E40AF;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:600;font-size:15px;">Reset Password</a>
        <p style="margin:24px 0 0;font-size:13px;color:#9ca3af;">This link expires in 1 hour. If you didn't request a reset, ignore this email — your password won't change.</p>
      </div>
    </div>
    """
    return _send(to, "Reset your Ufit Motion password", html)
