# Spec — Phase 2A: Session Logging

**Feature:** Coach session logging with student attendance
**Routes:** `POST /api/sessions`, `GET /api/sessions`
**Status:** Awaiting approval before implementation
**Author:** spec-writer agent
**Date:** 2026-04-19 (audited and revised)

---

## Audit Log

| Rev | Date | Change |
|---|---|---|
| v1 | 2026-04-19 | Initial spec |
| v2 | 2026-04-19 | Audit pass: 10 gaps closed — see §11 |
| v3 | 2026-04-19 | Second audit pass: 6 gaps closed — see §11 |
| v4 | 2026-04-19 | Third audit pass: 8 gaps closed — see §11 |
| v5 | 2026-04-19 | Final patch: 3 gaps closed — see §11 |

---

## 7-Property Verification

| Property | Status | Notes |
|---|---|---|
| Complete | ✅ | All context a new engineer needs is in this doc |
| Unambiguous | ✅ | All terms defined; enums fully listed; SQL join chains explicit |
| Consistent | ✅ | No contradictions between GET and POST specs |
| Verifiable | ✅ | Every requirement has a BDD scenario or measurable criterion |
| Bounded | ✅ | Out-of-scope list is explicit |
| Prioritized | ✅ | Trade-offs stated in Constraint Matrix |
| Grounded | ✅ | Concrete examples provided for every key behavior |

---

## 1. Overview

Coaches (head_coach, assistant_coach, site_coordinator, coach_overseer) log PE sessions from their phone immediately after the session ends. Each session captures:

- Which school and program the session belongs to
- The date, time window, and location
- Which students attended (selected from the coach's school roster)
- Notes and the coach's staff record as the lead

The system inserts one `sessions` row, one `session_staff` row (the current coach as lead), and one `student_session_attendance` row per attending student — all in a single atomic transaction.

Coaches also need to see their past sessions to link EOD reports (Phase 2B) and to review attendance history.

---

## 2. Definitions

| Term | Meaning |
|---|---|
| **Session** | A single scheduled PE period at one school on one date |
| **Lead coach** | The currently authenticated coach — always recorded in `session_staff` as `role = 'lead'` |
| **School roster** | All students where `students.school_id = coach's school_id`, `active_status = TRUE`, `deleted_at IS NULL` |
| **Coach's school** | The `school_id` from the coach's active `staff_assignments` row (same value `current_user()` returns) |
| **site_coordinator scope** | `site_coordinator` can log/view sessions at any school in their region. Region is resolved from `staff_profiles.assigned_region_id` (primary); if NULL, falls back to `schools.region_id` of their school assignment; if both NULL → 403 "You have no active region assignment. Contact your administrator." |
| **Overseer scope** | `coach_overseer` can log/view sessions at any school in their organization |
| **program_id** | Must reference an active program (`program_status = 'active'`) at the given `school_id` |
| **attendance_status** | One of: `present`, `absent`, `late`, `excused` |
| **session_type** | One of: `regular`, `makeup`, `enrichment`, `assessment` |
| **session_status** | Always `completed` on creation via this endpoint (future: `draft`) |
| **Today** | The calendar date in UTC at the moment the request is processed. See §3.2 rule 4 for timezone policy. |
| **EOD filed for a session** | A row exists in `eod_reports` where `staff_id = coach's staff_id` AND `school_id = session's school_id` AND `report_date = session's session_date` AND `deleted_at IS NULL`. The `eod_reports.session_id` FK is not used for this check — an EOD filed for the day covers all sessions that day. |

---

## 3. Route: POST /api/sessions

### 3.1 Request

**URL:** `POST /api/sessions`
**Auth:** `@coach_required` — roles: `head_coach`, `assistant_coach`, `site_coordinator`, `coach_overseer`
**Content-Type:** `application/json`

**Body fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `school_id` | integer | Yes | Must match coach's assigned school; overseer: any school in their org; site_coordinator: any school in their region |
| `program_id` | integer | Yes | Must be active program at the given `school_id` |
| `session_date` | string | Yes | ISO 8601 date: `YYYY-MM-DD`. See §3.2 rule 4 for date policy. |
| `start_time` | string | No | `HH:MM` (24-hour). If provided, both `start_time` and `end_time` must be provided and `start_time < end_time`. |
| `end_time` | string | No | `HH:MM` (24-hour). Required if `start_time` provided. |
| `session_type` | string | No | Default: `regular`. Enum: `regular`, `makeup`, `enrichment`, `assessment` |
| `location` | string | No | Max 200 chars. Freetext gym/field name. |
| `planned_activity` | string | No | Max 500 chars. |
| `actual_activity` | string | No | Max 500 chars. |
| `student_group_name` | string | No | Max 200 chars. e.g., "3rd Grade - Red Group" |
| `notes` | string | No | Max 1000 chars. |
| `student_ids` | array of integers | No | Default: `[]`. Each element must be a positive integer. Each ID must be an active student at the given `school_id`. |

**Example request body:**
```json
{
  "school_id": 4,
  "program_id": 7,
  "session_date": "2026-04-19",
  "start_time": "09:30",
  "end_time": "10:15",
  "session_type": "regular",
  "location": "Main Gym",
  "actual_activity": "Locomotor skills - galloping and skipping",
  "student_ids": [12, 15, 18, 22, 31]
}
```

### 3.2 Validation Rules (ordered — first failure returns immediately)

1. **`school_id` present and integer.** → 400 `{"error": "Missing required field: school_id."}` / 400 `{"error": "school_id must be an integer."}`
2. **`program_id` present and integer.** → 400 `{"error": "Missing required field: program_id."}` / 400 `{"error": "program_id must be an integer."}`
3. **`session_date` present, matches `YYYY-MM-DD`, and is a valid calendar date.** Parse with `datetime.date.fromisoformat(session_date)` — this rejects non-existent dates like `"2026-02-30"`. → 400 `{"error": "Missing required field: session_date."}` / 400 `{"error": "Invalid date format. Use YYYY-MM-DD."}`
4. **`session_date` date policy.** `session_date` must be no more than 7 calendar days in the past relative to today UTC, and must not be a future date (> today UTC). Rationale: coaches in US timezones (UTC-8 to UTC-4) may be up to 8 hours behind UTC; a 7-day lookback accommodates late submissions and travel without allowing arbitrary backdating. → 400 `{"error": "Session date cannot be in the future."}` / 400 `{"error": "Session date cannot be more than 7 days in the past."}`
5. **`start_time` / `end_time` pairing.** If either is provided, both must be provided. → 400 `{"error": "Both start_time and end_time are required if either is provided."}`
6. **`start_time` / `end_time` format.** Each must match `HH:MM` where HH is 00–23 and MM is 00–59. → 400 `{"error": "Invalid time format. Use HH:MM (24-hour)."}`
7. **`start_time < end_time`.** → 400 `{"error": "start_time must be before end_time."}`
8. **`session_type` enum.** If provided, must be one of `regular`, `makeup`, `enrichment`, `assessment`. → 400 `{"error": "Invalid session_type. Must be one of: regular, makeup, enrichment, assessment."}`
9. **String length limits.** Each string field must not exceed its max. → 400 `{"error": "Field 'notes' exceeds maximum length of 1000 characters."}`
10. **`student_ids` type.** If provided, must be a JSON array. Each element must be a positive integer (not null, not string, not float). → 400 `{"error": "student_ids must be an array of positive integers."}`
10b. **`student_ids` no duplicates.** The array must not contain the same integer more than once. A duplicate would hit the `UNIQUE(session_id, student_id)` constraint on `student_session_attendance` and cause an unhandled DB error. → 400 `{"error": "student_ids contains duplicate values."}` Check with `len(student_ids) != len(set(student_ids))`.
11. **Staff profile guard.** `current_user()["staff_id"]` must not be None. If it is, the authenticated user has no staff_profile — this is a data integrity error. → 500 `{"error": "Staff profile missing for this account. Contact your administrator."}` Log to stderr.
12. **Coach's school assignment guard.** For `head_coach` and `assistant_coach`: `current_user()["school_id"]` must not be None. → 403 `{"error": "You have no active school assignment. Contact your administrator."}` For `coach_overseer`: `current_user()["school_id"]` must also not be None — the overseer's organization is resolved from their school, and without a school assignment there is no org to check against. Same 403 message.
13. **School authorization — head_coach / assistant_coach.** `school_id` must equal `current_user()["school_id"]`. → 403 `{"error": "You are not assigned to this school."}`
14. **School authorization — site_coordinator.** Resolve the coordinator's region using this two-step lookup:
    - Step A: `SELECT assigned_region_id FROM staff_profiles WHERE staff_id = current_user()["staff_id"]`
    - Step B: if `assigned_region_id` is NULL and coordinator has a school assignment, `SELECT region_id FROM schools WHERE school_id = current_user()["school_id"]`
    - If both are NULL → 403 `{"error": "You have no active region assignment. Contact your administrator."}`
    - With the resolved `region_id`, verify: `SELECT 1 FROM schools WHERE school_id = submitted_school_id AND region_id = resolved_region_id`
    - If not found → 403 `{"error": "This school is not in your region."}`
15. **School authorization — coach_overseer.** `school_id` must belong to the same `organization_id` as the overseer's school. Query: `SELECT organization_id FROM schools WHERE school_id = overseer's school_id`. Then verify: `SELECT 1 FROM schools WHERE school_id = submitted_school_id AND organization_id = that_org_id`. → 403 `{"error": "School is not in your organization."}`
16. **Program validation.** `SELECT 1 FROM programs WHERE program_id = ? AND school_id = ? AND program_status = 'active'`. → 400 `{"error": "Program not found at this school."}`
17. **Student IDs validation.** Fetch all submitted IDs in one query: `SELECT student_id FROM students WHERE student_id IN (?) AND school_id = submitted_school_id AND active_status = TRUE AND deleted_at IS NULL`. The set difference between submitted IDs and returned IDs is the invalid set. If non-empty → 400 `{"error": "Invalid student IDs: [13, 45]."}` (list the invalid IDs).
18. **Duplicate session guard.** Query: `SELECT s.session_id FROM sessions s JOIN session_staff ss ON ss.session_id = s.session_id WHERE s.school_id = ? AND s.program_id = ? AND s.session_date = ? AND ss.staff_id = ? AND ss.role = 'lead' LIMIT 1`. If a row is returned → 409 `{"error": "A session for this school, program, and date has already been logged by you. Use the existing session ID to file an EOD report.", "existing_session_id": <returned session_id>}`. Use `SELECT s.session_id` (not `SELECT 1`) — the returned ID is required in the 409 body so the client can recover without re-logging.

### 3.3 Database Writes (single transaction)

Perform all five steps in one transaction. If any step fails, roll back everything and return 500.

1. **INSERT** one row into `sessions`:
   - `school_id`, `program_id`, `session_date`, `start_time`, `end_time`, `session_type`, `location`, `planned_activity`, `actual_activity`, `student_group_name`, `notes`
   - `session_status = 'completed'`
   - `total_students_present = len(student_ids)` — count of IDs submitted (all default to `present`)
   - `created_at = now_utc()`
   - Capture returned `session_id`.

2. **INSERT** one row into `session_staff`:
   - `session_id` = new session_id
   - `staff_id` = `current_user()["staff_id"]` (validated non-None in rule 11)
   - `role = 'lead'`

3. **INSERT** one row into `student_session_attendance` per `student_id` in `student_ids` (skip if list is empty):
   - `session_id` = new session_id
   - `student_id` = each ID
   - `attendance_status = 'present'`
   - `participation_level = NULL`
   - `notes = NULL`

4. **INSERT** one row into `audit_log` via `audit()` helper:
   - `user_id = current_user()["user_id"]`
   - `action = 'INSERT'`
   - `table_name = 'sessions'`
   - `record_id = session_id`
   - `new_values = {"school_id": ..., "program_id": ..., "session_date": ..., "student_count": len(student_ids)}`

5. **COMMIT.** Call `db.commit()`. Structure the handler as:
   ```python
   db = get_db()
   try:
       # all 4 inserts here, including audit()
       db.commit()
       # fetch school_name and program_name for response (separate SELECT after commit)
       return jsonify({...}), 201
   except Exception:
       # db.close() in finally rolls back uncommitted transaction automatically
       return jsonify({"error": "Session could not be saved — please try again or contact support."}), 500
   finally:
       db.close()
   ```
   Do not swallow exceptions — let `audit()` re-raise per the FERPA contract from Week 1-2. The rollback is implicit: `db.close()` on an uncommitted connection discards the transaction (both SQLite and psycopg2 behave this way).

### 3.4 Response — Success (201)

```json
{
  "ok": true,
  "session": {
    "session_id": 42,
    "school_id": 4,
    "school_name": "Lincoln Elementary",
    "program_id": 7,
    "program_name": "PE Support — 2025-26",
    "session_date": "2026-04-19",
    "start_time": "09:30",
    "end_time": "10:15",
    "session_type": "regular",
    "location": "Main Gym",
    "planned_activity": null,
    "actual_activity": "Locomotor skills - galloping and skipping",
    "student_group_name": null,
    "session_status": "completed",
    "total_students_present": 5,
    "notes": null,
    "created_at": "2026-04-19T14:33:00+00:00",
    "student_ids": [12, 15, 18, 22, 31]
  }
}
```

`school_name` and `program_name` are required in the 201 response — per SOUL.md voice: *"Confirmation messages: specific. 'Session saved for Lincoln Elementary, Period 3.' Not 'Success.'"* The client uses these to display a confirmation banner. Fetch via JOIN on `schools` and `programs` after insert.

`student_ids` in the response is the accepted list written to `student_session_attendance`, sorted ascending by student_id.

### 3.5 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| No active school assignment | 403 | `{"error": "You have no active school assignment. Contact your administrator."}` |
| Wrong school (head/assistant) | 403 | `{"error": "You are not assigned to this school."}` |
| No region assignment (site_coordinator) | 403 | `{"error": "You have no active region assignment. Contact your administrator."}` |
| School not in region (site_coordinator) | 403 | `{"error": "This school is not in your region."}` |
| School outside org (overseer) | 403 | `{"error": "School is not in your organization."}` |
| Missing required field | 400 | `{"error": "Missing required field: session_date."}` |
| Invalid date format | 400 | `{"error": "Invalid date format. Use YYYY-MM-DD."}` |
| Future date | 400 | `{"error": "Session date cannot be in the future."}` |
| Date > 7 days ago | 400 | `{"error": "Session date cannot be more than 7 days in the past."}` |
| Bad time format | 400 | `{"error": "Invalid time format. Use HH:MM (24-hour)."}` |
| Only one of start/end provided | 400 | `{"error": "Both start_time and end_time are required if either is provided."}` |
| start_time >= end_time | 400 | `{"error": "start_time must be before end_time."}` |
| Bad session_type | 400 | `{"error": "Invalid session_type. Must be one of: regular, makeup, enrichment, assessment."}` |
| Program not found/inactive | 400 | `{"error": "Program not found at this school."}` |
| student_ids not array of integers | 400 | `{"error": "student_ids must be an array of positive integers."}` |
| Invalid student IDs | 400 | `{"error": "Invalid student IDs: [13, 45]."}` |
| Field too long | 400 | `{"error": "Field 'notes' exceeds maximum length of 1000 characters."}` |
| Duplicate session (same coach, school, program, date) | 409 | `{"error": "A session for this school, program, and date has already been logged by you. Use the existing session ID to file an EOD report.", "existing_session_id": 37}` |
| Missing staff_profile | 500 | `{"error": "Staff profile missing for this account. Contact your administrator."}` |
| DB / internal error | 500 | `{"error": "Session could not be saved — please try again or contact support."}` |

---

## 4. Route: GET /api/sessions

### 4.1 Request

**URL:** `GET /api/sessions`
**Auth:** `@coach_required`

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `school_id` | integer | (role-scoped) | site_coordinator and coach_overseer only: filter to specific school within their scope. Ignored for head_coach / assistant_coach. |
| `from` | string | 30 days before today UTC | `YYYY-MM-DD`. Inclusive lower bound on `session_date`. |
| `to` | string | today UTC | `YYYY-MM-DD`. Inclusive upper bound on `session_date`. Must be ≥ `from`. |
| `page` | integer | 1 | Min 1. Non-integer or < 1 → 400. |
| `per_page` | integer | 20 | Min 1, max 100. Non-integer or out of range → 400. |

### 4.2 Scoping Rules

Scoping is applied via the coach's school → organization/region chain. No query may return sessions from outside the authenticated coach's organization.

**head_coach / assistant_coach:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`. (Without this guard, `WHERE sessions.school_id = NULL` silently returns zero rows — the coach sees an empty list rather than an actionable error.)
Sessions where `sessions.school_id = current_user()["school_id"]`.
This includes sessions logged by other coaches at the same school — the session list is school-scoped, not coach-scoped. Rationale: coaches at the same school need visibility into their team's activity for coordination and EOD continuity.

**site_coordinator:**
Sessions at all schools in the coordinator's region. Region is resolved using the same two-step logic as §3.2 rule 14: `staff_profiles.assigned_region_id` first, then `schools.region_id` of their school assignment, then 403 if both NULL.

SQL approach (after resolving `region_id`):
```sql
SELECT s.*
FROM sessions s
JOIN schools sc ON sc.school_id = s.school_id
WHERE sc.region_id = :resolved_region_id
```
If region resolution yields NULL (no assignment, no school region), return 403 `{"error": "You have no active region assignment. Contact your administrator."}`

**coach_overseer:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`. (Without this guard, the org resolution query returns nothing and the scope filter silently returns zero rows.)
Sessions at all schools in the same organization as the overseer's assigned school.
SQL approach:
```sql
SELECT s.*
FROM sessions s
JOIN schools sc ON sc.school_id = s.school_id
WHERE sc.organization_id = (
    SELECT organization_id FROM schools WHERE school_id = :overseer_school_id
)
```

**Optional school_id filter (site_coordinator and overseer only):**
If `?school_id=N` is provided, add `AND s.school_id = N` after the scope filter. Validate that N is within the coach's scope — if not → 403 `{"error": "You do not have access to this school."}`.

### 4.3 Response — Success (200)

```json
{
  "ok": true,
  "sessions": [
    {
      "session_id": 42,
      "session_date": "2026-04-19",
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "program_id": 7,
      "program_name": "PE Support — 2025-26",
      "session_type": "regular",
      "start_time": "09:30",
      "end_time": "10:15",
      "location": "Main Gym",
      "session_status": "completed",
      "total_students_present": 5,
      "eod_filed": false,
      "coach_name": "Marcus Rivera",
      "created_at": "2026-04-19T14:33:00+00:00"
    }
  ],
  "total": 47,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

**`eod_filed`** — boolean. True if a row exists in `eod_reports` where:
- `staff_id = current_user()["staff_id"]`
- `school_id = session's school_id`
- `report_date = session's session_date`
- `deleted_at IS NULL`

This is a date-level check, not session_id-level. The `eod_reports.session_id` FK exists but is nullable and does not reliably represent "this EOD covers this session." Use the date match instead.

**`coach_name`** — must be resolved without N+1 queries. Include in the main session SELECT via a LEFT JOIN, not a per-row subquery:
```sql
SELECT s.*, sc.school_name, p.program_name,
       (u.first_name || ' ' || u.last_name) AS coach_name
FROM sessions s
JOIN schools sc ON sc.school_id = s.school_id
JOIN programs p ON p.program_id = s.program_id
LEFT JOIN session_staff ss ON ss.session_id = s.session_id AND ss.role = 'lead'
LEFT JOIN staff_profiles sp ON sp.staff_id = ss.staff_id
LEFT JOIN users u ON u.user_id = sp.user_id
WHERE <scope filter> AND <date filter>
ORDER BY s.session_date DESC, s.session_id DESC
LIMIT :per_page OFFSET :offset
```
If no lead record exists (data inconsistency), `coach_name` is `null`.

**`pages`** — computed as `ceil(total / per_page)`. If `total = 0`, return `pages = 0`.

**`program_name`** — `programs.program_name` joined on `sessions.program_id`. Required in list items — `program_id: 7` is meaningless to a coach on a phone.

Sessions are ordered `ORDER BY session_date DESC, session_id DESC`. Use `session_id` (not `created_at`) as the tiebreaker — it is monotonically increasing and guarantees stable pagination across requests even if two sessions share the same timestamp.

**`eod_filed`** — must not be computed with a per-row query. After the main session SELECT, fetch EOD data in one bulk query and build a lookup set keyed on `(school_id, report_date)` tuples — not date alone. Keying on date only produces false positives for site_coordinators and overseers who see sessions from multiple schools (an EOD at school A would incorrectly mark a session at school B as filed).

```python
session_keys = [(s["school_id"], s["session_date"]) for s in sessions]
# single query using IN on (school_id, report_date) pairs
eod_filed_set = {
    (row["school_id"], row["report_date"])
    for row in db.execute(
        "SELECT school_id, report_date FROM eod_reports "
        "WHERE staff_id = ? AND deleted_at IS NULL",
        (current_user()["staff_id"],)
    ).fetchall()
}
for s in sessions:
    s["eod_filed"] = (s["school_id"], s["session_date"]) in eod_filed_set
```

**FERPA audit decision for GET:** Sessions contain `total_students_present` (an aggregate count) and `school_name` — no student PII (names, IDs, scores). FERPA §99.2(b) audit is therefore **not required** for `GET /api/sessions`. This is a conscious decision, not an omission. If student PII is ever added to this response, auditing becomes mandatory. Document this in a code comment in the route handler.

### 4.4 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| school_id filter not in scope | 403 | `{"error": "You do not have access to this school."}` |
| `from` > `to` | 400 | `{"error": "from must be before or equal to to."}` |
| Bad date format | 400 | `{"error": "Invalid date format. Use YYYY-MM-DD."}` |
| `page` < 1 or non-integer | 400 | `{"error": "page must be a positive integer."}` |
| `per_page` < 1 or > 100 | 400 | `{"error": "per_page must be between 1 and 100."}` |
| DB / internal error | 500 | `{"error": "Could not load sessions — please try again or contact support."}` |

---

## 5. BDD Acceptance Criteria

### 5.1 POST — Happy Path

```
Given a head_coach authenticated at school_id=4, staff_id=2
And program_id=7 is active at school_id=4
And student_ids [12, 15, 18] are all active students at school_id=4
When the coach POSTs { school_id:4, program_id:7, session_date:"2026-04-19", student_ids:[12,15,18] }
Then the response is 201
And sessions table has one new row with school_id=4, total_students_present=3
And session_staff has one row with staff_id=2, role='lead'
And student_session_attendance has 3 rows, all with attendance_status='present'
And audit_log has one INSERT row for table_name='sessions'
And all 5 writes share one commit (no partial writes on failure)
```

### 5.2 POST — Zero Students

```
Given a head_coach authenticated at school_id=4
When the coach POSTs { school_id:4, program_id:7, session_date:"2026-04-19" } (no student_ids)
Then the response is 201
And sessions.total_students_present = 0
And student_session_attendance has 0 new rows
And session_staff still has 1 row for the coach
```

### 5.3 POST — Wrong School (head_coach)

```
Given a head_coach authenticated at school_id=4
When the coach POSTs { school_id:99, program_id:7, session_date:"2026-04-19" }
Then the response is 403
And the body is {"error": "You are not assigned to this school."}
And no rows are inserted in sessions, session_staff, or student_session_attendance
```

### 5.4 POST — Future Date

```
Given today UTC is 2026-04-19
When a coach POSTs { session_date: "2026-04-20", ... }
Then the response is 400
And the body is {"error": "Session date cannot be in the future."}
```

### 5.5 POST — Date Too Far in the Past

```
Given today UTC is 2026-04-19
When a coach POSTs { session_date: "2026-04-11", ... }  (8 days ago)
Then the response is 400
And the body is {"error": "Session date cannot be more than 7 days in the past."}
```

### 5.6 POST — Invalid Student in List

```
Given student_id=999 does not exist at school_id=4
When a coach POSTs { student_ids:[12, 999], ... }
Then the response is 400
And the body contains "Invalid student IDs: [999]"
And no session row is inserted
```

### 5.7 POST — Non-Integer in student_ids

```
When a coach POSTs { student_ids:[12, "abc", null], ... }
Then the response is 400
And the body is {"error": "student_ids must be an array of positive integers."}
```

### 5.8 POST — Duplicate Session (mobile double-tap)

```
Given a session already exists: staff_id=2, school_id=4, program_id=7, session_date="2026-04-19", role='lead'
  with session_id=37
When the coach POSTs the same { school_id:4, program_id:7, session_date:"2026-04-19", ... }
Then the response is 409
And the body is {"error": "A session for this school, program, and date has already been logged by you. Use the existing session ID to file an EOD report.", "existing_session_id": 37}
And no new session row is inserted
```

### 5.9 POST — Missing staff_profile

```
Given a user with role='head_coach' but no row in staff_profiles
When they POST to /api/sessions
Then the response is 500
And the body is {"error": "Staff profile missing for this account. Contact your administrator."}
And the error is logged to stderr
```

### 5.10 POST — Coach Overseer Cross-School (in org)

```
Given a coach_overseer whose school_id=4 belongs to organization_id=2
And school_id=7 also belongs to organization_id=2
When the overseer POSTs { school_id:7, program_id:8, session_date:"2026-04-19" }
Then the response is 201
And sessions row has school_id=7
```

### 5.11 POST — Coach Overseer Wrong Org

```
Given a coach_overseer in organization_id=2
And school_id=50 belongs to organization_id=9
When the overseer POSTs { school_id:50, ... }
Then the response is 403
And the body is {"error": "School is not in your organization."}
```

### 5.12 POST — site_coordinator in-region

```
Given a site_coordinator at school_id=4 (region_id=1)
And school_id=5 also has region_id=1
When the coordinator POSTs { school_id:5, program_id:9, session_date:"2026-04-19" }
Then the response is 201
And sessions row has school_id=5
```

### 5.13 POST — site_coordinator out-of-region

```
Given a site_coordinator at school_id=4 (region_id=1)
And school_id=20 has region_id=3
When the coordinator POSTs { school_id:20, ... }
Then the response is 403
And the body is {"error": "This school is not in your region."}
```

### 5.14 POST — site_coordinator with no region assignment

```
Given a site_coordinator with staff_profiles.assigned_region_id = NULL
And their school_id is also NULL (no active assignment)
When they POST to /api/sessions
Then the response is 403
And the body is {"error": "You have no active region assignment. Contact your administrator."}
```

### 5.15 POST — site_coordinator resolves region from staff_profiles.assigned_region_id

```
Given a site_coordinator with staff_profiles.assigned_region_id = 1
And their current_user()["school_id"] = NULL (no school assignment)
And school_id=5 has region_id=1
When the coordinator POSTs { school_id:5, program_id:9, session_date:"2026-04-19" }
Then the response is 201
(Region resolved from staff_profiles.assigned_region_id, not from school chain)
```

### 5.16 GET — Scoped to School (head_coach)

```
Given a head_coach at school_id=4
And the DB has sessions for school_id=4 and school_id=50
When the coach GETs /api/sessions
Then the response contains only sessions with school_id=4
And school_id=50 sessions are never returned
```

### 5.17 GET — Sees Other Coach's Sessions at Same School

```
Given head_coach_A and head_coach_B are both at school_id=4
And head_coach_B logged a session (session_id=10) at school_id=4
When head_coach_A GETs /api/sessions
Then session_id=10 appears in the results
(school-scoped, not coach-scoped — both coaches at the same school see all sessions)
```

### 5.18 GET — Paginated List

```
Given a head_coach at school_id=4 with 47 sessions in the date window
When the coach GETs /api/sessions?per_page=20&page=1
Then the response is 200
And sessions array has 20 items
And total=47, page=1, per_page=20, pages=3
And every session in the list has school_id=4
And eod_filed is a boolean for each session
And sessions are ordered by session_date DESC, session_id DESC
```

### 5.19 GET — Default Date Range

```
Given today UTC is 2026-04-19
When a coach GETs /api/sessions with no from/to params
Then sessions returned have session_date between 2026-03-20 and 2026-04-19 (inclusive)
```

### 5.20 GET — eod_filed True

```
Given a session at school_id=4, session_date="2026-04-19", session_id=42
And an eod_reports row with staff_id=coach's staff_id, school_id=4, report_date="2026-04-19", deleted_at=NULL
When the coach GETs /api/sessions
Then the session with session_id=42 has eod_filed=true
```

### 5.21 GET — eod_filed False (EOD exists for different date)

```
Given session_id=42 has session_date="2026-04-19"
And an eod_reports row exists for same coach, same school, but report_date="2026-04-18"
When the coach GETs /api/sessions
Then session_id=42 has eod_filed=false
```

### 5.22 GET — No Cross-Org Leakage

```
Given coach_A is at school_id=4 (organization_id=2)
And coach_B is at school_id=50 (organization_id=9)
And the DB has sessions for both schools
When coach_A GETs /api/sessions
Then the response contains only sessions with school_id=4
And school_id=50 sessions are never returned
```

### 5.23 GET — site_coordinator Region Scope

```
Given a site_coordinator at school_id=4 (region_id=1)
And school_id=5 also has region_id=1
And school_id=20 has region_id=3
And sessions exist for school_id=4, 5, and 20
When the coordinator GETs /api/sessions
Then sessions for school_id=4 and school_id=5 are returned
And sessions for school_id=20 are not returned
```

### 5.24 GET — Unauthenticated

```
Given no session cookie is present
When a request is made to GET /api/sessions
Then the response is 401
And the body is {"error": "Authentication required."}
```

---

## 6. Out of Scope (Phase 2A)

The following are explicitly NOT part of this spec:

- Per-student attendance status customization (absent, late, excused) — all attendance defaults to `present`. Phase 2B or a later iteration.
- Editing or deleting a session after creation.
- `session_status = 'draft'` — sessions are always created as `completed`.
- Multiple coaches on a session (session_staff supports it, but the creation endpoint only records the submitting coach).
- `GET /api/sessions/:id` — detail view for a single session.
- Mobile UI for session logging (Phase 3 — ui-designer handles templates).
- EOD report creation (Phase 2B).
- Student program enrollment enforcement — students do not need to be enrolled in the program to be recorded as attending.
- Supabase RLS policies — required separately before production deploy.
- `PATCH /api/sessions/:id` — session amendment.

---

## 7. Constraint Matrix

| Dimension | Constraint | Trade-off |
|---|---|---|
| **Speed** | Coach completes session log in < 90 seconds on mobile | Prioritized over form completeness — minimal required fields |
| **Accuracy > flexibility** | Date policy: no future, max 7 days past | Accommodates US timezone lag without allowing arbitrary backdating |
| **Data isolation** | Student scope check and school auth run before every write | Extra DB queries per request; mandatory — no exceptions |
| **Atomicity** | All inserts in one transaction | Simpler than compensating transactions; SQLite and Postgres both support this |
| **Audit completeness** | audit() re-raises on failure; a session with no audit entry is blocked | FERPA §99.2(b) compliance; caller handles 500 gracefully |
| **Pagination** | Default per_page=20, max 100 | Coach phone screens have limited height; large pages degrade mobile UX |
| **Deduplication** | 409 on duplicate (school+program+date+staff_id) | Protects against mobile retry storms; `existing_session_id` in 409 body lets client recover |

---

## 8. Dependencies and Preconditions

Before this spec can be implemented:

1. `programs` table has at least one active program per school in the dev seed data.
2. `staff_profiles` and `staff_assignments` are populated for the coach test accounts.
3. `students` are seeded for the coach's school.
4. `current_user()` in `app/auth.py` already returns `staff_id` and `school_id` — confirmed.
5. `audit()` helper in `_helpers.py` is working — confirmed in Week 1-2.
6. For site_coordinator tests: at least 2 schools with the same `region_id` must be seeded.
7. For overseer tests: at least 2 schools with the same `organization_id` must be seeded.

**Agent routing for implementation:**

```
tdd-guide → (write tests/) → planner → implementation → python-reviewer →
code-reviewer → security-reviewer (auth scope checks) → api-design skill →
doc-updater (docs/api.md) → smart-commit
```

---

## 9. Test File Skeleton (for tdd-guide)

`tests/test_sessions.py` must cover at minimum:

**POST tests:**
- `test_create_session_success` — 201, all 4 tables written, atomic; response includes school_name and program_name
- `test_create_session_zero_students` — 201, attendance empty, session_staff present
- `test_create_session_wrong_school_head_coach` — 403
- `test_create_session_no_school_assignment` — 403
- `test_create_session_future_date` — 400
- `test_create_session_past_8_days` — 400 (8 days ago rejected)
- `test_create_session_past_7_days` — 201 (exactly 7 days ago, allowed)
- `test_create_session_invalid_student_ids` — 400 with ID list
- `test_create_session_non_integer_student_ids` — 400
- `test_create_session_duplicate_student_ids` — 400 (same ID twice in array)
- `test_create_session_inactive_program` — 400
- `test_create_session_unauthenticated` — 401
- `test_create_session_duplicate_same_coach` — 409 with existing_session_id
- `test_create_session_no_staff_profile` — 500
- `test_create_session_school_not_in_org_overseer` — 403
- `test_create_session_overseer_cross_school_success` — 201
- `test_create_session_site_coordinator_in_region` — 201
- `test_create_session_site_coordinator_out_of_region` — 403
- `test_create_session_site_coordinator_no_region_assignment` — 403
- `test_create_session_site_coordinator_region_from_staff_profiles` — 201 (no school assignment, but assigned_region_id set)

**GET tests:**
- `test_list_sessions_scoped_to_school_head_coach` — no cross-school data
- `test_list_sessions_head_coach_sees_other_coach_sessions` — school-scoped, not coach-scoped
- `test_list_sessions_pagination` — total/page/pages correct; order is session_date DESC, session_id DESC
- `test_list_sessions_default_date_range` — 30-day window
- `test_list_sessions_eod_filed_true` — date+staff_id+school_id match
- `test_list_sessions_eod_filed_false_different_date` — different date = false
- `test_list_sessions_no_cross_org_leakage` — org boundary enforced
- `test_list_sessions_site_coordinator_region_scope` — region included, out-of-region excluded
- `test_list_sessions_overseer_all_schools_in_org` — org-wide visibility
- `test_list_sessions_unauthenticated` — 401
- `test_list_sessions_school_filter_out_of_scope` — 403
- `test_list_sessions_response_includes_program_name` — program_name present in each item

---

## 10. Approval Gate

**Implementation does NOT begin until this spec is approved.**

To approve: respond "Spec approved — proceed to tdd-guide for Phase 2A."

If changes are needed, note them and this doc will be updated before approval.

---

## 11. Audit Log — Gaps Closed

### v2 — 10 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 1 | `eod_filed` used `session_id` match (wrong) — `eod_reports.session_id` is nullable and not a reliable "covers this session" signal | Changed to date+staff_id+school_id match in §2 definition and §4.3 |
| 2 | `staff_id` NULL not guarded — LEFT JOIN on staff_profiles means staff_id can be None | Added rule 11 in §3.2: 500 with explicit message if staff_id is None |
| 3 | No active school assignment unhandled for head/assistant | Added rule 12 in §3.2: 403 with clear message |
| 4 | site_coordinator POST scope undefined — spec grouped them with single-school coaches | Added rule 14 in §3.2: region-based auth; added BDDs 5.12 and 5.13 |
| 5 | `student_ids` array element type not validated — non-integers silently break | Added rule 10 in §3.2; added BDD 5.7 |
| 6 | GET site_coordinator JOIN chain not described | Added explicit SQL in §4.2 for both site_coordinator and overseer |
| 7 | No duplicate session detection — mobile retry creates phantom rows | Added rule 18 in §3.2: 409 with `existing_session_id`; added BDD 5.8 |
| 8 | `pages` calculation never defined | Added `ceil(total / per_page)` formula in §4.3 |
| 9 | head/assistant coaches seeing other coaches' sessions at same school was implicit | Made explicit in §4.2 with rationale; added BDD 5.17 |
| 10 | Date comparison timezone undefined — UTC could block West Coast coaches | Added 7-day lookback policy in §3.2 rule 4; updated definitions §2 |

### v3 — 6 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 11 | site_coordinator region derivation ignored `staff_profiles.assigned_region_id` — breaks when coordinator has no school assignment | Rule 14 now uses assigned_region_id as primary, school's region_id as fallback; added BDDs 5.14 and 5.15 |
| 12 | POST 201 response missing `school_name` and `program_name` — SOUL.md requires specific confirmation copy | Added both fields to §3.4 response; added JOIN requirement |
| 13 | GET list items missing `program_name` — `program_id: 7` is meaningless in field conditions | Added `program_name` to §4.3 list item shape |
| 14 | GET ordering used `created_at` as tiebreaker — unstable for pagination if two sessions share a timestamp | Changed to `ORDER BY session_date DESC, session_id DESC` in §4.3 |
| 15 | FERPA audit logging decision for GET absent — silent omission vs. my_students which audits | Added explicit FERPA decision in §4.3: GET not audited (no PII in response); document in code comment |
| 16 | 500 error message strings violated SOUL.md voice — "An unexpected error occurred." gives coach no next step | Updated to actionable strings in §3.5 and §4.4 |

### v4 — 8 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 17 | `student_ids` duplicates not caught — `UNIQUE(session_id, student_id)` on `student_session_attendance` means `[12,12]` causes a DB constraint crash (500) instead of 400 | Added rule 10b: dedup check with `len != len(set(...))` → 400; added test case |
| 18 | Rule 18 used `SELECT 1` but returned `existing_session_id` — impossible to get the ID from a `SELECT 1` | Changed to `SELECT s.session_id … LIMIT 1` in rule 18 |
| 19 | Rule 3 accepted non-existent calendar dates like `"2026-02-30"` — regex passes but `fromisoformat()` throws | Rule 3 now specifies `datetime.date.fromisoformat()` parse which rejects invalid dates |
| 20 | `coach_overseer` with no school assignment had no guard — results in wrong 403 ("not in your org" when the real problem is "no assignment") | Rule 12 extended to cover `coach_overseer`; no school_id → same 403 as head_coach |
| 21 | `coach_name` and `eod_filed` had no query strategy — naive implementation would be N+1 on every paginated GET | §4.3 now specifies JOIN-based main query for `coach_name`/`school_name`/`program_name`, and bulk prefetch strategy for `eod_filed` |
| 22 | GET list response missing `start_time` / `end_time` — coaches can't distinguish two sessions at the same school on the same day without times | Added both fields to §4.3 response shape |
| 23 | §6 out-of-scope still said "site_coordinator fallback to single-school if region_id NULL" — contradicts v3 which made this a 403 | Removed stale item from §6 |
| 24 | Transaction rollback mechanism never specified — developer had to infer from existing code | §3.3 step 5 now shows the try/commit/finally pattern with explanation of implicit rollback |

### v5 — 3 gaps closed

| # | Gap | Resolution |
|---|---|---|
| 25 | `eod_filed` bulk lookup keyed on date only — multi-school roles get false positives when an EOD exists at a different school on the same date | §4.3 now keys the lookup set on `(school_id, report_date)` tuples with example code |
| 26 | GET has no school assignment guard for head_coach/assistant_coach — NULL school_id causes silent empty list instead of actionable 403 | Guard added to §4.2 head_coach/assistant_coach section |
| 27 | GET has no school assignment guard for coach_overseer — NULL school_id causes silent empty list via failed org resolution | Guard added to §4.2 coach_overseer section |
