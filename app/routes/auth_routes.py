"""
auth_routes.py — Authentication blueprint for Ufit Motion.

Portals map to role groups:
  admin  → ceo, admin
  coach  → head_coach, assistant_coach, site_coordinator, coach_overseer
  staff  → principal, school_staff, parent

All passwords are hashed with werkzeug.security (PBKDF2-SHA256).
Password reset tokens are stored in the users table and expire after 1 hour.
"""

import secrets
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import current_user, ADMIN_ROLES, COACH_ROLES, SCHOOL_ROLES
from app.database import get_db
from app.routes._helpers import audit, now_utc, parse_json, serialize_user

auth_bp = Blueprint("auth", __name__)

# Pre-computed hash for constant-time "user not found" path — prevents timing attacks.
_TIMING_HASH = generate_password_hash("constant_timing_dummy_ufit", method="pbkdf2:sha256")

# ---------------------------------------------------------------------------
# Portal → allowed roles mapping
# ---------------------------------------------------------------------------
PORTAL_ROLES: dict[str, tuple[str, ...]] = {
    "admin": ADMIN_ROLES,
    "coach": COACH_ROLES,
    "staff": SCHOOL_ROLES + ("parent",),
}


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """
    Authenticate a user.

    Body: { email, password, portal }
    Portal must be 'admin', 'coach', or 'staff'.
    The user's role must be in the portal's allowed-roles list.

    Returns: { ok, user } on success or { error } on failure.
    """
    data = parse_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    portal = (data.get("portal") or "").strip().lower()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    allowed_roles = PORTAL_ROLES.get(portal)
    if allowed_roles is None:
        return jsonify({"error": "Invalid portal. Must be admin, coach, or staff."}), 400

    db = get_db()
    try:
        try:
            row = db.execute(
                """SELECT u.user_id, u.role, u.first_name, u.last_name, u.email,
                          u.password_hash, u.active_status, u.auth_uid,
                          sp.staff_id, sp.position_title,
                          s.school_id, s.school_name
                   FROM users u
                   LEFT JOIN staff_profiles sp ON sp.user_id = u.user_id
                   LEFT JOIN staff_assignments sa
                          ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
                   LEFT JOIN schools s ON s.school_id = sa.school_id
                   WHERE u.email = ? AND u.deleted_at IS NULL""",
                (email,),
            ).fetchone()
        except Exception:
            return jsonify({"error": "Login unavailable. Please try again."}), 500

        # Constant-time "no such user" path — still run check_password_hash to
        # prevent timing attacks.
        if row is None:
            check_password_hash(_TIMING_HASH, password)
            audit(db, None, "LOGIN_FAILED", "users", None,
                  new_values={"email": email, "reason": "user_not_found", "ip": request.remote_addr})
            db.commit()
            return jsonify({"error": "Invalid email or password."}), 401

        if not check_password_hash(row["password_hash"], password):
            audit(db, row["user_id"], "LOGIN_FAILED", "users", row["user_id"],
                  new_values={"reason": "invalid_password", "ip": request.remote_addr})
            db.commit()
            return jsonify({"error": "Invalid email or password."}), 401

        if not row["active_status"]:
            audit(db, row["user_id"], "LOGIN_FAILED", "users", row["user_id"],
                  new_values={"reason": "account_deactivated", "ip": request.remote_addr})
            db.commit()
            return jsonify({"error": "This account has been deactivated. Contact your administrator."}), 403

        if row["role"] not in allowed_roles:
            audit(db, row["user_id"], "LOGIN_FAILED", "users", row["user_id"],
                  new_values={"reason": "wrong_portal", "portal": portal, "ip": request.remote_addr})
            db.commit()
            return jsonify({"error": "You do not have access to this portal."}), 403

        session.clear()
        session["user_id"] = row["user_id"]
        session.permanent = True

        audit(db, row["user_id"], "LOGIN", "users", row["user_id"],
              new_values={"portal": portal, "ip": request.remote_addr})
        db.commit()

        return jsonify({"ok": True, "user": serialize_user(dict(row))})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Clear the session. Safe to call even when not logged in."""
    session.clear()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# POST /api/auth/change-password
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/change-password", methods=["POST"])
def change_password():
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = parse_json()
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    if not current_pw or not new_pw:
        return jsonify({"error": "current_password and new_password are required."}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters."}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT password_hash FROM users WHERE user_id = ? AND deleted_at IS NULL",
            (user["user_id"],),
        ).fetchone()
        if not row or not check_password_hash(row["password_hash"], current_pw):
            return jsonify({"error": "Current password is incorrect."}), 400

        new_hash = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?",
            (new_hash, user["user_id"]),
        )
        db.commit()
        audit(db, user["user_id"], "change_password", "users", user["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/auth/setup-admin
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/setup-admin", methods=["POST"])
def setup_admin():
    """
    Create the first CEO or admin account.

    Fails if any admin/ceo user already exists (prevents privilege escalation).

    Body: { first_name, last_name, email, password, role }
    role must be 'ceo' or 'admin'.
    """
    db = get_db()
    try:
        existing = db.execute(
            "SELECT user_id FROM users WHERE role IN ('ceo', 'admin') AND deleted_at IS NULL LIMIT 1"
        ).fetchone()
        if existing:
            return jsonify({"error": "An admin account already exists. Use the login page."}), 409

        data = parse_json()
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        role = (data.get("role") or "").strip().lower()

        if not all([first_name, last_name, email, password]):
            return jsonify({"error": "first_name, last_name, email, and password are required."}), 400

        if role != "admin":
            return jsonify({"error": "role must be 'admin'. CEO accounts are created by an existing admin."}), 400

        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters."}), 400

        # Check email not already taken.
        dup = db.execute(
            "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL", (email,)
        ).fetchone()
        if dup:
            return jsonify({"error": "An account with that email already exists."}), 409

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        cur = db.execute(
            """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                  active_status, created_at)
               VALUES (?, ?, ?, ?, ?, TRUE, ?)""",
            (role, first_name, last_name, email, password_hash, now_utc()),
        )
        new_id = cur.lastrowid
        db.commit()

        user = db.execute(
            "SELECT user_id, role, first_name, last_name, email, active_status FROM users WHERE user_id = ?",
            (new_id,),
        ).fetchone()

        return jsonify({"ok": True, "user": {
            "user_id": user["user_id"], "role": user["role"],
            "first_name": user["first_name"], "last_name": user["last_name"],
            "email": user["email"], "active_status": user["active_status"],
        }}), 201
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/auth/session
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/session", methods=["GET"])
def get_session():
    """
    Return the currently authenticated user, or 401 if not logged in.
    Used by the SPA on page load to hydrate auth state.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    return jsonify({"ok": True, "user": serialize_user(dict(user))})


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    """
    Generate a password reset token and store it in the database.

    Always returns { ok: true } to avoid leaking whether an email exists.
    In production, an email would be sent with the reset link — that
    integration is wired up separately (email provider config).

    Body: { email }
    """
    data = parse_json()
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required."}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL AND active_status = TRUE",
            (email,),
        ).fetchone()

        if row:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            db.execute(
                """UPDATE users
                   SET password_reset_token = ?, password_reset_expires_at = ?
                   WHERE user_id = ?""",
                (token, expires_at, row["user_id"]),
            )
            db.commit()

            # TODO: send reset email via configured email provider.
            # from app.email import send_password_reset
            # send_password_reset(email, token)
            # Reset URL: {APP_BASE_URL}/reset-password?token={token}

        # Always return ok to avoid email enumeration.
        return jsonify({"ok": True})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/auth/reset-password
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    """
    Validate a reset token and update the user's password.

    Body: { token, password }
    Token must exist and not be expired. Password must be at least 8 chars.
    Clears the token after successful reset.
    """
    data = parse_json()
    token = (data.get("token") or "").strip()
    password = data.get("password") or ""

    if not token:
        return jsonify({"error": "Reset token is required."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    db = get_db()
    try:
        row = db.execute(
            """SELECT user_id, password_reset_expires_at
               FROM users
               WHERE password_reset_token = ? AND deleted_at IS NULL AND active_status = TRUE""",
            (token,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "Invalid or expired reset token."}), 400

        # Check expiry.
        expires_raw = row["password_reset_expires_at"]
        if expires_raw:
            # Handle both offset-aware and naive datetimes from the DB.
            if isinstance(expires_raw, str):
                expires_dt = datetime.fromisoformat(expires_raw)
            else:
                expires_dt = expires_raw
            # Make timezone-aware if naive.
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_dt:
                return jsonify({"error": "Reset token has expired. Please request a new one."}), 400

        new_hash = generate_password_hash(password, method="pbkdf2:sha256")
        db.execute(
            """UPDATE users
               SET password_hash = ?,
                   password_reset_token = NULL,
                   password_reset_expires_at = NULL
               WHERE user_id = ?""",
            (new_hash, row["user_id"]),
        )
        db.commit()

        return jsonify({"ok": True, "message": "Password updated successfully."})
    finally:
        db.close()
