# Ufit Motion API Reference

**Base URL:** `/api`
**Auth:** Session-cookie based. All routes require a valid login session. Role restrictions listed per route.
**Content-Type:** `application/json` for all POST/PUT/PATCH bodies.

---

## Conventions

- All timestamps are ISO 8601 UTC strings (`2026-04-19T14:33:00+00:00`)
- All dates are `YYYY-MM-DD` strings
- Error bodies: `{"error": "Human-readable message."}`
- Success bodies always include `"ok": true`
- Pagination params: `?page=1&per_page=20` (max per_page: 100)

---

## Auth Routes

### `POST /api/login`
Log in to any portal. Returns session cookie.

**Body:** `{ "email", "password", "portal" }` — portal: `"coach"` | `"admin"` | `"parent"`

**Response 200:**
```json
{ "ok": true, "user": { "user_id", "role", "first_name", "last_name", "email", "school_id", "school_name" } }
```

**Errors:** 400 missing fields · 401 bad credentials · 403 wrong portal

---

### `POST /api/logout`
Clears session cookie.

**Response 200:** `{ "ok": true }`

---

### `GET /api/me`
Returns the currently authenticated user.

**Roles:** Any authenticated user

**Response 200:** `{ "ok": true, "user": { ...user fields... } }`

**Errors:** 401 unauthenticated

---

## Coach Routes

All coach routes require one of: `head_coach`, `assistant_coach`, `site_coordinator`, `coach_overseer`

---

### `GET /api/my-students`

Return students at the authenticated coach's school. `coach_overseer` sees all students in their org.

**Query params:**
- `grade_level` — filter by grade (string)
- `search` — name search (alphanumeric + spaces/hyphens/apostrophes, max 100 chars)

**Response 200:**
```json
{
  "ok": true,
  "students": [
    {
      "student_id": 12,
      "student_first_name": "Jordan",
      "student_last_name": "Rivera",
      "grade_level": "3",
      "school_id": 4,
      "school_name": "Lincoln Elementary",
      "active_status": true,
      "created_at": "2026-01-15T10:00:00+00:00"
    }
  ],
  "count": 47
}
```

**FERPA:** AUDIT logged on every access.

---

### `POST /api/sessions`

Log a PE session with student attendance. All writes are atomic (sessions + session_staff + student_session_attendance + audit_log).

**Roles:** head_coach · assistant_coach · site_coordinator · coach_overseer

**Body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `school_id` | integer | Yes | Must be within coach's scope |
| `program_id` | integer | Yes | Must be active at school_id |
| `session_date` | string | Yes | YYYY-MM-DD, max 7 days past, not future |
| `start_time` | string | No | HH:MM 24h. If provided, end_time required |
| `end_time` | string | No | HH:MM 24h. Must be after start_time |
| `session_type` | string | No | `regular`\|`makeup`\|`enrichment`\|`assessment`. Default: `regular` |
| `location` | string | No | Max 200 chars |
| `planned_activity` | string | No | Max 500 chars |
| `actual_activity` | string | No | Max 500 chars |
| `student_group_name` | string | No | Max 200 chars |
| `notes` | string | No | Max 1000 chars |
| `student_ids` | integer[] | No | Positive integers, no duplicates, must be active at school_id |

**Response 201:**
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
    "actual_activity": "Locomotor skills",
    "student_group_name": null,
    "session_status": "completed",
    "total_students_present": 5,
    "notes": null,
    "student_ids": [12, 15, 18, 22, 31],
    "created_at": "2026-04-19T14:33:00+00:00"
  }
}
```

**Errors:**
- 400 validation failure (first failing rule returns immediately)
- 403 school outside coach's scope
- 409 duplicate session — includes `"existing_session_id"` in body
- 500 DB error or missing staff_profile

**FERPA:** AUDIT logged. Audit failure rolls back the entire transaction (no session without audit).

---

### `GET /api/sessions`

List sessions within the coach's scope, with pagination.

**Roles:** head_coach · assistant_coach · site_coordinator · coach_overseer

**Scoping:**
- head_coach / assistant_coach → their assigned school only
- site_coordinator → all schools in their region
- coach_overseer → all schools in their org

**Query params:**

| Param | Default | Notes |
|---|---|---|
| `from` | 30 days ago (UTC) | YYYY-MM-DD inclusive lower bound |
| `to` | today (UTC) | YYYY-MM-DD inclusive upper bound |
| `school_id` | (scoped) | site_coordinator and overseer only |
| `page` | 1 | Min 1 |
| `per_page` | 20 | Min 1, max 100 |

**Response 200:**
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

`eod_filed` — true if a non-deleted EOD report exists for this coach, school, and date.

**FERPA:** No audit required — response contains aggregate counts only, no student PII.

---

## EOD Report Routes

*Phase 2B — not yet implemented*

### `POST /api/eod-reports` — stub
### `GET /api/eod-reports` — stub

---

## Incident Routes

*Phase 2C — not yet implemented*

### `POST /api/incidents` — stub
### `GET /api/incidents` — stub

---

## Assessment Routes

*Phase 2D — not yet implemented*

### `POST /api/assessments` — stub
### `GET /api/assessments` — stub

---

*Last updated: 2026-04-19 after Phase 2A commit 40d0f7f*
