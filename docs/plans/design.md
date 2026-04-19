# Design Decisions — Ufit Motion

## Project Classification
- Type: Product/UI (multi-role SaaS web app)
- Codebase: Greenfield
- Topology: Single-session (no AI agents in the app itself in Week 1-2; agent-assisted development)
- Playbook: building-professional-websites.md for design; production patterns for auth

## Four Pillars (for future AI features — Weeks 3-5)

### Prompt Pillar
- System prompt constraint: never expose student data across organization boundaries
- Output format: structured JSON for all API responses
- Key constraint: all PII fields (student names, emails, phone) excluded from any AI summary prompts

### Model Pillar
- Report generation (Week 3): Claude Sonnet 4.6 (balance of quality and cost)
- Hubspot integration summaries (Week 4): Claude Haiku 4.5 (high volume, low cost)
- Cost ceiling per request: $0.05 max
- No Opus for automated/background tasks — only for human-in-loop design sessions

### Context Pillar
- Student data: org-scoped only — RLS enforces at DB layer
- Coach context: school-scoped, never cross-school
- Admin context: org-scoped, filtered by active organization
- Never in context: password hashes, auth tokens, raw database IDs for external systems

### Tools Pillar (Week 3-4 AI features)
- Allowed: read school data, generate report summaries, read assessment scores
- Restricted: no write to student records, no delete actions, no cross-org reads
- Fallback: if AI call fails, return structured data without summary (graceful degradation)
- HITL gate: all AI-generated reports reviewed by admin before export

## Context Window Architecture
- Short-term only for Week 1-2 (no AI in app)
- Week 3: episodic memory per school (rolling 30-day session history)
- Week 4: semantic memory for benchmarks (skill descriptions always available)

## Memory Architecture
- Week 1-2: none (stateless Flask sessions)
- Week 3+: Supabase as semantic store (student summaries, school averages)

## Execution Topology
- Single agent per request (no parallelism needed at this scale)
- Week 4 report generation: sequential pipeline (fetch data → summarize → format → store)

## Loop Pattern
- Week 1-2: request/response (no loops)
- Week 3+: Plan-Build-Review for report generation

## HITL Gates
- All school_reports: admin must approve before PDF is exported
- All incident_reports severity=high/critical: coach_overseer or admin must acknowledge
- All user role changes: admin must confirm
- Student data export: ceo or admin only, logged in audit_log

## Error Handling Contract
| Failure | Behavior |
|---------|----------|
| DB connection fail on startup | Log error, return 503 on all routes |
| DB query fail | Return 500 with generic message, log full error server-side |
| Auth token expired | Return 401, clear session, redirect to login |
| Permission denied | Return 403, log attempt in audit_log |
| AI API fail (Week 3+) | Return structured data without AI summary, alert admin |
| Invalid input | Return 400 with specific field errors |
| Rate limit | Return 429, retry-after header |

## SOUL Character (see SOUL.md)
- Accuracy-first: student data must be correct
- Coach speed: every coach action < 2 minutes
- Security: no cross-org data leakage ever

## Eval Criteria (Week 4-5)
- Auth: 100% of role-gating tests pass
- DB: all 32 tables present in Supabase, all FKs valid
- Coach EOD submit: end-to-end in < 2 minutes (manual timing test)
- Admin dashboard: all stats accurate (verified against DB counts)
- RLS: coach at School A cannot see School B data (automated test)
- Assessment score: normalized_score = raw_level * 20 (automated)

## Security Threat Model (initial pass — expanded in security-review)
- Primary threats: cross-org data exposure, student PII leak, unauthorized role escalation
- FERPA implications: student records require org-level isolation, audit log for all access
- Mitigations: RLS on all tables, audit_log on all writes, soft-deletes (no permanent loss), password reset via signed tokens
- Open: RLS policies not yet written (Week 3-4 task). Current mitigation: application-layer role checks.
- Open: No rate limiting yet (Week 3-4 task)
- Open: No HTTPS enforcement at app level (Railway provides TLS termination)

## Tech Stack Rationale
- Flask: proven, minimal, easy to deploy on Railway, matches team familiarity
- Supabase: managed Postgres + Storage + future Auth migration path
- Vanilla JS: no build step, fast iteration, works on slow school networks
- Railway: zero-config deployment from GitHub, auto-deploy on push
