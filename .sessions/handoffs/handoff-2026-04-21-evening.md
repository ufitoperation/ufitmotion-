# Session Handoff — 2026-04-21 (Evening)

## Status
- **Branch**: main
- **Commits this session**: 3 (`ab08737`, `5b432ff`)
- **Uncommitted changes**: none — working tree clean
- **Tests**: 270 passing, 2 pre-existing Python 3.9/scrypt errors in test_auth.py
- **Remote**: fully pushed — origin/main at `5b432ff`

---

## What's Done

### This session:
- **`migrations/002_seed_skills.sql`** — rewrote for SQLite/Postgres compatibility using UNION ALL subqueries; applied to local DB; committed + pushed. DB now has 3 domains, 26 skills, 130 benchmarks.
- **`docs/requirements-external.md`** — full product spec (scoring formulas, 24 tables, grade-band weighting, coach observation rubric, reporting outputs) extracted from the external requirements document. This is the SOURCE OF TRUTH for all scoring and reporting work.
- **`CLAUDE.md`** — session start protocol now requires reading `docs/requirements-external.md` as step 3, so every future session is anchored to the spec. Also updated hosting from Railway → Render.

---

## What's In Progress
- Nothing — session ended cleanly

---

## Gap Analysis vs. docs/requirements-external.md

### Schema gaps (minor — schema is ~95% complete):
| Spec field | Table | Status |
|---|---|---|
| `contract_id` | schools | Missing — `contracts` table exists separately; schools not linked by FK |
| `linked_staff_id`, `linked_parent_id` | users | Missing — reverse lookup works via staff_profiles.user_id / parents.user_id, but spec calls for direct FK on users |
| `coach_lead_staff_id` | sessions | Replaced by `session_staff` table with a `role` column — architecturally better, not a regression |
| `scoring_notes` | benchmarks | Present in schema ✓ |
| `observed_independence/consistency/accuracy` | assessment_scores | Present ✓ |

### Scoring engine — COMPLETELY MISSING (biggest gap):
The spec defines a full calculation chain. None of it is implemented as backend logic:

1. **Normalized score auto-calculation** — `normalized_score` is stored in `assessment_scores` but is entered by the client. Must be server-computed as `raw_level * 20`. Client should never be trusted to calculate this.
2. **student_skill_summary not populated** — table exists, nothing writes to it. Must be updated on every `POST /api/assessments`.
3. **student_domain_summary not populated** — same; must be recalculated after each assessment.
4. **student_overall_summary not populated** — same; grade-band-weighted formula (K-2: 70/30, 3-5: 60/25/15, 6-8: 45/30/25) not implemented anywhere.
5. **Growth flag** — `growth_flag` in assessment_scores exists but nothing sets it; should be 1 when current normalized_score > baseline.
6. **Performance band** — `performance_band` in student_skill_summary and `readiness_band` in student_overall_summary exist but never assigned. Spec bands: 20-39=Emerging, 40-59=Developing, 60-79=On Track, 80-89=Proficient, 90-100=Advanced.

### Missing routes (features entirely absent):
| Feature | Spec ref | Status |
|---|---|---|
| `POST/GET /api/behavior-observations` | TABLE 17 | No routes — coaches have no way to submit session-level SEL scores |
| `POST/GET /api/coach-observations` | TABLE 20 | No routes — evaluators (head_coach, admin) can't score coach performance |
| `POST/GET /api/assessment-windows` | TABLE 14 | No CRUD — coaches must submit assessments without windows; blocks proper baseline/progress/reporting cycles |
| PDF generation for school reports | TABLE 21 | `school_reports` table has `pdf_link` but nothing generates PDFs |
| `GET/POST /api/students` (admin) | TABLE 7 | Stub in admin_routes.py:555 |
| `GET/POST /api/programs` (admin) | TABLE 8 | Stub in admin_routes.py:590 |
| `DELETE /api/schools/<id>` | — | Stub at admin_routes.py:320 |
| `DELETE /api/users/<id>` | — | Stub at admin_routes.py:543 |

### UX issues vs. spec Section 15:
- Observation tags (independent/needs_prompt/inconsistent/strong_control/low_confidence/gameplay_transfer_observed) must be a **dropdown**, not a free-text notes field. The assessment modal in `static/app.js` currently uses an optional textarea. Must add a required tag selector to each skill score row.

### Two SEL pathways (needs design decision):
The spec has:
- `assessment_scores` with SEL skills (formal benchmarked assessment, happens at assessment windows)
- `behavior_observations` TABLE 17 (lightweight session-by-session tracking — 6 scores, no benchmark context)

Both are intentional and serve different purposes. Current app only has assessment_scores for SEL. Behavior observations need their own coach-facing form.

### EOD + Compliance:
- `submitted_on_time` field in EOD reports exists but nothing calculates it — no cutoff time logic
- Compliance formula in admin_routes.py ~line 701 counts (staff_id, session_date) but should be (staff_id, school_id, session_date) for multi-school coaches — open audit finding

---

## What's Pending (prioritized)

### P0 — Scoring engine (core product value, currently a black hole):
1. **Server-side normalized_score** — when coach submits an assessment, compute `raw_level * 20` server-side; don't accept it from client
2. **student_skill_summary trigger** — after each assessment, upsert student_skill_summary: set baseline_score if null, update current_score/highest_score/latest_date/growth_amount/performance_band
3. **student_domain_summary trigger** — recalculate domain average after each skill update
4. **student_overall_summary trigger** — apply grade-band weighting after each domain update
5. **GET /api/students/<id>/progress** — return skill/domain/overall scores for admin+principal+parent views

### P1 — Missing coach workflows:
6. **Behavior observations** — `POST /api/behavior-observations` (coach submits 6 SEL scores per session), `GET /api/behavior-observations` (retrieve by student/session)
7. **Assessment windows** — `POST/GET/PATCH /api/assessment-windows` (admin creates; coaches select when assessing)
8. **Observation tags on assessment scores** — add required `observation_tag` field (enum) to assessment score submission form and API

### P2 — Admin/evaluator tools:
9. **Coach observations** — `POST/GET /api/coach-observations` (evaluator scores a coach on 6 dimensions)
10. **Implement GET/POST /api/students** (admin_routes.py:555 stub)
11. **Implement GET/POST /api/programs** (admin_routes.py:590 stub)
12. **EOD compliance formula fix** — add school_id to compliance grouping (admin_routes.py ~line 701)

### P3 — Deployment:
13. **Supabase migration** — apply `migrations/001_sqlite_dev.sql` + `migrations/002_seed_skills.sql` + `migrations/004_rls_policies.sql` to Supabase `adsewsosdnufmcjxinkj`; note: `002_seed_skills.sql` uses `INSERT OR IGNORE` (SQLite syntax) — convert to `INSERT ... ON CONFLICT DO NOTHING` for Postgres, or run manually via Supabase SQL editor
14. **Deploy to Render** — same Procfile (`web: gunicorn "app:create_app()"`); env vars: `DATABASE_URL`, `UFIT_SECRET_KEY`, `APP_ENV=production`

### P4 — High-priority audit findings still open:
15. **Rate limiting** — Flask-Limiter on login/forgot-password/reset-password
16. **coach_overseer org scoping** — 4 admin routes at admin_routes.py:755,820,871,926 return unscoped data
17. **Global error handler** — add `@app.errorhandler(Exception)` to `app/__init__.py`

### P5 — Medium priority:
18. **Reports page** — admin portal still shows renderComingSoon; PDF generation for school_reports
19. **Demo seed data** — 3 schools, 10 coaches, 50 students for client demo
20. **Delete endpoints** — DELETE /api/schools, DELETE /api/users

### Catch-up agents (technical debt):
- `security-reviewer` — not run on auth bug fixes or change-password endpoint
- `python-reviewer` — not run on auth_routes.py, admin_routes.py changes
- `api-design` — not run on new endpoints from session 2026-04-21

---

## Key Decisions Made

- **`(VALUES ...) AS v()` → UNION ALL** — SQLite doesn't support table-valued VALUES in FROM; UNION ALL is portable
- **Requirements doc locked into CLAUDE.md** — `docs/requirements-external.md` now in session start protocol; every future session reads it
- **session_staff table preferred over coach_lead_staff_id** — architecturally cleaner, handles multi-coach sessions; spec's flat column approach not needed

---

## Files Touched This Session

- `migrations/002_seed_skills.sql` — SQLite-compatible rewrite; seeds 3 domains, 26 skills, 130 benchmarks
- `docs/requirements-external.md` — NEW: full product spec as markdown
- `CLAUDE.md` — session start protocol + hosting fix

---

## Gotchas for Next Session

- **Server start**: `APP_ENV=development UFIT_SECRET_KEY=local-dev-key .venv/bin/flask --app wsgi.py run --port 5055`
- **Python 3.9 scrypt errors** — 2 test_auth.py errors are pre-existing; not regressions
- **GitHub push** — `gh auth token --user ufitoperation`; embed in remote URL temporarily
- **SQLite locally, Postgres in prod** — do NOT set DATABASE_URL for local dev
- **Scoring tables are empty** — student_skill_summary, student_domain_summary, student_overall_summary are schema-only; no routes write to them yet
- **Behavior observations and coach observations have no routes** — both tables exist in schema but are completely unwired

---

## Open Audit Findings

| Severity | Finding | Location | Status |
|----------|---------|----------|--------|
| HIGH | No rate limiting on auth endpoints | auth_routes.py | Open |
| HIGH | coach_overseer sees all-org data on 4 admin routes | admin_routes.py:755,820,871,926 | Open |
| MEDIUM | EOD compliance formula ignores school per coach | admin_routes.py ~line 701 | Open |
| MEDIUM | Global error handler missing | app/__init__.py | Open |
| LOW | No audit log for logout / notification reads | auth_routes.py:127, shared_routes.py:149 | Open |
| LOW | No DB indexes on school_id, student_id, session_date | Schema | Add before prod |

---

## Resume Command

> Continue on `main`. Requirements doc is now `docs/requirements-external.md` — read it. Skills are seeded (26 skills, 130 benchmarks, `ab08737`). The biggest unbuilt feature is the **scoring engine**: normalized_score must be server-computed (Level * 20), and student_skill_summary/domain_summary/overall_summary tables are never populated. Per AGENTS.md, next task needs `planner` → `python-reviewer` → `code-reviewer` → `smart-commit`. Recommend starting with P0: scoring engine, or P3: Render/Supabase deployment to go live.
