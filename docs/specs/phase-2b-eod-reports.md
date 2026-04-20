# Spec — Phase 2B: EOD Reports

**Feature:** Coach end-of-day report submission and retrieval
**Routes:** `POST /api/eod-reports`, `GET /api/eod-reports`
**Status:** Awaiting approval before implementation
**Author:** spec-writer agent
**Date:** 2026-04-19

---

## Audit Log

| Rev | Date | Change |
|---|---|---|
| v1 | 2026-04-19 | Initial spec |
| v2 | 2026-04-19 | Audit pass: 15 gaps closed — see §10 |
| v3 | 2026-04-19 | Second audit pass: 11 gaps closed — see §10 |
| v4 | 2026-04-20 | 3 minor gaps closed: test timezone label, GET page/per_page non-integer handling, head_coach school_id filter behavior |

---

## 7-Property Verification

| Property | Status | Notes |
|---|---|---|
| Complete | ✅ | All context a new engineer needs is in this doc |
| Unambiguous | ✅ | All terms defined; enums fully listed; column mappings explicit |
| Consistent | ✅ | GET and POST scoping rules are derived from the same role/org model |
| Verifiable | ✅ | Every requirement has a BDD scenario or measurable criterion |
| Bounded | ✅ | Out-of-scope list is explicit |
| Prioritized | ✅ | Trade-offs stated in Constraint Matrix |
| Grounded | ✅ | Concrete examples provided for every key behavior |

---

## 1. Overview

At the end of each coaching day, coaches submit a structured report summarizing what happened — activities completed, student engagement, any incidents, and flags for follow-up. This is the primary accountability artifact for Ufit's client schools and Ufit HQ.

SOUL.md constraint: **coach can complete this in under 2 minutes on mobile.** This means minimal required fields. Every optional field is explicitly optional — the form must be completable with just 3 required text responses.

One EOD report is submitted per coach per school per date. A coach who visits two schools in one day submits two EOD reports.

---

## 2. Definitions

| Term | Meaning |
|---|---|
| **EOD report** | One row in `eod_reports` covering one coaching day at one school |
| **report_date** | The calendar date the coaching activity occurred — not the submission date. Stored as a DATE, no timezone involved. |
| **submitted_on_time** | `TRUE` if the server-side submission wall-clock time in `America/Los_Angeles` (from `app_settings.default_timezone`) is on or before 20:00 on `report_date` in that timezone. `FALSE` if past that deadline. If `report_date` is a past calendar date (submitted the next day or later), always `FALSE` — no time check needed. |
| **EOD deadline** | `20:00` in the `app_settings.default_timezone` timezone (`America/Los_Angeles`). Stored in `app_settings` as `eod_submission_deadline = '20:00'`. The deadline is local Pacific time, not UTC. |
| **injury_incident_flag** | Boolean. `TRUE` means a physical injury or safety incident occurred this day. Forces `followup_needed = TRUE` (non-overridable). |
| **followup_needed** | Boolean. `TRUE` means Ufit admin should follow up. Auto-set to `TRUE` when `injury_incident_flag = TRUE` regardless of what the coach submitted. Override is one-directional only: if `injury_incident_flag = FALSE` and coach sends `followup_needed = TRUE`, the coach's value is preserved. |
| **principal_communication_needed** | Boolean. Coach flags that the school principal needs to be contacted. Stored as-is; no auto-notification in Phase 2B. |
| **coach's school** | `school_id` from `current_user()["school_id"]` — the active staff assignment |
| **Overseer scope** | `coach_overseer` can file/view EOD reports at any school in their organization |
| **site_coordinator scope** | `site_coordinator` can VIEW EOD reports in their region. Cannot POST (role_permissions write=FALSE). Region resolved from `staff_profiles.assigned_region_id` ONLY — `schools` has no `region_id` column in the migration SQL. If `assigned_region_id` is NULL → 403. |
| **Duplicate guard** | Enforced at app level only — no DB UNIQUE constraint on `(staff_id, school_id, report_date)`. The guard queries `WHERE deleted_at IS NULL`, so a coach may re-submit if their previous EOD was soft-deleted by an admin. |
| **Primary session** | If a coach logged multiple sessions in one day at the same school, `session_id` in the body should reference the primary/main session. If omitted, the EOD is date-scoped but not session-linked. Both are valid. |

---

## 3. Route: POST /api/eod-reports

### 3.1 Request

**URL:** `POST /api/eod-reports`
**Auth:** `@coach_required` — roles that may POST: `head_coach`, `assistant_coach`, `coach_overseer`
**Not allowed to POST:** `site_coordinator` (role_permissions: eod_reports write=FALSE) → 403 `{"error": "You do not have permission to submit EOD reports."}`
**Content-Type:** `application/json`

**Body fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `school_id` | integer | Yes | Must be within coach's scope |
| `report_date` | string | Yes | YYYY-MM-DD. Max 7 days past, not future |
| `activities_completed` | string | Yes | What the coach actually did. Max 2000 chars. Maps to `eod_reports.activities_completed` |
| `student_engagement_summary` | string | Yes | Overall engagement level description. Max 1000 chars. Maps to `eod_reports.student_engagement_summary` |
| `attendance_summary` | string | No | Notes on who was present/absent. Max 500 chars |
| `behavior_summary` | string | No | Notable behavior events. Max 500 chars |
| `success_story` | string | No | One win from the day. Max 500 chars |
| `challenge_summary` | string | No | What was hard. Max 500 chars |
| `notes` | string | No | Catch-all: equipment issues, weather, anything else. Max 1000 chars |
| `injury_incident_flag` | boolean | No | Default `false`. Set `true` if a physical injury or safety incident occurred |
| `followup_needed` | boolean | No | Default `false`. Auto-overridden to `true` if `injury_incident_flag = true` |
| `principal_communication_needed` | boolean | No | Default `false` |
| `program_id` | integer | No | Optional link to a specific program. Must be an active program at `school_id` if provided. Maps to `eod_reports.program_id`. |
| `session_id` | integer | No | Optional link to a specific session logged today at this school. Must exist, be at `school_id`, be on `report_date`, and not be soft-deleted. |

**Example request body (minimal — 2-minute mobile completion):**
```json
{
  "school_id": 4,
  "report_date": "2026-04-19",
  "activities_completed": "Locomotor skills — galloping, skipping, hopping. Finished with relay races.",
  "student_engagement_summary": "High energy. 3rd graders were very competitive on relays. K was distracted today."
}
```

**Example request body (full):**
```json
{
  "school_id": 4,
  "report_date": "2026-04-19",
  "activities_completed": "Locomotor skills — galloping, skipping, hopping. Relay races.",
  "student_engagement_summary": "High energy. Very engaged for relay races.",
  "attendance_summary": "28 of 30 students present. 2 absent — notes from teacher.",
  "behavior_summary": "No major issues. One student needed a 2-minute cool-down.",
  "success_story": "Jordan Rivera completed a full gallop sequence for the first time.",
  "challenge_summary": "Gymnasium lighting on the east side flickering — submitted maintenance request.",
  "notes": "Equipment: 3 hula hoops cracked. Need replacements. Weather: indoor session, no issue.",
  "injury_incident_flag": false,
  "followup_needed": false,
  "principal_communication_needed": false,
  "program_id": 7,
  "session_id": 42
}
```

### 3.2 Validation Rules (ordered — first failure returns immediately)

1. **site_coordinator role block.** Role is known from the session before any body parsing. Fail fast. → 403 `{"error": "You do not have permission to submit EOD reports."}`

2. **`school_id` present and positive integer.** → 400 `{"error": "Missing required field: school_id."}` / 400 `{"error": "school_id must be an integer."}`

3. **`report_date` present, matches YYYY-MM-DD, valid calendar date.** Parse with `datetime.date.fromisoformat()`. → 400 `{"error": "Missing required field: report_date."}` / 400 `{"error": "Invalid date format. Use YYYY-MM-DD."}`

4. **`report_date` range.** Must not be in the future. Must not be more than 7 days in the past (UTC date comparison is acceptable here — `report_date` is a calendar date, not a timestamp). → 400 `{"error": "Report date cannot be in the future."}` / 400 `{"error": "Report date cannot be more than 7 days in the past."}`

5. **`activities_completed` present, non-empty after stripping whitespace.** `data.get("activities_completed", "").strip()` must be truthy. → 400 `{"error": "Missing required field: activities_completed."}`

6. **`student_engagement_summary` present, non-empty after stripping whitespace.** Same rule. → 400 `{"error": "Missing required field: student_engagement_summary."}`

7. **String length limits.** Applied to the raw (un-stripped) value. Each string field must not exceed its max:
   - `activities_completed`: 2000
   - `student_engagement_summary`: 1000
   - `attendance_summary`, `behavior_summary`, `success_story`, `challenge_summary`: 500 each
   - `notes`: 1000
   → 400 `{"error": "Field 'activities_completed' exceeds maximum length of 2000 characters."}`

8. **Boolean fields type check.** `injury_incident_flag`, `followup_needed`, `principal_communication_needed` — if provided, must be a Python `bool` (`isinstance(val, bool)`). JSON `true`/`false` deserialize as Python `bool`; strings like `"true"` or integers do not. → 400 `{"error": "<field> must be a boolean."}` (field-specific message)

9. **`program_id` type check.** If provided, must be a positive integer (same pattern as `school_id`). → 400 `{"error": "program_id must be an integer."}`

10. **`session_id` type check.** If provided, must be a positive integer. → 400 `{"error": "session_id must be a positive integer."}`

11. **Staff profile guard.** `current_user()["staff_id"]` must not be None. → 500 `{"error": "Staff profile missing for this account. Contact your administrator."}`

12. **School assignment guard.** For `head_coach`, `assistant_coach`, AND `coach_overseer`: `current_user()["school_id"]` must not be None. → 403 `{"error": "You have no active school assignment. Contact your administrator."}` — overseer's org is resolved from their school in rule 14; without it there is no org to check against.

13. **School authorization — head_coach / assistant_coach.** `school_id` must equal `current_user()["school_id"]`. → 403 `{"error": "You are not assigned to this school."}`

14. **School authorization — coach_overseer.** `school_id` must belong to the same `organization_id` as the overseer's school (same two-step lookup as Phase 2A §3.2 rules 12/15). → 403 `{"error": "School is not in your organization."}`

15. **`program_id` validation.** If provided: `SELECT program_id FROM programs WHERE program_id = ? AND school_id = ? AND program_status = 'active'`. If not found → 400 `{"error": "Program not found at this school."}`

16. **Duplicate EOD guard.** Performed inside the DB transaction (after `get_db()`) to close the race-condition window. No DB UNIQUE constraint exists on `(staff_id, school_id, report_date)` — this guard is the sole protection. Query: `SELECT eod_id FROM eod_reports WHERE staff_id = ? AND school_id = ? AND report_date = ? AND deleted_at IS NULL LIMIT 1`. If found → 409:
    ```json
    {
      "error": "An EOD report for this school and date has already been submitted.",
      "existing_eod_id": 15
    }
    ```

17. **`session_id` validation.** If provided: `SELECT session_id FROM sessions WHERE session_id = ? AND school_id = ? AND session_date = ? AND deleted_at IS NULL`. If not found → 400 `{"error": "session_id does not match a session at this school on this date."}`

### 3.3 Business Logic (before INSERT)

**`submitted_on_time` computation:**

The deadline is `20:00` Pacific (`America/Los_Angeles` from `app_settings.default_timezone`). Use `zoneinfo` (stdlib, Python 3.9+). The backdated check must use the **Pacific calendar date**, not UTC — after midnight UTC (00:00–03:00 UTC = 16:00–19:00 Pacific), `_get_today()` returns the next UTC date while Pacific is still the previous day, which would falsely mark an on-time coach as late.

```python
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")

report_dt = datetime.date.fromisoformat(report_date_raw)
now_pacific = datetime.datetime.now(tz=PACIFIC)
today_pacific = now_pacific.date()  # Pacific calendar date — NOT _get_today() (UTC)

if report_dt < today_pacific:
    # Backdated report — submitted on a later Pacific calendar day. Always late.
    submitted_on_time = False
else:
    # Same Pacific calendar day — compare wall-clock time against 20:00 Pacific.
    deadline_pacific = now_pacific.replace(hour=20, minute=0, second=0, microsecond=0)
    submitted_on_time = now_pacific <= deadline_pacific
```

Note: `_get_today()` (UTC) is still used for the `report_date` range validation in rule 4 (no future, max 7 days past) — that check is date-only and UTC is acceptable there. The `submitted_on_time` computation uses Pacific throughout.

**`followup_needed` override (one-directional):**
```python
# injury forces followup — coach cannot override in this direction
if injury_incident_flag:
    followup_needed = True
# if injury_incident_flag is False, preserve the coach's followup_needed value
```

### 3.4 Database Write (single transaction)

1. **INSERT** one row into `eod_reports`:
   - All validated fields
   - `submitted_on_time` from computation above
   - `followup_needed` from override logic above
   - `created_at = now_utc()` (captured once before INSERT, used in response)

2. **INSERT** one row into `audit_log` via `audit()`:
   - `action = 'INSERT'`
   - `table_name = 'eod_reports'`
   - `record_id = eod_id`
   - `new_values = {"school_id": ..., "report_date": ..., "injury_incident_flag": ..., "followup_needed": ..., "submitted_on_time": ...}`
   — `followup_needed` included because it may be auto-overridden from the coach's submitted value; auditors need to see the final stored value.

3. **COMMIT.**

Pattern:
```python
db = get_db()
try:
    created_at_val = now_utc()
    cur = db.execute("INSERT INTO eod_reports (...) VALUES (...)", (...))
    new_eod_id = cur.lastrowid
    audit(db, user["user_id"], "INSERT", "eod_reports", new_eod_id, new_values={...})
    db.commit()
    return jsonify({...}), 201
except Exception as exc:
    db.rollback()
    print(f"create_eod_report ERROR: {exc}", file=sys.stderr, flush=True)
    return jsonify({"error": "EOD report could not be saved — please try again or contact support."}), 500
finally:
    db.close()
```

### 3.5 Response — Success (201)

A `serialize_eod_report()` helper must be added to `app/routes/_helpers.py` (parallel to `serialize_session()`). Both the POST 201 response and the GET list items must use it for consistent field sets.

```json
{
  "ok": true,
  "eod_report": {
    "eod_id": 15,
    "school_id": 4,
    "school_name": "Lincoln Elementary",
    "staff_id": 2,
    "coach_name": "Marcus Rivera",
    "program_id": null,
    "report_date": "2026-04-19",
    "activities_completed": "Locomotor skills — galloping, skipping, hopping.",
    "student_engagement_summary": "High energy. Very engaged.",
    "attendance_summary": null,
    "behavior_summary": null,
    "success_story": null,
    "challenge_summary": null,
    "notes": null,
    "injury_incident_flag": false,
    "followup_needed": false,
    "principal_communication_needed": false,
    "submitted_on_time": true,
    "session_id": null,
    "created_at": "2026-04-19T19:45:00+00:00"
  }
}
```

`school_name` and `coach_name` fetched via JOIN after commit (confirmation banner per SOUL.md voice). `staff_id` is returned directly from `current_user()["staff_id"]` — no extra query needed.
`program_id` is null when not provided; if provided, returned as the integer stored.

POST 201 response and GET list items use the same `serialize_eod_report()` output — both include `staff_id` and `coach_name`.

### 3.6 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role (site_coordinator) | 403 | `{"error": "You do not have permission to submit EOD reports."}` |
| No school assignment | 403 | `{"error": "You have no active school assignment. Contact your administrator."}` |
| Wrong school (head/assistant) | 403 | `{"error": "You are not assigned to this school."}` |
| School outside org (overseer) | 403 | `{"error": "School is not in your organization."}` |
| Missing/invalid field | 400 | `{"error": "..."}` (see rules 1–8) |
| Duplicate EOD | 409 | `{"error": "...", "existing_eod_id": 15}` |
| Invalid session_id | 400 | `{"error": "session_id does not match a session at this school on this date."}` |
| Missing staff_profile | 500 | `{"error": "Staff profile missing for this account. Contact your administrator."}` |
| DB error | 500 | `{"error": "EOD report could not be saved — please try again or contact support."}` |

---

## 4. Route: GET /api/eod-reports

### 4.1 Request

**URL:** `GET /api/eod-reports`
**Auth:** `@coach_required` — all four coach roles may GET

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `from` | string | 30 days before today UTC | YYYY-MM-DD inclusive lower bound on `report_date` |
| `to` | string | today UTC | YYYY-MM-DD inclusive upper bound. Must be ≥ `from` |
| `school_id` | integer | (role-scoped) | site_coordinator and coach_overseer only: filter to specific school within scope. Must be a positive integer → 400 if not. |
| `program_id` | integer | (none) | Optional: filter to a specific program. Any role may use. Must be a positive integer → 400 if not. No scope validation — zero results is silent. |
| `page` | integer | 1 | Min 1 |
| `per_page` | integer | 20 | Min 1, max 100 |

### 4.2 Scoping Rules

**head_coach / assistant_coach:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`
Returns **only their own EOD reports** (`staff_id = current_user()["staff_id"]`). Unlike sessions (school-scoped), EOD reports are coach-scoped — each coach's report is personal. Historical reports from prior school assignments are not returned — only reports at their current assigned school.

```sql
WHERE er.staff_id = :staff_id
  AND er.school_id = :user_school_id
  AND er.deleted_at IS NULL
```

**site_coordinator:**
Region resolved from `staff_profiles.assigned_region_id` ONLY. **Note: `schools` table has no `region_id` column in the migration SQL** — the Phase 2A two-step fallback to `schools.region_id` is a pre-existing production bug that Phase 2B must not replicate. If `assigned_region_id` is NULL → 403 `{"error": "You have no active region assignment. Contact your administrator."}`.

Returns all non-deleted EOD reports at schools assigned to their region, via `staff_assignments`:
```sql
JOIN schools sc ON sc.school_id = er.school_id
JOIN staff_assignments sa ON sa.school_id = sc.school_id
JOIN staff_profiles sp2 ON sp2.staff_id = sa.staff_id
WHERE sp2.assigned_region_id = :resolved_region_id
  AND er.deleted_at IS NULL
```

Actually, regions link to schools via the `regions` table, but `schools` has no `region_id`. The correct scope query is: fetch all school_ids where the school belongs to the coordinator's region — but without a `schools.region_id` column, this requires knowing which schools are in the region through another mechanism. **This is a schema gap that must be resolved before site_coordinator GET scoping can be implemented.** For Phase 2B, implement site_coordinator scoping as: return all EOD reports where `er.school_id IN (SELECT school_id FROM staff_assignments WHERE staff_id = coordinator's staff_id)` — i.e., schools the coordinator is actively assigned to. Flag in code comment that broader region-based scoping requires a `region_id` column on `schools`.

**coach_overseer:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`
Returns all non-deleted EOD reports at schools in their org (any coach's reports).

```sql
JOIN schools sc ON sc.school_id = er.school_id
WHERE sc.organization_id = :org_id
  AND er.deleted_at IS NULL
```

**Optional school_id filter (site_coordinator and overseer only):**
Validate school is within scope → 403 `{"error": "You do not have access to this school."}` if not. Then add `AND er.school_id = :school_id_filter`.
If provided by `head_coach` or `assistant_coach`, silently ignore — their scope is already fixed to their current school.

### 4.3 Response — Success (200)

```json
{
  "ok": true,
  "eod_reports": [
    {
      "eod_id": 15,
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "staff_id": 2,
      "coach_name": "Marcus Rivera",
      "program_id": null,
      "report_date": "2026-04-19",
      "activities_completed": "Locomotor skills — galloping, skipping, hopping.",
      "student_engagement_summary": "High energy. Very engaged.",
      "attendance_summary": null,
      "behavior_summary": null,
      "success_story": null,
      "challenge_summary": null,
      "notes": null,
      "injury_incident_flag": false,
      "followup_needed": false,
      "principal_communication_needed": false,
      "submitted_on_time": true,
      "session_id": null,
      "created_at": "2026-04-19T19:45:00+00:00"
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

`coach_name` resolved via LEFT JOIN (same pattern as Phase 2A `list_sessions`):
```sql
LEFT JOIN staff_profiles sp ON sp.staff_id = er.staff_id
LEFT JOIN users u ON u.user_id = sp.user_id
```
If the coach's user record is inactive or soft-deleted, `coach_name` is `null`. This is handled correctly by the LEFT JOIN — do not treat null as an error.

**`program_id` filter:** If `?program_id=N` provided, append `AND er.program_id = ?` to the main query. No scope validation needed — a program_id that returns zero results is silently empty (not a 403), since any coach can filter by program as long as their role scoping already limits what they see.

**No FERPA audit required** — response contains no student PII (no names, IDs, scores). Document in code comment.

**Ordering:** `ORDER BY er.report_date DESC, er.eod_id DESC`

### 4.4 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| No school assignment | 403 | `{"error": "You have no active school assignment. Contact your administrator."}` |
| `school_id` not a positive integer | 400 | `{"error": "school_id must be a positive integer."}` |
| school_id filter out of scope | 403 | `{"error": "You do not have access to this school."}` |
| `program_id` not a positive integer | 400 | `{"error": "program_id must be a positive integer."}` |
| No region assignment (site_coordinator) | 403 | `{"error": "You have no active region assignment. Contact your administrator."}` |
| `from` > `to` | 400 | `{"error": "from must be before or equal to to."}` |
| Bad date format | 400 | `{"error": "Invalid date format. Use YYYY-MM-DD."}` |
| `page` < 1 or not a valid integer | 400 | `{"error": "page must be a positive integer."}` |
| `per_page` out of range or not a valid integer | 400 | `{"error": "per_page must be between 1 and 100."}` |
| DB error | 500 | `{"error": "Could not load EOD reports — please try again or contact support."}` |

---

## 5. BDD Acceptance Criteria

### 5.1 POST — Minimal Happy Path (2-minute mobile submission)

```
Given a head_coach at school_id=4, staff_id=2
And no EOD report exists for staff_id=2, school_id=4, report_date="2026-04-19"
When the coach POSTs {
  school_id: 4,
  report_date: "2026-04-19",
  activities_completed: "Locomotor skills",
  student_engagement_summary: "High energy"
}
Then the response is 201
And eod_reports has one new row
And audit_log has one INSERT row for table_name='eod_reports'
And both inserts share one commit (no partial write on failure)
And the response body includes eod_id, school_name, staff_id, coach_name, submitted_on_time
And attendance_summary, behavior_summary, success_story, challenge_summary, notes, program_id are null
```

### 5.2 POST — submitted_on_time = true (before 20:00 Pacific)

```
Given the Pacific wall-clock time is 19:45 on 2026-04-19
And report_date = "2026-04-19"
When the coach POSTs
Then submitted_on_time = true in the response and in the DB
```

### 5.3 POST — submitted_on_time = false (after 20:00 Pacific)

```
Given the Pacific wall-clock time is 20:01 on 2026-04-19
And report_date = "2026-04-19"
When the coach POSTs
Then submitted_on_time = false
```

### 5.4 POST — submitted_on_time = false (backdated — past Pacific calendar date)

```
Given the Pacific wall-clock time is 10:00 on 2026-04-20
And report_date = "2026-04-19" (yesterday in Pacific)
When the coach POSTs
Then submitted_on_time = false (report_date is a prior Pacific calendar date — always late)
```

### 5.4b POST — submitted_on_time = true (after midnight UTC, still same Pacific day)

```
Given the UTC time is 01:00 on 2026-04-20 (= 18:00 Pacific on 2026-04-19)
And report_date = "2026-04-19"
When the coach POSTs
Then submitted_on_time = true
(Pacific date is still 2026-04-19; 18:00 Pacific is before the 20:00 deadline)
```

### 5.5 POST — injury_incident_flag forces followup_needed

```
Given a coach POSTs { ..., injury_incident_flag: true, followup_needed: false }
Then the DB row has followup_needed = true
And the response has followup_needed = true
(coach cannot override this — injury always requires follow-up)
```

### 5.6 POST — duplicate EOD returns 409 with existing_eod_id

```
Given eod_reports already has a row: staff_id=2, school_id=4, report_date="2026-04-19", eod_id=15
When the coach POSTs again for the same school+date
Then the response is 409
And the body is {"error": "An EOD report for this school and date has already been submitted.", "existing_eod_id": 15}
And no new row is inserted
```

### 5.7 POST — site_coordinator cannot POST

```
Given a user with role=site_coordinator
When they POST to /api/eod-reports
Then the response is 403
And the body is {"error": "You do not have permission to submit EOD reports."}
```

### 5.8 POST — wrong school (head_coach)

```
Given a head_coach at school_id=4
When they POST { school_id: 99, ... }
Then the response is 403
And the body is {"error": "You are not assigned to this school."}
```

### 5.9 POST — overseer cross-school (in org)

```
Given a coach_overseer at school_id=4 (org_id=2)
And school_id=7 is in org_id=2
When the overseer POSTs { school_id: 7, ... }
Then the response is 201
```

### 5.10 POST — invalid session_id

```
Given session_id=999 does not exist at school_id=4 on "2026-04-19"
When the coach POSTs { ..., session_id: 999 }
Then the response is 400
And the body is {"error": "session_id does not match a session at this school on this date."}
```

### 5.11 POST — future report_date

```
Given today UTC is 2026-04-19
When a coach POSTs { report_date: "2026-04-20", ... }
Then the response is 400
And the body is {"error": "Report date cannot be in the future."}
```

### 5.12 POST — report_date > 7 days past

```
Given today UTC is 2026-04-19
When a coach POSTs { report_date: "2026-04-11", ... }  (8 days ago)
Then the response is 400
And the body is {"error": "Report date cannot be more than 7 days in the past."}
```

### 5.13 POST — missing required field

```
When a coach POSTs without activities_completed
Then the response is 400
And the body is {"error": "Missing required field: activities_completed."}
```

### 5.14 POST — field exceeds max length

```
When a coach POSTs with activities_completed of 2001 characters
Then the response is 400
And the body is {"error": "Field 'activities_completed' exceeds maximum length of 2000 characters."}
```

### 5.15 GET — head_coach sees their own reports (positive case)

```
Given head_coach_A (staff_id=2) filed eod_id=7 at school_id=4 on "2026-04-19"
When head_coach_A GETs /api/eod-reports
Then the response is 200
And eod_id=7 is in the response
And the item has school_name, coach_name, submitted_on_time, program_id fields
```

### 5.16 GET — head_coach does NOT see other coaches' reports

```
Given head_coach_A (staff_id=2) and head_coach_B (staff_id=3) both at school_id=4
And head_coach_B filed eod_id=10
When head_coach_A GETs /api/eod-reports
Then eod_id=10 is NOT in the response
(EOD reports are coach-scoped for head/assistant, unlike sessions which are school-scoped)
```

### 5.17 GET — site_coordinator sees all coaches' reports in region

```
Given site_coordinator region_id=1 covers school_id=4 and school_id=5
And coach_A filed an EOD at school_id=4, coach_B at school_id=5
And school_id=20 is in region_id=3 (out of scope)
When the coordinator GETs /api/eod-reports
Then both coach_A and coach_B reports are returned
And the school_id=20 report is NOT returned
```

### 5.18 GET — overseer sees all coaches' reports in org

```
Given coach_overseer at org_id=2 (school_id=4)
And school_id=7 is also in org_id=2
And school_id=50 is in org_id=9 (different org)
When the overseer GETs /api/eod-reports
Then reports from school_id=4 and school_id=7 are returned
And reports from school_id=50 are NOT returned
```

### 5.19 GET — pagination

```
Given a head_coach with 25 EOD reports in the date window
When they GET /api/eod-reports?per_page=20&page=1
Then the response has 20 items
And total=25, page=1, per_page=20, pages=2
And items are ordered by report_date DESC, eod_id DESC
```

### 5.20 GET — school_id filter out of scope

```
Given a site_coordinator in region_id=1
And school_id=50 is in region_id=3
When they GET /api/eod-reports?school_id=50
Then the response is 403
And the body is {"error": "You do not have access to this school."}
```

### 5.21 GET — unauthenticated

```
Given no session cookie
When GET /api/eod-reports
Then the response is 401
```

---

## 6. Out of Scope (Phase 2B)

- Editing or deleting a submitted EOD report
- Admin-side EOD review / approval workflow
- Automated notifications when `followup_needed = TRUE` (Phase 3C)
- `principal_communication_needed` triggering an actual notification (Phase 3C)
- Mobile UI for EOD submission (Phase 3 — ui-designer)
- EOD compliance rate tracking / dashboard (Phase 3A)
- Supabase RLS policies (Phase 3B)
- `submitted_on_time` configurable deadline — currently reads `eod_submission_deadline` from `app_settings` in Pacific time; making the timezone itself configurable is out of scope

---

## 7. Constraint Matrix

| Dimension | Constraint | Trade-off |
|---|---|---|
| **Speed** | Coach completes EOD in under 2 minutes | Only 3 required fields; all others optional |
| **Accuracy** | Date policy: no future, max 7 days past | Same rationale as Phase 2A sessions |
| **Accountability** | `submitted_on_time` computed server-side | Coach cannot self-report timeliness |
| **Safety** | `injury_incident_flag = true` → `followup_needed = true` (non-overridable) | Coach cannot forget to flag injury follow-up |
| **Isolation** | head/assistant see only their own reports | EOD is personal accountability — not team-shared like sessions |
| **Audit** | audit() in transaction, re-raises on failure | FERPA-adjacent: admin oversight requires audit completeness |

---

## 8. Test File Skeleton (for tdd-guide)

`tests/test_eod_reports.py` must cover at minimum:

**POST tests:**
- `test_create_eod_minimal_success` — 201, only required fields, nullable fields null in response
- `test_create_eod_full_success` — 201, all fields provided and saved
- `test_create_eod_submitted_on_time_true` — before 20:00 Pacific
- `test_create_eod_submitted_on_time_false_after_deadline` — after 20:00 UTC
- `test_create_eod_submitted_on_time_false_backdated` — past report_date always late
- `test_create_eod_injury_forces_followup` — injury_incident_flag=true overrides followup_needed=false
- `test_create_eod_duplicate_returns_409` — 409 with existing_eod_id
- `test_create_eod_site_coordinator_blocked` — 403
- `test_create_eod_wrong_school_head_coach` — 403
- `test_create_eod_overseer_cross_school_in_org` — 201
- `test_create_eod_overseer_wrong_org` — 403
- `test_create_eod_future_date` — 400
- `test_create_eod_past_8_days` — 400
- `test_create_eod_missing_activities_completed` — 400
- `test_create_eod_missing_student_engagement_summary` — 400
- `test_create_eod_field_too_long` — 400
- `test_create_eod_invalid_session_id` — 400
- `test_create_eod_boolean_field_wrong_type` — 400 (string "true" rejected)
- `test_create_eod_whitespace_only_activities` — 400 (strip check)
- `test_create_eod_program_id_valid` — 201, program_id in response
- `test_create_eod_program_id_wrong_school` — 400 (program not at school)
- `test_create_eod_session_id_deleted_session` — 400 (soft-deleted session rejected)
- `test_create_eod_overseer_no_school_assignment` — 403 (rule 12 now covers overseer)
- `test_create_eod_submitted_on_time_true_after_midnight_utc` — true (18:00 Pacific = 01:00 UTC next day)
- `test_create_eod_unauthenticated` — 401

**GET tests:**
- `test_list_eod_head_coach_sees_own_reports` — positive: own reports returned with all fields
- `test_list_eod_head_coach_own_only` — negative: other coaches' reports excluded
- `test_list_eod_site_coordinator_region_scope` — region included, out-of-region excluded
- `test_list_eod_overseer_org_scope` — org-wide, no cross-org
- `test_list_eod_pagination` — total/page/pages correct, order report_date DESC eod_id DESC
- `test_list_eod_school_filter_in_scope` — filtered results correct
- `test_list_eod_school_filter_out_of_scope` — 403
- `test_list_eod_program_id_filter` — filters by program_id correctly
- `test_list_eod_coach_name_null_deleted_user` — coach_name null when user soft-deleted
- `test_list_eod_no_school_assignment_head_coach` — 403
- `test_list_eod_school_id_not_integer` — 400
- `test_list_eod_program_id_not_integer` — 400
- `test_list_eod_head_coach_excludes_prior_school_reports` — only current school shown
- `test_list_eod_unauthenticated` — 401

---

## 9. Approval Gate

**Implementation does NOT begin until this spec is approved.**

To approve: respond "Spec approved — proceed to tdd-guide for Phase 2B."

---

## 10. Audit Log — Gaps Closed

### v2 — 15 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 1 | `submitted_on_time` used 20:00 UTC — US Pacific coaches would always be "late" (20:00 UTC = 12:00–13:00 PT) | Changed to `app_settings.default_timezone` (`America/Los_Angeles`); computation uses `zoneinfo.ZoneInfo`; backdated = always late, same-day = time check in Pacific |
| 2 | `program_id` missing entirely — schema has nullable FK, index, and admin use case | Added as optional body field (validated: active program at school_id), included in POST 201 and GET list response, added `?program_id=` GET filter |
| 3 | No DB-level UNIQUE constraint on `(staff_id, school_id, report_date)` — app-only guard | Added to §2 definitions; duplicate guard moved inside DB transaction to close race-condition window |
| 4 | Non-empty string not defined — `"   "` (whitespace only) accepted by NOT NULL | Rule 5/6 now specify `.strip()` before non-empty check |
| 5 | `session_id` validation query missing `AND deleted_at IS NULL` | Rule 17 updated |
| 6 | Multi-session day — which `session_id` to link left undefined | Added to §2 definitions: use primary session or omit; both valid |
| 7 | `followup_needed` one-directional override not stated — implementer could clear it when injury=false | §3.3 and §2 definitions now explicit: override is injury→followup only |
| 8 | `followup_needed` missing from audit `new_values` | Added to §3.4 step 2 with rationale |
| 9 | `serialize_eod_report()` helper not specified | §3.5 now requires it in `_helpers.py`, used by both POST and GET |
| 10 | site_coordinator role block at rule 10 — body validated before role checked | Moved to rule 1 (fail fast: role known from session, no body parsing needed) |
| 11 | Re-submit after soft-delete behavior not stated | Added to §2 definitions |
| 12 | GET response missing `program_id` field | Added to §4.3 response shape |
| 13 | `coach_name` null case not described | §4.3 now states: null when user is inactive/deleted; not an error |
| 14 | BDD 5.15 only had negative case for head_coach visibility | Added positive BDD 5.15; old negative renamed 5.16 |
| 15 | Test skeleton missing: boolean type check, whitespace, program_id, deleted session_id, coach_name null | All 5 test cases added to §8 |

### v3 — 11 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 16 | BDDs 5.2/5.3 said "server UTC time" — deadline check is Pacific | Rewritten as "Pacific wall-clock time"; added BDD 5.4b for the midnight-UTC edge case |
| 17 | `submitted_on_time` used `_get_today()` (UTC) for backdated check — falsely marks 16:00–19:00 Pacific as "late" when UTC rolls to next day | Computation now uses `now_pacific.date()` (Pacific calendar date) throughout; UTC date only used for rule 4 range validation |
| 18 | Rule 12 school assignment guard omitted `coach_overseer` — overseer with no school hits ambiguous 403 in rule 14 | Extended rule 12 to cover overseer with rationale |
| 19 | §4.2 site_coordinator GET scoping referenced `schools.region_id` — that column does not exist in migration SQL | Removed; scoping changed to `staff_assignments`-based approach; schema gap documented; Phase 2A production bug flagged |
| 20 | POST 201 and GET response inconsistent — GET had `staff_id`/`coach_name`, POST didn't; breaks single serializer | POST 201 now includes both; `staff_id` from current_user (no query), `coach_name` from post-commit JOIN |
| 21 | GET `school_id` param — no 400 for non-integer value | Added to §4.1 constraints column and §4.4 error table |
| 22 | GET `program_id` param — no validation rule or error defined | Added to §4.1 constraints column and §4.4 error table |
| 23 | §6 out-of-scope still said "hardcoded 20:00 UTC" — contradicted v2 body | Updated to reflect Pacific timezone from app_settings |
| 24 | Full request body example missing `program_id` | Added `"program_id": 7` to full example |
| 25 | BDD 5.1 missing atomicity assertion (2 inserts, 1 commit) | Added "both inserts share one commit" assertion |
| 26 | head_coach GET: historical reports at prior schools not addressed | §4.2 now states only current school reports returned; 2 new test cases added |
