"""
shared_routes.py — Endpoints used across all portals.

Bootstrap: called by the SPA immediately on load to hydrate state.
Notifications: bell-icon feed for the current user.
"""

from flask import Blueprint, jsonify

from app.auth import current_user, login_required
from app.database import get_db
from app.routes._helpers import now_utc, serialize_school, serialize_user

shared_bp = Blueprint("shared", __name__)


# ---------------------------------------------------------------------------
# GET /api/bootstrap
# ---------------------------------------------------------------------------
@shared_bp.route("/api/bootstrap", methods=["GET"])
def bootstrap():
    """
    Return all data the SPA needs on first load:
      - current_user (or null if not authenticated)
      - schools list (public — used for login school selectors, etc.)
      - app_settings key/value map

    This endpoint is intentionally unauthenticated so the SPA can always
    load the base configuration, even before login.
    """
    db = get_db()
    try:
        user = current_user(connection=db)

        # Schools — all active schools ordered by name.
        school_rows = db.execute(
            """SELECT school_id, organization_id, region_id, school_name, school_type,
                      address, city, state, zip_code,
                      principal_name, principal_email, active_status, created_at
               FROM schools
               WHERE active_status = TRUE AND deleted_at IS NULL
               ORDER BY school_name ASC""",
        ).fetchall()
        schools = [serialize_school(r) for r in school_rows]

        # App settings — all key/value pairs.
        setting_rows = db.execute(
            "SELECT key, value FROM app_settings"
        ).fetchall()
        app_settings = {r["key"]: r["value"] for r in setting_rows}

        return jsonify({
            "ok": True,
            "current_user": serialize_user(dict(user)) if user else None,
            "schools": schools,
            "app_settings": app_settings,
        })
    except Exception:
        return jsonify({"error": "Bootstrap failed. Please refresh."}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /api/notifications
# ---------------------------------------------------------------------------
@shared_bp.route("/api/notifications", methods=["GET"])
@login_required
def get_notifications():
    """
    Return unread notifications for the current user, newest first.
    Limit: 50.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        rows = db.execute(
            """SELECT notification_id, title, body, notification_type,
                      related_table, related_id, is_read, created_at
               FROM notifications
               WHERE user_id = ? AND is_read = FALSE
               ORDER BY created_at DESC
               LIMIT 50""",
            (user["user_id"],),
        ).fetchall()

        return jsonify({
            "ok": True,
            "notifications": rows,
            "unread_count": len(rows),
        })
    except Exception:
        return jsonify({"error": "Unable to fetch notifications."}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/notifications/<id>/read
# ---------------------------------------------------------------------------
@shared_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    """
    Mark a single notification as read.

    Only the owning user can mark their own notifications — the WHERE clause
    scopes the update to the current user's user_id.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    db = get_db()
    try:
        result = db.execute(
            """UPDATE notifications
               SET is_read = TRUE, read_at = ?
               WHERE notification_id = ? AND user_id = ?""",
            (now_utc(), notification_id, user["user_id"]),
        )
        db.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Notification not found."}), 404

        return jsonify({"ok": True, "notification_id": notification_id})
    finally:
        db.close()
