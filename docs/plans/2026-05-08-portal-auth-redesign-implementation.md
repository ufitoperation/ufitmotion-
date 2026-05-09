# Portal Auth Redesign — Implementation Plan

> **For Claude:** Implement task-by-task. Demo deadline is tomorrow (2026-05-09), so prioritize working code over exhaustive tests. Manual browser verification at the end of each task is sufficient. Commit after each task.

**Goal:** Build a 4-portal login screen with parent self-registration, admin-driven invite emails, and auto-login creation when adding schools/coaches — all demo-ready by tomorrow.

**Architecture:** Backend changes wire the existing `send_invite_email()` (already gracefully no-ops without API key) into user/school creation. Frontend gets a 4-card portal selector and a parent registration flow. The existing `?reset_token=` URL handler and set-password screen are reused for invite consumption.

**Tech Stack:** Flask, vanilla JS SPA, PostgreSQL/Supabase, Resend (email — graceful no-op without key).

---

## Existing Assets (Do Not Rewrite)

| Asset | Location | Status |
|-------|----------|--------|
| `send_invite_email()` | `app/email.py:45` | Works, no-ops without `RESEND_API_KEY` |
| `send_password_reset_email()` | `app/email.py:67` | Works, same graceful pattern |
| `POST /api/auth/reset-password` | `app/routes/auth_routes.py:326` | **Needs fix** — requires `active_status=TRUE`, must allow inactive users to consume invite |
| `POST /api/admin/users/<id>/send-invite` | `app/routes/admin_routes.py:710` | Works, just needs frontend Resend button |
| `?reset_token=...` URL handler | `static/app.js:5022` | Works end-to-end |
| `renderSetPasswordScreen()` | `static/app.js:5022+` | Works, no changes needed |
| `notify_school_created()` HubSpot company+contact | `app/routes/_hubspot.py` | Works, pattern to follow for parent helper |
| User delete "last CEO" guard | `app/routes/admin_routes.py:670` | Already exists, mirror for deactivate |

---

## Task Sequencing

```
Phase 1 — Backend (sequential)
  Task 1.1: Allow inactive users to consume invite token (reset-password endpoint)
  Task 1.2: Auto-invite on POST /api/users
  Task 1.3: Auto-invite on POST /api/schools (when principal email present)
  Task 1.4: Add account_status to user list responses
  Task 1.5: Last-CEO deactivation guard

Phase 2 — Parent Registration Backend (sequential, depends on Phase 1)
  Task 2.1: POST /api/auth/parent-register/verify-student
  Task 2.2: POST /api/auth/parent-register/create
  Task 2.3: notify_parent_registered HubSpot helper

Phase 3 — Frontend (parallelizable internally, depends on Phase 1+2)
  Task 3.1: 4-portal login card grid
  Task 3.2: Parent registration 2-step flow
  Task 3.3: Status badges + Resend Invite on user list

Phase 4 — Seed Data (last, parallel-safe)
  Task 4.1: Miss A CEO seed user

Phase 5 — Final Verification
  Task 5.1: End-to-end demo walkthrough
```

---

## Phase 1 — Backend Foundations

### Task 1.1: Fix reset-password endpoint to activate inactive invited users

**Files:**
- Modify: `app/routes/auth_routes.py:326-388`

**Why:** Currently the endpoint's SELECT requires `active_status = TRUE`. New users created via admin invite will have `active_status = FALSE`. They need to be able to consume the token AND get activated as part of password set.

**Step 1: Update the SELECT to drop the active_status guard**

Change line 352:

```python
# BEFORE
WHERE password_reset_token = ? AND deleted_at IS NULL AND active_status = TRUE

# AFTER
WHERE password_reset_token = ? AND deleted_at IS NULL
```

**Step 2: Update the UPDATE to also set active_status = TRUE**

Change lines 374-381:

```python
# AFTER
db.execute(
    """UPDATE users
       SET password_hash = ?,
           active_status = TRUE,
           email_verified = TRUE,
           password_reset_token = NULL,
           password_reset_expires_at = NULL
       WHERE user_id = ?""",
    (new_hash, row["user_id"]),
)
```

**Step 3: Manual verify**

```bash
# In a Python REPL or test:
# 1. Create a user with active_status=FALSE and a password_reset_token
# 2. POST /api/auth/reset-password with that token + new password
# 3. Verify user is now active_status=TRUE with the new password set
```

**Step 4: Commit**

```bash
git add app/routes/auth_routes.py
git commit -m "auth: allow inactive invited users to activate via reset-password token"
```

---

### Task 1.2: Auto-send invite when admin creates a user

**Files:**
- Modify: `app/routes/admin_routes.py` — the `POST /api/users` endpoint (around line 564 where password_hash is generated)

**Why:** Currently admin must click "Send Invite" separately. We want creation to fire the invite automatically.

**Step 1: Find the user creation endpoint**

```bash
grep -n "@admin_bp.route.*api/users.*POST\|def create_user" /Users/jahleel/Desktop/ufit-motion/app/routes/admin_routes.py
```

The handler is `create_user` — locate where it INSERTs into `users`.

**Step 2: Replace inline password creation with invite-token flow**

Find the section where the current logic is creating a user with `password_hash = generate_password_hash(password, ...)`. Modify to:

```python
import secrets
import hashlib
from datetime import datetime, timezone, timedelta

# Generate invite token (24-hour expiry)
invite_token = secrets.token_urlsafe(32)
invite_token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
invite_expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

# Insert user with active_status=FALSE, no password yet, with invite token
cur = db.execute(
    """INSERT INTO users (first_name, last_name, email, phone, role,
                          active_status, password_reset_token,
                          password_reset_expires_at, created_at)
       VALUES (?, ?, ?, ?, ?, FALSE, ?, ?, ?)""",
    (first_name, last_name, email, phone or None, role,
     invite_token_hash, invite_expires, ts),
)
new_user_id = cur.lastrowid

# ... existing staff_profiles / parents / staff_assignments creation ...

# After db.commit() of the user creation, send invite
try:
    from app.email import send_invite_email
    send_invite_email(email, first_name or "there", role, invite_token)
except Exception as exc:
    logging.getLogger(__name__).warning("Invite email send failed for %s: %s", email, exc)
```

**Step 3: Remove or disable the existing password-required check**

If the endpoint currently requires `password` in request body, make it optional (or remove that requirement entirely — the user sets password via the email link).

**Step 4: Manual verify**

```bash
# Restart server, then:
# 1. Log in as admin
# 2. Add a coach via the admin UI (no password field visible)
# 3. Check Render logs (or local stdout) — should see the invite email logged
# 4. The user record should have active_status=FALSE and a password_reset_token
```

**Step 5: Commit**

```bash
git add app/routes/admin_routes.py
git commit -m "admin: auto-send invite email on user creation, drop required password field"
```

---

### Task 1.3: Auto-send invite on school creation (when principal email present)

**Files:**
- Modify: `app/routes/admin_routes.py` — the `POST /api/schools` endpoint (around line 208-289)

**Why:** Currently the school endpoint creates a user row for the principal but doesn't auto-invite them.

**Step 1: Find where the school endpoint creates the principal user**

Look for the section in `create_school` that handles `principal_email` — it likely INSERTs into `users` directly.

**Step 2: Refactor to use the same invite-token flow as Task 1.2**

The principal user should be created with:
- `active_status = FALSE`
- `password_reset_token = <hashed invite token>`
- `password_reset_expires_at = now + 24h`
- No `password_hash`

Then after `db.commit()`:

```python
from app.email import send_invite_email
send_invite_email(principal_email, principal_first or "there", "principal", invite_token)
```

**Step 3: Manual verify**

```bash
# 1. Log in as admin
# 2. Add a school with principal info
# 3. Check logs for invite email
# 4. Verify principal user has active_status=FALSE
```

**Step 4: Commit**

```bash
git add app/routes/admin_routes.py
git commit -m "schools: auto-send invite to principal when school created with principal info"
```

---

### Task 1.4: Add account_status to user list responses

**Files:**
- Modify: `app/routes/admin_routes.py` — `list_users` endpoint (around line 425+)

**Why:** Frontend needs to render Pending vs Active badges.

**Step 1: Update the SELECT to include a derived account_status field**

Find the user list SELECT and add a CASE expression:

```python
# In the SELECT clause, add:
CASE
    WHEN u.active_status = TRUE THEN 'active'
    WHEN u.password_reset_token IS NOT NULL THEN 'pending_invite'
    ELSE 'inactive'
END AS account_status
```

**Step 2: Make sure it's serialized in the response**

The endpoint typically does `[dict(r) for r in rows]` — that already includes the new column.

**Step 3: Manual verify**

```bash
# In browser dev tools, GET /api/admin/users
# Each user should now have an account_status field with one of: active, pending_invite, inactive
```

**Step 4: Commit**

```bash
git add app/routes/admin_routes.py
git commit -m "admin: expose account_status on user list (active/pending_invite/inactive)"
```

---

### Task 1.5: Last-CEO deactivation guard

**Files:**
- Modify: `app/routes/admin_routes.py` — wherever users are deactivated/deleted (the `delete_user` endpoint already has the "last CEO" check around line 670)

**Why:** Mirror the existing delete safeguard for the active_status PATCH endpoint so Miss A can't accidentally lock everyone out.

**Step 1: Find the user PATCH endpoint and find the active_status update path**

```bash
grep -n "active_status.*= ?\|update_user\|@admin_bp.route.*api/users.*PATCH" /Users/jahleel/Desktop/ufit-motion/app/routes/admin_routes.py
```

**Step 2: Before updating active_status to FALSE, check if it would leave zero CEOs**

Add this check (similar to existing line 670):

```python
if "active_status" in data and not data["active_status"]:
    target_role = db.execute(
        "SELECT role FROM users WHERE user_id = ? AND deleted_at IS NULL",
        (user_id,),
    ).fetchone()
    if target_role and target_role["role"] == "ceo":
        active_ceos = db.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE role = 'ceo' AND active_status = TRUE AND deleted_at IS NULL AND user_id != ?",
            (user_id,),
        ).fetchone()["cnt"]
        if active_ceos == 0:
            return jsonify({"error": "Cannot deactivate the last CEO account."}), 409
```

**Step 3: Manual verify**

```bash
# Try to PATCH the only CEO user with active_status=False — should get 409.
# Try with a non-CEO user — should succeed.
```

**Step 4: Commit**

```bash
git add app/routes/admin_routes.py
git commit -m "admin: guard against deactivating the last CEO account"
```

---

## Phase 2 — Parent Registration Backend

### Task 2.1: Add verify-student endpoint

**Files:**
- Modify: `app/routes/auth_routes.py` — add a new endpoint

**Step 1: Add the endpoint at the bottom of auth_routes.py**

```python
# ---------------------------------------------------------------------------
# POST /api/auth/parent-register/verify-student
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/parent-register/verify-student", methods=["POST"])
@limiter.limit("10 per minute")
def parent_register_verify_student():
    """
    Verify a student's identity for parent registration.
    Body: { student_first_name, student_last_name, student_id }
    Returns: { ok: true, student_id, school_id, school_name } if found.
    """
    data = parse_json()
    first = (data.get("student_first_name") or "").strip()
    last = (data.get("student_last_name") or "").strip()
    student_id_raw = data.get("student_id")

    try:
        student_id = int(student_id_raw)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid student ID."}), 400

    if not first or not last:
        return jsonify({"error": "Student first and last name are required."}), 400

    db = get_db()
    try:
        row = db.execute(
            """SELECT s.student_id, s.school_id, s.parent_primary_id, s.parent_secondary_id,
                      sc.school_name
               FROM students s
               JOIN schools sc ON sc.school_id = s.school_id
               WHERE s.student_id = ?
                 AND LOWER(s.student_first_name) = LOWER(?)
                 AND LOWER(s.student_last_name) = LOWER(?)
                 AND s.deleted_at IS NULL
                 AND s.active_status = TRUE
                 AND sc.deleted_at IS NULL""",
            (student_id, first, last),
        ).fetchone()

        if not row:
            return jsonify({
                "error": "We couldn't find that student. Please check the spelling and ID, or contact your school."
            }), 404

        return jsonify({
            "ok": True,
            "student_id": row["student_id"],
            "school_id": row["school_id"],
            "school_name": row["school_name"],
            "primary_filled": row["parent_primary_id"] is not None,
            "secondary_filled": row["parent_secondary_id"] is not None,
        })
    finally:
        db.close()
```

**Step 2: Manual verify**

```bash
# Use curl to test:
curl -X POST http://localhost:5000/api/auth/parent-register/verify-student \
  -H "Content-Type: application/json" \
  -d '{"student_first_name":"Aaron","student_last_name":"Brown","student_id":1}'
# Should return ok:true if student exists
```

**Step 3: Commit**

```bash
git add app/routes/auth_routes.py
git commit -m "auth: add parent-register/verify-student endpoint"
```

---

### Task 2.2: Add parent register/create endpoint

**Files:**
- Modify: `app/routes/auth_routes.py`

**Step 1: Add the endpoint**

```python
# ---------------------------------------------------------------------------
# POST /api/auth/parent-register/create
# ---------------------------------------------------------------------------
@auth_bp.route("/api/auth/parent-register/create", methods=["POST"])
@limiter.limit("5 per minute")
def parent_register_create():
    """
    Create a parent account after student verification has succeeded.
    Body: { student_id, first_name, last_name, email, phone, password, relationship }
    Re-verifies student to prevent tampering.
    """
    data = parse_json()
    student_id_raw = data.get("student_id")
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    relationship = (data.get("relationship") or "").strip().lower()

    try:
        student_id = int(student_id_raw)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid student ID."}), 400

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Invalid email format."}), 400
    if relationship not in ("mother", "father", "guardian", "other"):
        relationship = "guardian"

    db = get_db()
    try:
        # Re-verify student exists (prevents tampering between verify + create)
        student = db.execute(
            """SELECT s.student_id, s.school_id, s.parent_primary_id, s.parent_secondary_id,
                      sc.school_name
               FROM students s
               JOIN schools sc ON sc.school_id = s.school_id
               WHERE s.student_id = ? AND s.deleted_at IS NULL AND s.active_status = TRUE""",
            (student_id,),
        ).fetchone()
        if not student:
            return jsonify({"error": "Student not found."}), 404

        # Check email not already in use
        existing = db.execute(
            "SELECT user_id FROM users WHERE email = ? AND deleted_at IS NULL",
            (email,),
        ).fetchone()
        if existing:
            return jsonify({"error": "An account with that email already exists."}), 409

        ts = now_utc()
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        # Create user
        u_cur = db.execute(
            """INSERT INTO users (first_name, last_name, email, phone, password_hash,
                                  role, active_status, email_verified, created_at)
               VALUES (?, ?, ?, ?, ?, 'parent', TRUE, TRUE, ?)""",
            (first_name, last_name, email, phone or None, password_hash, ts),
        )
        user_id = u_cur.lastrowid

        # Create parents row
        p_cur = db.execute(
            """INSERT INTO parents (user_id, parent_first_name, parent_last_name,
                                    relationship_to_student, primary_contact_phone,
                                    active_status, created_at)
               VALUES (?, ?, ?, ?, ?, TRUE, ?)""",
            (user_id, first_name, last_name, relationship, phone or None, ts),
        )
        parent_id = p_cur.lastrowid

        # Link to student if a slot is available
        if student["parent_primary_id"] is None:
            db.execute(
                "UPDATE students SET parent_primary_id = ? WHERE student_id = ?",
                (parent_id, student_id),
            )
        elif student["parent_secondary_id"] is None:
            db.execute(
                "UPDATE students SET parent_secondary_id = ? WHERE student_id = ?",
                (parent_id, student_id),
            )
        # else: both slots filled, parent created but not linked. Admin can link later.

        audit(db, user_id, "parent_self_register", "users", user_id,
              new_values={"student_id": student_id, "school_id": student["school_id"]})
        db.commit()

        # Auto-login: set session
        from flask import session
        session.clear()
        session["user_id"] = user_id
        session["role"] = "parent"
        session.permanent = True

        # Fire HubSpot sync (in background, don't block on it)
        try:
            from app.routes._hubspot import notify_parent_registered
            import threading
            threading.Thread(
                target=notify_parent_registered,
                args=({
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone,
                    "relationship": relationship,
                    "school_name": student["school_name"],
                },),
                daemon=True,
            ).start()
        except Exception as exc:
            logging.getLogger(__name__).warning("Parent HubSpot sync threading failed: %s", exc)

        return jsonify({"ok": True, "user_id": user_id})
    finally:
        db.close()
```

**Step 2: Add required imports at top of file (if missing)**

```python
from werkzeug.security import generate_password_hash
import logging
```

**Step 3: Manual verify**

After Task 2.3 is complete, full end-to-end test via the UI.

**Step 4: Commit**

```bash
git add app/routes/auth_routes.py
git commit -m "auth: add parent-register/create endpoint with auto-login + HubSpot sync"
```

---

### Task 2.3: notify_parent_registered HubSpot helper

**Files:**
- Modify: `app/routes/_hubspot.py`

**Step 1: Append the helper to `_hubspot.py`**

```python
def notify_parent_registered(parent: dict) -> None:
    """
    Create a HubSpot Contact when a parent self-registers.
    parent dict keys: first_name, last_name, email, phone, relationship, school_name
    Associates the contact with the school's existing Company in HubSpot.
    """
    api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
    if not api_key:
        logger.info("HUBSPOT_API_KEY not set — skipping HubSpot sync for parent %s", parent.get("email"))
        return

    headers = _HEADERS(api_key)
    email = (parent.get("email") or "").strip()
    school_name = (parent.get("school_name") or "").strip()

    # 1. Find the company by school name
    company_id = None
    if school_name:
        try:
            search_resp = httpx.post(
                "https://api.hubapi.com/crm/v3/objects/companies/search",
                headers=headers,
                json={
                    "filterGroups": [{"filters": [{"propertyName": "name", "operator": "EQ", "value": school_name}]}],
                    "limit": 1,
                },
                timeout=5.0,
            )
            if search_resp.status_code == 200:
                results = search_resp.json().get("results", [])
                if results:
                    company_id = results[0].get("id")
        except Exception as exc:
            logger.warning("HubSpot company lookup failed for %s: %s", school_name, exc)

    # 2. Create the Contact
    try:
        contact_resp = httpx.post(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers=headers,
            json={"properties": {
                "email": email,
                "firstname": parent.get("first_name", ""),
                "lastname": parent.get("last_name", ""),
                "phone": parent.get("phone") or "",
                "jobtitle": f"Parent ({(parent.get('relationship') or 'Guardian').title()})",
            }},
            timeout=5.0,
        )
        if contact_resp.status_code in (200, 201):
            contact_id = contact_resp.json().get("id")
            logger.info("HubSpot contact created for parent: %s", email)
            # 3. Associate with company if found
            if company_id and contact_id:
                httpx.put(
                    f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company",
                    headers=headers,
                    timeout=5.0,
                )
                logger.info("HubSpot parent contact %s associated with company %s", contact_id, company_id)
        elif contact_resp.status_code == 409:
            logger.info("HubSpot contact already exists for parent %s", email)
        else:
            logger.warning("HubSpot parent contact creation returned %s for %s: %s",
                           contact_resp.status_code, email, contact_resp.text[:200])
    except Exception as exc:
        logger.warning("HubSpot parent sync failed for %s: %s", email, exc)
```

**Step 2: Manual verify**

After frontend is built, register a parent end-to-end and check HubSpot Companies → school → Contacts to see the parent listed.

**Step 3: Commit**

```bash
git add app/routes/_hubspot.py
git commit -m "hubspot: add notify_parent_registered helper for parent contact sync"
```

---

## Phase 3 — Frontend

### Task 3.1: 4-Portal Login Card Grid

**Files:**
- Modify: `static/app.js` — `renderLogin()` at line 307

**Step 1: Replace renderLogin() body**

```javascript
function renderLogin() {
  const portals = [
    { key: 'admin',  label: 'Admin Portal',        icon: '🏢', desc: 'For Ufit operations & administrators' },
    { key: 'coach',  label: 'Coach Portal',        icon: '🏃', desc: 'For head and assistant coaches' },
    { key: 'org',    label: 'Organization Portal', icon: '🏫', desc: 'For principals and school staff' },
    { key: 'parent', label: 'Parent Portal',       icon: '👨‍👩‍👧', desc: 'View your child\'s progress' },
  ];
  const sel = state._loginPortal || null;
  const isParent = sel === 'parent';
  const showRegister = state._showParentRegister === true;
  return `
    <div class="login-page">
      <div class="login-shell">
        <div class="login-logo">
          <div class="login-logo-mark"><span class="login-logo-ufit">UFIT</span><span class="login-logo-motion">MOTION</span></div>
          <div class="login-logo-tagline">School Fitness Platform</div>
        </div>
        <div class="portal-grid">
          ${portals.map(p => `
            <button class="portal-card ${sel === p.key ? 'active' : ''}" data-portal="${p.key}" type="button">
              <div class="portal-card-icon">${p.icon}</div>
              <div class="portal-card-label">${p.label}</div>
              <div class="portal-card-desc">${p.desc}</div>
            </button>
          `).join('')}
        </div>
        ${sel ? `
          <div class="login-form-wrap">
            ${isParent && showRegister
              ? renderParentRegister()
              : renderPortalLoginForm(portals.find(p => p.key === sel), isParent)}
          </div>
        ` : ''}
        <div class="login-footer-text">Ufit Motion &mdash; &copy; ${new Date().getFullYear()} Ufit Online</div>
      </div>
    </div>`;
}

function renderPortalLoginForm(portal, allowRegister) {
  return `
    <div class="login-card-form">
      <div class="login-card-form-header">${portal.icon} Sign in to ${portal.label}</div>
      <form id="login-form" novalidate>
        <div class="form-stack">
          <div id="login-alert-area"></div>
          <div class="form-group">
            <label class="form-label" for="email">Email address</label>
            <input class="form-input" type="email" id="email" name="email" placeholder="you@school.edu" autocomplete="username" inputmode="email" required />
          </div>
          <div class="form-group">
            <label class="form-label" for="password">Password</label>
            <input class="form-input" type="password" id="password" name="password" placeholder="Enter your password" autocomplete="current-password" required />
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="signin-btn">Sign In</button>
          <div style="text-align:center;margin-top:4px;display:flex;flex-direction:column;gap:6px;">
            <button class="btn btn-ghost btn-sm" type="button" id="forgot-pw-link" style="font-size:0.875rem;">Forgot password?</button>
            ${allowRegister ? `<button class="btn btn-ghost btn-sm" type="button" id="parent-register-link" style="font-size:0.875rem;color:var(--color-primary);">New here? Create Account</button>` : ''}
          </div>
        </div>
      </form>
    </div>`;
}

// Stub — replaced in Task 3.2
function renderParentRegister() {
  return `<div class="login-card-form"><div>Parent registration form (placeholder for Task 3.2)</div></div>`;
}
```

**Step 2: Update attachLoginListeners() (around line 348)**

```javascript
function attachLoginListeners() {
  $$('.portal-card').forEach(btn => btn.addEventListener('click', () => {
    state._loginPortal = btn.dataset.portal;
    state._showParentRegister = false;
    renderApp();
  }));

  document.getElementById('forgot-pw-link')?.addEventListener('click', openForgotPasswordModal);
  document.getElementById('parent-register-link')?.addEventListener('click', () => {
    state._showParentRegister = true;
    renderApp();
  });

  const form = document.getElementById('login-form');
  if (!form) return;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const email = form.querySelector('#email').value.trim();
    const password = form.querySelector('#password').value;
    if (!email || !password) { showLoginError('Please enter your email and password.'); return; }
    try {
      const portalKey = state._loginPortal || 'admin';
      const data = await api('POST', '/api/auth/login', { email, password, portal: portalKey });
      state.user = data.user;
      state._loginPortal = null;
      window.location.href = '/';
    } catch (err) {
      showLoginError(err.message || 'Invalid email or password.');
    }
  });
}
```

**Step 3: Add CSS for portal cards**

Append to `static/styles.css`:

```css
.login-shell { max-width:880px; width:100%; margin:0 auto; padding:32px 16px; }
.portal-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:16px; margin:24px 0; }
.portal-card { background:#fff; border:2px solid #e5e7eb; border-radius:12px; padding:24px 20px; text-align:left; cursor:pointer; transition:all 0.15s; min-height:120px; display:flex; flex-direction:column; gap:6px; }
.portal-card:hover { border-color:#1E40AF; transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.06); }
.portal-card.active { border-color:#1E40AF; background:#EFF6FF; }
.portal-card-icon { font-size:32px; line-height:1; }
.portal-card-label { font-weight:700; font-size:1.0625rem; color:#111827; }
.portal-card-desc { color:#6b7280; font-size:0.875rem; }
.login-form-wrap { margin-top:12px; }
.login-card-form { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:24px; }
.login-card-form-header { font-weight:700; font-size:1.125rem; margin-bottom:16px; color:#111827; }
@media (max-width:640px) {
  .portal-grid { grid-template-columns:1fr; }
}
```

**Step 4: Manual verify**

```bash
# Open the app at /
# Should see 4 portal cards in 2x2 grid
# Click each — login form expands beneath the grid
# Click Parent — should see "New here? Create Account" link
# Try logging in as an existing user via the Admin card — should work
```

**Step 5: Commit**

```bash
git add static/app.js static/styles.css
git commit -m "frontend: 4-portal login card grid with inline form expansion"
```

---

### Task 3.2: Parent Registration 2-Step Flow

**Files:**
- Modify: `static/app.js` — replace the `renderParentRegister()` stub

**Step 1: Implement renderParentRegister and listeners**

```javascript
function renderParentRegister() {
  const step = state._parentRegStep || 1;
  if (step === 1) {
    return `
      <div class="login-card-form">
        <div class="login-card-form-header">👨‍👩‍👧 Create Parent Account — Step 1 of 2</div>
        <p style="color:#6b7280;font-size:0.875rem;margin:0 0 16px;">Verify your child's information to begin.</p>
        <form id="parent-verify-form" novalidate>
          <div class="form-stack">
            <div id="parent-verify-alert"></div>
            <div class="form-group">
              <label class="form-label">Student First Name</label>
              <input class="form-input" name="first" required />
            </div>
            <div class="form-group">
              <label class="form-label">Student Last Name</label>
              <input class="form-input" name="last" required />
            </div>
            <div class="form-group">
              <label class="form-label">Student ID</label>
              <input class="form-input" name="sid" inputmode="numeric" required />
            </div>
            <button class="btn btn-primary btn-full" type="submit">Verify</button>
            <button class="btn btn-ghost btn-full btn-sm" type="button" id="parent-back-to-login">Back to Sign In</button>
          </div>
        </form>
      </div>`;
  }
  // Step 2
  const verified = state._parentRegVerified || {};
  return `
    <div class="login-card-form">
      <div class="login-card-form-header">👨‍👩‍👧 Create Parent Account — Step 2 of 2</div>
      <p style="color:#6b7280;font-size:0.875rem;margin:0 0 16px;">Verified: <strong>${esc(verified.school_name || '')}</strong></p>
      <form id="parent-create-form" novalidate>
        <div class="form-stack">
          <div id="parent-create-alert"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div class="form-group"><label class="form-label">Your First Name</label><input class="form-input" name="first_name" required /></div>
            <div class="form-group"><label class="form-label">Your Last Name</label><input class="form-input" name="last_name" required /></div>
          </div>
          <div class="form-group"><label class="form-label">Email</label><input class="form-input" type="email" name="email" required /></div>
          <div class="form-group"><label class="form-label">Phone</label><input class="form-input" type="tel" name="phone" /></div>
          <div class="form-group"><label class="form-label">Relationship to Student</label>
            <select class="form-input" name="relationship" required>
              <option value="">Select...</option>
              <option value="mother">Mother</option>
              <option value="father">Father</option>
              <option value="guardian">Guardian</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div class="form-group"><label class="form-label">Password (min 8 chars)</label><input class="form-input" type="password" name="password" minlength="8" required /></div>
          <button class="btn btn-primary btn-full" type="submit">Create Account</button>
          <button class="btn btn-ghost btn-full btn-sm" type="button" id="parent-back-to-step1">Back</button>
        </div>
      </form>
    </div>`;
}

function attachParentRegisterListeners() {
  document.getElementById('parent-back-to-login')?.addEventListener('click', () => {
    state._showParentRegister = false;
    state._parentRegStep = 1;
    renderApp();
  });
  document.getElementById('parent-back-to-step1')?.addEventListener('click', () => {
    state._parentRegStep = 1;
    renderApp();
  });
  document.getElementById('parent-verify-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target;
    const alertEl = document.getElementById('parent-verify-alert');
    try {
      const data = await api('POST', '/api/auth/parent-register/verify-student', {
        student_first_name: f.first.value.trim(),
        student_last_name: f.last.value.trim(),
        student_id: f.sid.value.trim(),
      });
      state._parentRegVerified = data;
      state._parentRegStep = 2;
      renderApp();
    } catch (err) {
      if (alertEl) alertEl.innerHTML = errorCard(err.message);
    }
  });
  document.getElementById('parent-create-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target;
    const alertEl = document.getElementById('parent-create-alert');
    const verified = state._parentRegVerified || {};
    try {
      await api('POST', '/api/auth/parent-register/create', {
        student_id: verified.student_id,
        first_name: f.first_name.value.trim(),
        last_name: f.last_name.value.trim(),
        email: f.email.value.trim(),
        phone: f.phone.value.trim(),
        password: f.password.value,
        relationship: f.relationship.value,
      });
      // Auto-login happened server-side; just reload to enter the parent portal.
      window.location.href = '/';
    } catch (err) {
      if (alertEl) alertEl.innerHTML = errorCard(err.message);
    }
  });
}
```

**Step 2: Hook into attachLoginListeners**

In `attachLoginListeners()`, after the existing logic, add:

```javascript
attachParentRegisterListeners();
```

**Step 3: Manual verify**

```bash
# 1. Open app, click Parent card, click "New here? Create Account"
# 2. Step 1 form appears
# 3. Enter a real seeded student's name and ID — should advance to step 2
# 4. Enter parent info, submit — should auto-login as parent and show parent portal
# 5. Try with wrong student ID — should show error
```

**Step 4: Commit**

```bash
git add static/app.js
git commit -m "frontend: parent self-registration 2-step flow"
```

---

### Task 3.3: Status Badges and Resend Invite Button

**Files:**
- Modify: `static/app.js` — find the user list rendering (`loadUsersPage` or similar)

**Step 1: Locate the user list render**

```bash
grep -n "loadUsersPage\|renderUsersPage\|users-content\|/api/admin/users" /Users/jahleel/Desktop/ufit-motion/static/app.js | head -10
```

**Step 2: Add status badge rendering and Resend button**

Inside the user row template, where status is displayed, add:

```javascript
// Where each user row is rendered:
const statusBadge = u.account_status === 'pending_invite'
  ? `<span class="badge badge-warning">Pending Invite</span>`
  : u.account_status === 'active'
  ? `<span class="badge badge-success">Active</span>`
  : `<span class="badge badge-secondary">Inactive</span>`;

const resendBtn = u.account_status === 'pending_invite'
  ? `<button class="btn btn-ghost btn-sm" onclick="resendInvite(${u.user_id})" title="Resend invite email">Resend Invite</button>`
  : '';
```

Insert these in the appropriate `<td>` cells in the user row template.

**Step 3: Add the resendInvite function**

```javascript
async function resendInvite(userId) {
  try {
    await api('POST', `/api/admin/users/${userId}/send-invite`);
    showAlert('Invite email resent.', 'success');
  } catch (err) {
    showAlert(err.message || 'Could not resend invite.', 'error');
  }
}
```

**Step 4: Manual verify**

```bash
# 1. As admin, add a coach (with the new auto-invite flow)
# 2. Go to Users page — coach should show Pending Invite badge with Resend button
# 3. Click Resend Invite — see success alert
# 4. Check logs for the email send
# 5. After the coach actually completes set-password, refresh — badge becomes Active and Resend disappears
```

**Step 5: Commit**

```bash
git add static/app.js
git commit -m "frontend: pending-invite badges and Resend Invite button on user list"
```

---

## Phase 4 — Seed Data

### Task 4.1: Miss A CEO Seed User

**Files:**
- Modify: `app/seeds.py` — add a CEO user named after the founder

**Step 1: Find the seed users section**

```bash
grep -n "ceo\|admin@ufit\|seed.*user\|INSERT INTO users" /Users/jahleel/Desktop/ufit-motion/app/seeds.py | head -10
```

**Step 2: Add Miss A's CEO record**

Find where seed users are inserted, add (or update if exists):

```python
# Miss A — Ufit Founder, CEO-level access
db.execute(
    """INSERT INTO users (first_name, last_name, email, phone, password_hash,
                          role, active_status, email_verified, created_at)
       VALUES (?, ?, ?, ?, ?, 'ceo', TRUE, TRUE, ?)
       ON CONFLICT (email) DO NOTHING""",
    ("Miss", "A",
     "missa@ufitonline.com", None,
     generate_password_hash("UfitDemo2026!", method="pbkdf2:sha256"),
     now_utc()),
)
```

(If your seeds use SQLite + Postgres compat, use the same `INSERT OR IGNORE` / `ON CONFLICT` pattern as elsewhere in seeds.py.)

**Step 3: Re-seed and verify**

```bash
# Run whatever the project uses for seeding (likely flask db init or scripts/seed_demo.py)
# Then log in at the app with missa@ufitonline.com / UfitDemo2026!
# Should land in admin portal with full access
```

**Step 4: Commit**

```bash
git add app/seeds.py
git commit -m "seeds: add Miss A as the founding CEO account"
```

---

## Phase 5 — Final Verification

### Task 5.1: End-to-End Demo Walkthrough

Run through every demo path in a browser to confirm nothing regressed:

1. **Login screen** — see 4 portal cards, click each, see form expand
2. **Existing seeded user login** — log in as a seeded admin via Admin card, verify full app works
3. **Add coach** — go to Users → Add Coach, fill in info (no password field), submit
   - Verify Render logs show invite email
   - Verify coach appears with Pending Invite badge
4. **Click Resend Invite** — verify success alert + new log line
5. **Add school with principal** — go to Schools → Add School with principal info
   - Verify principal user created with Pending Invite
   - Verify HubSpot company + contact created (if API key set)
6. **Set password via invite link** — copy `?reset_token=...` from logs (in dev mode), open in browser
   - Set password → land on login → log in → success
7. **Parent self-register** — log out, click Parent → Create Account
   - Step 1: enter seeded student's name + ID → advance
   - Step 2: fill profile → submit → auto-login → parent portal loads
   - Verify HubSpot contact created (if API key set)
8. **Miss A login** — log in as `missa@ufitonline.com` → verify CEO portal access
9. **Last-CEO guard** — try to deactivate Miss A as another admin → expect 409 if she's the only CEO
10. **Delete a school** — verify cascade still works (users get soft-deleted)

If everything passes, the build is demo-ready.

```bash
git tag demo-ready-2026-05-09
git push --tags
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Email sends fail silently if `RESEND_API_KEY` missing | Already handled — `_send()` logs to stdout. User adds key tomorrow. |
| Token expires before user clicks link | 24-hour expiry is generous; if hit, friendly error already in place at `reset-password` endpoint. |
| Existing seeded users have `active_status=TRUE` and known passwords | Untouched — only new admin-created users go through the invite flow. |
| Parent registration tries to use a deleted school's student | The verify endpoint joins `schools sc ON sc.school_id = s.school_id` and filters `sc.deleted_at IS NULL`. Already covered. |
| HubSpot company lookup by name is fragile (case sensitivity, special chars) | Acceptable for demo. If needed, store HubSpot company IDs on the schools table later. |
| Backend changes break existing tests | Run pytest before final commit. Most existing tests should still pass since we're additive. |
| Frontend changes to renderLogin break the existing login flow | Keep the existing `attachLoginListeners` logic intact, only swap the markup. |

---

## File Manifest

**New files:** none

**Modified files:**
- `app/routes/auth_routes.py` — fix reset-password, add 2 parent endpoints
- `app/routes/admin_routes.py` — auto-invite on user/school create, add account_status, last-CEO guard
- `app/routes/_hubspot.py` — add notify_parent_registered
- `app/seeds.py` — add Miss A
- `static/app.js` — 4-portal login + parent register flow + status badges + resend button
- `static/styles.css` — portal grid styles
