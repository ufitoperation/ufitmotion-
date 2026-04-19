# PROJECT.md — Ufit Motion

Project intelligence file. Everything a new agent or developer needs to understand what we're building, who we're building it for, and what decisions have already been made.

---

## What This Is

Ufit Motion is a web application for Ufit, a PE program delivery company serving K-8 school districts. Ufit contracts with school districts to place trained PE coaches in their schools. Ufit Motion is the operational layer that makes those placements trackable, accountable, and measurable.

**For coaches:** Log daily sessions, file EOD (end-of-day) reports, submit incident reports, and record student assessments — all from their phone, in under 2 minutes per report.

**For Ufit admins:** Monitor coach activity across all schools and districts, track compliance with session quotas, review assessment data, identify underperforming programs, and report to district leadership.

**For school principals and coordinators:** Review their school's PE program outcomes — participation rates, assessment scores, coach activity — without needing to contact Ufit directly.

**For parents:** View their child's PE participation and assessment progress.

---

## Target Audience

### Primary: PE Coaches in the Field

- Uses this app on a phone (iOS and Android)
- Outdoors or in a gymnasium — bright light, possibly gloved hands
- Time-pressured: they have 2–3 minutes between classes to log data
- Not highly technical — the app must be self-explanatory
- Motivated: they want to know their students are improving

**Design implication:** Large touch targets. Fast paths. Minimal required fields. Clear confirmation messages. The app should feel like a sports tracking app, not enterprise HR software.

### Secondary: Ufit Admins Reviewing Coach Compliance and Student Growth

- Uses this app on desktop (laptop/monitor)
- Data-oriented: they want numbers, trends, exceptions
- Time is valuable — they manage dozens of coaches across many schools
- Comfortable with dashboards but not developers

**Design implication:** Dense data tables. Filtering and sorting on every list. Export capabilities. Dashboard widgets that answer the most common questions without drilling in.

### Tertiary: School Principals Reviewing Program Outcomes

- Uses this occasionally — monthly or at review time
- Not a daily user — the app must orient them quickly
- Wants to see their school's data, not all schools
- Primarily desktop, but may access on a tablet

**Design implication:** School-scoped views that load pre-filtered. Simple summary metrics first, details available but not prominent.

### Quaternary: Parents Viewing Student Progress

- Access is limited to their own child's data
- Probably accesses via a link from a school communication
- May not know what Ufit Motion is — the page must explain itself
- Mobile-first

---

## Primary Goal

**Coaches submit EOD reports and session data in under 2 minutes.**

This is the single most important usability target. Everything about the coach workflow — form length, navigation, field defaults, confirmation flow — is designed around this constraint.

**Admins can pull any school's performance data in under 3 clicks.**

From the admin dashboard, reaching a specific school's full performance view must take no more than 3 clicks. The information architecture is designed around this.

---

## Brand Personality

**Energetic, trustworthy, professional. "We take PE seriously."**

Ufit is not a clipboard-and-whistle operation. They bring structure, data, and accountability to PE programs that often have neither. The product should feel like it was built by people who care about physical education and student development.

**Not:** corporate, bureaucratic, complicated, or cold.

**In practice:** The UI uses sports-adjacent visual energy (bold colors, clear scoreboard-style metrics) while maintaining the cleanliness and reliability of enterprise software. Coaches should feel like they're using something designed for athletes — not filing paperwork.

---

## What This Is NOT

- **Not a social media app.** There are no feeds, likes, shares, or social connections. Data is operational, not social.
- **Not a gradebook.** Ufit Motion does not replace school Student Information Systems (SIS). We track PE-specific assessments, not academic grades. We never sync with or compete with PowerSchool, Infinite Campus, etc.
- **Not a video platform.** No video uploads, no video playback, no live streaming. Assessment is observational and rubric-based.
- **Not a communication platform.** No in-app messaging between coaches, no group chats. Reports and dashboards, not communication tools.

---

## Competitors / Reference Products

| Reference | Why It Matters |
|---|---|
| BambooHR | Admin UX reference — dense, filterable data, clean hierarchy. What the admin dashboard should feel like. |
| Hudl | Coach UX reference — fast data entry, athlete-centric, mobile-native. What the coach dashboard should feel like. |
| TeamSnap | Parent/team management reference — simple parent-facing views, clear progress indicators. |

We are not trying to be any of these products. We are borrowing UX patterns that match our users' mental models.

---

## Content Inventory

### Core Pages

| Page | Primary Role | Description |
|---|---|---|
| Login | All | Single login page, routes to role-appropriate dashboard after auth |
| Admin Dashboard | ceo, admin, coach_overseer | Cross-school overview: active coaches, session counts, assessment trends, compliance alerts |
| Coach Dashboard | head_coach, assistant_coach | Today's schedule, recent sessions, pending reports, quick-log button |
| Assessment Entry | head_coach, assistant_coach | Per-student assessment form for a given session/standard |
| EOD Report | head_coach, assistant_coach | End-of-day summary: sessions held, incidents, notes |
| Incident Report | head_coach, assistant_coach, site_coordinator | Structured incident report form |
| Student Profile | All (org-scoped) | Individual student: assessment history, participation trend, notes |
| School Report | site_coordinator, principal, admin, ceo | School-level summary: coach roster, session compliance, student outcomes |
| Settings | All | Account settings, notification preferences; admin-only: org config, user management |

### Supporting Pages

| Page | Description |
|---|---|
| User Management (admin) | Create/edit/deactivate users, assign roles and schools |
| Coach Performance (admin/overseer) | Individual coach drill-down: sessions, assessments, compliance rate |
| Organization Settings (admin/ceo) | Org-level config: schools, academic year, assessment standards |

---

## Data Architecture (high-level)

Multi-org architecture. Every data record is scoped to an organization. The core hierarchy:

```
Organization
  └── School (belongs to one org)
        └── Coach Assignment (coach + school + date range)
        └── Student (belongs to one school)
              └── Session Record (coach + student + date + standards)
              └── Assessment Record (student + standard + score + date)
        └── Incident Report (coach + school + date + narrative)
        └── EOD Report (coach + school + date + summary)
```

**Org isolation is enforced at the query level.** No query returns data across org boundaries. RLS policies at the Supabase level provide an additional enforcement layer.

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend framework | Flask (Python) | Lightweight, well-understood, easy to deploy on Railway |
| Database | PostgreSQL via Supabase | Managed Postgres with built-in RLS support |
| Frontend | Vanilla JS | No build step, fast initial load, coaches on slow connections |
| Auth | Flask session-based | Simple, secure, no third-party auth dependency |
| Hosting | Railway | Simple deployment, environment variable management, PostgreSQL support |
| Migrations | Raw SQL files | Explicit, reviewable, no ORM magic hiding schema changes |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `UFIT_SECRET_KEY` | Yes | Flask session signing key — must be a long random string in production |
| `DATABASE_URL` | Yes | PostgreSQL connection string (Supabase connection string) |
| `APP_ENV` | Yes | `development`, `staging`, or `production` |
| `UFIT_APP_BASE_URL` | No | Base URL for generating links (defaults to localhost in development) |

---

## Open Questions (to be resolved in planning)

- Assessment standards: are they configurable per org, or is there a global standard set with org-specific additions?
- Session quota: is the expected sessions-per-week value set at the org level, school level, or coach level?
- Parent access: is this invite-based (coach or coordinator sends a link) or self-registration with school code?
- Incident report routing: who gets notified when a coach files an incident? Site coordinator only, or also Ufit admin?
- Offline support: coaches in gyms may have poor connectivity. Do we need any offline-first capability for session logging?
