# AGENTS.md — Ufit Motion

**Mission:** Ufit Motion delivers PE program management, student assessment tracking, and coach performance reporting across multiple school organizations.

This file defines which agent handles which task and the order in which they must be invoked. Every Claude session must route work through this protocol — no ad-hoc coding without consulting the role directory first.

---

## Sequential Protocol Ordering

Work proceeds in four phases. Phases are not optional — you cannot start Phase 3 without completing Phase 2.

### Phase 1 — Architecture & Database

**Agent:** `architect`
**Trigger:** Any new tables, schema changes, relationship decisions, or architectural decisions (e.g., how to model multi-org data isolation, how to structure role permissions).

**Outputs required before Phase 2 begins:**
- Entity-relationship description or diagram note
- Migration SQL file in `migrations/`
- Row-level security (RLS) policy notes if applicable
- Updated schema section in `docs/schema.md`

### Phase 2 — Backend Implementation

**Sequence:** `planner` → `implementation`

**Routing by feature type:**

| Feature Type | Additional Step |
|---|---|
| Any new feature | `spec-writer` produces spec first; implementation waits for spec approval |
| Auth routes, login, session, role checks | Invoke `security-reviewer` after implementation, before commit |
| Any database query or migration | Use `database-migrations` skill; verify RLS scope |
| New API endpoint | `api-design` skill validates naming + response shape; add to `docs/api.md` |
| Role-permission logic | Document in `docs/roles.md`; security-reviewer required |
| Any Python file changed | `python-reviewer` runs after code-reviewer |
| Any UI screen built | `accessibility-reviewer` runs before screen is marked complete |
| Any new feature with tests missing | `tdd-guide` runs before implementation code is written |

**Output:** Working Flask routes, models, and services. No frontend yet.

### Phase 3 — Frontend & Design

**Sequence:** `design-system-architect` → `ui-designer` (per screen)

**Rule:** `design-system-architect` must confirm design tokens are consistent with `DESIGN.md` before any screen is built. If tokens need updating, update `DESIGN.md` first.

**Per-screen sequence:**
1. `design-system-architect` reviews the screen's component needs
2. `ui-designer` builds the Jinja2 template and associated vanilla JS
3. Self-review against mobile usability constraints (44px touch targets, outdoor contrast)

### Phase 4 — Quality & Pre-Ship

**Sequence:** `code-reviewer` → `pre-ship` (before any deploy)

`code-reviewer` runs after every completed feature, not just before deploy.
`pre-ship` is a hard gate — no Railway deploy without passing it.

---

## Role Directory

| Agent | Model | Trigger Condition |
|---|---|---|
| architect | opus | New tables, schema changes, architectural decisions |
| planner | opus | Feature planning, implementation breakdown |
| spec-writer | sonnet | Before any feature implementation — converts fuzzy requirements to verifiable specs |
| ui-designer | sonnet | New screens, component design, visual polish |
| design-system-architect | sonnet | Design tokens, DESIGN.md updates |
| code-reviewer | sonnet | After completing any feature, before commit |
| python-reviewer | sonnet | After any Python file changes — idiomatic review, type hints, Flask patterns |
| security-reviewer | sonnet | Auth changes, RLS policy changes, any user data handling |
| tdd-guide | sonnet | Before writing any feature code — write tests first |
| accessibility-reviewer | sonnet | After any UI screen is built — WCAG 2.1 AA + mobile/outdoor usability |
| doc-updater | sonnet | After schema changes, update migration README |

---

## Agent Responsibilities (detail)

### architect
- Owns `migrations/` and `docs/schema.md`
- Produces migration SQL files named `YYYYMMDD_NNN_description.sql`
- Documents all foreign key relationships and org-scoping decisions
- Must flag any design that would allow cross-org data leakage

### planner
- Reads architect output before planning
- Produces task list in `docs/plans/` with file-level implementation steps
- Identifies which routes need security-reviewer involvement
- Does NOT write code — only plans

### ui-designer
- Works only from approved `DESIGN.md` tokens
- Produces Jinja2 templates in `templates/`
- Produces vanilla JS in `static/js/`
- Minimum touch target: 44x44px on all interactive elements
- Must annotate any deviation from DESIGN.md with a comment

### design-system-architect
- Owns `DESIGN.md`
- Reviews component needs before each Phase 3 sprint
- Approves or rejects new tokens before they enter templates
- Updates DESIGN.md when new patterns are established

### code-reviewer
- Reads the diff of every completed feature
- Checks: auth on every route, no cross-org queries, no hardcoded secrets, no inline SQL, error handling present, mobile usability on any new template
- Blocks commit if any check fails

### security-reviewer
- Invoked on: any login/logout/session logic, any role-permission check, any RLS policy, any route handling student or user data
- Checks: session fixation, privilege escalation paths, org boundary enforcement, input validation
- Must approve before smart-commit on auth-related work

### doc-updater
- Runs after any schema change
- Updates: `docs/schema.md`, migration README, `docs/api.md` if endpoints changed
- Keeps `docs/roles.md` current with any role-permission changes

### spec-writer
- Produces a 7-property spec (Complete, Consistent, Verifiable, Bounded, Traceable, Prioritized, Unambiguous) before any feature implementation
- Writes BDD Given/When/Then acceptance criteria for every key behavior
- Output lives in `docs/specs/` — one file per feature
- Implementation does NOT begin until spec is approved

### python-reviewer
- Runs on all `.py` file changes
- Checks: PEP 8, type hints, Pythonic idioms, Flask-specific patterns (request context, blueprint structure, g object), parameterized queries, no f-string SQL
- Flags any issues the generic code-reviewer would miss (e.g., implicit string concatenation in SQL, bare `except:`, mutable default args)

### tdd-guide
- Runs before implementation code is written for any new feature
- Produces test file skeletons in `tests/` before routes/models are implemented
- Enforces Red-Green-Refactor cycle: failing test → passing implementation → refactor
- Minimum coverage target: 80% on all new code

### accessibility-reviewer
- Runs after any UI screen or component is built — required before marking screen complete
- Checks WCAG 2.1 AA compliance AND Ufit-specific mobile constraints:
  - Minimum 44×44px touch targets (coaches using one hand)
  - High contrast ratios for outdoor use (bright sunlight)
  - No hover-only interactions (mobile/touchscreen)
  - Form completion possible without keyboard (coach using phone)
- Outdoor-specific: color must communicate meaning even in direct sunlight glare
