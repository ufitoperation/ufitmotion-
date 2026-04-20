# Spec — Phase 3A: Admin Dashboard Routes

**Feature:** Org-wide admin analytics and compliance monitoring
**Routes:** `GET /api/admin/dashboard`, `GET /api/admin/schools`, `GET /api/admin/coaches`, `GET /api/admin/incidents`, `GET /api/admin/students/growth`
**Status:** Approved — proceed to tdd-guide
**Author:** spec-writer
**Date:** 2026-04-20

---

## Audit Log

| Rev | Date | Change |
|---|---|---|
| v1 | 2026-04-20 | Initial spec |

---

## 7-Property Verification

| Property | Status | Notes |
|---|---|---|
| Complete | ✅ | All context a new engineer needs is in this document |
| Unambiguous | ✅ | All terms defined; column names taken directly from 001_sqlite_dev.sql |
| Consistent | ✅ | Week definition, role scoping, and auth pattern are the same across all 5 routes |
| Verifiable | ✅ | Every requirement has a BDD scenario or measurable criterion |
| Bounded | ✅ | Out-of-scope list is explicit |
| Prioritized | ✅ | Constraint matrix states trade-offs |
| Grounded | ✅ | Concrete examples for every key behavior |

---

## 1. Overview

Admins and overseers need a real-time picture of coach activity, compliance, and student progress across the entire organization. These five read-only routes aggregate data from the coach-facing tables (sessions, eod_reports, incident_reports, assessments) into views optimized for the admin dashboard.

All routes are read-only (GET). No writes occur. No audit logging is required (no PII returned — only counts, rates, and aggregate stats).

---

## 2. Auth & Roles

**Authorized roles for ALL Phase 3A routes:** `ceo`, `admin`, `coach_overseer`

**Decorator to use:** `@roles_required("ceo", "admin", "coach_overseer")` from `app.auth`

> Note: `admin_required` in `app/auth.py` only covers `ceo` and `admin`. Phase 3A routes must use `roles_required("ceo", "admin", "coach_overseer")` directly — do NOT use `admin_required`.

**Response for unauthorized roles:** 403 `{"error": "You do not have permission for this action."}`
**Response for unauthenticated:** 401 `{"error": "Authentication required."}`

---

## 3. Definitions

| Term | Meaning |
|---|---|
| **current week** | Monday 00:00:00 Pacific through Sunday 23:59:59 Pacific. Calculated as: `today = _now_pacific().date()`, `week_start = today - timedelta(days=today.weekday())`, `week_end = week_start + timedelta(days=6)`. Stored as ISO strings for SQL comparison. |
| **active coach** | A user with `role IN ('head_coach', 'assistant_coach')` AND `active_status = 1` AND `deleted_at IS NULL`. |
| **active school** | A school with `active_status = 1` AND `deleted_at IS NULL`. |
| **active student** | A student with `active_status = 1` AND `deleted_at IS NULL`. |
| **open incident** | An `incident_reports` row with `status = 'open'` AND `deleted_at IS NULL`. |
| **EOD compliance** | Ratio of EODs submitted vs. expected. Expected = number of distinct `(staff_id, session_date)` pairs in `sessions` this week where the session is not soft-deleted. Compliance = count of `eod_reports` rows this week (by `report_date`) / expected. Returns `0.0` if expected = 0. Capped at `1.0` (a coach can't over-comply). |
| **`weeks` window** | For `/api/admin/incidents`: rolling window of N complete weeks back from today's Monday. Week N starts at `week_start - timedelta(weeks=N)`, ends at `week_start - timedelta(days=1)`. Integer param, default 4, min 1, max 12. |
| **`_now_pacific()`** | Module-level function returning `datetime.datetime.now(tz=_PACIFIC)`. Same pattern as `coach_routes.py`. Must be monkeypatchable. |
| **`_get_week_bounds()`** | Module-level function returning `(week_start_str, week_end_str)` as ISO date strings. Calls `_now_pacific()` internally. |

---

## 4. Shared Helper (define in `admin_routes.py`)

```python
_PACIFIC = ZoneInfo("America/Los_Angeles")

def _now_pacific() -> datetime.datetime:
    return datetime.datetime.now(tz=_PACIFIC)

def _get_week_bounds() -> tuple[str, str]:
    today = _now_pacific().date()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday
    week_end = week_start + datetime.timedelta(days=6)             # Sunday
    return week_start.isoformat(), week_end.isoformat()
```

---

## 5. Route: GET /api/admin/dashboard

### 5.1 Request

**URL:** `GET /api/admin/dashboard`
**Auth:** `@roles_required("ceo", "admin", "coach_overseer")`
**Query params:** none
**Request body:** none

### 5.2 Response — Success (200)

```json
{
  "ok": true,
  "active_schools": 12,
  "active_coaches": 28,
  "sessions_this_week": 47,
  "eod_compliance_rate": 0.89,
  "open_incidents": 3
}
```

**Field definitions:**

| Field | Type | SQL |
|---|---|---|
| `active_schools` | int | `SELECT COUNT(*) AS cnt FROM schools WHERE active_status=1 AND deleted_at IS NULL` |
| `active_coaches` | int | `SELECT COUNT(*) AS cnt FROM users WHERE role IN ('head_coach','assistant_coach') AND active_status=1 AND deleted_at IS NULL` |
| `sessions_this_week` | int | `SELECT COUNT(*) AS cnt FROM sessions WHERE session_date BETWEEN :week_start AND :week_end AND deleted_at IS NULL` |
| `eod_compliance_rate` | float (2 decimal places, 0.0–1.0) | See §3 EOD compliance definition |
| `open_incidents` | int | `SELECT COUNT(*) AS cnt FROM incident_reports WHERE status='open' AND deleted_at IS NULL` |

**EOD compliance SQL:**
```sql
-- Expected: distinct (staff_id via session_staff, session_date) pairs this week
SELECT COUNT(*) AS cnt
FROM (
    SELECT DISTINCT ss.staff_id, s.session_date
    FROM sessions s
    JOIN session_staff ss ON ss.session_id = s.session_id
    WHERE s.session_date BETWEEN :week_start AND :week_end
      AND s.deleted_at IS NULL
) AS expected

-- Actual: EOD reports submitted this week
SELECT COUNT(*) AS cnt FROM eod_reports
WHERE report_date BETWEEN :week_start AND :week_end
  AND deleted_at IS NULL
```
`eod_compliance_rate = min(1.0, actual / expected)` if `expected > 0`, else `0.0`. Round to 2 decimal places.

### 5.3 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| DB error | 500 | `{"error": "Could not load dashboard — please try again or contact support."}` |

---

## 6. Route: GET /api/admin/schools

### 6.1 Request

**URL:** `GET /api/admin/schools`
**Auth:** `@roles_required("ceo", "admin", "coach_overseer")`
**Query params:** none
**Request body:** none

### 6.2 Response — Success (200)

```json
{
  "ok": true,
  "schools": [
    {
      "school_id": 4,
      "organization_id": 2,
      "region_id": 1,
      "school_name": "Lincoln Elementary",
      "school_type": "elementary",
      "address": "123 Main St",
      "city": "Los Angeles",
      "state": "CA",
      "zip_code": "90001",
      "principal_name": "Sandra Lee",
      "principal_email": "slee@lausd.net",
      "active_status": 1,
      "created_at": "2026-01-10T00:00:00",
      "coach_count": 3,
      "session_count_this_week": 8,
      "last_eod_date": "2026-04-19"
    }
  ],
  "total": 12
}
```

**Field definitions:**

- School fields: all fields returned by `serialize_school()` — see `_helpers.py`
- `coach_count` (int): `SELECT COUNT(*) FROM users WHERE school_id = ? AND role IN ('head_coach','assistant_coach') AND active_status=1 AND deleted_at IS NULL` — via subquery or JOIN. Use subquery approach for clarity.
- `session_count_this_week` (int): sessions at this school with `session_date BETWEEN :week_start AND :week_end AND deleted_at IS NULL`
- `last_eod_date` (str or null): `SELECT MAX(report_date) FROM eod_reports WHERE school_id = ? AND deleted_at IS NULL`

**Implementation note:** Use a single SQL query with subqueries or aggregate JOINs for all schools at once — do NOT run per-school queries in a Python loop (N+1 forbidden).

**Ordering:** `ORDER BY s.school_name ASC`

### 6.3 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| DB error | 500 | `{"error": "Could not load schools — please try again or contact support."}` |

---

## 7. Route: GET /api/admin/coaches

### 7.1 Request

**URL:** `GET /api/admin/coaches`
**Auth:** `@roles_required("ceo", "admin", "coach_overseer")`
**Query params:** none
**Request body:** none

### 7.2 Response — Success (200)

```json
{
  "ok": true,
  "coaches": [
    {
      "user_id": 5,
      "role": "head_coach",
      "first_name": "Marcus",
      "last_name": "Rivera",
      "email": "mrivera@ufit.com",
      "active_status": 1,
      "staff_id": 2,
      "position_title": "Head Coach",
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "created_at": "2026-01-10T00:00:00",
      "updated_at": null,
      "eod_submissions_this_week": 4,
      "late_submissions_this_week": 1,
      "incidents_filed_this_week": 0
    }
  ],
  "total": 28
}
```

**Field definitions:**

- User fields: all fields returned by `serialize_user()` — see `_helpers.py`
- `eod_submissions_this_week` (int): `SELECT COUNT(*) FROM eod_reports WHERE staff_id = ? AND report_date BETWEEN :week_start AND :week_end AND deleted_at IS NULL`
- `late_submissions_this_week` (int): same as above with `AND submitted_on_time = 0`
- `incidents_filed_this_week` (int): `SELECT COUNT(*) FROM incident_reports WHERE reported_by_staff_id = ? AND report_date BETWEEN :week_start AND :week_end AND deleted_at IS NULL`

**Filter:** Only active coaches (`role IN ('head_coach','assistant_coach') AND active_status=1 AND u.deleted_at IS NULL`). JOIN to `staff_profiles` (LEFT JOIN — coach may lack a staff profile, though that's a data integrity issue). JOIN to `staff_assignments` + `schools` for `school_id`/`school_name` — same pattern as `current_user()` in `auth.py`.

**Implementation note:** Use aggregate subqueries in the main SQL rather than per-coach loops. Compute `week_start`/`week_end` once and pass as parameters.

**Ordering:** `ORDER BY u.last_name ASC, u.first_name ASC`

### 7.3 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| DB error | 500 | `{"error": "Could not load coaches — please try again or contact support."}` |

---

## 8. Route: GET /api/admin/incidents

### 8.1 Request

**URL:** `GET /api/admin/incidents`
**Auth:** `@roles_required("ceo", "admin", "coach_overseer")`

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `weeks` | integer | 4 | Min 1, max 12. Non-integer or out-of-range → 422. |

### 8.2 Window Calculation

```python
week_start_str, _ = _get_week_bounds()
window_start_date = datetime.date.fromisoformat(week_start_str) - datetime.timedelta(weeks=weeks)
window_end_date = datetime.date.fromisoformat(week_start_str) - datetime.timedelta(days=1)
# window covers: window_start_date (inclusive) through window_end_date (inclusive)
# i.e. the N complete weeks before the current week
```

For `by_week` breakdown: iterate from `window_start_date` in 7-day steps (each Monday), count incidents where `report_date BETWEEN step AND step+6days`.

### 8.3 Response — Success (200)

```json
{
  "ok": true,
  "weeks": 4,
  "window_start": "2026-03-24",
  "window_end": "2026-04-19",
  "total": 11,
  "by_severity": [
    {"severity_level": "low", "count": 6},
    {"severity_level": "medium", "count": 3},
    {"severity_level": "high", "count": 2}
  ],
  "by_school": [
    {"school_id": 4, "school_name": "Lincoln Elementary", "count": 5},
    {"school_id": 7, "school_name": "Jefferson K-8", "count": 4},
    {"school_id": 11, "school_name": "Rosa Parks ES", "count": 2}
  ],
  "by_week": [
    {"week_start": "2026-03-24", "count": 2},
    {"week_start": "2026-03-31", "count": 4},
    {"week_start": "2026-04-07", "count": 3},
    {"week_start": "2026-04-14", "count": 2}
  ]
}
```

**Field definitions:**

- `weeks`: the N value used (after clamping/validation)
- `window_start`, `window_end`: ISO date strings for the window used
- `total`: `SELECT COUNT(*) FROM incident_reports WHERE report_date BETWEEN :window_start AND :window_end AND deleted_at IS NULL`
- `by_severity`: `SELECT severity_level, COUNT(*) AS cnt FROM incident_reports WHERE ... GROUP BY severity_level ORDER BY cnt DESC`
- `by_school`: JOIN to `schools` for `school_name`. `ORDER BY cnt DESC`
- `by_week`: N rows always present (even if count=0 for a week). Build week list in Python, query counts per week, merge. `ORDER BY week_start ASC`

**by_week zero-fill:** If a week in the window has no incidents, still include `{"week_start": "...", "count": 0}`. Build the complete week list in Python and left-join against query results.

### 8.4 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| `weeks` not an integer | 422 | `{"error": "weeks must be an integer between 1 and 12."}` |
| `weeks` < 1 or > 12 | 422 | `{"error": "weeks must be an integer between 1 and 12."}` |
| DB error | 500 | `{"error": "Could not load incidents — please try again or contact support."}` |

---

## 9. Route: GET /api/admin/students/growth

### 9.1 Request

**URL:** `GET /api/admin/students/growth`
**Auth:** `@roles_required("ceo", "admin", "coach_overseer")`

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `window_id` | integer | (none) | Optional. Must be a positive integer if provided → 400. No existence validation (non-existent window returns zeroes, not an error). |

### 9.2 Response — Success (200)

```json
{
  "ok": true,
  "window_id": 3,
  "assessed_students": 142,
  "total_students": 320,
  "by_school": [
    {
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "assessed_count": 58,
      "total_students": 120
    },
    {
      "school_id": 7,
      "school_name": "Jefferson K-8",
      "assessed_count": 84,
      "total_students": 200
    }
  ],
  "by_skill_domain": [
    {
      "skill_domain_id": 1,
      "domain_name": "Physical / Psychomotor",
      "avg_raw_level": 3.14
    },
    {
      "skill_domain_id": 2,
      "domain_name": "Sports Fundamentals",
      "avg_raw_level": 2.87
    }
  ]
}
```

**Field definitions:**

- `window_id`: int if filter applied, null if not
- `assessed_students` (int): `SELECT COUNT(DISTINCT student_id) FROM assessments WHERE deleted_at IS NULL [AND window_id = ?]`
- `total_students` (int): `SELECT COUNT(*) FROM students WHERE active_status=1 AND deleted_at IS NULL`
- `by_school` array:
  - `total_students` per school: `SELECT school_id, COUNT(*) FROM students WHERE active_status=1 AND deleted_at IS NULL GROUP BY school_id`
  - `assessed_count` per school: `SELECT school_id, COUNT(DISTINCT student_id) FROM assessments WHERE deleted_at IS NULL [AND window_id=?] GROUP BY school_id`
  - Merge in Python. Include all active schools even if assessed_count=0.
  - JOIN `schools` for `school_name`. `ORDER BY school_name ASC`
- `by_skill_domain` array:
  - `SELECT sd.domain_id, sd.domain_name, ROUND(AVG(asco.raw_level), 2) AS avg_raw_level FROM assessment_scores asco JOIN skills sk ON sk.skill_id = asco.skill_id JOIN skill_domains sd ON sd.domain_id = sk.domain_id JOIN assessments a ON a.assessment_id = asco.assessment_id WHERE a.deleted_at IS NULL [AND a.window_id = ?] GROUP BY sd.domain_id, sd.domain_name ORDER BY sd.domain_name ASC`
  - `avg_raw_level`: float rounded to 2 decimal places. Omit domains with no scores (don't zero-fill).

### 9.3 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| `window_id` not a positive integer | 400 | `{"error": "window_id must be a positive integer."}` |
| DB error | 500 | `{"error": "Could not load student growth data — please try again or contact support."}` |

---

## 10. BDD Acceptance Criteria

### 10.1 GET /api/admin/dashboard — unauthenticated

```
Given no session
When GET /api/admin/dashboard
Then 401 {"error": "Authentication required."}
```

### 10.2 GET /api/admin/dashboard — wrong role

```
Given a user with role=head_coach
When GET /api/admin/dashboard
Then 403 {"error": "You do not have permission for this action."}
```

### 10.3 GET /api/admin/dashboard — ceo success

```
Given a user with role=ceo
And 5 active schools, 12 active coaches
And 8 sessions this week (Mon–Sun Pacific)
And 6 distinct (staff_id, session_date) pairs from sessions this week
And 5 eod_reports this week
And 2 open incidents
When GET /api/admin/dashboard
Then 200 {
  "ok": true,
  "active_schools": 5,
  "active_coaches": 12,
  "sessions_this_week": 8,
  "eod_compliance_rate": 0.83,
  "open_incidents": 2
}
```

### 10.4 GET /api/admin/dashboard — coach_overseer role allowed

```
Given a user with role=coach_overseer
When GET /api/admin/dashboard
Then 200 (not 403)
```

### 10.5 GET /api/admin/dashboard — zero sessions this week

```
Given no sessions this week
When GET /api/admin/dashboard
Then eod_compliance_rate is 0.0
```

### 10.6 GET /api/admin/schools — returns all schools with enrichment

```
Given 3 active schools
And school_id=4 has 2 coaches, 3 sessions this week, last eod on 2026-04-19
And school_id=7 has 0 coaches, 0 sessions, no EODs ever
When admin GETs /api/admin/schools
Then 200 with schools array length 3
And school_id=4 has coach_count=2, session_count_this_week=3, last_eod_date="2026-04-19"
And school_id=7 has coach_count=0, session_count_this_week=0, last_eod_date=null
And schools are ordered by school_name ASC
```

### 10.7 GET /api/admin/schools — wrong role

```
Given role=assistant_coach
When GET /api/admin/schools
Then 403
```

### 10.8 GET /api/admin/coaches — returns active coaches with compliance

```
Given coach staff_id=2 submitted 3 EODs this week, 1 was late, filed 1 incident this week
When admin GETs /api/admin/coaches
Then the coach row has eod_submissions_this_week=3, late_submissions_this_week=1, incidents_filed_this_week=1
```

### 10.9 GET /api/admin/coaches — inactive coaches excluded

```
Given coach user_id=9 has active_status=0
When admin GETs /api/admin/coaches
Then user_id=9 is NOT in the response
```

### 10.10 GET /api/admin/coaches — ordered by last name

```
Given coaches: Rivera, Adams, Thompson
When GET /api/admin/coaches
Then order is Adams, Rivera, Thompson
```

### 10.11 GET /api/admin/incidents — default 4 weeks, all breakdowns

```
Given incidents over the last 4 weeks with known severity and school distribution
When GET /api/admin/incidents (no ?weeks param)
Then response has weeks=4, total correct, by_severity sorted by count desc,
     by_school sorted by count desc, by_week has exactly 4 entries sorted asc
```

### 10.12 GET /api/admin/incidents — zero-fill empty weeks

```
Given incidents only in weeks 1 and 3 of a 4-week window
When GET /api/admin/incidents?weeks=4
Then by_week has 4 entries
And the entry for week 2 has count=0
And the entry for week 4 has count=0
```

### 10.13 GET /api/admin/incidents — invalid weeks param

```
When GET /api/admin/incidents?weeks=abc
Then 422 {"error": "weeks must be an integer between 1 and 12."}

When GET /api/admin/incidents?weeks=0
Then 422

When GET /api/admin/incidents?weeks=13
Then 422
```

### 10.14 GET /api/admin/students/growth — no filter

```
Given 320 total active students, 142 with at least one assessment
When GET /api/admin/students/growth (no window_id)
Then window_id=null, assessed_students=142, total_students=320
And by_school includes all schools, even those with assessed_count=0
And by_skill_domain has avg_raw_level rounded to 2 decimals
```

### 10.15 GET /api/admin/students/growth — window_id filter

```
Given window_id=3 exists with 50 assessed students
And window_id=5 exists with 30 assessed students
When GET /api/admin/students/growth?window_id=3
Then window_id=3, assessed_students=50
And by_skill_domain reflects only scores from window 3 assessments
```

### 10.16 GET /api/admin/students/growth — invalid window_id

```
When GET /api/admin/students/growth?window_id=abc
Then 400 {"error": "window_id must be a positive integer."}

When GET /api/admin/students/growth?window_id=0
Then 400
```

### 10.17 GET /api/admin/students/growth — non-existent window_id returns zeroes

```
When GET /api/admin/students/growth?window_id=99999
Then 200 with assessed_students=0, by_skill_domain=[]
```

---

## 11. Out of Scope (Phase 3A)

- Writing or modifying any records (all routes are read-only)
- Filtering dashboard stats by date range or school (global only)
- Pagination on `/api/admin/schools` or `/api/admin/coaches` (full list returned; pagination deferred to Phase 4 if needed)
- `GET /api/admin/sessions` — not part of Phase 3A
- Per-student growth details — only aggregates (student PII is Phase 4/principal portal)
- HubSpot sync triggers (Phase 3C)
- RLS policies (Phase 3B)
- EOD compliance alerts / scheduled jobs (Phase 3C)
- Exporting reports to PDF/CSV

---

## 12. Constraint Matrix

| Dimension | Constraint | Trade-off |
|---|---|---|
| **N+1 prevention** | All enrichment (coach_count, session_count, etc.) computed via subquery in single SQL | Slightly more complex SQL; eliminates O(n) round-trips |
| **Week definition** | Mon–Sun Pacific, current live week only (no historical) | Dashboard always shows "this week" — no date-range param for Phase 3A |
| **EOD compliance** | Expected based on session_staff entries, not user count | More accurate — counts only coaches who actually ran sessions |
| **Compliance capped at 1.0** | Over-submitting is capped | Prevents >100% compliance from skewing averages |
| **by_week zero-fill** | All N weeks always present | Ensures frontend chart has complete x-axis data |
| **No pagination on schools/coaches** | Full list returned | Acceptable for org sizes (< 100 schools, < 500 coaches) — add if needed |
| **No audit logging** | None of these routes return student PII | FERPA §99.2(b) audit only required for routes that expose PII |

---

## 13. File Targets

| File | Action |
|---|---|
| `app/routes/admin_routes.py` | NEW — all 5 route handlers + `_now_pacific()` + `_get_week_bounds()` |
| `app/app.py` | Register `admin_bp` blueprint |
| `tests/test_admin_dashboard.py` | NEW — test file |
| `tests/conftest.py` | Add `make_incident` fixture if not present |

---

## 14. Test File Skeleton (for tdd-guide)

`tests/test_admin_dashboard.py` must cover at minimum:

**GET /api/admin/dashboard:**
- `test_dashboard_unauthenticated` — 401
- `test_dashboard_wrong_role` — 403 (head_coach)
- `test_dashboard_coach_overseer_allowed` — 200
- `test_dashboard_active_counts` — correct school/coach/session counts
- `test_dashboard_eod_compliance_rate` — known ratio
- `test_dashboard_compliance_zero_sessions` — returns 0.0 when no sessions
- `test_dashboard_open_incidents` — correct open count

**GET /api/admin/schools:**
- `test_schools_unauthenticated` — 401
- `test_schools_wrong_role` — 403
- `test_schools_enrichment` — coach_count, session_count_this_week, last_eod_date
- `test_schools_no_eod_null` — last_eod_date is null when no EODs
- `test_schools_ordered_by_name` — alphabetical

**GET /api/admin/coaches:**
- `test_coaches_unauthenticated` — 401
- `test_coaches_wrong_role` — 403
- `test_coaches_compliance_metrics` — eod_submissions, late_submissions, incidents
- `test_coaches_inactive_excluded` — active_status=0 not returned
- `test_coaches_ordered_by_last_name`

**GET /api/admin/incidents:**
- `test_incidents_unauthenticated` — 401
- `test_incidents_wrong_role` — 403
- `test_incidents_default_4_weeks` — weeks=4 in response
- `test_incidents_custom_weeks` — ?weeks=6 uses 6-week window
- `test_incidents_invalid_weeks_non_integer` — 422
- `test_incidents_invalid_weeks_zero` — 422
- `test_incidents_invalid_weeks_too_large` — 422
- `test_incidents_by_severity_sorted` — sorted by count desc
- `test_incidents_by_week_zero_fill` — empty weeks present with count=0
- `test_incidents_total_correct` — matches sum of by_week counts

**GET /api/admin/students/growth:**
- `test_growth_unauthenticated` — 401
- `test_growth_wrong_role` — 403
- `test_growth_no_filter` — all students, no window
- `test_growth_window_filter` — window_id scopes results
- `test_growth_invalid_window_id` — 400 (non-integer)
- `test_growth_nonexistent_window` — 200 with zero counts
- `test_growth_by_school_includes_zero_assessed` — zero-assessed schools included
- `test_growth_by_skill_domain_avg` — avg_raw_level correct and rounded to 2 decimals
