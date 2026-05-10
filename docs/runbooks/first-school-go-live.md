# First-School Go-Live — Operator Handoff

**Date:** 2026-05-09
**Author:** Claude (Opus 4.7) — autonomous build session
**Audience:** TJ (you, doing this from your laptop alone)
**Goal:** Walk you through every step needed to take the 18-commit build live and onboard the first school.

---

## What got built (one-line summary per item)

| Item | Status | What it does |
|---|---|---|
| Plan | ✓ committed | `docs/plans/2026-05-09-first-school-onboarding-implementation.md` — 16-item TDD implementation plan |
| **A1** wipe script | ✓ tested | `scripts/production_wipe.py` — atomic TRUNCATE + first CEO from env vars |
| **A2** Gmail SMTP | ✓ tested | `app/email.py` rewritten — replaces Resend with Gmail App Password |
| **A3** Privacy + Terms | ✓ tested | `templates/privacy.html`, `templates/terms.html`, footer in SPA shell |
| **A4** Help modal | ✓ tested | Help button in top-nav, `/api/feedback` posts to `operations@ufitonline.net` |
| **A5** Backup runbook | ✓ shipped | `docs/runbooks/backup-restore.md` — Supabase PITR drill procedure |
| **B6** Multi-school picker | ✓ tested | Login returns `assignments[]`, picker UI, top-nav switcher chip |
| **B7** Bulk coach invite | ✓ tested | `POST /api/admin/coaches/bulk-invite` paste-CSV with per-row errors |
| **B8** School invite code | ✓ tested | `step16` migration + `/api/auth/coach-register` self-register flow |
| **B9** Edit coach role | ✓ tested | `PATCH /api/admin/users/<id>/role` with audit log + permission gates |
| **C10** CSV exports | ✓ tested | Schools / Coaches / Students CSV download buttons |
| **C11** Audit log API | ✓ tested | `GET /api/admin/audit-log` with filters (frontend page deferred) |
| **C12** Empty-state cards | ✓ shipped | Admin dashboard onboarding checklist when zero data |
| **C13** Forgot-password | ✓ tested | Pending users now get a fresh invite via forgot-password |
| **C14** Notifications | ✓ shipped | Admin notified on parent + coach self-register |
| **C15** Principal badge | ✓ shipped | Schools table shows principal active / pending / none |
| **D16** Walkthrough | ✓ shipped | `docs/walkthrough.html` — 16-scene ~10-min press-play video |

**Tests for new code:** 55 written, 55 passing.
**Pre-existing test failures NOT caused by this work:** ~129 unrelated to anything I added (CSRF + scrypt + others — flagged for a future cleanup pass; do not block go-live).

---

## What you need to do, in order

### Step 1 — Push to Render

Nothing has been pushed to GitHub yet. From your laptop:

```bash
cd ~/Desktop/ufit-motion
git push origin main
```

Render auto-deploys on push. Wait for green in the dashboard (~3-5 min). The deploy will succeed even if the env vars below aren't set yet — the new code is backwards-compatible (it just won't email anything until Step 3 is done).

### Step 2 — Apply the new Supabase migration

Only ONE new migration was added: **step16** for school invite codes.

Two ways:

**(A) Via Render Shell (one-click from dashboard):**

1. Render dashboard → `ufit-motion` → **Shell** tab.
2. Run:
   ```bash
   python run_migrations.py
   ```
3. The script is idempotent — already-applied steps are no-ops. You'll see `step16_school_coach_invite_code.sql` apply.

**(B) Via Supabase SQL Editor (manual):**

1. Open Supabase project `adsewsosdnufmcjxinkj` → **SQL Editor**.
2. Paste the contents of `migrations/supabase/step16_school_coach_invite_code.sql`.
3. Run.

Either path works. Render Shell is easier because it uses the same DSN your app already uses.

### Step 3 — Set new Render env vars

Go to Render dashboard → `ufit-motion` → **Environment**.

**Required NOW (otherwise emails silently no-op):**

| Key | Value |
|---|---|
| `GMAIL_USER` | `operations@ufitonline.net` (or whichever Google Workspace mailbox you want as the sender) |
| `GMAIL_APP_PASSWORD` | A 16-character Google App Password — generate at https://myaccount.google.com/apppasswords (you must have 2-Step Verification enabled on the account first) |

**Required ONLY for the wipe step (Step 4 below) — temporary:**

| Key | Value |
|---|---|
| `SUPER_ADMIN_EMAIL` | The CEO email (e.g. `ceo@ufitonline.net`) |
| `SUPER_ADMIN_PASSWORD` | A strong 12+ character password (don't reuse) |
| `SUPER_ADMIN_FIRST` | First name (e.g. `Miss`) |
| `SUPER_ADMIN_LAST` | Last name (e.g. `A`) |

**Legacy env vars you can leave alone or remove** (they're no longer read; they don't hurt):
- `RESEND_API_KEY`
- `EMAIL_FROM`

Click **Save Changes**. Render will redeploy automatically (~2 min).

### Step 4 — Run the production wipe + first-CEO bootstrap

⚠️ This **deletes all operational data** (organizations, schools, students, coaches, sessions, etc.) and creates the first CEO from the env vars in Step 3. Static data — skill catalog, app settings — survives.

You're aware: per the design, this is intentional. Miss A's seeded account, the 30 demo students at Lincoln, the LAUSD demo data — everything goes.

Run from Render Shell:

```bash
python -m scripts.production_wipe --yes-really
```

Expected output: `[wipe] complete. CEO seeded as <email>.`

If it refuses with exit code 2, check that `APP_ENV=production` is set in Render env.
If it refuses with exit code 3, check that all four `SUPER_ADMIN_*` env vars are set.

### Step 5 — Log in + change password

1. Visit `https://ufit-motion.onrender.com/login` (or your prod URL).
2. Click **Admin Portal**.
3. Sign in with `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD`.
4. From the dashboard, open **Settings → Change Password**. Set a new password (different from the env-var one).

   Why: the env-var password sat in three places (Render env, your terminal scrollback, possibly your clipboard). Rotating it now reduces blast radius.

### Step 6 — Scrub the temporary env vars

Render dashboard → Environment → delete:
- `SUPER_ADMIN_PASSWORD` (definitely — this is the secret)
- `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_FIRST`, `SUPER_ADMIN_LAST` (optional — they're not secrets, just dead weight)

Save Changes. Render redeploys.

After this, the wipe script refuses to run (exit code 3 — missing env vars) until you explicitly re-set them, which is the desired safety posture.

### Step 7 — Run the backup-restore drill (do this BEFORE you onboard the first school)

Don't skip this. The first time you discover restore doesn't work the way you thought is the wrong time to find out.

Follow `docs/runbooks/backup-restore.md` Path 1 (Drill). Budget 30 minutes. Update the timing log at the bottom of that file with your actual numbers.

### Step 8 — Onboard the first school

You're now ready. From the admin dashboard:

1. **Add School** modal → enter the school's details + principal email. Principal gets an auto-invite email.
2. **Coaches → Bulk Invite** → paste the coach roster as CSV. Each coach gets an auto-invite email.
3. **Students → Import CSV** → drop the school's roster. Students get the local-identifier-based parent-verification key.
4. Optional: copy the school's invite code (visible after Step 2-B; admin endpoint `POST /api/admin/schools/<id>/invite-code/regenerate` rotates it). Hand it to the school's HR rep so any new hires can self-register without you knowing first.

### Step 9 — Show the boss the walkthrough

Open `docs/walkthrough.html` from your laptop in any browser (it's a single self-contained file). Press **▶ Play**. ~10 minutes auto-play through 16 scenes covering admin / coach / principal / parent journeys.

This is what you walk her through to demo the platform without needing live data.

---

## Quick reference — new endpoints

All admin-gated unless marked public.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/feedback` | (auth required) In-app help/feedback → emails ops |
| POST | `/api/auth/select-school` | (auth) Multi-school coach picks active school |
| POST | `/api/auth/coach-register` | **Public** — self-register with school invite code |
| POST | `/api/admin/coaches/bulk-invite` | Paste/CSV bulk coach invite |
| POST | `/api/admin/schools/<id>/invite-code/regenerate` | Rotate school invite code |
| PATCH | `/api/admin/users/<id>/role` | Edit coach role + school assignments |
| GET | `/api/admin/schools/export.csv` | Schools CSV download |
| GET | `/api/admin/coaches/export.csv` | Coaches CSV download |
| GET | `/api/admin/students/export.csv` | Students CSV download |
| GET | `/api/admin/audit-log` | Audit log with filters |

---

## Things I deliberately deferred

These are explicitly NOT in this build but would be reasonable follow-ups:

- **Frontend admin Audit-Log viewer page** (C11 backend shipped — UI is one focused slice)
- **Frontend Edit Coach modal** (B9 backend shipped — admin can hit the PATCH endpoint via DevTools today)
- **Admin Schools detail Copy / Regenerate UI for invite code** (B8 backend shipped — admin can hit the regenerate endpoint via DevTools)
- **Pending-invite-expiring-soon notifications** (C14 — needs a cron job; pattern exists in `render.yaml` for ufit-coach-score-recalc)
- **Walkthrough cursor animation per scene** (D16 v1 ships press-play; pixel-perfect choreography is iteration 2)
- **Print-friendly student progress page** (C10 — CSV is shipped; print-PDF is a stretch goal)
- **Pre-existing test suite cleanup** — ~129 tests fail unrelated to this work (CSRF + scrypt issues that pre-date this session). Untouched here on purpose; needs a focused pass.

None of these block first-school onboarding.

---

## If something breaks

- **Render deploy fails** → check `gunicorn` logs in Render dashboard. Most likely a typo in env vars or a missing migration.
- **Login works but emails don't arrive** → `GMAIL_APP_PASSWORD` is wrong or 2FA isn't enabled on the Google Workspace account. Test with `python -c "from app.email import _send; _send('your-personal@gmail.com', 'test', '<p>hi</p>')"` from Render Shell.
- **Wipe script refused to run** → exit code 2 means `APP_ENV` ≠ `production`; exit code 3 means missing env var; exit code 4 means password too short.
- **A coach can't see a school they should** → check `/api/admin/audit-log?action=role_changed` and look at the `school_ids` field. If wrong, hit `PATCH /api/admin/users/<id>/role` with the correct `school_ids[]`.
- **Database emergency** → `docs/runbooks/backup-restore.md` Path 2.

For anything else, the in-app Help button in the top-nav posts straight to `operations@ufitonline.net`.

---

## Commits this session (18 total)

```
7b055be feat(D16): docs/walkthrough.html — 16-scene press-play walkthrough
1bde523 feat(C14): notifications coverage on parent + coach self-register
379afd3 feat(C11): GET /api/admin/audit-log with filters
c91d1f8 feat(C10): CSV exports for schools / coaches / students
91a9174 feat(C12): empty-state onboarding checklist on admin dashboard
bc97e24 feat(C15): schools table principal status badge
803a597 fix(C13): forgot-password also covers pending-invite users
110a12c feat(B9): edit coach role + school assignments
7b6571c feat(B8): school invite code — coach self-registration (Path 3)
44390af feat(B7): bulk coach invite (paste/CSV)
50e6437 feat(B6): multi-school coach picker + login response shape
d6fd3e7 fix(tests): admin_client / coach_client use pbkdf2:sha256
d6a4a8c docs(A5): backup-restore runbook
107c7f5 feat(A4): in-app Help & Feedback modal + /api/feedback
8525866 feat(A3): self-authored Privacy Policy + Terms of Service
47d3fd9 feat(A2): swap Resend → Gmail SMTP for transactional email
074684c feat(A1): production_wipe.py + first super admin bootstrap
58565dc plan: implementation plan (16 items, 4 phases)
```
