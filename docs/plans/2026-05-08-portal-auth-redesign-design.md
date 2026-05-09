# Portal Auth Redesign — Design

**Date:** 2026-05-08
**Status:** Approved, ready for implementation
**Demo deadline:** 2026-05-09 (boss demonstration)

---

## Problem

The current login screen has 3 portal buttons (Admin, Coach, Staff/Parent) that all submit to the same form. Critical gaps:

1. No way for a parent to create their own account — they must be manually created by an admin
2. Adding a school/coach in the admin UI creates a user row but doesn't deliver login credentials to that user
3. No visible distinction between active and pending accounts in the admin user list
4. No CEO-level "super admin" account for Miss A (the founder) provisioned in seed data
5. The Staff/Parent shared portal is confusing — principals and parents have nothing in common

## Goals

Build a complete, demo-ready auth flow that works without seed data:
- 4 distinct portals on the login screen
- Admin-only account creation with auto-sent email invites for staff
- Parent self-registration gated by student ID verification
- Auto-create logins when admin adds schools or coaches
- HubSpot sync for parent registrations
- Hardened CEO seed account for the founder

## Non-Goals

- Self-registration for coaches or principals (admin-only creation)
- Password reset flow improvements (existing flow is sufficient)
- Multi-factor authentication
- SSO integration

---

## Section 1: Portal Structure

The login screen becomes a full-page portal selector with 4 cards (2×2 grid). Clicking a card expands a login form inline beneath it (Option C from brainstorm — no page transition).

| Card | Label | Roles accepted |
|------|-------|----------------|
| 🏢 | Admin | ceo, admin, coach_overseer, site_coordinator |
| 🏃 | Coach | head_coach, assistant_coach |
| 🏫 | Organization | principal, school_staff |
| 👨‍👩‍👧 | Parent | parent |

The Parent card shows a "New here? Create Account" link below the sign-in form. All other portals are login-only.

## Section 2: Admin Creates Account → Email Invite Flow

When an admin creates a school (with principal), a coach, or any other staff user:

1. User row created with `active_status = FALSE`, `password_hash = NULL`
2. One-time invite token generated (`password_reset_token`, 7-day expiry)
3. Email sent with "Set your password" link → `/set-password?token=<token>`
4. User clicks link, sets password → `active_status = TRUE`
5. Admin Users list shows status badge: **Pending invite** (orange) or **Active** (green)
6. Pending rows show a **Resend Invite** button

**Demo-mode degradation:** If the email API key is not configured, the system skips the actual email send (logs a warning, like the HubSpot pattern) but the UI flow with badges and Resend buttons works correctly. Tomorrow's API key addition turns email send-out on without code changes.

The backend already has `app/email/send_invite_email()` and `/api/admin/users/<id>/send-invite`. Wiring needed:
- Auto-call `send_invite_email` from `POST /api/users` and `POST /api/schools` (when principal email present)
- Add `account_status` derived field to user list responses (Pending vs Active)
- Frontend: status badge in user row + Resend Invite button
- Frontend: `/set-password` page (consume token, set password, redirect to login)

## Section 3: Parent Self-Registration

Parent portal card shows "New here? Create Account" link. Clicking swaps form for a 2-step flow.

**Step 1 — Verify Student**
Inputs: Student First Name, Student Last Name, Student ID
Backend: query `students` table for exact match (active, not deleted, matching school_id derived from ID).
- Found → store verified `student_id` in session, proceed to step 2
- Not found → show "We couldn't find that student. Please check the spelling and ID, or contact your school."

**Step 2 — Create Profile**
Inputs: First Name, Last Name, Email, Phone, Password (with confirm), Relationship (Mother/Father/Guardian/Other)

On submit:
1. Create `users` row with role=`parent`, `active_status=TRUE` (auto-approved — student ID is the gate)
2. Create `parents` row linked to user
3. Update student: set `parent_primary_id` if empty, else `parent_secondary_id`. If both filled, create the parent but don't overwrite — admin can link later.
4. HubSpot sync: create Contact (parent name, email, phone, relationship, school name) and associate with the school's Company
5. Auto-login parent → redirect to parent portal

## Section 4: Super Admin Account (Miss A)

No new role needed — `ceo` is already the top role with full access.

Operational changes:
1. Seed a CEO user (`missa@ufitonline.com`, demo password) in seed data
2. Existing safeguard "Cannot delete the last CEO account" verified in user delete endpoint
3. Add new safeguard: cannot deactivate the last CEO (mirror the delete check)
4. No special UI — Miss A logs in via the Admin portal card

For the real production account, edit the seeded user's email to her real address and have her use Forgot Password to set her own password.

## Section 5: Auto-Create Logins When Adding Schools/Coaches

Current behavior changes:
- **Add School with principal info** → auto-create principal user + auto-send invite email
- **Add Coach** → auto-create user + auto-send invite email
- **Add Student** → no user created (parents register themselves)
- **Admin Users list** → status badges + Resend Invite button on pending rows

This is the piece that makes the app usable without seed data — every admin-driven account creation path now ends with the user receiving credentials.

---

## Data Model Changes

**No new tables.** All schema is sufficient already.

**Migration `step15`** (additive):
- Index `users.password_reset_token` for fast token lookups (if not already present)

**Backend code changes:**
- `app/auth.py`: add `verify_invite_token`, `consume_invite_token` helpers
- `app/routes/auth_routes.py`: new `POST /api/auth/set-password` endpoint that consumes a token + sets password + activates user
- `app/routes/auth_routes.py`: new `POST /api/auth/parent-register/verify-student` endpoint
- `app/routes/auth_routes.py`: new `POST /api/auth/parent-register/create` endpoint
- `app/routes/admin_routes.py`: in `POST /api/users` and `POST /api/schools` (principal branch), auto-generate token + auto-send invite email + create user with `active_status=FALSE`
- `app/routes/admin_routes.py`: extend user list responses with `account_status` (`pending` or `active`)
- `app/email/__init__.py`: ensure `send_invite_email` degrades gracefully (no-op log if API key missing)
- `app/hubspot.py` or `_hubspot.py`: add `notify_parent_registered(parent, student, school)` for HubSpot Contact sync

**Frontend changes:**
- `static/app.js`: rewrite `renderLogin()` for 4-card grid with inline expansion
- `static/app.js`: add parent registration 2-step flow
- `static/app.js`: add `/set-password` route handler
- `static/app.js`: status badges + Resend Invite button on user list
- `static/styles.css`: portal card grid styles, registration form styles

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Email API key not yet set, demo could show broken state | Email send gracefully no-ops if key missing; UI flow works with or without |
| Token expiry edge cases (user clicks expired link) | Show friendly message: "This invite has expired — ask your admin to resend it" |
| Parent registration spam (someone guesses student IDs) | Rate-limit `verify-student` endpoint; require all 3 fields exactly; log all attempts to audit_log |
| Existing seed users have `active_status=TRUE` but no password set | One-time migration: leave seed users active (they have demo passwords); only NEW users get pending state |
| HubSpot sync failure during parent registration | Already gracefully degrades (try/except in `_hubspot.py`); registration succeeds even if sync fails |

---

## Demo Readiness Checklist

By end of build:
- [ ] 4-card login screen renders correctly on desktop and mobile
- [ ] Click any portal card → form expands inline
- [ ] Parent card has "Create Account" link
- [ ] Parent registration verify step works against seed students
- [ ] Parent registration create step works and auto-logs in
- [ ] Admin can add a school with principal → user row created with pending status, invite email logged (or sent if key set)
- [ ] Admin can add a coach → same flow
- [ ] Users list shows Pending/Active badges
- [ ] Resend Invite button on pending rows works
- [ ] `/set-password?token=...` page works
- [ ] Miss A's CEO account exists in seed data
- [ ] All existing functionality (logging in as seeded users, navigating portals) still works
