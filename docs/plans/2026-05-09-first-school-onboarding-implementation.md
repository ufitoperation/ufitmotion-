# First-School Onboarding — Implementation Plan

> **For Claude:** Execute this plan task-by-task. Commit after each numbered build item completes. After committing the plan, start with Phase A item 1.

**Goal:** Ship the 16-item build queue from `2026-05-09-first-school-onboarding-design.md` so the first real school can be onboarded onto Ufit Motion in production.

**Architecture:** Four phases (A foundation → B coach onboarding → C UX polish → D walkthrough). Each item is a self-contained TDD slice — failing test → minimal implementation → passing test → commit. Phase A items are operational/legal blockers; Phase B unlocks the actual coach flows; Phase C closes UX gaps surfaced by the demo; Phase D ships the boss-facing walkthrough HTML.

**Tech stack:** Flask 3 (Python 3.12), Postgres via Supabase, vanilla JS SPA at `templates/index.html`, pytest + SQLite in-memory test fixtures, Render hosting, Gmail SMTP (replacing Resend), Supabase migrations as `migrations/supabase/stepN_*.sql` registered in `run_migrations.py`.

**Conventions followed:**
- Migrations run via `python run_migrations.py` and must be appended to the `MIGRATIONS` list in that file.
- Auth-touching routes get `security-reviewer` after implementation per `AGENTS.md`.
- All new routes must have an `@admin_required` / role gate before returning data (SOUL.md).
- Org-scoping enforced at the query level on any student/user query.
- Every state-change writes an `audit_log` row via `app.routes._helpers.audit()`.
- Frontend lives entirely in `static/app.js` + `static/styles.css` + `templates/index.html` (the SPA shell). No new template files unless a non-SPA page (privacy, terms, walkthrough).

**Branch / commit conventions:**
- Work on `main`. Commit after each numbered item, message format: `<phase>(<item>): short summary` e.g. `feat(A1): production_wipe.py + first super admin`.
- Don't squash. Push only when phase ends (after A5, B9, C15, D16) so Render rebuilds at well-defined boundaries.

---

## Index

- Phase A — Foundation: items 1-5
- Phase B — Coach onboarding: items 6-9
- Phase C — UX polish: items 10-15
- Phase D — Walkthrough HTML: item 16
- Cross-cutting: `git push` cadence, deploy verification, super-admin runbook

---

# Phase A — Foundation

## A1. Production wipe script + first super admin

**Files:**
- Create: `scripts/production_wipe.py`
- Create: `tests/test_production_wipe.py`
- Create: `docs/runbooks/super-admin-bootstrap.md`

**Behavior:**
- Read env vars: `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_FIRST`, `SUPER_ADMIN_LAST`, `APP_ENV`, `DATABASE_URL`.
- Refuse to run unless `APP_ENV == "production"` OR `--allow-non-prod` flag is present.
- Print a confirmation banner listing tables to truncate; require `--yes-really` to skip stdin confirmation.
- Single transaction: `TRUNCATE … RESTART IDENTITY CASCADE` over operational tables; INSERT one CEO using `werkzeug.security.generate_password_hash` (method=`pbkdf2:sha256`, the same method used elsewhere).
- Tables to TRUNCATE (mirror design doc Q1; ordering doesn't matter under CASCADE):
  ```
  organizations, regions, contracts, schools, users, parents, students,
  programs, sessions, student_session_attendance, assessments,
  assessment_scores, assessment_windows, behavior_observations,
  eod_reports, incident_reports, coach_observations, coach_evaluations,
  coach_performance_snapshots, school_reports, student_skill_summary,
  student_domain_summary, student_overall_summary, notifications,
  audit_log, principal_satisfaction_surveys, staff_profiles,
  staff_assignments, session_staff, parent_student_links
  ```
- Tables that survive: `skill_domains`, `skills`, `benchmarks`, `app_settings`, `role_permissions`. Verified by `assert` after truncate.
- After truncate, `INSERT INTO users (...) VALUES (... role='ceo', active_status=TRUE ...)` — atomic with the truncate, no zero-admin window.
- Exit code 0 on success, 1 on any failure. Stderr-only progress output so logs are readable.

**Step 1: Write the failing tests**

```python
# tests/test_production_wipe.py
import os
import pytest
from unittest.mock import patch

def test_wipe_refuses_when_not_production_without_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "x" * 12)
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "Ada")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "Lovelace")
    from scripts.production_wipe import main
    with pytest.raises(SystemExit) as e:
        main(argv=["--yes-really"])
    assert e.value.code != 0

def test_wipe_requires_super_admin_env_vars(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    for k in ("SUPER_ADMIN_EMAIL","SUPER_ADMIN_PASSWORD","SUPER_ADMIN_FIRST","SUPER_ADMIN_LAST"):
        monkeypatch.delenv(k, raising=False)
    from scripts.production_wipe import main
    with pytest.raises(SystemExit):
        main(argv=["--allow-non-prod","--yes-really"])

def test_wipe_truncates_and_creates_ceo(app, monkeypatch):
    """End-to-end against the SQLite test DB used by conftest."""
    from app.database import get_db
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "ceo@ufitonline.net")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "Sup3r$ecret!")
    monkeypatch.setenv("SUPER_ADMIN_FIRST", "Boss")
    monkeypatch.setenv("SUPER_ADMIN_LAST", "Lady")

    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO organizations (organization_name, organization_type, contract_status, created_at) VALUES ('LegacyOrg','school_district','active',?)", ("2026-01-01",))
        db.commit()
        db.close()

    from scripts.production_wipe import main
    main(argv=["--allow-non-prod","--yes-really"])

    with app.app_context():
        db = get_db()
        org_count = db.execute("SELECT COUNT(*) c FROM organizations").fetchone()["c"]
        ceo = db.execute("SELECT email, role FROM users WHERE email=?", ("ceo@ufitonline.net",)).fetchone()
        skills = db.execute("SELECT COUNT(*) c FROM skills").fetchone()["c"]
        db.close()
    assert org_count == 0
    assert ceo and ceo["role"] == "ceo"
    assert skills > 0  # skill catalog preserved
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_production_wipe.py -v
```
Expected: `ModuleNotFoundError: scripts.production_wipe` or all 3 FAIL.

**Step 3: Implement `scripts/production_wipe.py`**

Skeleton:

```python
"""
production_wipe.py — Atomic production reset + first super-admin bootstrap.

Run via:
    APP_ENV=production \
    SUPER_ADMIN_EMAIL=... SUPER_ADMIN_PASSWORD=... \
    SUPER_ADMIN_FIRST=... SUPER_ADMIN_LAST=... \
    python -m scripts.production_wipe --yes-really

Add --allow-non-prod for staging dry-runs.
"""
import argparse, os, sys
from werkzeug.security import generate_password_hash

OPERATIONAL_TABLES = [
    "audit_log","notifications","principal_satisfaction_surveys",
    "coach_performance_snapshots","coach_evaluations","coach_observations",
    "incident_reports","eod_reports","behavior_observations",
    "student_overall_summary","student_domain_summary","student_skill_summary",
    "school_reports","assessment_scores","assessments","assessment_windows",
    "student_session_attendance","session_staff","sessions","programs",
    "parent_student_links","parents","staff_assignments","staff_profiles",
    "students","schools","contracts","regions","organizations","users",
]
PRESERVED_TABLES = ["skill_domains","skills","benchmarks","app_settings","role_permissions"]

REQUIRED_ENV = ("SUPER_ADMIN_EMAIL","SUPER_ADMIN_PASSWORD","SUPER_ADMIN_FIRST","SUPER_ADMIN_LAST")

def _check_env(allow_non_prod: bool) -> dict:
    env = os.environ.get("APP_ENV","").strip().lower()
    if env != "production" and not allow_non_prod:
        sys.stderr.write(f"REFUSING: APP_ENV={env!r} is not 'production'. Pass --allow-non-prod to override.\n")
        sys.exit(2)
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.stderr.write(f"Missing env vars: {missing}\n")
        sys.exit(3)
    pw = os.environ["SUPER_ADMIN_PASSWORD"]
    if len(pw) < 12:
        sys.stderr.write("SUPER_ADMIN_PASSWORD must be at least 12 chars.\n")
        sys.exit(4)
    return {k: os.environ[k] for k in REQUIRED_ENV}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-non-prod", action="store_true")
    parser.add_argument("--yes-really", action="store_true")
    args = parser.parse_args(argv)
    creds = _check_env(args.allow_non_prod)

    if not args.yes_really:
        sys.stderr.write("Pass --yes-really to confirm destructive wipe.\n"); sys.exit(5)

    # Lazy-import so test fixtures can preload APP_ENV/DB_PATH first.
    from app import create_app
    from app.database import get_db
    app = create_app()
    with app.app_context():
        db = get_db()
        try:
            is_pg = bool(os.environ.get("DATABASE_URL"))
            if is_pg:
                tables = ", ".join(OPERATIONAL_TABLES)
                db.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
            else:
                # SQLite test path: DELETE in dependency-safe reverse order.
                db.execute("PRAGMA foreign_keys = OFF")
                for t in OPERATIONAL_TABLES:
                    try:
                        db.execute(f"DELETE FROM {t}")
                    except Exception:
                        pass
                db.execute("PRAGMA foreign_keys = ON")

            ph = generate_password_hash(creds["SUPER_ADMIN_PASSWORD"], method="pbkdf2:sha256")
            from app.routes._helpers import now_utc
            db.execute(
                """INSERT INTO users (role, first_name, last_name, email, password_hash,
                                      active_status, created_at)
                   VALUES ('ceo', ?, ?, ?, ?, %s, ?)""" % ("TRUE" if is_pg else "1"),
                (creds["SUPER_ADMIN_FIRST"], creds["SUPER_ADMIN_LAST"],
                 creds["SUPER_ADMIN_EMAIL"].lower(), ph, now_utc()),
            )
            db.commit()
        finally:
            db.close()
    sys.stderr.write("Wipe complete. CEO seeded.\n")

if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_production_wipe.py -v
```
Expected: 3 PASS.

**Step 5: Author runbook**

Create `docs/runbooks/super-admin-bootstrap.md` documenting:
- The four env vars to set in Render before invoking
- One-shot Render Job command: `python -m scripts.production_wipe --yes-really`
- Post-wipe verification: log in via `/login` with portal=admin
- Rotation: scrub the four env vars from Render after first use

**Step 6: Commit**

```bash
git add scripts/production_wipe.py tests/test_production_wipe.py docs/runbooks/super-admin-bootstrap.md
git commit -m "feat(A1): production_wipe.py + first super admin bootstrap

Atomic TRUNCATE-then-INSERT-CEO. Env-var gated. APP_ENV guard.
Runbook documents Render Job invocation. Tests cover guard rails
+ end-to-end SQLite path."
```

---

## A2. Email transport: Gmail SMTP

**Files:**
- Modify: `app/email.py:1-86` (full rewrite of `_send`; signatures of `send_invite_email` / `send_password_reset_email` unchanged)
- Modify: `tests/test_auth.py` (or new `tests/test_email_transport.py`)
- Modify: `render.yaml` (env var declarations)
- Modify: `README.md` (env vars section)
- Modify: `.env.example` (add `GMAIL_USER`, `GMAIL_APP_PASSWORD`)

**Behavior:**
- New env vars: `GMAIL_USER` (default `operations@ufitonline.net`), `GMAIL_APP_PASSWORD` (no default).
- If `GMAIL_APP_PASSWORD` unset → log to stdout, return True (existing graceful no-op).
- If set → SMTP_SSL to `smtp.gmail.com:465`, login, sendmail, multipart/alternative with HTML + plaintext fallback.
- `FROM_ADDRESS` becomes `Ufit Motion <{GMAIL_USER}>`.
- Drop `RESEND_API_KEY` reference; leaving the env var deadweight is fine (don't crash if set).

**Step 1: Failing test — graceful no-op**

```python
# tests/test_email_transport.py
import os
from app import email as email_mod

def test_no_op_without_password(monkeypatch, capsys):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "")
    ok = email_mod.send_invite_email("a@b.com", "Ada", "head_coach", "tok123")
    assert ok is True
    out = capsys.readouterr().out
    assert "DEV MODE" in out

def test_send_uses_smtplib_when_configured(monkeypatch):
    sent = {}
    class FakeSMTP:
        def __init__(self, host, port): sent["host"]=host; sent["port"]=port
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, u, p): sent["login"]=(u,p)
        def sendmail(self, frm, to, msg): sent["sendmail"]=(frm,to,msg)
    monkeypatch.setattr(email_mod, "GMAIL_USER", "ops@ufitonline.net")
    monkeypatch.setattr(email_mod, "GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)
    ok = email_mod.send_invite_email("dst@x.com","Bo","head_coach","tok9")
    assert ok is True
    assert sent["host"] == "smtp.gmail.com"
    assert sent["port"] == 465
    assert sent["login"][0] == "ops@ufitonline.net"
    assert sent["sendmail"][0] == "ops@ufitonline.net"
    assert sent["sendmail"][1] == ["dst@x.com"]
    assert b"Set My Password" in sent["sendmail"][2] or "Set My Password" in sent["sendmail"][2]
```

**Step 2: Run — both tests fail (smtplib path doesn't exist).**

**Step 3: Rewrite `app/email.py`**

```python
import os, sys, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as _html_escape

APP_BASE_URL = os.environ.get("UFIT_APP_BASE_URL", "http://localhost:5000")
GMAIL_USER = os.environ.get("GMAIL_USER", "operations@ufitonline.net")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
FROM_ADDRESS = f"Ufit Motion <{GMAIL_USER}>"

def _send(to: str, subject: str, html: str) -> bool:
    if not GMAIL_APP_PASSWORD:
        print(f"[email] DEV MODE — would send to {to}\n  Subject: {subject}\n  (Set GMAIL_APP_PASSWORD to enable real delivery)", flush=True)
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_ADDRESS
        msg["To"] = to
        # Plaintext fallback — strip tags very minimally.
        import re
        plain = re.sub(r"<[^>]+>", " ", html)
        plain = re.sub(r"\s+", " ", plain).strip()
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.sendmail(GMAIL_USER, [to], msg.as_string())
        return True
    except Exception as exc:
        print(f"[email] Send failed: {exc}", file=sys.stderr, flush=True)
        return False

# send_invite_email() and send_password_reset_email() bodies unchanged.
```

**Step 4: Run tests — PASS.**

**Step 5: Update `render.yaml`** to declare `GMAIL_USER` and `GMAIL_APP_PASSWORD` envVars (sync: false). Update `.env.example` with the same keys. Append to README env table.

**Step 6: Commit**

```bash
git add app/email.py tests/test_email_transport.py render.yaml .env.example README.md
git commit -m "feat(A2): swap Resend → Gmail SMTP for transactional email

Boss is non-technical; this avoids any DNS work. Uses Google App
Password via GMAIL_APP_PASSWORD env. Same graceful no-op pattern.
Multipart HTML+plaintext."
```

---

## A3. Privacy Policy + Terms of Service pages

**Files:**
- Create: `templates/privacy.html`
- Create: `templates/terms.html`
- Modify: `app/routes/pages.py:23-53` (add `/privacy` and `/terms` static routes)
- Modify: `templates/index.html` (footer with links)
- Modify: `static/styles.css` (footer styles)
- Create: `tests/test_static_pages.py`

**Step 1: Failing tests**

```python
# tests/test_static_pages.py
def test_privacy_returns_200(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert b"Privacy Policy" in resp.data
    assert b"FERPA" in resp.data
    assert b"operations@ufitonline.net" in resp.data

def test_terms_returns_200(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    assert b"Terms of Service" in resp.data
```

**Step 2: Run — 404 on both.**

**Step 3: Implementation**

In `app/routes/pages.py`, BEFORE the catch-all `/<path:path>`:

```python
@pages_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")

@pages_bp.route("/terms")
def terms():
    return render_template("terms.html")
```

Author `templates/privacy.html` (FERPA-aware boilerplate, ~600 words) and `templates/terms.html` (acceptable use, no warranty, governing law = California). Both must:
- Inherit the same brand chrome (top blue bar with "UFIT MOTION").
- Have last-updated date at top.
- Include a "Contact: operations@ufitonline.net" section.
- Link back to `/` from a footer button.

In `templates/index.html`, add a `<footer>` with links to `/privacy`, `/terms`, and `mailto:operations@ufitonline.net`. Keep it visible on the login screen and authenticated pages (the SPA renders one body — footer can sit outside the SPA root div).

**Step 4: Run — 2 PASS.**

**Step 5: Commit**

```bash
git add templates/privacy.html templates/terms.html app/routes/pages.py templates/index.html static/styles.css tests/test_static_pages.py
git commit -m "feat(A3): self-authored Privacy Policy + Terms of Service

FERPA-aware boilerplate. Footer links from login + SPA shell.
Iteration assumed; no legal review yet."
```

---

## A4. Help/Support modal + feedback endpoint

**Files:**
- Modify: `app/routes/shared_routes.py` (new `POST /api/feedback`)
- Modify: `static/app.js` (top-nav Help button + modal)
- Modify: `static/styles.css` (modal styles if not already)
- Create: `tests/test_feedback.py`

**Behavior:**
- `POST /api/feedback` body: `{ subject, message, page_url }`
- Auth required (any logged-in user).
- Rate-limited (`5 per minute` via `limiter`).
- Server emails `operations@ufitonline.net` (via existing `_send`) with subject `[Ufit Feedback] <subject>` and body containing user email, role, page_url, message.
- Returns `{ ok: true }`.

**Step 1: Failing test**

```python
# tests/test_feedback.py
def test_feedback_requires_auth(client):
    resp = client.post("/api/feedback", json={"subject":"x","message":"y"})
    assert resp.status_code == 401

def test_feedback_sends_email(admin_client, monkeypatch):
    sent = []
    def fake_send(to, subject, html):
        sent.append((to, subject, html)); return True
    monkeypatch.setattr("app.email._send", fake_send)
    resp = admin_client.post("/api/feedback", json={
        "subject":"login broken","message":"i cant log in","page_url":"/login"
    })
    assert resp.status_code == 200
    assert sent and sent[0][0] == "operations@ufitonline.net"
    assert "login broken" in sent[0][1]
```

**Step 2: Run — 404/AttributeError.**

**Step 3: Implement endpoint in `shared_routes.py`** (look for existing `@shared_bp` or matching blueprint pattern; add at bottom). Auth gate via `current_user()`. Email sender as above.

**Step 4: Frontend** — add Help button to `static/app.js` topbar component. Open modal with `<form>` posting to `/api/feedback`. Modal includes:
- "Need help? Email operations@ufitonline.net or use the form below."
- Subject input, textarea, Submit.
- Auto-fills `page_url` from `location.pathname`.
- Shows toast on success.

**Step 5: Run tests — PASS. Manually click Help button in browser to confirm modal renders.**

**Step 6: Commit**

```bash
git add app/routes/shared_routes.py static/app.js static/styles.css tests/test_feedback.py
git commit -m "feat(A4): in-app Help & Feedback modal

Help button in top-nav opens modal posting to /api/feedback.
Server emails operations@ufitonline.net via Gmail SMTP. Rate-
limited 5/min."
```

---

## A5. Backup-restore drill + runbook

**Files:**
- Create: `docs/runbooks/backup-restore.md`

**Behavior:** This is operational, not code. The user runs Supabase Point-in-Time Recovery against a staging project to validate restore actually works, then documents the steps so future-us can do it under pressure.

**Steps:**
1. User opens Supabase dashboard → `adsewsosdnufmcjxinkj` → Database → Backups.
2. Click "Restore to a new project" → pick a timestamp from 5 minutes ago.
3. Wait for the restore (typically 5-15 min for our row count).
4. Connect with `psql` (or Supabase SQL editor) to the new project; run a smoke query: `SELECT COUNT(*) FROM students;`
5. Verify counts roughly match production.
6. Document the timing, the destination project name, and any quirks in `docs/runbooks/backup-restore.md`.
7. Decommission the staging project.

The runbook must contain:
- Exact dashboard click path
- Required env vars to point a local Flask at the restored DB for verification
- Estimated wall-clock time
- Cost note (Supabase charges for the staging project until deleted)
- "What to do if the restore fails" — open ticket with Supabase support, include project ref + timestamp

**Step 1: Author the runbook.**

**Step 2: Commit**

```bash
git add docs/runbooks/backup-restore.md
git commit -m "docs(A5): backup-restore drill runbook

Documents the Supabase PITR procedure. User to perform an actual
drill before first-school go-live and update timing notes."
```

---

# Phase B — Coach Onboarding

## B6. Multi-school coach assignment + login picker + top-nav switcher

**Files:**
- Modify: `app/routes/auth_routes.py:48-139` (login returns `assignments[]`)
- Modify: `app/routes/auth_routes.py` (new `POST /api/auth/select-school`)
- Modify: `app/routes/_helpers.py` (`current_school_id()` reads from session, falls back to single-assignment auto-select)
- Modify: `static/app.js` (school-picker screen + top-nav chip)
- Modify: `tests/test_auth.py`

**Behavior:**
- `POST /api/auth/login` response now includes `assignments`: an array of `{school_id, school_name, role}` for that user (active assignments only).
- If `len(assignments) == 1`, auto-select on the server (same response sets `session.current_school_id`).
- If `len(assignments) > 1`, response includes `"needs_school_selection": true`; frontend shows picker.
- New endpoint `POST /api/auth/select-school { school_id }` validates the user has an active assignment to that school, writes `session["current_school_id"]`, returns `{ ok: true, school: {...} }`.
- `_helpers.current_school_id()` reads `session.get("current_school_id")` first, falls back to the existing single-assignment query.
- All existing school-scoped endpoints continue working (they already call `current_school_id()`).

**Step 1: Failing tests**

```python
# tests/test_auth.py — append
def test_login_returns_assignments_array(client, make_user_with_staff, make_org, make_school):
    org = make_org(); s1 = make_school(org); s2 = make_school(org)
    u = make_user_with_staff(role="head_coach", school_id=s1, email="multi@x.com")
    # Add a 2nd assignment manually (factory only does 1).
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        db.execute("INSERT INTO staff_assignments (staff_id, school_id, assignment_role, start_date, active_status, created_at) VALUES (?,?,?,?,1,?)",
                   (u["staff_id"], s2, "head_coach", "2025-08-01", "2025-08-01"))
        # Set a known password.
        from werkzeug.security import generate_password_hash
        db.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                   (generate_password_hash("p@ssw0rd!", method="pbkdf2:sha256"), u["user_id"]))
        db.commit(); db.close()
    resp = client.post("/api/auth/login", json={"email":"multi@x.com","password":"p@ssw0rd!","portal":"coach"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "assignments" in body["user"]
    assert len(body["user"]["assignments"]) == 2
    assert body.get("needs_school_selection") is True

def test_select_school_writes_session(coach_client, make_org, make_school):
    # coach@ufit.com from fixture has no assignments — set one up
    org = make_org(); s = make_school(org)
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        sp = db.execute("SELECT staff_id FROM staff_profiles WHERE user_id=(SELECT user_id FROM users WHERE email='coach@ufit.com')").fetchone()
        db.execute("INSERT INTO staff_assignments (staff_id, school_id, assignment_role, start_date, active_status, created_at) VALUES (?,?,?,?,1,?)",
                   (sp["staff_id"], s, "head_coach", "2025-08-01", "2025-08-01"))
        db.commit(); db.close()
    resp = coach_client.post("/api/auth/select-school", json={"school_id": s})
    assert resp.status_code == 200
    assert resp.get_json()["school"]["school_id"] == s

def test_select_school_rejects_unassigned(coach_client, make_org, make_school):
    org = make_org(); s = make_school(org)
    resp = coach_client.post("/api/auth/select-school", json={"school_id": s})
    assert resp.status_code == 403
```

**Step 2: Run — 3 FAIL.**

**Step 3: Implementation**

In `app/routes/auth_routes.py`, after `session["user_id"] = row["user_id"]`:
- Replace the single-school SELECT with a multi-row query of all active assignments.
- If 1 assignment, set `session["current_school_id"]`.
- If >1 assignments, include `needs_school_selection: true` in response.
- Modify `serialize_user` (in `_helpers.py`) to accept and embed `assignments`.

Add new route:

```python
@auth_bp.route("/api/auth/select-school", methods=["POST"])
def select_school():
    user = current_user()
    if not user: return jsonify({"error":"Authentication required."}), 401
    data = parse_json()
    school_id = data.get("school_id")
    db = get_db()
    try:
        row = db.execute(
            """SELECT s.school_id, s.school_name FROM schools s
               JOIN staff_assignments sa ON sa.school_id=s.school_id AND sa.active_status=TRUE AND sa.deleted_at IS NULL
               JOIN staff_profiles sp ON sp.staff_id=sa.staff_id
               WHERE sp.user_id=? AND s.school_id=? AND s.deleted_at IS NULL""",
            (user["user_id"], school_id)).fetchone()
        if not row: return jsonify({"error":"You don't have an active assignment to that school."}), 403
        session["current_school_id"] = row["school_id"]
        return jsonify({"ok": True, "school": dict(row)})
    finally: db.close()
```

Update `_helpers.current_school_id()` (or equivalent) to prefer `session.get("current_school_id")`.

**Step 4: Frontend** — `static/app.js`:
- After login resolves, if `needs_school_selection` is true, render `<SchoolPickerScreen>` with cards for each assignment. Card click POSTs `/api/auth/select-school`, then routes to coach dashboard.
- Add a top-nav chip showing current school + dropdown of other assignments. Selecting one POSTs `/api/auth/select-school` then reloads the current page.

**Step 5: Run tests — 3 PASS. Manually verify the picker in the browser.**

**Step 6: Commit**

```bash
git add app/routes/auth_routes.py app/routes/_helpers.py static/app.js tests/test_auth.py
git commit -m "feat(B6): multi-school coach assignment + login picker + nav switcher

Login response now includes assignments[]. New /api/auth/select-school
writes session.current_school_id. Frontend renders picker when N>1
and a top-nav switcher chip for mid-day moves. Schema unchanged —
staff_assignments already supports it."
```

---

## B7. Bulk coach invite

**Files:**
- Modify: `app/routes/admin_routes.py` (new `POST /api/admin/coaches/bulk-invite`)
- Modify: `static/app.js` (Bulk Invite modal in admin Coaches view)
- Create: `tests/test_bulk_invite.py`

**Behavior:**
- Body: `{ rows: [{ first_name, last_name, email, role, school_ids[] }, ...], default_role }`
- Server validates each row (email format, role in allowlist, all school_ids exist & in admin's org).
- Per-row outcome: `{ row_index, status: "created"|"skipped_duplicate"|"error", message? }`.
- Response shape: `{ summary: { created: N, errors: M, duplicates: K }, results: [...] }`.
- Reuses existing invite-token + email flow from `create_user`.
- Wraps each row in try/except — never aborts the whole batch on one row.

**Step 1: Failing tests**

```python
# tests/test_bulk_invite.py
def test_bulk_invite_creates_pending_users(admin_client, make_org, make_school, monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)
    org = make_org(); s = make_school(org)
    rows = [
        {"first_name":"A","last_name":"X","email":"a@x.com","role":"head_coach","school_ids":[s]},
        {"first_name":"B","last_name":"Y","email":"b@y.com","role":"assistant_coach","school_ids":[s]},
    ]
    resp = admin_client.post("/api/admin/coaches/bulk-invite", json={"rows": rows})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["summary"]["created"] == 2
    assert body["summary"]["errors"] == 0

def test_bulk_invite_skips_duplicates_continues_batch(admin_client, make_org, make_school, monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)
    org = make_org(); s = make_school(org)
    admin_client.post("/api/users", json={"first_name":"A","last_name":"X","email":"a@x.com","role":"head_coach","school_id":s})
    rows = [
        {"first_name":"A","last_name":"X","email":"a@x.com","role":"head_coach","school_ids":[s]},  # dup
        {"first_name":"C","last_name":"Z","email":"c@z.com","role":"head_coach","school_ids":[s]},
    ]
    resp = admin_client.post("/api/admin/coaches/bulk-invite", json={"rows": rows})
    body = resp.get_json()
    assert body["summary"]["duplicates"] == 1
    assert body["summary"]["created"] == 1

def test_bulk_invite_rejects_invalid_email_per_row(admin_client, make_org, make_school):
    org = make_org(); s = make_school(org)
    rows = [{"first_name":"D","last_name":"W","email":"not-an-email","role":"head_coach","school_ids":[s]}]
    resp = admin_client.post("/api/admin/coaches/bulk-invite", json={"rows": rows})
    body = resp.get_json()
    assert body["summary"]["errors"] == 1
    assert "email" in body["results"][0]["message"].lower()
```

**Step 2: Run — 3 FAIL.**

**Step 3: Implementation** in `admin_routes.py`. Pattern:

```python
@admin_bp.route("/api/admin/coaches/bulk-invite", methods=["POST"])
@limiter.limit("10 per minute")
@admin_required
def bulk_invite_coaches():
    actor = current_user()
    data = parse_json()
    rows = data.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return jsonify({"error":"rows[] required"}), 400
    if len(rows) > 200:
        return jsonify({"error":"max 200 rows per batch"}), 400

    results, summary = [], {"created":0,"errors":0,"duplicates":0}
    db = get_db()
    try:
        for i, row in enumerate(rows):
            try:
                # Validate; resolve duplicates; create user with invite token; insert
                # staff_assignments per school_id; send invite email.
                # Same code path as create_user, but multi-school.
                ...
                summary["created"] += 1
                results.append({"row_index": i, "status":"created"})
            except DuplicateEmail:
                summary["duplicates"] += 1
                results.append({"row_index": i, "status":"skipped_duplicate"})
            except Exception as exc:
                summary["errors"] += 1
                results.append({"row_index": i, "status":"error","message":str(exc)})
        db.commit()
    finally:
        db.close()
    return jsonify({"summary": summary, "results": results})
```

**Step 4: Frontend** — Bulk Invite modal in Coaches tab:
- Textarea: paste `first,last,email,role` rows (one per line) OR upload CSV.
- "Default role" dropdown applies if a row omits role.
- "Default schools" multi-select applies if a row omits school_ids.
- Submit → show per-row table with green/red status icons.

**Step 5: Run tests — PASS.**

**Step 6: Commit**

```bash
git add app/routes/admin_routes.py static/app.js tests/test_bulk_invite.py
git commit -m "feat(B7): bulk coach invite (paste/CSV + per-row role)

POST /api/admin/coaches/bulk-invite. Per-row try/except so one
malformed row doesn't kill the batch. Reuses existing invite-token
+ email flow."
```

---

## B8. School invite code (Path 3 self-registration)

**Files:**
- Create: `migrations/supabase/step16_school_coach_invite_code.sql`
- Modify: `run_migrations.py:14-29` (append step16 to MIGRATIONS list)
- Modify: `app/database.py` (add SQLite shim for the new columns in `_apply_schema_to_sqlite()` if that pattern exists; otherwise rely on `ensure_column` at boot)
- Modify: `app/routes/admin_routes.py` (school detail returns code; new POST `/api/admin/schools/<id>/invite-code/regenerate`)
- Modify: `app/routes/auth_routes.py` (new public `POST /api/auth/coach-register`)
- Modify: `static/app.js` (school detail Copy + Regenerate buttons; coach portal "Sign up with school code" form)
- Create: `tests/test_school_invite_code.py`

**Migration `step16_school_coach_invite_code.sql`:**

```sql
-- step16: schools get a public invite code so coaches can self-register.
ALTER TABLE schools ADD COLUMN IF NOT EXISTS coach_invite_code TEXT;
ALTER TABLE schools ADD COLUMN IF NOT EXISTS coach_invite_code_expires_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_coach_invite_code ON schools(coach_invite_code) WHERE coach_invite_code IS NOT NULL;

-- Backfill: generate a code for any existing rows. Format: SCHOOL-<random8>-YYYY
UPDATE schools
SET coach_invite_code = UPPER(
      SUBSTRING(school_name FROM 1 FOR 3) || '-' ||
      SUBSTRING(MD5(school_id::text || NOW()::text) FOR 8) || '-' ||
      EXTRACT(YEAR FROM NOW())::text
    ),
    coach_invite_code_expires_at = NOW() + INTERVAL '180 days'
WHERE coach_invite_code IS NULL;
```

**Behavior:**
- `POST /api/auth/coach-register` body: `{ code, first_name, last_name, email, role }`
- Validates: code exists + not expired; email not already taken; role is `head_coach` or `assistant_coach` only (no admin escalation).
- Creates pending user (no password) + staff_profile + staff_assignment to that school + sends invite email (existing path).
- Audit `coach_self_register` with school_id.
- Rate limited `5 per hour per IP` — code is meant to be shared; brute-force search for valid codes is not.
- Admin endpoint `POST /api/admin/schools/<id>/invite-code/regenerate` regenerates and audits.

**Step 1: Failing tests**

```python
# tests/test_school_invite_code.py
def test_coach_register_with_valid_code_creates_pending_user(client, admin_client, make_org, make_school, monkeypatch):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)
    org = make_org(); s = make_school(org)
    # Ensure school has a code. Hit the migration-backfill path or set explicitly.
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        db.execute("UPDATE schools SET coach_invite_code='LCN-X7M9-2026', coach_invite_code_expires_at='2030-01-01' WHERE school_id=?", (s,))
        db.commit(); db.close()
    resp = client.post("/api/auth/coach-register", json={
        "code":"LCN-X7M9-2026","first_name":"Z","last_name":"K","email":"zk@x.com","role":"head_coach"
    })
    assert resp.status_code == 201

def test_coach_register_rejects_expired_code(client, make_org, make_school):
    org = make_org(); s = make_school(org)
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        db.execute("UPDATE schools SET coach_invite_code='OLD-CODE-2020', coach_invite_code_expires_at='2020-01-01' WHERE school_id=?", (s,))
        db.commit(); db.close()
    resp = client.post("/api/auth/coach-register", json={
        "code":"OLD-CODE-2020","first_name":"Z","last_name":"K","email":"zk2@x.com","role":"head_coach"
    })
    assert resp.status_code == 400

def test_coach_register_blocks_admin_role_escalation(client, make_org, make_school):
    org = make_org(); s = make_school(org)
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        db.execute("UPDATE schools SET coach_invite_code='ESC-CODE-2026', coach_invite_code_expires_at='2030-01-01' WHERE school_id=?", (s,))
        db.commit(); db.close()
    resp = client.post("/api/auth/coach-register", json={
        "code":"ESC-CODE-2026","first_name":"E","last_name":"V","email":"ev@x.com","role":"admin"
    })
    assert resp.status_code == 400

def test_admin_regenerate_invite_code(admin_client, make_org, make_school):
    org = make_org(); s = make_school(org)
    resp = admin_client.post(f"/api/admin/schools/{s}/invite-code/regenerate")
    assert resp.status_code == 200
    assert "code" in resp.get_json()
```

**Step 2: Run — 4 FAIL (route missing).**

**Step 3: Migration + endpoints**

- Author migration `step16_school_coach_invite_code.sql` and append filename to `MIGRATIONS` in `run_migrations.py`.
- Apply against the SQLite test schema: there's a SQLite schema-mirror file (likely `app/database.py` or a `migrations/sqlite/` mirror). Add the same columns there so tests can run.
- Implement `POST /api/auth/coach-register` and `POST /api/admin/schools/<id>/invite-code/regenerate` per the behavior spec.

**Step 4: Frontend**
- Coach portal login screen: add "Sign up with a school code" link → opens form (code, first/last/email).
- Admin school detail: show code with Copy + Regenerate buttons; show expiry.

**Step 5: Run tests — 4 PASS.**

**Step 6: Commit**

```bash
git add migrations/supabase/step16_school_coach_invite_code.sql run_migrations.py app/database.py app/routes/auth_routes.py app/routes/admin_routes.py static/app.js tests/test_school_invite_code.py
git commit -m "feat(B8): school invite code for coach self-registration

step16 migration adds schools.coach_invite_code + expires_at.
Public POST /api/auth/coach-register creates pending user.
Admin can Copy/Regenerate. Role allowlist blocks privilege escalation."
```

---

## B9. Edit Coach role + school modal

**Files:**
- Modify: `app/routes/admin_routes.py` (new `PATCH /api/admin/users/<id>/role`)
- Modify: `static/app.js` (Edit Coach modal with role + multi-school)
- Create: `tests/test_edit_coach.py`

**Behavior:**
- Body: `{ role, school_ids[] }`
- Permission: admin can change any non-CEO/admin role. CEO can change anyone except themselves.
- Cannot self-promote: actor.user_id != target.user_id when role-changing.
- Replaces `staff_assignments` rows for that staff_id atomically (mark old active=FALSE, INSERT new ones).
- Audits `role_changed` with `old_values: {role, school_ids[]}`, `new_values: {role, school_ids[]}`.

**Step 1: Failing tests**

```python
# tests/test_edit_coach.py
def test_admin_can_change_coach_role(admin_client, make_org, make_school, make_user_with_staff):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="assistant_coach", school_id=s, email="ac@x.com")
    resp = admin_client.patch(f"/api/admin/users/{u['user_id']}/role",
                              json={"role":"head_coach","school_ids":[s]})
    assert resp.status_code == 200

def test_admin_cannot_promote_to_ceo(admin_client, make_org, make_school, make_user_with_staff):
    org = make_org(); s = make_school(org)
    u = make_user_with_staff(role="head_coach", school_id=s, email="hc@x.com")
    resp = admin_client.patch(f"/api/admin/users/{u['user_id']}/role",
                              json={"role":"ceo","school_ids":[s]})
    assert resp.status_code == 403

def test_self_role_change_blocked(admin_client):
    # admin_client is admin@ufit.com (role=admin)
    from app.database import get_db
    from app import create_app
    with create_app().app_context():
        db = get_db()
        uid = db.execute("SELECT user_id FROM users WHERE email='admin@ufit.com'").fetchone()["user_id"]
        db.close()
    resp = admin_client.patch(f"/api/admin/users/{uid}/role",
                              json={"role":"head_coach","school_ids":[]})
    assert resp.status_code == 409
```

**Step 2: Run — FAIL (route missing).**

**Step 3: Implement endpoint.**

```python
@admin_bp.route("/api/admin/users/<int:user_id>/role", methods=["PATCH"])
@admin_required
def update_user_role(user_id: int):
    actor = current_user()
    data = parse_json()
    new_role = data.get("role")
    school_ids = data.get("school_ids") or []
    if actor["user_id"] == user_id:
        return jsonify({"error":"You cannot change your own role."}), 409
    if new_role not in ("coach_overseer","site_coordinator","head_coach","assistant_coach","principal","school_staff","parent","admin","ceo"):
        return jsonify({"error":"invalid role"}), 400
    if new_role in ("ceo","admin") and actor["role"] != "ceo":
        return jsonify({"error":"Only CEO can grant admin/ceo roles."}), 403
    db = get_db()
    try:
        target = db.execute("SELECT user_id, role FROM users WHERE user_id=? AND deleted_at IS NULL",(user_id,)).fetchone()
        if not target: return jsonify({"error":"User not found"}), 404
        if target["role"] in ("ceo","admin") and actor["role"] != "ceo":
            return jsonify({"error":"Only CEO can demote admin/ceo accounts."}), 403
        ts = now_utc()
        old_assignments = [r["school_id"] for r in db.execute(
            """SELECT sa.school_id FROM staff_assignments sa
               JOIN staff_profiles sp ON sp.staff_id=sa.staff_id
               WHERE sp.user_id=? AND sa.active_status=TRUE""",(user_id,)).fetchall()]
        db.execute("UPDATE users SET role=? WHERE user_id=?", (new_role, user_id))
        sp = db.execute("SELECT staff_id FROM staff_profiles WHERE user_id=?",(user_id,)).fetchone()
        if sp:
            db.execute("UPDATE staff_assignments SET active_status=FALSE WHERE staff_id=?",(sp["staff_id"],))
            for sid in school_ids:
                db.execute("""INSERT INTO staff_assignments (staff_id, school_id, assignment_role, start_date, active_status, created_at)
                              VALUES (?,?,?,?,TRUE,?)""",(sp["staff_id"], sid, new_role, ts[:10], ts))
        audit(db, actor["user_id"], "role_changed", "users", user_id,
              old_values={"role":target["role"],"school_ids":old_assignments},
              new_values={"role":new_role,"school_ids":school_ids})
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
```

**Step 4: Frontend** — Edit Coach modal:
- Triggered by "Edit" button on each row of admin Coaches table.
- Role dropdown (same options as Add Coach).
- Multi-select school list.
- Save → PATCH endpoint, refresh table, toast.

**Step 5: Run tests — PASS.**

**Step 6: Security review** — invoke `security-reviewer` agent on the diff (auth-route work per AGENTS.md).

**Step 7: Commit**

```bash
git add app/routes/admin_routes.py static/app.js tests/test_edit_coach.py
git commit -m "feat(B9): Edit Coach role + school modal (PATCH /api/admin/users/<id>/role)

Role + multi-school assignment edit. Self-edit blocked.
CEO-only on admin/ceo grants. Audit log captures old → new."
```

**End of Phase B — push to Render.**

```bash
git push origin main
```

Verify Render deploy succeeds, smoke-test login + multi-school picker on production URL.

---

# Phase C — UX Polish

## C10. Reporting exports (CSV / PDF)

**Files:**
- Modify: `app/routes/admin_routes.py` (new `GET /api/admin/<resource>/export.csv` for schools, coaches, students)
- Modify: `app/routes/principal_routes.py` (`GET /api/students/<id>/progress.pdf`)
- Modify: `static/app.js` (Export buttons on each table)
- Add: `weasyprint` to `requirements.txt` (or use jinja → server-rendered HTML the user prints to PDF; weasyprint adds 50MB to Render slug, prefer print-stylesheet HTML)
- Create: `tests/test_exports.py`

**Decision:** Use server-rendered HTML with print-only CSS. User clicks "Print PDF" in the rendered page → browser saves PDF. No weasyprint dependency.

**Step 1: Failing tests**

```python
# tests/test_exports.py
def test_schools_csv_export(admin_client, make_org, make_school):
    org = make_org(); make_school(org, name="Lincoln")
    resp = admin_client.get("/api/admin/schools/export.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"Lincoln" in resp.data

def test_student_progress_html_print(admin_client, make_org, make_school, make_student):
    org = make_org(); s = make_school(org); st = make_student(s, first="Z", last="Q")
    resp = admin_client.get(f"/api/students/{st}/progress.print")
    assert resp.status_code == 200
    assert b"Z Q" in resp.data
```

**Step 2-5:** Implement CSV streaming (`Content-Type: text/csv`, `Content-Disposition: attachment; filename=...`) and a print-only HTML template at `templates/student_progress_print.html`. Include print stylesheet (`@media print { ... }`).

**Step 6: Commit**

```bash
git add app/routes/admin_routes.py app/routes/principal_routes.py templates/student_progress_print.html static/app.js tests/test_exports.py
git commit -m "feat(C10): CSV exports + print-friendly student progress

CSV streaming for schools/coaches/students. Server-rendered HTML
report with @media print stylesheet — user prints to PDF via
browser. Avoids weasyprint slug bloat."
```

---

## C11. Audit log viewer

**Files:**
- Modify: `app/routes/admin_routes.py` (new `GET /api/admin/audit-log` with filters)
- Modify: `static/app.js` (new Audit page, admin-only)
- Create: `tests/test_audit_log_viewer.py`

**Behavior:**
- Filters: `user_id`, `action`, `table_name`, `date_from`, `date_to`, `limit` (default 50, max 500).
- CEO/admin only.
- Returns paginated rows with `created_at`, `actor_email`, `action`, `table_name`, `record_id`, `old_values`, `new_values`.

**Step 1: Failing test**

```python
def test_audit_log_returns_recent_entries(admin_client):
    resp = admin_client.get("/api/admin/audit-log?limit=10")
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["entries"], list)
```

**Step 2-5:** Implement endpoint with parameterized SQL (no string concat) + frontend table with filter form.

**Step 6: Commit**

```bash
git add app/routes/admin_routes.py static/app.js tests/test_audit_log_viewer.py
git commit -m "feat(C11): admin audit log viewer with filters"
```

---

## C12. Empty-state onboarding cards

**Files:**
- Modify: `static/app.js` (replace generic "No coaches yet" empty states)
- Modify: `static/styles.css` (card styling)

**Behavior:** When the admin dashboard, coaches list, or students list is empty, show a checklist card:
- ✓ Add a school
- ☐ Add coaches
- ☐ Import students
- ☐ Schedule first session

Each unchecked row is a button that takes admin to the relevant action.

**Steps:**
1. Edit the empty-state branches in `app.js` for each table.
2. Add `.onboarding-card` CSS in `styles.css`.
3. Manual browser test on a wiped DB.
4. Commit.

```bash
git add static/app.js static/styles.css
git commit -m "feat(C12): empty-state onboarding checklist cards"
```

---

## C13. Forgot-password covers pending users

**Files:**
- Modify: `app/routes/auth_routes.py:284-336` (the existing `/api/auth/forgot-password` route)
- Modify: `tests/test_auth.py`

**Behavior:** Currently rejects pending-invite users (no password_hash). Allow them through — emit a fresh invite token + invite email. Same code path as `send_user_invite`.

**Step 1: Failing test**

```python
def test_forgot_password_works_for_pending_user(client, admin_client, monkeypatch, make_org, make_school):
    monkeypatch.setattr("app.email._send", lambda *a, **kw: True)
    org = make_org(); s = make_school(org)
    admin_client.post("/api/users", json={"first_name":"P","last_name":"P","email":"pending@x.com","role":"head_coach","school_id":s})
    # No password set yet — pending invite.
    resp = client.post("/api/auth/forgot-password", json={"email":"pending@x.com"})
    assert resp.status_code == 200
```

**Step 2-5:** Drop the `password_hash IS NOT NULL` filter (if present) in the SELECT; treat pending users as eligible.

**Step 6: Commit**

```bash
git add app/routes/auth_routes.py tests/test_auth.py
git commit -m "fix(C13): forgot-password emits invite for pending users"
```

---

## C14. Notifications coverage audit

**Files:**
- Modify: `app/routes/coach_routes.py` (incident filed → notify org admins)
- Modify: `app/routes/admin_routes.py` (parent-registers → notify, pending-invite-expiring → notify)
- Modify: `app/routes/auth_routes.py` (parent register, coach self-register notify admins)

**Step 1: Audit list each state-changing route via grep:**

```bash
grep -rn "INSERT INTO notifications" app/routes/
grep -rn "@admin_bp.route.*POST\|@coach_bp.route.*POST" app/routes/
```

For each state-change without a `notifications` insert, decide if it warrants one. Write a test asserting the notification row appears.

**Step 2: Implement missing notifications.**

**Step 3: Run full test suite.**

**Step 4: Commit**

```bash
git add app/routes/ tests/
git commit -m "feat(C14): notifications coverage on incident/registration paths"
```

---

## C15. Schools page principal status indicator

**Files:**
- Modify: `app/routes/admin_routes.py:173-208` (`list_schools` already returns coach counts; add `principal_status` field)
- Modify: `static/app.js` (render badge in schools table)

**Behavior:** Mirror coach pending-invite badge pattern. Each school row shows:
- "Principal: Sarah Smith ✓ Active" (green dot)
- "Principal: Jane Doe ⏱ Pending Invite [Resend]" (yellow dot + button)
- "Principal: — Not assigned" (gray)

**Steps:**
1. Modify `list_schools` SQL to LEFT JOIN principal user via `staff_assignments`.
2. Compute `principal_status` ∈ {`active`, `pending_invite`, `none`}.
3. Render badges in `app.js`.
4. Resend button hits the existing `/api/admin/users/<id>/send-invite`.
5. Commit.

```bash
git add app/routes/admin_routes.py static/app.js
git commit -m "feat(C15): schools table shows principal active/pending/none badges"
```

**End of Phase C — push to Render.**

```bash
git push origin main
```

---

# Phase D — Walkthrough HTML

## D16. `docs/walkthrough.html`

**Files:**
- Create: `docs/walkthrough.html`

**Behavior:** Single self-contained HTML file mirroring the format of existing `demo.html`. 16 scenes covering admin/coach/principal/parent journeys. Press-play, captioned, mouse-cursor visible, no audio. Section bookmarks sidebar. Target ~10 min auto-play.

**Steps:**
1. Read `demo.html` (70KB, already in repo) to copy CSS/JS scaffolding for cursor animation, scene transitions, captions.
2. Author 16 scenes per the design doc list.
3. Side-by-side test in browser at `file:///.../docs/walkthrough.html`.
4. Commit.

```bash
git add docs/walkthrough.html
git commit -m "feat(D16): walkthrough.html — 16 scenes, ~10 min animated demo

Press-play, captioned, mouse-visible. Mirrors demo.html scaffolding.
Self-contained — no external deps."
```

**Push to Render.**

```bash
git push origin main
```

---

# Cross-cutting concerns

## Deploy verification (after each phase push)

1. Render dashboard → wait for green deploy.
2. Hit `/health` and `/api/auth/session` (logged out) — both should 200.
3. Log in via portal that exercises the new code path.
4. Spot-check one of the new tests against production DB by running a manual curl.

## Super-admin runbook (referenced from Phase A1)

After A1 ships, but BEFORE first-school onboarding:
1. User sets four `SUPER_ADMIN_*` env vars in Render.
2. User runs the wipe via Render Job: `python -m scripts.production_wipe --yes-really`.
3. User immediately scrubs the four env vars from Render.
4. User logs into `/login` via Admin portal.
5. User changes their password through the in-app Change Password modal (so the env-var-supplied password isn't lingering anywhere).

## Rollback plan

If any phase causes production breakage:
1. `git revert <hash>` of the offending commit.
2. `git push origin main` — Render redeploys the prior version.
3. If Supabase migration was applied, write a rollback SQL file (e.g. `step16_rollback.sql`) and apply manually via SQL Editor.

---

# Execution order summary

```
A1 → A2 → A3 → A4 → A5  → push
B6 → B7 → B8 → B9       → push
C10 → C11 → C12 → C13 → C14 → C15  → push
D16  → push
```

After each commit, run `pytest -x` to confirm nothing prior regressed. After each phase push, do the deploy verification checklist above.
