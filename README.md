# Ufit Motion

A multi-organization PE program management platform for Ufit, serving K-8 school districts. Coaches log sessions and assessments from their phones. Admins monitor compliance and student growth across all schools.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3.1 (Python 3.12) |
| Database | PostgreSQL via Supabase |
| Frontend | Vanilla JS (no build step) |
| Hosting | Render |
| Auth | Flask session-based |

---

## Running Locally

**1. Clone and set up the virtual environment**

```bash
git clone <repo-url>
cd ufit-motion
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your values — see Environment Variables below
```

**4. Apply database migrations**

```bash
psql $DATABASE_URL -f migrations/001_initial_schema.sql
# Apply subsequent migrations in numerical order
```

**5. Run the development server**

```bash
flask run
```

The app will be available at `http://localhost:5000`.

For hot reload during development:

```bash
flask run --debug
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `UFIT_SECRET_KEY` | Yes | Flask session signing key. Long random string — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Yes | Supabase transaction pooler connection string (`aws-0-<region>.pooler.supabase.com:6543`). Do NOT use the direct DSN. |
| `APP_ENV` | Yes | One of `development`, `staging`, `production`. Controls debug mode and error verbosity. |
| `UFIT_APP_BASE_URL` | Prod | Base URL for email links (e.g. `https://ufitmotion.onrender.com`). Defaults to `http://localhost:5000`. |
| `UFIT_APP_ROOT` | Prod | Render deploy root — set to `/opt/render/project/src`. Not needed in dev. |
| `RESEND_API_KEY` | Prod | Resend API key for password reset and invite emails. |
| `EMAIL_FROM` | Prod | Sender address (e.g. `Ufit Motion <noreply@yourdomain.com>`). |
| `SENTRY_DSN` | Optional | Sentry DSN for error tracking. App runs without it; errors only go to logs. |
| `HUBSPOT_API_KEY` | Optional | HubSpot CRM integration. Webhook routes return 503 if unset. |
| `HUBSPOT_WEBHOOK_SECRET` | Optional | Validates HubSpot webhook signatures. Required if HubSpot integration is active. |
| `REDIS_URL` | Optional | Redis for distributed rate-limit state. Not needed with 1 gunicorn worker (current config). |
| `UFIT_SEED_PASSWORD` | Dev only | Password used for all seed accounts. Never set in production — guard in seeds.py blocks seed run outside `development` env. |

Copy `.env.example` to `.env` and fill in your values. The `.env` file is gitignored — never commit it.

---

## Applying Migrations

Migrations are plain SQL files in `migrations/`. Apply them in numerical order against your PostgreSQL database:

```bash
# Apply a single migration
psql $DATABASE_URL -f migrations/001_initial_schema.sql

# Apply all migrations in order (bash)
for f in migrations/*.sql; do
  echo "Applying $f..."
  psql $DATABASE_URL -f "$f"
done
```

In production (Render), run migrations via the Supabase SQL editor before deploying a new release that depends on schema changes.

---

## Project Structure

```
ufit-motion/
├── app/                    # Flask application package
│   ├── __init__.py         # create_app factory
│   ├── auth/               # Auth blueprint (login, logout, session)
│   ├── coach/              # Coach-facing routes and views
│   ├── admin/              # Admin-facing routes and views
│   ├── api/                # JSON API routes
│   └── models/             # Database query functions
├── docs/
│   ├── plans/
│   │   └── implementation.md   # Full build plan — start here
│   ├── schema.md           # Database schema reference
│   ├── api.md              # API route registry
│   └── roles.md            # Role-permission matrix
├── migrations/             # SQL migration files (numbered, in order)
├── scripts/                # Utility scripts (seed data, etc.)
├── static/
│   ├── css/                # Stylesheets
│   └── js/                 # Vanilla JS modules
├── templates/              # Jinja2 HTML templates
├── tests/                  # pytest test suite
├── .env.example            # Environment variable template
├── CLAUDE.md               # Agent operating instructions
├── AGENTS.md               # Agent role directory and protocol
├── SOUL.md                 # Project identity and values
├── DESIGN.md               # Full design system
├── PROJECT.md              # Project intelligence and decisions
├── requirements.txt        # Pinned Python dependencies
├── render.yaml             # Render deployment configuration (web + cron)
└── wsgi.py                 # WSGI entry point
```

---

## Build Plan

The full implementation plan — phases, tasks, and file-level breakdown — is at `docs/plans/implementation.md`. Start there if you're picking up this project for the first time.

---

## Deployment

This project deploys to Render via the configuration in `render.yaml`. Deployment is triggered by pushing to the main branch.

**Required environment variables on Render (set in Dashboard → Environment):**
- `UFIT_SECRET_KEY` — long random string (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- `DATABASE_URL` — Supabase **transaction pooler** DSN (`aws-0-<region>.pooler.supabase.com:6543`). Do NOT use the direct DSN.
- `APP_ENV=production`
- `UFIT_APP_BASE_URL` — your public domain (e.g. `https://ufitmotion.onrender.com`)
- `UFIT_APP_ROOT=/opt/render/project/src` — Render's deploy root
- `RESEND_API_KEY` — for password reset and invite emails
- `EMAIL_FROM` — sender address (e.g. `Ufit Motion <noreply@yourdomain.com>`)
- `SENTRY_DSN` — Sentry project DSN for error tracking (optional but strongly recommended)
- `HUBSPOT_API_KEY` — HubSpot CRM integration (optional)
- `HUBSPOT_WEBHOOK_SECRET` — HubSpot webhook validation (optional, required if HubSpot active)

The health check endpoint is `/api/health`. Render will verify this is responding before marking a deployment successful.

---

## Production Migrations

The `migrations/supabase/` directory contains numbered SQL files that must be applied in order against your Supabase database. Apply them using the Supabase SQL editor or `psql`:

```bash
# Apply all Supabase migrations in order
for f in migrations/supabase/step*.sql; do
  echo "Applying $f..."
  psql $DATABASE_URL -f "$f"
done
```

**Migration sequence:**
| File | Purpose |
|---|---|
| `step1_schema.sql` | Full base schema (all tables, indexes, RLS) |
| `step2_eod_fields.sql` | EOD report additional fields |
| `step3_seed_skills.sql` | Seed PE skill definitions |
| `step4_schema_gaps.sql` | Schema gap fixes from QA |
| `step5_rls.sql` | Row-level security policies |
| `step6_sessions_soft_delete.sql` | Soft-delete for sessions |
| `step7_coach_scoring.sql` | Coach scoring columns |
| `step8_staff_profiles_soft_delete.sql` | Soft-delete for staff_profiles |
| `step9_assessment_windows_soft_delete.sql` | Soft-delete for assessment_windows |
| `step10_sessions_duration.sql` | Session duration column |
| `step11_obs_soft_delete.sql` | Soft-delete for behavior/coach observations |
| `step12_principal_surveys.sql` | Principal satisfaction survey table |
| `step13_coach_evaluations.sql` | Head coach evaluation form table |

Always apply migrations before deploying application code that depends on the new schema.

---

## Running Tests

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

Tests are in `tests/`. The test suite requires a test database — set `DATABASE_URL` to a separate test database or use SQLite for unit tests (check `tests/conftest.py` for configuration).
