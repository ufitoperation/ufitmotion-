"""
shared_routes.py — Endpoints used across all portals.

Bootstrap: called by the SPA immediately on load to hydrate state.
Notifications: bell-icon feed for the current user.
"""

from flask import Blueprint, jsonify, request

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
# GET /api/skills
# ---------------------------------------------------------------------------
@shared_bp.route("/api/skills", methods=["GET"])
@login_required
def list_skills():
    """Return all active skills grouped by domain. Used by assessment forms."""
    db = get_db()
    try:
        domain_rows = db.execute(
            """SELECT domain_id, domain_name, domain_type
               FROM skill_domains
               WHERE active_status = 1
               ORDER BY domain_name ASC"""
        ).fetchall()
        skill_rows = db.execute(
            """SELECT skill_id, domain_id, skill_name, grade_band, skill_description
               FROM skills
               WHERE active_status = 1
               ORDER BY domain_id ASC, skill_name ASC"""
        ).fetchall()

        skill_map = {}
        for s in skill_rows:
            skill_map.setdefault(s["domain_id"], []).append({
                "skill_id": s["skill_id"],
                "skill_name": s["skill_name"],
                "grade_band": s["grade_band"],
                "skill_description": s["skill_description"],
            })

        domains = [
            {
                "domain_id": d["domain_id"],
                "domain_name": d["domain_name"],
                "domain_type": d["domain_type"],
                "skills": skill_map.get(d["domain_id"], []),
            }
            for d in domain_rows
        ]
        return jsonify({"ok": True, "domains": domains})
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


# ---------------------------------------------------------------------------
# GET /api/students/<student_id>/progress
# ---------------------------------------------------------------------------
PROGRESS_ROLES = ("ceo", "admin", "coach_overseer", "head_coach",
                  "assistant_coach", "principal", "school_staff")

@shared_bp.route("/api/students/<int:student_id>/progress", methods=["GET"])
@login_required
def student_progress(student_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    if user.get("role") not in PROGRESS_ROLES:
        return jsonify({"error": "Access denied."}), 403

    db = get_db()
    try:
        student = db.execute(
            """SELECT s.student_id, s.student_first_name, s.student_last_name,
                      s.grade_level, s.school_id, sc.school_name
               FROM students s
               JOIN schools sc ON sc.school_id = s.school_id
               WHERE s.student_id = ? AND s.deleted_at IS NULL""",
            (student_id,),
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found."}), 404

        role = user.get("role")
        if role in ("head_coach", "assistant_coach", "principal", "school_staff"):
            if user.get("school_id") != student["school_id"]:
                return jsonify({"error": "Access denied."}), 403
        elif role == "coach_overseer":
            overseer_org = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ? AND deleted_at IS NULL",
                (user.get("school_id"),),
            ).fetchone()
            student_org = db.execute(
                "SELECT organization_id FROM schools WHERE school_id = ? AND deleted_at IS NULL",
                (student["school_id"],),
            ).fetchone()
            if not overseer_org or not student_org or overseer_org["organization_id"] != student_org["organization_id"]:
                return jsonify({"error": "Access denied."}), 403

        overall = db.execute(
            """SELECT overall_score, performance_band, growth_amount,
                      baseline_overall_score, last_calculated_at
               FROM student_overall_summary WHERE student_id = ?""",
            (student_id,),
        ).fetchone()

        domain_rows = db.execute(
            """SELECT sds.domain_id, sd.domain_name,
                      sds.current_domain_score, sds.baseline_domain_score,
                      sds.growth_amount, sds.performance_band, sds.updated_at
               FROM student_domain_summary sds
               JOIN skill_domains sd ON sd.domain_id = sds.domain_id
               WHERE sds.student_id = ?
               ORDER BY sd.domain_name""",
            (student_id,),
        ).fetchall()

        skill_rows = db.execute(
            """SELECT sss.skill_id, sk.skill_name, sd.domain_name, sd.domain_id,
                      sss.current_score, sss.baseline_score, sss.highest_score,
                      sss.growth_amount, sss.performance_band, sss.latest_assessment_date
               FROM student_skill_summary sss
               JOIN skills sk ON sk.skill_id = sss.skill_id
               JOIN skill_domains sd ON sd.domain_id = sk.domain_id
               WHERE sss.student_id = ?
               ORDER BY sd.domain_name, sk.skill_name""",
            (student_id,),
        ).fetchall()

        recent_assessments = db.execute(
            """SELECT a.assessment_id, a.assessment_date, a.assessment_method,
                      a.overall_assessment_notes,
                      COUNT(asco.assessment_score_id) AS score_count
               FROM assessments a
               LEFT JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
               WHERE a.student_id = ? AND a.deleted_at IS NULL
               GROUP BY a.assessment_id
               ORDER BY a.assessment_date DESC
               LIMIT 10""",
            (student_id,),
        ).fetchall()

        return jsonify({
            "ok": True,
            "student": dict(student),
            "overall": dict(overall) if overall else None,
            "domains": [dict(r) for r in domain_rows],
            "skills": [dict(r) for r in skill_rows],
            "recent_assessments": [dict(r) for r in recent_assessments],
        })
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/webhooks/hubspot
# ---------------------------------------------------------------------------
import hashlib
import hmac
import logging

_hs_logger = logging.getLogger(__name__)

@shared_bp.route("/api/webhooks/hubspot", methods=["POST"])
def hubspot_webhook():
    """
    Receives HubSpot company creation webhooks and auto-creates a school.

    Setup in HubSpot:
      1. Settings → Integrations → Private Apps → your app → Webhooks
      2. Subscribe to: crm.object.company.creation
      3. Target URL: https://<your-render-url>/api/webhooks/hubspot
      4. Set HUBSPOT_WEBHOOK_SECRET in Render env vars (from HubSpot webhook settings)

    HubSpot sends a JSON array of event objects. We handle company.creation only.
    School is assigned to the first active org (or a new "Ufit" org is created).
    """
    import os

    secret = os.environ.get("HUBSPOT_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Secret must be configured — refuse all requests in its absence so
        # an unconfigured env can't be abused to create arbitrary schools.
        _hs_logger.error("HUBSPOT_WEBHOOK_SECRET not set; rejecting webhook")
        return jsonify({"error": "Webhook not configured"}), 503

    sig_header = request.headers.get("X-HubSpot-Signature", "")
    body = request.get_data()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig_header, expected):
        _hs_logger.warning("HubSpot webhook signature mismatch")
        return jsonify({"error": "Invalid signature"}), 401

    events = request.get_json(silent=True)
    if not events or not isinstance(events, list):
        return jsonify({"ok": True, "processed": 0})

    db = get_db()
    processed = 0
    try:
        for event in events:
            if event.get("subscriptionType") != "company.creation":
                continue

            object_id = event.get("objectId")
            props = event.get("propertyValue") or {}

            # HubSpot sends minimal data in the webhook — use the company name
            # from propertyValue if present, otherwise fall back to objectId as label
            company_name = (
                props if isinstance(props, str) else
                event.get("propertyName") or f"HubSpot Company {object_id}"
            )

            # Fetch full company details if we have an API key
            city, state = "", ""
            api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
            if api_key and object_id:
                try:
                    import httpx
                    resp = httpx.get(
                        f"https://api.hubapi.com/crm/v3/objects/companies/{object_id}",
                        params={"properties": "name,city,state"},
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        p = resp.json().get("properties", {})
                        company_name = p.get("name") or company_name
                        city = p.get("city") or ""
                        state = p.get("state") or ""
                except Exception as e:
                    _hs_logger.warning("Could not fetch HubSpot company details: %s", e)

            # Skip if a school with this name already exists
            existing = db.execute(
                "SELECT school_id FROM schools WHERE school_name = ? AND deleted_at IS NULL",
                (company_name,),
            ).fetchone()
            if existing:
                _hs_logger.info("School already exists for HubSpot company: %s", company_name)
                continue

            # Find or create the default org
            org = db.execute(
                "SELECT organization_id FROM organizations WHERE deleted_at IS NULL ORDER BY organization_id LIMIT 1"
            ).fetchone()
            if org:
                org_id = org["organization_id"]
            else:
                org_id = db.execute(
                    """INSERT INTO organizations (organization_name, organization_type, contract_status, created_at)
                       VALUES ('Ufit', 'school_district', 'active', ?)""",
                    (now_utc(),),
                ).lastrowid

            db.execute(
                """INSERT INTO schools
                   (organization_id, school_name, school_type, city, state,
                    active_status, created_at)
                   VALUES (?, ?, 'elementary', ?, ?, 1, ?)""",
                (org_id, company_name, city, state, now_utc()),
            )
            db.commit()
            processed += 1
            _hs_logger.info("Created school from HubSpot webhook: %s", company_name)

        return jsonify({"ok": True, "processed": processed})
    except Exception as e:
        _hs_logger.error("HubSpot webhook error: %s", e)
        return jsonify({"error": "Webhook processing failed"}), 500
    finally:
        db.close()
