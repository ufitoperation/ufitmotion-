"""
email.py — Transactional email transport.

Tries Resend (HTTP API) first if RESEND_API_KEY is set, otherwise falls
back to Gmail SMTP. If neither is configured, logs to stdout (dev mode).

Why dual transport:
  - Render's free tier blocks outbound SMTP (errno 101, "Network is
    unreachable"). HTTP-based transports like Resend bypass that.
  - Gmail SMTP is preserved as the fallback so a paid-Render deploy
    or local dev can use the operations@ufitonline.net Workspace mailbox
    without configuring a separate provider.

Configure Resend:
  - RESEND_API_KEY=re_...
  - EMAIL_FROM='Ufit Motion <onboarding@resend.dev>'   ← test domain, no DNS
       OR
  - EMAIL_FROM='Ufit Motion <noreply@ufitonline.net>'  ← needs DNS records
       in Resend's "Domains" tab to verify SPF + DKIM

Configure Gmail SMTP fallback:
  - GMAIL_USER=operations@ufitonline.net
  - GMAIL_APP_PASSWORD=<16-char Google App Password>

Usage:
    from app.email import send_invite_email, send_password_reset_email
"""

from __future__ import annotations

import os
import re
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as _html_escape

APP_BASE_URL = os.environ.get("UFIT_APP_BASE_URL", "http://localhost:5000")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "operations@ufitonline.net")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
# Sender address used by Resend AND as the default Gmail SMTP From header.
# Prefer EMAIL_FROM if set (e.g. "Ufit Motion <onboarding@resend.dev>" while
# domain verification is pending). Otherwise fall back to GMAIL_USER.
FROM_ADDRESS = os.environ.get("EMAIL_FROM") or f"Ufit Motion <{GMAIL_USER}>"


def _html_to_text(html: str) -> str:
    """Minimal HTML → plaintext for the multipart/alternative fallback.
    Spam filters and screen readers prefer a real text/plain part."""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _send_via_resend(to: str, subject: str, html: str) -> bool:
    """HTTP POST to api.resend.com/emails. Works on any host with outbound
    HTTPS — bypasses SMTP-port firewalls (Render free tier blocks 465)."""
    try:
        import httpx
    except ImportError:
        # Fall through to Gmail. httpx is in requirements.txt so this
        # shouldn't happen on a fresh deploy.
        return False

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_ADDRESS,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": _html_to_text(html),
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True
        print(f"[email] Resend HTTP {resp.status_code}: {resp.text[:200]}",
              file=sys.stderr, flush=True)
        return False
    except Exception as exc:
        print(f"[email] Resend send failed ({type(exc).__name__}): {exc}",
              file=sys.stderr, flush=True)
        return False


def _send_via_gmail(to: str, subject: str, html: str) -> bool:
    """SMTP_SSL to smtp.gmail.com:465. Won't work on Render's free tier
    (outbound SMTP blocked) but works for paid Render and local dev."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_ADDRESS
        msg["To"] = to
        msg.attach(MIMEText(_html_to_text(html), "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, [to], msg.as_string())
        return True
    except Exception as exc:
        print(f"[email] Gmail send failed ({type(exc).__name__}): {exc}",
              file=sys.stderr, flush=True)
        return False


def _send(to: str, subject: str, html: str) -> bool:
    """Dispatch to whichever transport is configured.

    Order of preference: Resend (HTTP) > Gmail SMTP > stdout (dev mode).
    """
    if RESEND_API_KEY:
        return _send_via_resend(to, subject, html)

    if GMAIL_APP_PASSWORD:
        return _send_via_gmail(to, subject, html)

    print(
        f"[email] DEV MODE — would send to {to}\n"
        f"  Subject: {subject}\n"
        f"  (Set RESEND_API_KEY or GMAIL_APP_PASSWORD to enable real delivery)",
        flush=True,
    )
    return True


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
