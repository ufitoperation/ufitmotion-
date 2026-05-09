# Supabase Point-in-Time Restore — Runbook

**When to use:** A drill before first-school go-live, OR a real emergency restore (accidental wipe, corrupted migration, hostile-user data destruction).

**Authoritative source:** Supabase docs — [Point-in-Time Recovery (PITR)](https://supabase.com/docs/guides/platform/backups). This runbook captures the steps that actually matter for our project, plus our timing notes.

---

## Pre-flight

- [ ] You know the **target timestamp** in UTC (e.g. "5 minutes before the bad migration ran"). Round DOWN, not up — you can replay forward, but you can't replay back what you re-truncate.
- [ ] You have access to the Supabase dashboard for project `adsewsosdnufmcjxinkj`.
- [ ] You have the Render dashboard open in another tab — you'll need to swap `DATABASE_URL` if you decide to point production at the restored DB.
- [ ] You have **at least 30 minutes** of uninterrupted time. Restores are not instant; smoke-checks afterward are not optional.
- [ ] You have **not** run any migrations against the bad DB after the incident. If you did, stop and write down what they were before continuing — the restore won't include them.

---

## Path 1 — Drill (recommended before go-live)

**Goal:** Prove the restore mechanism works, document timing, and decommission cleanly. **No production change** until you've completed at least one drill.

### Step 1 — Take a fresh snapshot
1. Supabase → project `adsewsosdnufmcjxinkj` → **Database → Backups**.
2. Click **Take a backup now**. Wait until it appears as "Completed" (typically <2 min).
3. Note the timestamp (UTC).

### Step 2 — Restore to a NEW project
1. Stay on the Backups page.
2. On the snapshot row, click **⋯ → Restore to new project**.
3. Pick the timestamp from Step 1.
4. Name the new project `ufit-motion-restore-test-YYYYMMDD`.
5. Pick the same region (`us-east-1`).
6. Click **Restore**.

   This takes 5–15 min for our row count (≈30 students + assessments + 32 tables). Track wall-clock.

### Step 3 — Smoke-check the restored DB
1. New project → **SQL Editor**.
2. Run:
   ```sql
   SELECT COUNT(*) AS schools FROM schools WHERE deleted_at IS NULL;
   SELECT COUNT(*) AS students FROM students WHERE deleted_at IS NULL;
   SELECT COUNT(*) AS users FROM users WHERE deleted_at IS NULL;
   SELECT COUNT(*) AS sessions FROM sessions WHERE deleted_at IS NULL;
   SELECT COUNT(*) AS assessments FROM assessments WHERE deleted_at IS NULL;
   SELECT COUNT(*) AS skills FROM skills;  -- preserved set; should match production
   SELECT MAX(created_at) AS most_recent_user FROM users;
   ```
3. Compare counts to production (run the same query in the production project's SQL editor). They should match.
4. Note any drift (audit_log can be off by a row or two — not actionable). Schools / students / users must match.

### Step 4 — Optional — point a local Flask at the restored DB
1. Get the new project's connection string (Database → Connection string → **transaction pooler**).
2. In a fresh terminal:
   ```bash
   export DATABASE_URL='postgresql://postgres.<project>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres'
   export APP_ENV=development
   export UFIT_SECRET_KEY='temp-drill-key'
   export UFIT_APP_BASE_URL='http://localhost:5000'
   python wsgi.py  # or: flask --app wsgi:app run
   ```
3. Open `http://localhost:5000`. Log in with a known coach / admin account from production. Verify the dashboard loads and shows the expected data.

### Step 5 — Decommission
1. Supabase → restore-test project → **Settings → General → Delete project**.
2. Confirm. **Do not skip this** — the project bills until deleted.
3. Update `docs/runbooks/backup-restore.md` with your actual timing notes (see "Timing log" at the bottom of this file).

---

## Path 2 — Real emergency restore

**Use only when production data is actually lost or corrupted.**

### Step 1 — Stop write traffic
- Render dashboard → `ufit-motion` service → **Suspend Service**. (You'd rather have a blank 503 page than additional writes against the bad DB.)

### Step 2 — Take a snapshot of the bad DB anyway
Even if it's corrupted, you want a forensic copy before you overwrite it.
1. Supabase → Backups → **Take a backup now**.
2. Note the snapshot ID. Don't restore from this; just keep it.

### Step 3 — Restore to a new project at the target timestamp
Same as Path 1 Step 2, but pick the timestamp BEFORE the incident.

### Step 4 — Validate the restored project
Run the smoke-check queries (Path 1 Step 3) AGAINST THE RESTORED PROJECT. Confirm row counts match what you expected at that timestamp.

### Step 5 — Cut over production
1. New project → Settings → Connection string → copy the **transaction pooler** DSN.
2. Render → `ufit-motion` → Environment → update `DATABASE_URL` → save.
3. **Resume Service**.
4. Hit `/api/health` until it returns `{"db": true}`.
5. Smoke-test the app: log in, view a known school, view a known student.

### Step 6 — Re-apply any migrations that ran AFTER the incident timestamp
If migrations ran between the restore point and now, they will not be present in the restored project. Re-apply them via `python run_migrations.py` (or via Supabase SQL editor for individual `step*.sql` files).

### Step 7 — Notify
- Email `operations@ufitonline.net` with: incident timestamp, restore point, what was lost, what was recovered, ETA for any data the restore couldn't cover.
- Update the operational log (`docs/runbooks/operational-log.md`).

### Step 8 — Decommission the original (bad) project
Wait at least 7 days before deleting the original project — you may want to forensically inspect it. Then delete via Settings → General.

---

## Cost notes

- Each restore creates a new Supabase project. Free-tier projects are limited per Supabase account; verify the new project doesn't push you over the limit.
- A staged restore project costs ~$25/month at the Pro tier. Decommission when done.
- A drill-restore project deleted within 24 hours is typically prorated to a few cents.

---

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| "Restore failed" in Supabase dashboard | Snapshot is too old (PITR retention is 7 days on the Pro tier) | Open a Supabase support ticket — they may have longer retention you can request |
| New project's row counts wildly off | You picked the wrong timestamp | Try again with a different timestamp; PITR is granular to the second |
| `psql` connection from your laptop fails | IPv6-only direct host | Use the **transaction pooler** DSN (`aws-0-us-east-1.pooler.supabase.com:6543`) — never the direct one |
| `init_db()` errors on app boot | A migration ran after the restore point but isn't in the restored DB | Re-apply that migration via `python run_migrations.py` |
| Render service comes back but UI is blank | Frontend cached on old JS that expects fields the restored schema lacks | Hard-refresh / verify the restored migration step matches what the frontend expects |

---

## Timing log

Update this with the actual numbers when you do a drill.

| Date | Snapshot → restore (wall-clock) | Restore → smoke-pass (wall-clock) | Total minutes | Notes |
|---|---|---|---|---|
| _drill not yet run_ | | | | _fill in after first drill before go-live_ |

---

## Why we drill before go-live

The first time we discover restore doesn't work the way we thought is the wrong time to find out. A 30-minute drill before onboarding the first school protects against:
- Misunderstanding which DSN to use
- Migrations that depend on out-of-band setup
- FK chains that didn't survive the restore for whatever reason
- Realizing we actually need the direct DSN, not the pooler

If the drill passes, file the runbook and move on. If it fails, fix the gap before any real customer data lives in the system.
