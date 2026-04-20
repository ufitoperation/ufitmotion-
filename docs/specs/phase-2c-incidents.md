# Phase 2C — Incident Reporting
**Status:** v1 — approved for implementation  
**Routes:** `POST /api/incidents` · `GET /api/incidents`

---

## 1. Table Reference

`incident_reports`

| Column | Type | Notes |
|---|---|---|
| incident_id | PK | auto |
| school_id | FK schools | required |
| session_id | FK sessions | optional |
| report_date | TEXT (YYYY-MM-DD) | required |
| reported_by_staff_id | FK staff_profiles | set from session |
| student_id | FK students | optional |
| incident_type | TEXT | 'injury','behavior','property','medical','safety','other' |
| severity_level | TEXT | 'low','medium','high','critical' |
| description | TEXT | required, max 2000 |
| immediate_action_taken | TEXT | required, max 1000 |
| school_notified | INTEGER (bool) | default 0 |
| family_notified | INTEGER (bool) | default 0 |
| escalated_to_supervisor | INTEGER (bool) | default 0 |
| status | TEXT | always 'open' on create |
| resolution_notes | TEXT | optional, max 1000 |
| admin_response | TEXT | admin-only, read-only from this API |
| acknowledged_at | TEXT | admin-only, read-only |
| acknowledged_by | FK users | admin-only, read-only |
| created_at | TEXT | auto |
| deleted_at | TEXT | soft-delete |

---

## 2. Role Access Matrix

| Role | POST | GET |
|---|---|---|
| head_coach | own school | own reports, own school |
| assistant_coach | own school | own reports, own school |
| site_coordinator | **403** | assigned schools (all staff) |
| coach_overseer | **403** | full org |

---

## 3. POST /api/incidents

### 3.1 Request Body

```json
{
  "school_id": 1,
  "report_date": "2026-04-20",
  "incident_type": "injury",
  "severity_level": "high",
  "description": "Student fell during relay race and scraped knee.",
  "immediate_action_taken": "Applied first aid. Student sat out rest of session.",
  "session_id": 42,
  "student_id": 7,
  "school_notified": true,
  "family_notified": false,
  "escalated_to_supervisor": false,
  "resolution_notes": "Parent picked up student early."
}
```

### 3.2 Validation Rules (in order)

| # | Check | Response |
|---|---|---|
| 1 | Role is site_coordinator | 403 `"Incident reports must be filed by a coach."` |
| 2 | Role is coach_overseer | 403 `"Incident reports must be filed by a coach."` |
| 3 | `school_id` missing or not a positive integer | 400 `"school_id is required and must be a positive integer."` |
| 4 | `report_date` missing or not YYYY-MM-DD | 400 `"report_date is required in YYYY-MM-DD format."` |
| 5 | `report_date` is in the future | 400 `"report_date cannot be in the future."` |
| 6 | `report_date` is more than 7 days in the past | 400 `"report_date cannot be more than 7 days in the past."` |
| 7 | `incident_type` missing or not in allowed set | 400 `"incident_type must be one of: injury, behavior, property, medical, safety, other."` |
| 8 | `severity_level` missing or not in allowed set | 400 `"severity_level must be one of: low, medium, high, critical."` |
| 9 | `description` missing or empty string | 400 `"description is required."` |
| 10 | `description` length > 2000 | 400 `"description cannot exceed 2000 characters."` |
| 11 | `immediate_action_taken` missing or empty | 400 `"immediate_action_taken is required."` |
| 12 | `immediate_action_taken` length > 1000 | 400 `"immediate_action_taken cannot exceed 1000 characters."` |
| 13 | `resolution_notes` present and length > 1000 | 400 `"resolution_notes cannot exceed 1000 characters."` |
| 14 | `school_notified`, `family_notified`, `escalated_to_supervisor` present but not JSON boolean | 400 `"<field> must be a boolean."` |
| 15 | head_coach/assistant_coach: school_id ≠ their assigned school | 403 `"You are not assigned to this school."` |
| 16 | `session_id` provided: no matching row in sessions with that school_id and session_date, or soft-deleted | 400 `"session_id does not match a valid session for this school and date."` |
| 17 | `student_id` provided: student not found or does not belong to this school | 400 `"student_id does not belong to this school."` |

### 3.3 Write Logic

```
INSERT INTO incident_reports (
    school_id, session_id, report_date, reported_by_staff_id,
    student_id, incident_type, severity_level, description,
    immediate_action_taken, school_notified, family_notified,
    escalated_to_supervisor, status, resolution_notes, created_at
) VALUES (...)
```

- `reported_by_staff_id` = `current_user().staff_id`
- `status` = `'open'` always
- `admin_response`, `acknowledged_at`, `acknowledged_by` = NULL (admin-only fields)

**Critical incident notification** — if `severity_level == 'critical'`, after INSERT (within same transaction), INSERT one notification row per user with role IN `('ceo', 'admin', 'coach_overseer')` from the same organization:

```sql
INSERT INTO notifications (user_id, title, body, notification_type, related_table, related_id, created_at)
SELECT u.user_id,
       'Critical Incident Filed',
       'A critical incident was filed at ' || s.school_name || ' on ' || :report_date,
       'incident',
       'incident_reports',
       :incident_id,
       :now
FROM users u
JOIN staff_profiles sp ON sp.user_id = u.user_id
JOIN schools sc ON sc.school_id = :school_id
WHERE u.role IN ('ceo', 'admin', 'coach_overseer')
  AND sp.organization_id = sc.organization_id
  AND u.deleted_at IS NULL
```

**Audit:** call `audit(conn, user_id, 'INSERT', 'incident_reports', incident_id, None, new_values)` within the same transaction.

### 3.4 Success Response — 201

```json
{
  "ok": true,
  "incident": {
    "incident_id": 1,
    "school_id": 1,
    "school_name": "Lincoln Elementary",
    "staff_id": 3,
    "coach_name": "Jane Smith",
    "session_id": 42,
    "student_id": 7,
    "report_date": "2026-04-20",
    "incident_type": "injury",
    "severity_level": "high",
    "description": "...",
    "immediate_action_taken": "...",
    "school_notified": true,
    "family_notified": false,
    "escalated_to_supervisor": false,
    "status": "open",
    "resolution_notes": null,
    "created_at": "2026-04-20T..."
  }
}
```

---

## 4. GET /api/incidents

### 4.1 Query Parameters

| Param | Type | Default | Notes |
|---|---|---|---|
| `from` | YYYY-MM-DD | none | report_date ≥ from |
| `to` | YYYY-MM-DD | none | report_date ≤ to |
| `status` | text | none | open / under_review / resolved / closed |
| `severity` | text | none | low / medium / high / critical |
| `school_id` | int | none | overseer only (ignored for coach/sc) |
| `page` | int | 1 | non-integer → 400 `"page must be a positive integer."` |
| `per_page` | int | 20 | non-integer → 400; capped at 100 |

### 4.2 Role Scoping

| Role | WHERE clause additions |
|---|---|
| head_coach | `ir.reported_by_staff_id = :staff_id AND ir.school_id = :school_id` |
| assistant_coach | `ir.reported_by_staff_id = :staff_id AND ir.school_id = :school_id` |
| site_coordinator | `ir.school_id IN (SELECT school_id FROM staff_assignments WHERE staff_id = :staff_id AND active = 1)` |
| coach_overseer | `sc.organization_id = :org_id` (JOIN schools sc) |

All roles: `ir.deleted_at IS NULL`

### 4.3 Success Response — 200

```json
{
  "ok": true,
  "total": 5,
  "page": 1,
  "per_page": 20,
  "incidents": [...]
}
```

Each incident object matches the POST 201 response fields.

---

## 5. Serializer Fields

`serialize_incident(row)` returns:

```
incident_id, school_id, school_name, staff_id, coach_name,
session_id, student_id, student_name,
report_date, incident_type, severity_level, description,
immediate_action_taken, resolution_notes, status, created_at
```

Boolean conversions (SQLite 0/1 → Python bool):
```
school_notified, family_notified, escalated_to_supervisor
```

Admin-only fields (`admin_response`, `acknowledged_at`, `acknowledged_by`) are **never returned** from this API.

---

## 6. Audit Log

| Action | Trigger |
|---|---|
| INSERT | POST /api/incidents — records new_values |

---

## 7. Changelog

| Version | Date | Change |
|---|---|---|
| v1 | 2026-04-20 | Initial spec |
