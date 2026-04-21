# Spec — Phase 4: Principal & Parent Portal Routes

**Feature:** School-scoped principal dashboard and parent child-progress portal
**Routes:** `GET /api/principal/dashboard`, `GET /api/principal/students`, `GET /api/parent/student`
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
| Consistent | ✅ | Week definition and school-scope pattern match Phase 3A admin routes |
| Verifiable | ✅ | Every requirement has a BDD scenario or measurable criterion |
| Bounded | ✅ | Out-of-scope list is explicit |
| Prioritized | ✅ | Constraint matrix states trade-offs |
| Grounded | ✅ | Concrete examples for every key behavior |

---

## 1. Overview

Phase 4 exposes two new authenticated portal surfaces:

1. **Principal portal** — school-scoped views for principals and school staff. Data is hard-filtered to the principal's assigned school. No cross-school data is ever returned.
2. **Parent portal** — a parent sees only their own children's session attendance and assessment summary. No other student's data is accessible.

All three routes are read-only (GET). No writes occur. All routes that return student records are subject to FERPA scoping requirements.

---

## 2. Auth & Roles

### Principal routes

**Authorized roles:** `principal`, `school_staff`

**Decorator:** `@roles_required("principal", "school_staff")`

**School resolution:** The principal's `school_id` is resolved at request time:

```sql
SELECT sa.school_id
FROM staff_assignments sa
JOIN staff_profiles sp ON sp.staff_id = sa.staff_id
WHERE sp.user_id = :current_user_id
  AND sa.active_status = 1
ORDER BY sa.created_at DESC
LIMIT 1
```

If this query returns no rows, respond **403** `{"error": "No school assignment found for your account."}`.

All subsequent queries in principal routes MUST use this resolved `school_id` as a filter — never trust a `school_id` from the request.

### Parent routes

**Authorized roles:** `parent`

**Decorator:** `@roles_required("parent")`

**Parent record resolution:**

```sql
SELECT parent_id FROM parents WHERE user_id = :current_user_id
```

If no row is found, respond **404** `{"error": "Parent record not found."}`.

### Shared error responses

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |

---

## 3. Definitions

| Term | Meaning |
|---|---|
| **current week** | Monday 00:00:00 Pacific through Sunday 23:59:59 Pacific. Same calculation as Phase 3A: `today = _now_pacific().date()`, `week_start = today - timedelta(days=today.weekday())`, `week_end = week_start + timedelta(days=6)`. Stored as ISO strings for SQL comparison. |
| **active student** | `students.active_status = 1 AND students.deleted_at IS NULL` |
| **active session** | `sessions.deleted_at IS NULL` |
| **assessed student** | A student with at least one row in `assessments` where `assessments.deleted_at IS NULL` for the principal's school |
| **open incident** | `incident_reports.status = 'open' AND incident_reports.deleted_at IS NULL` scoped to the principal's `school_id` |
| **EOD compliance** | Same formula as Phase 3A, scoped to the principal's school. Expected = distinct `(staff_id, session_date)` pairs in `sessions JOIN session_staff` this week for this school. Actual = `eod_reports` rows this week for this school. `min(1.0, actual / expected)` if expected > 0, else `0.0`. Round to 2 decimal places. |
| **latest assessment window** | For `avg_raw_level` on the students list: the single `assessment_windows` row whose `end_date` is the most recent for the student's school. Scores come from `assessment_scores` joined to `assessments` in that window. |
| **`_now_pacific()`** | Module-level function returning `datetime.datetime.now(tz=_PACIFIC)`. Must be monkeypatchable. Define in `principal_routes.py` and `parent_routes.py`. |
| **`_get_week_bounds()`** | Module-level function returning `(week_start_str, week_end_str)` as ISO date strings. Calls `_now_pacific()` internally. Same pattern as `admin_routes.py`. |

---

## 4. Shared Helpers (define in each route file)

```python
_PACIFIC = ZoneInfo("America/Los_Angeles")

def _now_pacific() -> datetime.datetime:
    return datetime.datetime.now(tz=_PACIFIC)

def _get_week_bounds() -> tuple[str, str]:
    today = _now_pacific().date()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()
```

---

## 5. Route: GET /api/principal/dashboard

### 5.1 Request

**URL:** `GET /api/principal/dashboard`
**Auth:** `@roles_required("principal", "school_staff")`
**Query params:** none
**Request body:** none

### 5.2 Response — Success (200)

```json
{
  "ok": true,
  "school": {
    "school_id": 4,
    "school_name": "Lincoln Elementary",
    "school_type": "elementary",
    "city": "Los Angeles",
    "state": "CA"
  },
  "sessions_this_week": 8,
  "students_total": 120,
  "students_assessed": 95,
  "eod_compliance_rate": 0.88,
  "open_incidents": 1,
  "coaches": [
    {"user_id": 5, "first_name": "Marcus", "last_name": "Rivera", "role": "head_coach"},
    {"user_id": 9, "first_name": "Deja", "last_name": "Okafor", "role": "assistant_coach"}
  ]
}
```

### 5.3 Field Definitions

| Field | Type | Source |
|---|---|---|
| `school` | object | `schools` row for the resolved `school_id`. Fields: `school_id`, `school_name`, `school_type`, `city`, `state`. |
| `sessions_this_week` | int | `SELECT COUNT(*) FROM sessions WHERE school_id = :school_id AND session_date BETWEEN :week_start AND :week_end AND deleted_at IS NULL` |
| `students_total` | int | `SELECT COUNT(*) FROM students WHERE school_id = :school_id AND active_status = 1 AND deleted_at IS NULL` |
| `students_assessed` | int | `SELECT COUNT(DISTINCT a.student_id) FROM assessments a WHERE a.school_id = :school_id AND a.deleted_at IS NULL` |
| `eod_compliance_rate` | float (0.0–1.0, 2 decimals) | See §3 EOD compliance definition, scoped to `school_id` |
| `open_incidents` | int | `SELECT COUNT(*) FROM incident_reports WHERE school_id = :school_id AND status = 'open' AND deleted_at IS NULL` |
| `coaches` | array | See §5.4 |

### 5.4 Coaches List SQL

Returns all users with an active `staff_assignments` row at the principal's school, joined to `users` for name/role. Ordered by `last_name ASC, first_name ASC`.

```sql
SELECT DISTINCT u.user_id, u.first_name, u.last_name, u.role
FROM users u
JOIN staff_profiles sp ON sp.user_id = u.user_id
JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
WHERE sa.school_id = :school_id
  AND sa.active_status = 1
  AND u.active_status = 1
  AND u.deleted_at IS NULL
ORDER BY u.last_name ASC, u.first_name ASC
```

Each element: `{"user_id": int, "first_name": str, "last_name": str, "role": str}`.

### 5.5 EOD Compliance SQL (school-scoped)

```sql
-- Expected
SELECT COUNT(*) AS cnt
FROM (
    SELECT DISTINCT ss.staff_id, s.session_date
    FROM sessions s
    JOIN session_staff ss ON ss.session_id = s.session_id
    WHERE s.school_id = :school_id
      AND s.session_date BETWEEN :week_start AND :week_end
      AND s.deleted_at IS NULL
) AS expected

-- Actual
SELECT COUNT(*) AS cnt
FROM eod_reports
WHERE school_id = :school_id
  AND report_date BETWEEN :week_start AND :week_end
  AND deleted_at IS NULL
```

### 5.6 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| No school assignment | 403 | `{"error": "No school assignment found for your account."}` |
| DB error | 500 | `{"error": "Could not load dashboard — please try again or contact support."}` |

---

## 6. Route: GET /api/principal/students

### 6.1 Request

**URL:** `GET /api/principal/students`
**Auth:** `@roles_required("principal", "school_staff")`

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `page` | integer | 1 | Min 1. Non-integer or < 1 → 422. |
| `per_page` | integer | 25 | Min 1, max 100. Non-integer or out-of-range → 422. |
| `search` | string | `""` | Optional. Applied as case-insensitive prefix/substring match on `student_first_name` or `student_last_name`. Empty string means no filter. Max 100 characters; longer values → 422. |

### 6.2 Response — Success (200)

```json
{
  "ok": true,
  "page": 1,
  "per_page": 25,
  "total": 120,
  "students": [
    {
      "student_id": 44,
      "first_name": "Amara",
      "last_name": "Johnson",
      "grade_level": "3",
      "latest_assessment_date": "2026-03-15",
      "avg_raw_level": 3.2
    },
    {
      "student_id": 51,
      "first_name": "Darius",
      "last_name": "Kim",
      "grade_level": "4",
      "latest_assessment_date": null,
      "avg_raw_level": null
    }
  ]
}
```

### 6.3 Field Definitions

| Field | Type | Source |
|---|---|---|
| `student_id` | int | `students.student_id` |
| `first_name` | str | `students.student_first_name` |
| `last_name` | str | `students.student_last_name` |
| `grade_level` | str | `students.grade_level` |
| `latest_assessment_date` | str (ISO) or null | `MAX(assessments.assessment_date)` for the student where `assessments.deleted_at IS NULL` |
| `avg_raw_level` | float (1 decimal) or null | `ROUND(AVG(asco.raw_level), 1)` from `assessment_scores` for the student's latest assessment window (see §6.4). Null if no assessments exist. |

### 6.4 Core SQL

All queries are scoped to the resolved `school_id`. N+1 queries are forbidden — use a single SQL with subqueries.

```sql
-- Count query (for pagination total)
SELECT COUNT(*) AS cnt
FROM students
WHERE school_id = :school_id
  AND active_status = 1
  AND deleted_at IS NULL
  AND (:search = '' OR student_first_name LIKE :search_pattern
                    OR student_last_name  LIKE :search_pattern)

-- Data query
SELECT
    s.student_id,
    s.student_first_name,
    s.student_last_name,
    s.grade_level,
    latest_a.latest_assessment_date,
    ROUND(AVG(asco.raw_level), 1) AS avg_raw_level
FROM students s
LEFT JOIN (
    SELECT student_id, MAX(assessment_date) AS latest_assessment_date
    FROM assessments
    WHERE school_id = :school_id
      AND deleted_at IS NULL
    GROUP BY student_id
) AS latest_a ON latest_a.student_id = s.student_id
LEFT JOIN assessments a
    ON a.student_id = s.student_id
    AND a.school_id = :school_id
    AND a.assessment_date = latest_a.latest_assessment_date
    AND a.deleted_at IS NULL
LEFT JOIN assessment_scores asco ON asco.assessment_id = a.assessment_id
WHERE s.school_id = :school_id
  AND s.active_status = 1
  AND s.deleted_at IS NULL
  AND (:search = '' OR s.student_first_name LIKE :search_pattern
                    OR s.student_last_name  LIKE :search_pattern)
GROUP BY s.student_id, s.student_first_name, s.student_last_name,
         s.grade_level, latest_a.latest_assessment_date
ORDER BY s.student_last_name ASC, s.student_first_name ASC
LIMIT :per_page OFFSET :offset
```

`search_pattern = f"%{search}%"`. `offset = (page - 1) * per_page`.

**Ordering:** `ORDER BY student_last_name ASC, student_first_name ASC` always applied before pagination.

### 6.5 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| No school assignment | 403 | `{"error": "No school assignment found for your account."}` |
| `page` not a positive integer | 422 | `{"error": "page must be a positive integer."}` |
| `per_page` not in 1–100 | 422 | `{"error": "per_page must be an integer between 1 and 100."}` |
| `search` longer than 100 chars | 422 | `{"error": "search must be 100 characters or fewer."}` |
| DB error | 500 | `{"error": "Could not load students — please try again or contact support."}` |

---

## 7. Route: GET /api/parent/student

### 7.1 Request

**URL:** `GET /api/parent/student`
**Auth:** `@roles_required("parent")`
**Query params:** none
**Request body:** none

### 7.2 Response — Success (200)

Returns all children linked to the authenticated parent (0, 1, or 2 children).

```json
{
  "ok": true,
  "children": [
    {
      "student_id": 44,
      "first_name": "Amara",
      "last_name": "Johnson",
      "grade_level": "3",
      "school_name": "Lincoln Elementary",
      "recent_sessions": [
        {
          "session_date": "2026-04-18",
          "session_type": "regular",
          "attendance_status": "present"
        },
        {
          "session_date": "2026-04-15",
          "session_type": "regular",
          "attendance_status": "present"
        }
      ],
      "assessment_summary": [
        {
          "domain_name": "Physical / Psychomotor",
          "avg_raw_level": 3.4
        },
        {
          "domain_name": "Sports Fundamentals",
          "avg_raw_level": 2.8
        }
      ]
    }
  ]
}
```

### 7.3 Field Definitions

| Field | Type | Source |
|---|---|---|
| `student_id` | int | `students.student_id` |
| `first_name` | str | `students.student_first_name` |
| `last_name` | str | `students.student_last_name` |
| `grade_level` | str | `students.grade_level` |
| `school_name` | str | `schools.school_name` JOIN on `students.school_id` |
| `recent_sessions` | array (max 10) | Last 10 attendance records for the student, ordered by `sessions.session_date DESC`. Each record: `session_date`, `session_type`, `attendance_status`. |
| `assessment_summary` | array | Average `raw_level` per `skill_domains.domain_name` across all non-deleted assessments for the student. Domains with no scores are omitted. `avg_raw_level` rounded to 1 decimal. |

### 7.4 Children Query

Children are fetched in a single query — no per-parent loops.

```sql
SELECT
    s.student_id,
    s.student_first_name,
    s.student_last_name,
    s.grade_level,
    s.school_id,
    sc.school_name
FROM students s
JOIN schools sc ON sc.school_id = s.school_id
WHERE (s.parent_primary_id = :parent_id OR s.parent_secondary_id = :parent_id)
  AND s.active_status = 1
  AND s.deleted_at IS NULL
ORDER BY s.student_last_name ASC, s.student_first_name ASC
```

### 7.5 Recent Sessions SQL

Fetched in a single query for ALL children in one round-trip using `student_id IN (...)`, then partitioned in Python.

```sql
SELECT
    ssa.student_id,
    s.session_date,
    s.session_type,
    ssa.attendance_status
FROM student_session_attendance ssa
JOIN sessions s ON s.session_id = ssa.session_id
WHERE ssa.student_id IN :student_ids
  AND s.deleted_at IS NULL
ORDER BY ssa.student_id, s.session_date DESC
```

In Python: for each student, take the first 10 rows from this result set (already ordered DESC per student).

### 7.6 Assessment Summary SQL

Fetched in a single query for all children.

```sql
SELECT
    asco.student_id,
    sd.domain_name,
    ROUND(AVG(asco.raw_level), 1) AS avg_raw_level
FROM assessment_scores asco
JOIN assessments a ON a.assessment_id = asco.assessment_id
JOIN skills sk ON sk.skill_id = asco.skill_id
JOIN skill_domains sd ON sd.domain_id = sk.domain_id
WHERE asco.student_id IN :student_ids
  AND a.deleted_at IS NULL
GROUP BY asco.student_id, sd.domain_id, sd.domain_name
ORDER BY asco.student_id, sd.domain_name ASC
```

### 7.7 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| Wrong role | 403 | `{"error": "You do not have permission for this action."}` |
| Parent record not found | 404 | `{"error": "Parent record not found."}` |
| DB error | 500 | `{"error": "Could not load student data — please try again or contact support."}` |

**Note:** An authenticated parent with no children returns `200` with `"children": []` — not a 404. The 404 is only for a missing `parents` row.

---

## 8. BDD Acceptance Criteria

### 8.1 GET /api/principal/dashboard — unauthenticated

```
Given no session
When GET /api/principal/dashboard
Then 401 {"error": "Authentication required."}
```

### 8.2 GET /api/principal/dashboard — wrong role

```
Given a user with role=head_coach
When GET /api/principal/dashboard
Then 403 {"error": "You do not have permission for this action."}
```

### 8.3 GET /api/principal/dashboard — no school assignment

```
Given a user with role=principal
And that user has no active row in staff_assignments
When GET /api/principal/dashboard
Then 403 {"error": "No school assignment found for your account."}
```

### 8.4 GET /api/principal/dashboard — success

```
Given a principal assigned to school_id=4
And school_id=4 has school_name="Lincoln Elementary"
And 3 active sessions this week at school_id=4, 2 at school_id=7
And 90 active students at school_id=4
And 70 assessed students at school_id=4
And 1 open incident at school_id=4
And 2 coaches assigned to school_id=4
When GET /api/principal/dashboard
Then 200
And sessions_this_week=3 (not 5 — school_id=7 excluded)
And students_total=90
And students_assessed=70
And open_incidents=1
And coaches array has 2 entries
And school.school_name="Lincoln Elementary"
```

### 8.5 GET /api/principal/dashboard — EOD compliance

```
Given school_id=4 has 4 distinct (staff_id, session_date) pairs this week
And 3 eod_reports submitted this week for school_id=4
When GET /api/principal/dashboard
Then eod_compliance_rate=0.75
```

### 8.6 GET /api/principal/dashboard — zero sessions this week

```
Given no sessions this week for the principal's school
When GET /api/principal/dashboard
Then eod_compliance_rate=0.0
```

### 8.7 GET /api/principal/dashboard — school_staff role allowed

```
Given a user with role=school_staff and an active staff_assignment
When GET /api/principal/dashboard
Then 200 (not 403)
```

### 8.8 GET /api/principal/students — paginated roster

```
Given school_id=4 has 60 active students
When GET /api/principal/students?page=1&per_page=25
Then 200
And total=60
And students array has 25 entries
And page=1, per_page=25 echoed in response
```

### 8.9 GET /api/principal/students — second page

```
Given 60 students, page=3, per_page=25
When GET /api/principal/students?page=3&per_page=25
Then students array has 10 entries (students 51–60)
```

### 8.10 GET /api/principal/students — search filter

```
Given students: "Amara Johnson", "Darius Kim", "Amanda Torres" at school_id=4
When GET /api/principal/students?search=am
Then response includes "Amara Johnson" and "Amanda Torres"
And "Darius Kim" is not in the response
And total reflects the filtered count (2)
```

### 8.11 GET /api/principal/students — cross-school isolation

```
Given principal is assigned to school_id=4
And student_id=99 belongs to school_id=7
When GET /api/principal/students
Then student_id=99 is NOT in the response
```

### 8.12 GET /api/principal/students — student with no assessments

```
Given student_id=51 has no assessments
When GET /api/principal/students
Then the student_id=51 row has latest_assessment_date=null and avg_raw_level=null
```

### 8.13 GET /api/principal/students — avg_raw_level rounded to 1 decimal

```
Given student_id=44 has assessment_scores with raw_level values [3, 4, 3]
When GET /api/principal/students
Then student_id=44 has avg_raw_level=3.3
```

### 8.14 GET /api/principal/students — invalid pagination params

```
When GET /api/principal/students?page=0
Then 422 {"error": "page must be a positive integer."}

When GET /api/principal/students?per_page=200
Then 422 {"error": "per_page must be an integer between 1 and 100."}

When GET /api/principal/students?page=abc
Then 422

When GET /api/principal/students?search=<101-character string>
Then 422 {"error": "search must be 100 characters or fewer."}
```

### 8.15 GET /api/parent/student — unauthenticated

```
Given no session
When GET /api/parent/student
Then 401 {"error": "Authentication required."}
```

### 8.16 GET /api/parent/student — wrong role

```
Given a user with role=principal
When GET /api/parent/student
Then 403 {"error": "You do not have permission for this action."}
```

### 8.17 GET /api/parent/student — parent record not found

```
Given a user with role=parent
And no row in parents WHERE user_id = current_user_id
When GET /api/parent/student
Then 404 {"error": "Parent record not found."}
```

### 8.18 GET /api/parent/student — parent with no children

```
Given a valid parent record with parent_id=12
And no students have parent_primary_id=12 or parent_secondary_id=12
When GET /api/parent/student
Then 200 {"ok": true, "children": []}
```

### 8.19 GET /api/parent/student — two children returned

```
Given parent_id=12 is primary parent of student_id=44 and secondary parent of student_id=51
When GET /api/parent/student
Then children array has 2 entries with student_id 44 and 51
```

### 8.20 GET /api/parent/student — recent sessions capped at 10

```
Given student_id=44 has 15 attendance records
When GET /api/parent/student
Then recent_sessions for student_id=44 has exactly 10 entries
And they are the 10 most recent by session_date
```

### 8.21 GET /api/parent/student — cross-student isolation

```
Given parent_id=12 is parent of student_id=44 only
And student_id=55 belongs to a different parent
When GET /api/parent/student
Then student_id=55 is NOT in the response
And assessment_summary and recent_sessions for student_id=44 contain no data from student_id=55
```

### 8.22 GET /api/parent/student — assessment_summary per domain

```
Given student_id=44 has assessment_scores:
  skill_id=1 (domain="Physical / Psychomotor") raw_level=3
  skill_id=2 (domain="Physical / Psychomotor") raw_level=4
  skill_id=3 (domain="Sports Fundamentals")    raw_level=2
When GET /api/parent/student
Then assessment_summary for student_id=44 contains:
  {"domain_name": "Physical / Psychomotor", "avg_raw_level": 3.5}
  {"domain_name": "Sports Fundamentals", "avg_raw_level": 2.0}
```

### 8.23 GET /api/parent/student — domain with no scores omitted

```
Given student_id=44 has no scores for domain="Behavior / SEL"
When GET /api/parent/student
Then "Behavior / SEL" is NOT in assessment_summary
```

---

## 9. Out of Scope (Phase 4)

- Writing or modifying any records (all routes are read-only)
- Principal filtering by date range (dashboard always shows current week)
- Pagination on the coaches list in the dashboard (full list returned)
- Parent viewing EOD reports or incident reports
- Parent viewing assessment detail beyond domain averages (per-skill breakdown is out of scope)
- Push or email notifications to parents
- Principal downloading/exporting the student roster to CSV/PDF
- RLS policies (Phase 3B)
- `GET /api/principal/sessions` — not part of Phase 4
- `GET /api/principal/incidents` — not part of Phase 4
- Student photo or PII fields beyond name, grade, school

---

## 10. Constraint Matrix

| Dimension | Constraint | Trade-off |
|---|---|---|
| **FERPA scoping** | All principal queries filter by resolved `school_id`; `school_id` never sourced from the request | Hard requirement — no opt-out |
| **N+1 prevention** | `recent_sessions` and `assessment_summary` fetched with `IN` batch queries; principal students fetched with subquery join | Slightly more complex SQL; eliminates O(n) round-trips |
| **School resolution** | Derived from `staff_assignments` at request time, not stored on `users` | Single source of truth; allows reassignment without re-auth |
| **Pagination** | `per_page` max 100 | Prevents oversized payloads on large rosters |
| **avg_raw_level precision** | 1 decimal place for student list, 1 decimal place for parent summary | Consistent rounding; parent view matches coach-facing precision |
| **recent_sessions cap** | 10 records | Keeps parent payload small; historical scroll not in scope |
| **Parent 404 vs 200** | Missing `parents` row → 404; zero children → 200 with empty array | Distinguishes "no account" from "no children" for frontend error handling |
| **Audit logging** | Not required for these routes | Routes return student PII — logging deferred to Phase 5 security hardening pass |

---

## 11. File Targets

| File | Action |
|---|---|
| `app/routes/principal_routes.py` | NEW — `GET /api/principal/dashboard`, `GET /api/principal/students`, `_now_pacific()`, `_get_week_bounds()`, `_resolve_school_id()` |
| `app/routes/parent_routes.py` | NEW — `GET /api/parent/student`, `_now_pacific()` |
| `app/app.py` | Register `principal_bp` and `parent_bp` blueprints |
| `tests/test_principal_routes.py` | NEW — test file for principal routes |
| `tests/test_parent_routes.py` | NEW — test file for parent route |

---

## 12. Test File Skeleton (for tdd-guide)

`tests/test_principal_routes.py` must cover at minimum:

**GET /api/principal/dashboard:**
- `test_dashboard_unauthenticated` — 401
- `test_dashboard_wrong_role` — 403 (head_coach)
- `test_dashboard_school_staff_allowed` — 200
- `test_dashboard_no_school_assignment` — 403
- `test_dashboard_school_info` — correct school name in response
- `test_dashboard_sessions_scoped_to_school` — other school sessions excluded
- `test_dashboard_students_total` — correct count
- `test_dashboard_students_assessed` — correct count
- `test_dashboard_eod_compliance` — known ratio
- `test_dashboard_compliance_zero_sessions` — returns 0.0
- `test_dashboard_open_incidents_scoped` — only school's incidents counted
- `test_dashboard_coaches_list` — correct users, ordered by last name

**GET /api/principal/students:**
- `test_students_unauthenticated` — 401
- `test_students_wrong_role` — 403
- `test_students_no_school_assignment` — 403
- `test_students_pagination_page1` — first page correct
- `test_students_pagination_page2` — second page correct
- `test_students_total_reflects_full_count` — total not capped to page
- `test_students_search_by_first_name` — filters correctly
- `test_students_search_by_last_name` — filters correctly
- `test_students_search_empty_returns_all` — no filter when search=""
- `test_students_cross_school_excluded` — other school students not returned
- `test_students_no_assessments_null_fields` — null date and avg
- `test_students_avg_raw_level_rounded` — correct rounding to 1 decimal
- `test_students_ordered_by_last_name`
- `test_students_invalid_page` — 422
- `test_students_invalid_per_page` — 422
- `test_students_search_too_long` — 422

`tests/test_parent_routes.py` must cover at minimum:

**GET /api/parent/student:**
- `test_parent_unauthenticated` — 401
- `test_parent_wrong_role` — 403
- `test_parent_record_not_found` — 404
- `test_parent_no_children` — 200 with empty array
- `test_parent_one_child` — single child returned
- `test_parent_two_children` — primary and secondary child returned
- `test_parent_cross_student_isolation` — other student not returned
- `test_parent_recent_sessions_capped_at_10` — max 10 records
- `test_parent_recent_sessions_ordered_desc` — most recent first
- `test_parent_assessment_summary_per_domain` — correct avg per domain
- `test_parent_assessment_summary_domain_omitted_if_no_scores`
- `test_parent_school_name_included`
