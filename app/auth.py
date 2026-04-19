from functools import wraps
from flask import jsonify, session

COACH_ROLES = ("head_coach", "assistant_coach", "site_coordinator", "coach_overseer")
ADMIN_ROLES = ("ceo", "admin")
SCHOOL_ROLES = ("principal", "school_staff")
ALL_STAFF_ROLES = ADMIN_ROLES + COACH_ROLES + SCHOOL_ROLES


def current_user(connection=None):
    """Return the logged-in user dict, or None."""
    from app.database import get_db

    user_id = session.get("user_id")
    if not user_id:
        return None

    owns = connection is None
    if owns:
        connection = get_db()
    try:
        user = connection.execute(
            """SELECT u.user_id, u.role, u.first_name, u.last_name, u.email,
                      u.active_status, u.auth_uid,
                      sp.staff_id, sp.position_title,
                      s.school_id, s.school_name
               FROM users u
               LEFT JOIN staff_profiles sp ON sp.user_id = u.user_id
               LEFT JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
               LEFT JOIN schools s ON s.school_id = sa.school_id
               WHERE u.user_id = ? AND u.deleted_at IS NULL AND u.active_status = TRUE""",
            (user_id,),
        ).fetchone()
        if user is None:
            session.pop("user_id", None)
            return None
        return user
    finally:
        if owns:
            connection.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return jsonify({"error": "Authentication required."}), 401
        return view(*args, **kwargs)

    return wrapped


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"error": "Authentication required."}), 401
            if user["role"] not in allowed_roles:
                return jsonify({"error": "You do not have permission for this action."}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view):
    return roles_required(*ADMIN_ROLES)(view)


def coach_required(view):
    return roles_required(*COACH_ROLES)(view)


def staff_required(view):
    return roles_required(*ALL_STAFF_ROLES)(view)
