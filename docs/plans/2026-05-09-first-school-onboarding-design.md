# First-School Onboarding — Design

**Date:** 2026-05-09
**Status:** Approved, ready for implementation
**Context:** Post-LAUSD-demo. Preparing for actual production go-live with the first real school.
**Build target:** All 10 items below must land before the first school is onboarded.

---

## Decisions (all approved during brainstorm session)

### Q1. Seed-data wipe scope: NUCLEAR
Wipe ALL operational data including Miss A's seeded CEO account. Keep only static reference data:
- Skill catalog: `skill_domains`, `skills`, `benchmarks`
- System config: `app_settings`, `role_permissions`
- Everything else (`organizations`, `regions`, `contracts`, `schools`, `users`, `parents`, `students`, `programs`, `sessions`, `attendance`, `assessments`, `assessment_scores`, `behavior_observations`, `eod_reports`, `incident_reports`, `coach_observations`, `school_reports`, all summary tables, `notifications`, `audit_log`, `principal_satisfaction_surveys`, `coach_evaluations`, `coach_performance_snapshots`, `staff_profiles`, `staff_assignments`) gets truncated.

### Q2. First super admin: atomic via wipe script
Wipe script accepts `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_FIRST`, `SUPER_ADMIN_LAST` env vars. Creates the first CEO in the same transaction as the wipe. No window of "zero admins". User provides the credentials at runtime.

### Q3. Email transport: Gmail SMTP via operations@ufitonline.net
- No DNS changes required (Google Workspace handles SPF/DKIM)
- App password from Google → `GMAIL_APP_PASSWORD` env var
- `app/email.py` swaps from `httpx` (Resend) → `smtplib` (Gmail)
- 2,000 emails/day limit is far above realistic onboarding volume
- Sender shows as `Ufit Motion <operations@ufitonline.net>` — replies route to real ops inbox
- Same graceful no-op pattern: missing creds → log to stdout, no crash

### Q4. Multi-school coach assignment with hybrid picker
- `staff_assignments` already supports multi-school (no schema change)
- `/api/auth/login` returns ALL active assignments
- New endpoint `POST /api/auth/select-school` stores chosen school in session
- New "Where are you working today?" screen between login and coach dashboard (when N>1 assignments)
- Top-nav school-switcher chip on coach pages for mid-session switching
- Add Coach modal: school field becomes multi-select

### Q5. Coach onboarding: three converging paths
- **Path 1 (existing):** single coach added via Add Coach modal, system emails invite
- **Path 2 (NEW):** bulk roster invite — admin pastes/uploads `(first, last, email, role)` rows, system creates pending users + emails each
- **Path 3 (NEW):** school invite code — `schools.coach_invite_code` (e.g. `LCN-X7M9-2026`); coach goes to Coach Portal → "Sign up with school code" → enters code + their info → backend creates pending user + emails invite link
- All three paths converge at the same email → set-password → coach portal flow
- Per-row role override in Path 2 (with "default role for all" convenience)
- Admin can edit any coach's role + school assignments via new Edit Coach modal
- Permission rules: admin can change all roles except CEO/admin; CEO can change anyone

### Q7. Walkthrough HTML video: 16 scenes, ~10 min auto-play
Single self-contained `docs/walkthrough.html` mirroring the format of existing `demo.html` / `demo-portrait.html`. Mouse cursor visible, captioned, press-play, no audio. Section bookmarks sidebar.

Scenes:
1. Cold-load → portal selector
2. Admin login → dashboard
3. Settings tour
4. Add school
4a. Multi-school coach picker
5. Bulk add coaches with role mix
6. Import students CSV
7. Coach self-registration via school code
8. Coach files EOD
8a. Coach assessment scoring
9. Coach files incident
9a. Principal portal review
10. Parent self-registration
10a. Parent views child's progress
11. Admin CSV report export
12. Help / support

---

## Build queue (must complete in order before go-live)

### Phase A — Foundation (operational/infrastructure)
1. **Wipe script + first super admin** (Q1+Q2)
   - `scripts/production_wipe.py` — TRUNCATE listed tables CASCADE, INSERT first CEO from env vars
   - Idempotent guard: refuse to run if `APP_ENV != "production"` AND user doesn't pass `--allow-non-prod`
2. **Email transport: Gmail SMTP** (Q3)
   - Rewrite `app/email.py` to use `smtplib` with `GMAIL_USER` + `GMAIL_APP_PASSWORD`
   - Keep existing `send_invite_email()` and `send_password_reset_email()` signatures
   - Document Render env vars needed
3. **Privacy Policy + Terms of Service pages** (gap #1)
   - New static templates `templates/privacy.html` + `templates/terms.html`
   - Footer links from login + every authenticated page
   - Boilerplate FERPA-compliant copy (user reviews + customizes)
4. **Help/Support modal** (gap #2)
   - "Help" button in top-nav opens modal with: support email, known issues link, feedback form
   - Form posts to a new `/api/feedback` endpoint that emails Miss A's inbox
5. **Backup restore drill + runbook** (gap #3, operational)
   - User runs Supabase point-in-time-restore to a staging project
   - Document the steps in `docs/runbooks/backup-restore.md`
   - This is a one-time human task, not a code change

### Phase B — Coach onboarding (Q4 + Q5)
6. **Multi-school coach assignment + picker** (Q4)
   - Backend: `/api/auth/login` returns assignments[]; new `/api/auth/select-school` endpoint
   - Frontend: school-picker screen + top-nav switcher
   - Migration: no schema change required
7. **Bulk coach invite (Path 2)** (Q5 part 2)
   - New admin UI: "Invite Coaches in Bulk" modal with paste/CSV input + per-row role + default-role dropdown
   - New endpoint: `POST /api/admin/coaches/bulk-invite`
   - Reuses existing invite token + email flow
8. **School invite code (Path 3)** (Q5 part 3)
   - Migration `step16_school_coach_invite_code.sql`: `schools.coach_invite_code TEXT UNIQUE`, `schools.coach_invite_code_expires_at TIMESTAMPTZ`
   - Backfill: generate codes for any existing schools
   - Admin UI: school detail page shows code + Copy + Regenerate buttons
   - New public endpoint: `POST /api/auth/coach-register` (validates code → creates pending user → sends invite email)
   - New frontend: Coach Portal → "Sign up with school code" form
9. **Edit Coach role + school modal** (Q5 part 4)
   - New endpoint: `PATCH /api/admin/users/<id>/role`
   - Frontend: Edit button on coaches table → modal with role + multi-school
   - Audit logging: `role_changed` action with old → new

### Phase C — UX polish
10. **Reporting exports (CSV / PDF)** (gap #5)
    - CSV export buttons on schools/coaches/students tables (server-side `Content-Type: text/csv`)
    - PDF export on student progress detail page (server-side render via `weasyprint` or similar; alternative: server-rendered HTML the user prints to PDF)
11. **Audit log viewer** (gap #6)
    - New admin route: `/api/admin/audit-log` with filters (user, action, table, date range)
    - New admin page: `/audit` showing paginated log entries
    - CEO/admin only
12. **Empty-state onboarding cards** (gap #7)
    - Replace generic "No coaches yet" / "No students yet" with checklist cards
    - Show: ✓ Add coaches → ✓ Import students → ✓ Schedule first session
    - Cards link to the relevant action
13. **Forgot-password covers pending users** (gap #8)
    - Relax `forgot-password` SELECT to also accept `password_hash IS NULL` rows
    - Pending user gets a fresh invite link (same flow as Path 1)
14. **Notifications coverage audit** (gap #9)
    - Audit every state-changing route: does it write a `notifications` row when appropriate?
    - Specifically: incident filed → admin notified; coach pending invite expires soon → admin notified; parent registers → admin notified
15. **Schools page principal status indicator** (gap #10)
    - Mirror the coach pending-invite badge pattern on the schools table
    - "Principal: Sarah Smith ✓ Active" or "Principal: Jane Doe ⏱ Pending Invite [Resend]"

### Phase D — Walkthrough HTML
16. **`docs/walkthrough.html`** (Q7)
    - Single-file animated walkthrough, 16 scenes, ~10 min
    - Press-play, captioned, mouse-cursor visible
    - Section bookmarks sidebar
    - Mirrors existing `demo.html` format

---

## Operational gaps (non-code, user must address before go-live)

These are NOT in the build queue but are go-live blockers:

- **Signed contract / Data Processing Agreement** with the first school district (handled outside this app — Ufit's existing sales process)
- **FERPA Designation of School Official** form executed (handled outside this app)
- **Liability insurance** verified — most districts require contractor coverage (handled outside this app)

**Explicitly NOT a gap:**
- **Pricing/billing** — Ufit charges schools through their existing process, not via this app. The app is a service-delivery tool only; school staff log in with credentials we provision.
- **SLA documentation** — informal expectations are fine for the first school; can formalize later.
- **Privacy Policy attorney review** — no legal team access. Phase A item 3 will generate a standards-based FERPA-aware Privacy Policy + Terms of Service. We iterate as feedback comes in. The policy is required for iOS App Store submission (later milestone) and basic legitimacy, not for day-1 LAUSD-style onboarding.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Wipe runs against the wrong database | Script refuses to run if `APP_ENV != "production"` without explicit override flag |
| Gmail SMTP gets rate-limited (2,000/day) | Volume estimate is ~30 emails/school. Render env logging captures rejected sends. |
| Coach invite code leaks publicly | Regenerate button + audit log; new code immediately invalidates old |
| Bulk invite has malformed rows (typos, missing email) | Backend validates per-row; frontend surfaces row-level errors instead of failing the whole batch |
| Multi-school session race | School selection writes to session before any school-scoped query; existing endpoints continue to read `session.current_school_id` |
| Edit Coach role on yourself | Backend explicitly blocks self-role-changes for non-CEO actors |

---

## Out of scope (deferred indefinitely or until specifically requested)

- SSO (Google / Microsoft) — first school unlikely to require
- 2FA — defer until district security team flags it
- Custom branded subdomain per district
- Mobile native app
- District-level rollup dashboards (only have one district)
- Real-time notifications via WebSocket (polling is fine at this scale)

---

## Success criteria for this design

- All 16 build items completed and shipped
- Operational gaps signed off by user/boss
- First school's principal logs in via invite email and successfully reviews their first EOD report
- First parent self-registers and sees their child's progress
- Walkthrough HTML video covers all 16 scenes and plays in <12 minutes total
