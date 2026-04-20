# Implementation Plan — Ufit Motion

## Overview
30-day build across 5 phases. This plan covers Week 1-2 (foundation) in detail. Weeks 3-5 are outlined at phase level.

## Week 1-2: Database + Auth + Core Tables ($1,500 milestone)

### Phase 1A: Database Schema (COMPLETE)
**Status: Done** — migrations/001_initial_schema.sql written with all 32 tables.

Verification checklist (client checks both):
- [ ] All 32 tables visible in Supabase dashboard
- [ ] All foreign keys valid (no errors on apply)
- [ ] RLS enabled on all tables
- [ ] Seed data present (skill_domains, role_permissions, app_settings)

**Agent: architect**

### Phase 1B: Flask App Structure (COMPLETE)
**Status: Done** — app factory, config, database abstraction, auth utilities written.

**Agent: planner**

### Phase 1C: Auth System — All 9 Roles (IN PROGRESS)
1. **Implement login for all 3 portals** (File: app/routes/auth_routes.py)
   - Action: Portal → role mapping, session creation, serialize user
   - Agent: inline
   - Status: Skeleton written, needs testing

2. **Password reset flow** (File: app/routes/auth_routes.py)
   - Action: Token generation, expiry check, password update
   - Agent: security-reviewer validates
   - Status: Skeleton written

3. **Session validation** (File: app/auth.py)
   - Action: current_user() query with soft-delete filter
   - Agent: inline

### Phase 1D: Frontend Login + Dashboard
1. **Login screen** (File: static/app.js)
   - Action: Portal selector, form, API call, error handling
   - Status: Complete

2. **Dashboard shell** (File: static/app.js)
   - Action: Sidebar, top nav, stat cards, role-aware nav
   - Status: Complete

3. **Design system** (File: static/styles.css)
   - Action: Blue/yellow/white tokens, all components
   - Status: Complete
   - **Agent: ui-designer** for any screen-level polish

### Phase 1E: Apply Migration to Supabase (TODO)
1. Get DATABASE_URL from Supabase project settings
2. Run: `psql "$DATABASE_URL" -f migrations/001_initial_schema.sql`
3. Verify in Supabase dashboard: 32 tables present
4. Set DATABASE_URL in Railway environment variables
5. Push to GitHub → auto-deploy on Railway

**Agent: doc-updater** to update DEPLOYMENT.md after this step

### Phase 1F: FERPA + Security Review (QUEUED)
- Run security-review skill against current codebase
- Document FERPA compliance gaps
- Add missing protections before client demo
**Agent: security-reviewer**

---

## Week 2-3: Full Coach App ($1,000 milestone)

### Phase 2A: Session Logging — COMPLETE ✓
**Status: Done** — POST /api/sessions + GET /api/sessions fully implemented, 32/32 tests green.

- POST /api/sessions — full implementation (18-rule validation, atomic 4-table transaction, FERPA audit)
- GET /api/sessions — paginated, role-scoped (school/region/org), eod_filed flag, N+1-free
- Student attendance recording (student_session_attendance, all default to 'present')
- Coach can select students from their school roster
- Reviews complete: python-reviewer, code-reviewer, security-reviewer, api-design

Open notes (non-blocking, pre-production):
- Rate limiting on POST /api/sessions (HIGH — security-reviewer)
- 201 response should include Location header (LOW — api-design)
- EOD bulk query should add date-range bounds for large histories (MEDIUM — code-reviewer)

**Agent: spec-writer → tdd-guide → python-reviewer → code-reviewer → security-reviewer → api-design**

### Phase 2B: EOD Reports
- Full EOD form: activities, engagement, behavior, incidents flag
- Submit-on-time tracking
- Admin notification on EOD submission
**Agent: planner**

### Phase 2C: Incident Reporting
- Full incident form with severity levels
- Notification to admin on critical incidents
- Admin acknowledge flow
**Agent: security-reviewer** validates data handling

### Phase 2D: Assessments
- Skill selection UI (domain → skill → level 1-5)
- Assessment score entry per student
- student_skill_summary auto-update trigger
**Agent: ui-designer** for assessment entry screen

---

## Week 3-4: Admin Dashboard + Automation + Hubspot ($1,000 milestone)

### Phase 3A: Admin Dashboard
- Cross-school stats
- Coach compliance (EOD completion rate)
- Incident trends
- Student growth summary

### Phase 3B: RLS Policies
- Write and test Supabase RLS policies
- Coach cannot see other schools
- Parent can only see own student

### Phase 3C: Report Generation
- PDF school reports via Supabase Storage
- Hubspot contact sync for school principals
- Automated EOD compliance alerts

---

## Week 4-5: Testing + Deployment + Demo ($1,000 milestone)

### Phase 4A: Test Suite Expansion
- Integration tests for all API routes
- RLS policy tests (cross-org isolation)
- Assessment scoring accuracy tests

### Phase 4B: Performance
- Indexes verified with EXPLAIN ANALYZE
- Page load < 2s on slow 4G

### Phase 4C: Demo Preparation
- Seed realistic demo data (3 schools, 10 coaches, 50 students)
- Demo script for client walkthrough
- Loom recording of all 3 portals

## Done-Gate Checklist (Week 1-2 Payout)
- [ ] 32 tables in Supabase (client verifies in dashboard)
- [ ] Live URL accessible (Railway deploy)
- [ ] Admin portal login works
- [ ] Coach portal login works
- [ ] Staff/Parent portal login shows correct dashboard
- [ ] FERPA security review complete, critical issues resolved
- [ ] Tests pass (pytest output shown to client)
- [ ] GitHub repo has all code pushed
