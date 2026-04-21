# CLAUDE.md — Ufit Motion

This file is the operating contract for every Claude session on this project. Read it before touching any code.

---

## Session Start Protocol

Follow these steps at the start of every session, in order:

1. Read `SOUL.md` — understand the project's identity, values, and constraints before anything else.
2. Read `AGENTS.md` — load the role directory and sequential protocol so you know which agent to invoke for each task type.
3. **Read `docs/requirements-external.md`** — this is the product specification (scoring formulas, table definitions, reporting outputs). All scoring, assessment, and reporting work must conform to it.
4. Check `.sessions/handoffs/` — find the latest handoff file that is NOT marked superseded. Load its open tasks, decisions, and context.
5. Run `glob .claude/agents/*` — confirm which agent definitions are present and available.
6. Run `git log --oneline -5` — orient to the current branch state and recent commits.
7. If the loaded handoff lists skills to invoke at session start, invoke them now via the Skill tool before proceeding.

---

## Development Workflow

Tasks move through the following skill chain in order. Do not skip steps.

```
brainstorming → planning → execute → code-reviewer → smart-commit → session-handoff
```

**First session exception:** The implementation plan already exists at `docs/plans/implementation.md`. Skip brainstorming and planning — go directly to execute.

**Routing rule:** Before starting any task, consult the Role Directory in `AGENTS.md` to determine which agent handles it. Route accordingly before writing a single line of code.

Feature-type routing shortcuts:
- Auth changes → invoke security-reviewer after execute, before commit
- DB / schema changes → run through architect first, then database-migrations skill after planner
- New screen / UI → design-system-architect first (confirm tokens), then ui-designer per screen
- Any deploy → code-reviewer → pre-ship → deploy

---

## Required Rules

1. **Self-review every artifact before handing off.** After writing any file, function, migration, or template — read it back, check it against `SOUL.md` values, and fix anything that violates them.
2. **Run session-handoff before ending any session.** No session ends without a handoff document in `.sessions/handoffs/`. If the session is short and nothing changed, write a minimal handoff noting that.
3. **Never ship a route without auth.** Every Flask route that returns user data must check the session and role before responding. No exceptions.
4. **Follow AGENTS.md Sequential Protocol Ordering.** Architecture before backend. Design system before UI screens. Review before commit. Always.
5. **Never expose student data across org boundaries.** This is a hard constraint from `SOUL.md`. Any query that touches student records must be scoped to the current user's org.

---

## Project Context

**Product:** Ufit Motion — a multi-organization PE program management platform for K-8 school districts.

**Company:** Ufit — a PE program delivery company. Coaches are Ufit employees deployed to client school districts.

**What it does:**
- Coaches log daily sessions, file EOD reports, and submit incident reports from their phones in the field
- Admins (Ufit HQ) monitor coach activity, compliance, and student growth across all schools
- School principals and coordinators review program outcomes for their buildings
- Parents view their child's PE progress

**9 user roles:** `ceo`, `admin`, `coach_overseer`, `site_coordinator`, `head_coach`, `assistant_coach`, `principal`, `school_staff`, `parent`

**Tech stack:**
- Backend: Flask (Python 3.12)
- Database: PostgreSQL via Supabase
- Hosting: Render (migrated from Railway)
- Frontend: Vanilla JS (no framework)
- Auth: Flask session-based with role checks

**Brand:** Blue (`#1E40AF`) primary, Yellow (`#F59E0B`) accent, White (`#FFFFFF`) surface. Full design system in `DESIGN.md`.

**Design constraint:** Coaches use this on phones, outdoors, under time pressure. Every UI must be operable with one hand in bright sunlight.

**Data constraint:** Student data is scoped to org. No cross-org leakage under any circumstance.

**Key performance targets:**
- Coach EOD report submission: under 2 minutes
- Admin dashboard to any school's data: under 3 clicks
- Principal reading student progress: under 30 seconds
