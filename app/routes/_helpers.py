"""
_helpers.py — Shared helper functions for Ufit Motion route handlers.

All helpers are pure or near-pure functions with no side effects beyond
database writes (audit). Import these into any route module that needs them.
"""

import json
import sys
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional
from flask import request


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def parse_json() -> dict:
    """
    Safely parse the request body as JSON. Returns an empty dict if the body
    is missing, not JSON, or cannot be decoded.
    """
    try:
        data = request.get_json(silent=True, force=True)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------

def now_utc() -> str:
    """Return the current UTC time as an ISO 8601 string with timezone offset."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Row serializers
# ---------------------------------------------------------------------------

def serialize_user(row: dict) -> dict:
    """
    Convert a users DB row (or join result) to a safe public dict.
    Strips password_hash and auth_uid — never send these to the client.
    """
    if row is None:
        return {}
    SAFE_FIELDS = (
        "user_id",
        "role",
        "first_name",
        "last_name",
        "email",
        "active_status",
        "staff_id",
        "position_title",
        "school_id",
        "school_name",
        "created_at",
        "updated_at",
    )
    return {k: row[k] for k in SAFE_FIELDS if k in row}


def serialize_school(row: dict) -> dict:
    """Convert a schools DB row to a public dict."""
    if row is None:
        return {}
    SAFE_FIELDS = (
        "school_id",
        "organization_id",
        "region_id",
        "school_name",
        "school_type",
        "address",
        "city",
        "state",
        "zip_code",
        "principal_name",
        "principal_email",
        "active_status",
        "created_at",
    )
    return {k: row[k] for k in SAFE_FIELDS if k in row}


def serialize_session(row: dict) -> dict:
    if row is None:
        return {}
    ALL_FIELDS = (
        "session_id", "school_id", "school_name", "program_id", "program_name",
        "session_date", "start_time", "end_time", "session_type", "location",
        "planned_activity", "actual_activity", "student_group_name",
        "session_status", "total_students_present", "notes", "created_at",
        "coach_name",
    )
    return {k: row[k] for k in ALL_FIELDS if k in row}


def serialize_eod_report(row: dict) -> dict:
    if row is None:
        return {}
    result = {}
    for field in (
        "eod_id", "school_id", "school_name", "staff_id", "coach_name",
        "program_id", "report_date", "activities_completed", "student_engagement_summary",
        "attendance_summary", "behavior_summary", "success_story", "challenge_summary",
        "notes", "session_id", "created_at",
        "school_concerns", "school_concerns_notes", "schedule_changes",
        "late_arrivals", "verbal_warnings", "hr_app_issues",
        "safety_hazards", "equipment_requests",
        "principal_communication_notes", "ufit_standards_notes",
    ):
        if field in row.keys():
            result[field] = row[field]
    # Non-nullable booleans — SQLite stores as 0/1; always coerce to bool
    for field in (
        "injury_incident_flag", "followup_needed",
        "principal_communication_needed", "submitted_on_time",
    ):
        if field in row.keys():
            result[field] = bool(row[field])
    # Nullable booleans — NULL means "not answered"; preserve None instead of coercing to False
    for field in (
        "incident_report_filed", "school_concerns_resolved",
        "coaches_clocked_in", "coaches_in_uniform",
        "coaches_setup_ready", "equipment_accounted",
        "transitions_orderly", "yard_supervised", "curriculum_followed",
    ):
        if field in row.keys():
            val = row[field]
            result[field] = bool(val) if val is not None else None
    return result


def serialize_incident(row: dict) -> dict:
    """Convert an incident_reports DB row (or join result) to a public dict."""
    if row is None:
        return {}
    result = {}
    for field in (
        "incident_id", "school_id", "school_name", "staff_id", "coach_name",
        "session_id", "student_id",
        "report_date", "incident_type", "severity_level",
        "description", "immediate_action_taken", "resolution_notes",
        "status", "created_at",
    ):
        if field in row.keys():
            result[field] = row[field]
    for field in ("school_notified", "family_notified", "escalated_to_supervisor"):
        if field in row.keys():
            result[field] = bool(row[field])
    return result


def serialize_student(row: dict) -> dict:
    """
    Convert a students DB row to a public dict.
    Returns: student_id, first_name, last_name, grade_level, school_id.
    """
    if row is None:
        return {}
    SAFE_FIELDS = (
        "student_id",
        "student_first_name",
        "student_last_name",
        "grade_level",
        "school_id",
        "school_name",
        "active_status",
        "created_at",
    )
    return {k: row[k] for k in SAFE_FIELDS if k in row}


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def audit(
    connection,
    user_id: Optional[int],
    action: str,
    table_name: str,
    record_id: Optional[int],
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
) -> None:
    """
    Insert a row into audit_log.

    Parameters
    ----------
    connection   : active DB connection (not closed by this function)
    user_id      : ID of the user performing the action, or None for system ops
    action       : verb describing the change, e.g. 'INSERT', 'UPDATE', 'DELETE'
    table_name   : name of the affected table
    record_id    : primary key of the affected record, or None
    old_values   : snapshot before change (UPDATE / DELETE), or None
    new_values   : snapshot after change (INSERT / UPDATE), or None
    """
    def _json_default(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    old_json = json.dumps(old_values, default=_json_default) if old_values is not None else None
    new_json = json.dumps(new_values, default=_json_default) if new_values is not None else None

    try:
        connection.execute(
            """INSERT INTO audit_log
               (user_id, action, table_name, record_id, old_values, new_values, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, action, table_name, record_id, old_json, new_json, now_utc()),
        )
        # Commit is intentionally NOT called here — the caller controls the
        # transaction so that the audit entry and the main write are atomic.
    except Exception as exc:
        # Log to stderr and re-raise — a missing audit entry is a FERPA §99.2(b)
        # violation, so the calling route must handle this failure explicitly.
        print(f"AUDIT FAILURE [{action} {table_name}:{record_id}]: {exc}",
              file=sys.stderr, flush=True)
        raise
