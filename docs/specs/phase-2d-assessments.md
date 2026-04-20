# Spec — Phase 2D: Assessments

**Feature:** Coach skill assessment submission and retrieval
**Routes:** `POST /api/assessments`, `GET /api/assessments`
**Status:** Awaiting approval before implementation
**Author:** spec-writer agent
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
| Consistent | ✅ | GET and POST scoping rules derive from the same role/org model used in Phase 2B |
| Verifiable | ✅ | Every requirement has a BDD scenario or measurable criterion |
| Bounded | ✅ | Out-of-scope list is explicit |
| Prioritized | ✅ | Constraint matrix states trade-offs |
| Grounded | ✅ | Concrete examples for every key behavior |

---

## 1. Overview

Ufit coaches assess students' physical skill levels using a 1–5 rubric at defined points in the school year called assessment windows. This feature lets coaches submit those scores via the API and retrieve them for review.

Each assessment covers one student in one assessment window, with one or more skill scores. The scores land in two tables: `assessments` (the header record) and `assessment_scores` (one row per skill). Both writes happen in a single atomic transaction.

The GET route returns assessment records with their associated scores, scoped by the caller's role.

---

## 2. Definitions

| Term | Meaning |
|---|---|
| **assessment** | One row in `assessments`. Header record for a student/window combination. |
| **assessment_score** | One row in `assessment_scores`. One per skill within an assessment. `raw_level` stores the 1–5 score. |
| **assessment window** | A row in `assessment_windows`. Has a `status` column: `'active'` means coaches may submit scores against it. `'upcoming'` or `'closed'` means no new submissions. |
| **active window** | `assessment_windows.status = 'active'` AND `school_id` matches the student's school. |
| **skill** | A row in `skills`. Must have `active_status = 1` to accept scores. |
| **assessor** | The staff member who observed and rated the student. Defaults to the caller's `staff_id`. Overridable via `assessor_staff_id` body field. |
| **duplicate assessment** | A non-deleted row in `assessments` with the same `(student_id, window_id)`. Enforced at app level — no DB UNIQUE constraint on this pair. |
| **coach's school** | `school_id` from `current_user()["school_id"]` — the active staff assignment. |
| **normalized_score** | Set equal to `raw_level` in Phase 2D. Future phases may apply a formula. |

---

## 3. Route: POST /api/assessments

### 3.1 Request

**URL:** `POST /api/assessments`
**Auth:** `@coach_required` — roles that may POST: `head_coach`, `assistant_coach`, `coach_overseer`
**Not allowed to POST:** `site_coordinator` → 403 `{"error": "You do not have permission to submit assessments."}`
**Content-Type:** `application/json`

**Body fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `student_id` | integer | Yes | Positive integer. Student must belong to the coach's school. |
| `window_id` | integer | Yes | Positive integer. Window must exist and have `status = 'active'`. Window's `school_id` must match the student's school. |
| `scores` | array | Yes | At least 1 item. Each item: `{ "skill_id": int, "raw_score": int }`. |
| `scores[].skill_id` | integer | Yes (per item) | Must be a valid skill with `active_status = 1`. |
| `scores[].raw_score` | integer | Yes (per item) | 1–5 inclusive. Maps to `assessment_scores.raw_level`. |
| `assessor_staff_id` | integer | No | Defaults to `current_user()["staff_id"]`. If provided, must be a positive integer. No further validation — assessor may differ from submitter (e.g., overseer submitting on behalf of a field coach). |
| `assessment_date` | string | No | YYYY-MM-DD. Defaults to today (UTC). If provided, must be a valid date, not in the future, not more than 7 days in the past. |
| `assessment_method` | string | No | Defaults to `'observational'`. No enum validation in Phase 2D — stored as-is. |
| `overall_assessment_notes` | string | No | Free text. Max 2000 chars. Maps to `assessments.overall_assessment_notes`. |

**Example request body (minimal):**
```json
{
  "student_id": 42,
  "window_id": 3,
  "scores": [
    { "skill_id": 1, "raw_score": 3 },
    { "skill_id": 2, "raw_score": 4 }
  ]
}
```

**Example request body (full):**
```json
{
  "student_id": 42,
  "window_id": 3,
  "assessor_staff_id": 7,
  "assessment_date": "2026-04-19",
  "assessment_method": "observational",
  "overall_assessment_notes": "Student showed consistent improvement in balance skills.",
  "scores": [
    { "skill_id": 1, "raw_score": 3 },
    { "skill_id": 2, "raw_score": 5 }
  ]
}
```

### 3.2 Validation Rules (ordered — first failure returns immediately)

1. **site_coordinator role block.** Role is known from the session before any body parsing. → 403 `{"error": "You do not have permission to submit assessments."}`

2. **`student_id` present, positive integer.** → 400 `{"error": "Missing required field: student_id."}` or `{"error": "student_id must be a positive integer."}`

3. **`window_id` present, positive integer.** → 400 `{"error": "Missing required field: window_id."}` or `{"error": "window_id must be a positive integer."}`

4. **`scores` present, is a non-empty list.** → 400 `{"error": "Missing required field: scores."}` or `{"error": "scores must be a non-empty array."}`

5. **Each score item has `skill_id` (positive integer) and `raw_score` (integer 1–5).** Validate all items before any DB access. → 400 `{"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}` — one error message covers all malformed items.

6. **`assessor_staff_id` type check.** If provided, must be a positive integer. → 400 `{"error": "assessor_staff_id must be a positive integer."}`

7. **`assessment_date` validation.** If provided: must be YYYY-MM-DD, not in the future, not more than 7 days in the past (UTC). → 400 `{"error": "Invalid date format. Use YYYY-MM-DD."}` / `{"error": "Assessment date cannot be in the future."}` / `{"error": "Assessment date cannot be more than 7 days in the past."}`

8. **`overall_assessment_notes` length.** If provided, max 2000 chars. → 400 `{"error": "Field 'overall_assessment_notes' exceeds maximum length of 2000 characters."}`

9. **Staff profile guard.** `current_user()["staff_id"]` must not be None. → 500 `{"error": "Staff profile missing for this account. Contact your administrator."}`

10. **School assignment guard.** For `head_coach`, `assistant_coach`, AND `coach_overseer`: `current_user()["school_id"]` must not be None. → 403 `{"error": "You have no active school assignment. Contact your administrator."}`

11. **`student_id` existence and school scope.** Query: `SELECT student_id, school_id FROM students WHERE student_id = ? AND active_status = 1 AND deleted_at IS NULL`.
    - If not found → 403 `{"error": "Student not found or is not active."}`
    - For `head_coach`/`assistant_coach`: `student.school_id` must equal `current_user()["school_id"]`. → 403 `{"error": "Student does not belong to your school."}`
    - For `coach_overseer`: `student.school_id` must be in the overseer's org (two-step lookup: overseer's school → org_id → target school's org_id). → 403 `{"error": "Student does not belong to a school in your organization."}`

12. **`window_id` validation.** Query: `SELECT window_id, school_id, status FROM assessment_windows WHERE window_id = ?`.
    - If not found → 400 `{"error": "Assessment window not found."}`
    - If `status != 'active'` → 400 `{"error": "Assessment window is not active."}`
    - `window.school_id` must equal the student's `school_id` (resolved in rule 11). → 400 `{"error": "Assessment window does not belong to the student's school."}`

13. **`skill_id` validation.** For each unique `skill_id` in the scores array, verify `SELECT skill_id FROM skills WHERE skill_id = ? AND active_status = 1`. If any skill_id is invalid → 400 `{"error": "Invalid or inactive skill_id: <N>."}` where N is the first invalid skill_id found.

14. **Duplicate assessment guard.** Query: `SELECT assessment_id FROM assessments WHERE student_id = ? AND window_id = ? AND deleted_at IS NULL LIMIT 1`. If found → 409 `{"error": "An assessment for this student and window already exists.", "existing_assessment_id": <N>}`.

### 3.3 Business Logic (before INSERT)

**`assessment_date` default:** If not provided, use `_get_today().isoformat()` (UTC).

**`assessor_staff_id` default:** If not provided, use `current_user()["staff_id"]`.

**`normalized_score`:** Set equal to `raw_level` (the submitted `raw_score`). Formula reserved for a future phase.

**`program_id` and `session_id`:** Not accepted in the Phase 2D request body. Both are stored as NULL in the `assessments` row. They can be linked in a future phase.

**`school_id` for the assessments row:** Use the student's resolved `school_id` (from rule 11), not a body field.

### 3.4 Database Write (single transaction)

1. **INSERT** one row into `assessments`:
   - `student_id`, `school_id` (from student lookup), `window_id`
   - `assessed_by_staff_id` = resolved `assessor_staff_id`
   - `assessment_date` = resolved date
   - `assessment_method` = provided value or `'observational'`
   - `overall_assessment_notes` = provided value or NULL
   - `program_id` = NULL, `session_id` = NULL (Phase 2D)
   - `created_at` = `now_utc()` (captured once before INSERT)

2. **INSERT** one row into `assessment_scores` per score in the `scores` array:
   - `assessment_id` = new assessment's PK
   - `student_id` = same as above
   - `skill_id` = from score item
   - `raw_level` = `raw_score` from score item
   - `normalized_score` = same as `raw_level`
   - `benchmark_id` = NULL (Phase 2D)
   - `confidence_rating` = NULL
   - `observed_independence` = 1 (default)
   - `observed_consistency` = 0 (default)
   - `observed_accuracy` = 0 (default)
   - `growth_flag` = 0 (default)
   - `created_at` = same `now_utc()` value

3. **INSERT** one row into `audit_log` via `audit()`:
   - `action = 'INSERT'`
   - `table_name = 'assessments'`
   - `record_id = assessment_id`
   - `new_values = {"student_id": ..., "school_id": ..., "window_id": ..., "score_count": len(scores)}`

4. **COMMIT.**

Pattern (same as Phase 2B):
```python
db = get_db()
try:
    created_at_val = now_utc()
    cur = db.execute("INSERT INTO assessments (...) VALUES (...)", (...))
    new_assessment_id = cur.lastrowid
    for score in scores:
        db.execute("INSERT INTO assessment_scores (...) VALUES (...)", (...))
    audit(db, user["user_id"], "INSERT", "assessments", new_assessment_id, new_values={...})
    db.commit()
    return jsonify({...}), 201
except Exception as exc:
    db.rollback()
    return jsonify({"error": "Assessment could not be saved — please try again or contact support."}), 500
finally:
    db.close()
```

### 3.5 Response — Success (201)

A `serialize_assessment()` helper must be added to `app/routes/_helpers.py`. Both the POST 201 response and the GET list items use it.

```json
{
  "ok": true,
  "assessment": {
    "assessment_id": 11,
    "student_id": 42,
    "school_id": 4,
    "school_name": "Lincoln Elementary",
    "window_id": 3,
    "window_name": "Fall 2026 Assessment",
    "assessed_by_staff_id": 2,
    "assessor_name": "Marcus Rivera",
    "assessment_date": "2026-04-19",
    "assessment_method": "observational",
    "overall_assessment_notes": null,
    "created_at": "2026-04-19T19:45:00+00:00",
    "scores": [
      {
        "score_id": 21,
        "skill_id": 1,
        "skill_name": "Galloping",
        "raw_level": 3,
        "normalized_score": 3
      },
      {
        "score_id": 22,
        "skill_id": 2,
        "skill_name": "Skipping",
        "raw_level": 4,
        "normalized_score": 4
      }
    ]
  }
}
```

`school_name` and `window_name` fetched via JOIN after commit. `assessor_name` resolved from `staff_profiles` + `users` via `assessed_by_staff_id`.

### 3.6 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| site_coordinator | 403 | `{"error": "You do not have permission to submit assessments."}` |
| No school assignment | 403 | `{"error": "You have no active school assignment. Contact your administrator."}` |
| Student not found / inactive | 403 | `{"error": "Student not found or is not active."}` |
| Student not at coach's school | 403 | `{"error": "Student does not belong to your school."}` |
| Student not in overseer's org | 403 | `{"error": "Student does not belong to a school in your organization."}` |
| Missing student_id | 400 | `{"error": "Missing required field: student_id."}` |
| Missing window_id | 400 | `{"error": "Missing required field: window_id."}` |
| Missing / empty scores | 400 | `{"error": "Missing required field: scores."}` or `{"error": "scores must be a non-empty array."}` |
| Malformed score item | 400 | `{"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}` |
| raw_score out of range | 400 | `{"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}` |
| Window not found | 400 | `{"error": "Assessment window not found."}` |
| Window not active | 400 | `{"error": "Assessment window is not active."}` |
| Window school mismatch | 400 | `{"error": "Assessment window does not belong to the student's school."}` |
| Invalid skill_id | 400 | `{"error": "Invalid or inactive skill_id: <N>."}` |
| Duplicate assessment | 409 | `{"error": "An assessment for this student and window already exists.", "existing_assessment_id": N}` |
| Missing staff_profile | 500 | `{"error": "Staff profile missing for this account. Contact your administrator."}` |
| DB error | 500 | `{"error": "Assessment could not be saved — please try again or contact support."}` |

---

## 4. Route: GET /api/assessments

### 4.1 Request

**URL:** `GET /api/assessments`
**Auth:** `@coach_required` — all four roles may GET

**Query parameters:**

| Param | Type | Default | Constraints |
|---|---|---|---|
| `student_id` | integer | (none) | Optional. Filter to a specific student. Must be a positive integer → 400. |
| `window_id` | integer | (none) | Optional. Filter to a specific assessment window. Must be a positive integer → 400. |
| `school_id` | integer | (role-scoped) | `coach_overseer` and `site_coordinator` only. Must be a positive integer → 400. |
| `page` | integer | 1 | Min 1. |
| `per_page` | integer | 20 | Min 1, max 100. |

### 4.2 Scoping Rules

**head_coach / assistant_coach:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`
Returns only assessments where `assessments.school_id = current_user()["school_id"]`.
`student_id` filter applied within that school scope. `school_id` query param silently ignored.

```sql
WHERE a.school_id = :user_school_id
  AND a.deleted_at IS NULL
```

**site_coordinator:**
Returns assessments at schools the coordinator is actively staff-assigned to (same pattern as Phase 2B EOD scoping):
```sql
WHERE a.school_id IN (
    SELECT school_id FROM staff_assignments
    WHERE staff_id = :coordinator_staff_id AND active_status = 1
)
AND a.deleted_at IS NULL
```
If `school_id` filter provided, validate it is in that set → 403 `{"error": "You do not have access to this school."}` if not.

**coach_overseer:**
Guard: if `current_user()["school_id"]` is None → 403 `{"error": "You have no active school assignment. Contact your administrator."}`
Returns all non-deleted assessments at schools in their org:
```sql
JOIN schools sc ON sc.school_id = a.school_id
WHERE sc.organization_id = :org_id
  AND a.deleted_at IS NULL
```
If `school_id` filter provided, validate it is in the org → 403 if not.

**`student_id` filter:** Any role may use it. Appended after scope: `AND a.student_id = ?`. No additional scope validation — the scope SQL already constrains to visible schools, so a student from another org simply returns zero results.

**`window_id` filter:** Any role may use it. Appended after scope: `AND a.window_id = ?`. No access validation needed.

**Ordering:** `ORDER BY a.assessment_date DESC, a.assessment_id DESC`

### 4.3 Response — Success (200)

```json
{
  "ok": true,
  "assessments": [
    {
      "assessment_id": 11,
      "student_id": 42,
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "window_id": 3,
      "window_name": "Fall 2026 Assessment",
      "assessed_by_staff_id": 2,
      "assessor_name": "Marcus Rivera",
      "assessment_date": "2026-04-19",
      "assessment_method": "observational",
      "overall_assessment_notes": null,
      "created_at": "2026-04-19T19:45:00+00:00",
      "scores": [
        {
          "score_id": 21,
          "skill_id": 1,
          "skill_name": "Galloping",
          "raw_level": 3,
          "normalized_score": 3
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

`assessor_name` resolved via LEFT JOIN on `staff_profiles` + `users`. NULL when user is soft-deleted (not an error).
`window_name` resolved via LEFT JOIN on `assessment_windows`.
`skill_name` resolved via LEFT JOIN on `skills`.
`scores` array is always present; empty array `[]` when no score rows exist (e.g., deleted scores).

**FERPA note:** Response contains `student_id` (an opaque integer, no PII). Audit is not required for GET assessments — no names, no identifying strings. Document in code comment.

### 4.4 Response — Errors

| Condition | HTTP | Body |
|---|---|---|
| Not authenticated | 401 | `{"error": "Authentication required."}` |
| No school assignment | 403 | `{"error": "You have no active school assignment. Contact your administrator."}` |
| `school_id` not a positive integer | 400 | `{"error": "school_id must be a positive integer."}` |
| `school_id` out of scope | 403 | `{"error": "You do not have access to this school."}` |
| `student_id` not a positive integer | 400 | `{"error": "student_id must be a positive integer."}` |
| `window_id` not a positive integer | 400 | `{"error": "window_id must be a positive integer."}` |
| `page` < 1 or non-integer | 400 | `{"error": "page must be a positive integer."}` |
| `per_page` out of range or non-integer | 400 | `{"error": "per_page must be between 1 and 100."}` |
| DB error | 500 | `{"error": "Could not load assessments — please try again or contact support."}` |

---

## 5. BDD Acceptance Criteria

### 5.1 POST — Minimal Happy Path

```
Given a head_coach at school_id=4, staff_id=2
And student_id=42 is active at school_id=4
And window_id=3 is active at school_id=4
And no assessment exists for student_id=42, window_id=3
When the coach POSTs {
  student_id: 42,
  window_id: 3,
  scores: [{ skill_id: 1, raw_score: 3 }]
}
Then the response is 201
And assessments has one new row with school_id=4
And assessment_scores has one new row with raw_level=3, normalized_score=3
And audit_log has one INSERT row for table_name='assessments'
And all three inserts share one commit
And the response body includes assessment_id, student_id, school_name, window_name,
    assessor_name, scores array with score_id, skill_name, raw_level
```

### 5.2 POST — Full Body

```
Given a head_coach at school_id=4
And valid student, window, and two skills
When the coach POSTs with all optional fields including assessor_staff_id,
     assessment_date, assessment_method, overall_assessment_notes
Then the response is 201
And all provided field values appear in the response
And scores array has two items
```

### 5.3 POST — site_coordinator blocked

```
Given a user with role=site_coordinator
When they POST to /api/assessments
Then the response is 403
And the body is {"error": "You do not have permission to submit assessments."}
```

### 5.4 POST — student not at coach's school

```
Given head_coach at school_id=4
And student_id=99 is at school_id=7 (a different school)
When the coach POSTs { student_id: 99, window_id: 3, ... }
Then the response is 403
And the body is {"error": "Student does not belong to your school."}
```

### 5.5 POST — invalid window_id (not found)

```
Given window_id=99999 does not exist
When a head_coach POSTs { window_id: 99999, ... }
Then the response is 400
And the body is {"error": "Assessment window not found."}
```

### 5.6 POST — window not active

```
Given window_id=5 exists but has status='closed'
When a head_coach POSTs { window_id: 5, ... }
Then the response is 400
And the body is {"error": "Assessment window is not active."}
```

### 5.7 POST — raw_score out of range

```
Given scores: [{ skill_id: 1, raw_score: 6 }]
When a head_coach POSTs
Then the response is 400
And the body is {"error": "Each score must have skill_id (integer) and raw_score (integer 1-5)."}
```

### 5.8 POST — raw_score = 0 (below range)

```
Given scores: [{ skill_id: 1, raw_score: 0 }]
When a head_coach POSTs
Then the response is 400
```

### 5.9 POST — duplicate assessment

```
Given an assessment already exists for student_id=42, window_id=3, assessment_id=11
When the coach POSTs again for the same student+window
Then the response is 409
And the body is {
  "error": "An assessment for this student and window already exists.",
  "existing_assessment_id": 11
}
And no new row is inserted
```

### 5.10 POST — missing required fields

```
When a coach POSTs without student_id
Then the response is 400 and body contains "Missing required field: student_id."

When a coach POSTs without window_id
Then the response is 400 and body contains "Missing required field: window_id."

When a coach POSTs without scores
Then the response is 400 and body contains "Missing required field: scores."

When a coach POSTs with scores = []
Then the response is 400 and body contains "scores must be a non-empty array."
```

### 5.11 POST — unauthenticated

```
Given no session cookie
When POST /api/assessments
Then the response is 401
```

### 5.12 POST — overseer submits for any school in org

```
Given coach_overseer at school_id=4 (org_id=2)
And student_id=50 is at school_id=7 (also org_id=2)
And window_id=3 is active at school_id=7
When the overseer POSTs { student_id: 50, window_id: 3, scores: [...] }
Then the response is 201
```

### 5.13 POST — overseer blocked for student outside org

```
Given coach_overseer at org_id=2
And student_id=200 is at school_id=99 (org_id=9, different org)
When the overseer POSTs { student_id: 200, ... }
Then the response is 403
And the body is {"error": "Student does not belong to a school in your organization."}
```

### 5.14 POST — invalid skill_id

```
Given skill_id=99999 does not exist or has active_status=0
When a head_coach POSTs with that skill_id in scores
Then the response is 400
And the body contains "Invalid or inactive skill_id:"
```

### 5.15 GET — head_coach sees own school only

```
Given head_coach at school_id=4
And two assessments exist: assessment_A at school_id=4, assessment_B at school_id=7
When the coach GETs /api/assessments
Then the response is 200
And assessment_A is in the response
And assessment_B is NOT in the response
```

### 5.16 GET — overseer sees org-wide

```
Given coach_overseer at org_id=2 (school_id=4)
And school_id=7 is in org_id=2, school_id=50 is in org_id=9
And assessments exist at all three schools
When the overseer GETs /api/assessments
Then assessments at school_id=4 and school_id=7 are returned
And the assessment at school_id=50 is NOT returned
```

### 5.17 GET — pagination correct

```
Given a head_coach with 7 assessments at their school
When they GET /api/assessments?per_page=3&page=1
Then the response has at most 3 items
And total >= 7, page=1, per_page=3, pages=ceil(total/3)
And items are ordered assessment_date DESC, assessment_id DESC
```

### 5.18 GET — student_id filter

```
Given a head_coach with assessments for student_A and student_B
When they GET /api/assessments?student_id=<student_A_id>
Then only student_A's assessment is returned
And student_B's assessment is NOT returned
```

### 5.19 GET — window_id filter

```
Given a head_coach with assessments in window 3 and window 5
When they GET /api/assessments?window_id=3
Then only window 3 assessments are returned
```

### 5.20 GET — unauthenticated

```
Given no session cookie
When GET /api/assessments
Then the response is 401
```

---

## 6. Out of Scope (Phase 2D)

- Editing or deleting a submitted assessment
- `benchmark_id` assignment (stored NULL in Phase 2D)
- `program_id` and `session_id` linkage for assessments (stored NULL)
- `student_skill_summary`, `student_domain_summary`, `student_overall_summary` recalculation after assessment submission (reserved for Phase 3A)
- `confidence_rating`, `observed_independence`, `observed_consistency`, `observed_accuracy`, `growth_flag` fields — stored with defaults; not accepted in request body
- Admin-side assessment review workflow
- Parent portal assessment visibility
- Supabase RLS policies

---

## 7. Constraint Matrix

| Dimension | Constraint | Trade-off |
|---|---|---|
| **Data integrity** | One assessment per student per window | Duplicate guard is app-level only; no DB UNIQUE on (student_id, window_id) |
| **Isolation** | head/assistant see only their school's assessments | Matches student data scoping in Phase 2A |
| **Safety** | Student ownership validated before window/skill lookup | Prevents cross-org score injection |
| **Simplicity** | normalized_score = raw_level in Phase 2D | Scoring formula deferred to Phase 3A |
| **Audit** | audit() in transaction, re-raises on failure | FERPA-adjacent: assessment records require audit completeness |
| **Atomicity** | All inserts (assessment + scores + audit) in one commit | Partial writes would leave orphaned score rows |

---

## 8. Test File Skeleton (for tdd-guide)

`tests/test_assessments.py` must cover at minimum:

**POST tests:**
- `test_create_assessment_minimal_success` — 201, one score, audit row, response shape
- `test_create_assessment_full_success` — 201, all fields including assessor_staff_id and notes
- `test_create_assessment_site_coordinator_blocked` — 403
- `test_create_assessment_student_not_at_coaches_school` — 403
- `test_create_assessment_invalid_window_id` — 400 window not found
- `test_create_assessment_window_not_active` — 400 window is closed
- `test_create_assessment_raw_score_too_high` — 400 raw_score=6
- `test_create_assessment_raw_score_too_low` — 400 raw_score=0
- `test_create_assessment_duplicate_returns_409` — 409 with existing_assessment_id
- `test_create_assessment_missing_student_id` — 400
- `test_create_assessment_missing_window_id` — 400
- `test_create_assessment_missing_scores` — 400
- `test_create_assessment_empty_scores_array` — 400
- `test_create_assessment_invalid_skill_id` — 400
- `test_create_assessment_overseer_cross_school_in_org` — 201
- `test_create_assessment_overseer_student_outside_org` — 403
- `test_create_assessment_unauthenticated` — 401

**GET tests:**
- `test_list_assessments_head_coach_sees_own_school` — positive: own school's assessments returned
- `test_list_assessments_head_coach_excludes_other_schools` — negative: other school excluded
- `test_list_assessments_overseer_org_scope` — org-wide, cross-org excluded
- `test_list_assessments_pagination` — total/page/pages correct, order DESC
- `test_list_assessments_student_id_filter` — filters correctly
- `test_list_assessments_window_id_filter` — filters correctly
- `test_list_assessments_unauthenticated` — 401

---

## 9. Approval Gate

**Implementation does NOT begin until this spec is approved.**

To approve: respond "Spec approved — proceed to tdd-guide for Phase 2D."

---

## 10. Schema Notes

Column names used in this spec are taken verbatim from `migrations/001_sqlite_dev.sql`:

**`assessments` table:**
- `assessment_id`, `student_id`, `school_id`, `program_id` (NULL), `session_id` (NULL)
- `window_id`, `assessed_by_staff_id`, `assessment_date`, `assessment_method`
- `overall_assessment_notes`, `created_at`, `deleted_at`

**`assessment_scores` table:**
- `score_id`, `assessment_id`, `student_id`, `skill_id`, `benchmark_id` (NULL)
- `raw_level` (CHECK 1–5), `normalized_score`
- `confidence_rating` (NULL), `observed_independence` (default 1), `observed_consistency` (default 0)
- `observed_accuracy` (default 0), `growth_flag` (default 0)
- `notes`, `created_at`
- UNIQUE `(assessment_id, skill_id)` — DB-level constraint prevents duplicate skills within one assessment

**`assessment_windows` table:**
- `window_id`, `school_id`, `program_id`, `window_name`
- `start_date`, `end_date`, `assessment_focus`
- `status` (default `'upcoming'`), `created_at`

**`skills` table:**
- `skill_id`, `domain_id`, `skill_name`, `grade_band`, `sport_type`
- `skill_description`, `assessment_type`, `active_status`, `created_at`
