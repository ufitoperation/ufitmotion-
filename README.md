# Ufit Motion

A multi-organization PE program management platform for Ufit, serving K-8 school districts. Coaches log sessions and assessments from their phones. Admins monitor compliance and student growth across all schools.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3.1 (Python 3.12) |
| Database | PostgreSQL via Supabase |
| Frontend | Vanilla JS (no build step) |
| Hosting | Railway |
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
| `UFIT_SECRET_KEY` | Yes | Flask session signing key. Use a long random string in production (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | Yes | PostgreSQL connection string. Format: `postgresql://user:password@host:5432/dbname` |
| `APP_ENV` | Yes | One of `development`, `staging`, `production`. Controls debug mode and error verbosity. |
| `UFIT_APP_BASE_URL` | No | Base URL for generating absolute links. Defaults to `http://localhost:5000` in development. |

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

In production (Railway), run migrations manually via the Railway CLI or the Supabase SQL editor before deploying a new release that depends on schema changes.

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
├── runtime.txt             # Python version for Railway/Nixpacks
├── Procfile                # Process definition for Railway
├── railway.toml            # Railway deployment configuration
└── wsgi.py                 # WSGI entry point
```

---

## Build Plan

The full implementation plan — phases, tasks, and file-level breakdown — is at `docs/plans/implementation.md`. Start there if you're picking up this project for the first time.

---

## Deployment

This project deploys to Railway via the configuration in `railway.toml`. Deployment is triggered by pushing to the main branch.

**Required environment variables on Railway:**
- `UFIT_SECRET_KEY`
- `DATABASE_URL` (Railway PostgreSQL plugin or Supabase connection string)
- `APP_ENV=production`

The health check endpoint is `/api/health`. Railway will verify this is responding before marking a deployment successful.

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
