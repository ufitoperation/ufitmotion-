"""
add_demo_parent.py — Inserts a demo parent user into production Postgres.

Run:
  DATABASE_URL="postgresql://..." python3 scripts/add_demo_parent.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL not set")

from werkzeug.security import generate_password_hash

DEMO_EMAIL    = "parent@ufit.demo"
DEMO_PASSWORD = "UfitParent2026!"
DEMO_FIRST    = "Maria"
DEMO_LAST     = "Johnson"

# Students to link as primary parent (school 2 — Lincoln Elementary)
STUDENT_IDS = [11, 12, 13]   # Emma Johnson, Liam Davis, Sofia Martinez

pw_hash = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")

try:
    import psycopg
except ImportError:
    sys.exit("pip install psycopg[binary]")

conn = psycopg.connect(DATABASE_URL, autocommit=False, connect_timeout=30)
conn.prepare_threshold = None
cur = conn.cursor()

# 1. Insert user (skip if already exists)
cur.execute("""
    INSERT INTO users (first_name, last_name, email, role, password_hash,
                       active_status, email_verified)
    VALUES (%s, %s, %s, 'parent', %s, TRUE, TRUE)
    ON CONFLICT (email) DO NOTHING
    RETURNING user_id
""", (DEMO_FIRST, DEMO_LAST, DEMO_EMAIL, pw_hash))
row = cur.fetchone()
if row:
    user_id = row[0]
    print(f"  Created user: user_id={user_id}")
else:
    cur.execute("SELECT user_id FROM users WHERE email=%s", (DEMO_EMAIL,))
    user_id = cur.fetchone()[0]
    print(f"  User already exists: user_id={user_id}")

# 2. Insert parent row
cur.execute("""
    INSERT INTO parents (user_id, first_name, last_name, email, portal_access_status)
    VALUES (%s, %s, %s, %s, TRUE)
    ON CONFLICT (user_id) DO NOTHING
    RETURNING parent_id
""", (user_id, DEMO_FIRST, DEMO_LAST, DEMO_EMAIL))
row = cur.fetchone()
if row:
    parent_id = row[0]
    print(f"  Created parent: parent_id={parent_id}")
else:
    cur.execute("SELECT parent_id FROM parents WHERE user_id=%s", (user_id,))
    parent_id = cur.fetchone()[0]
    print(f"  Parent already exists: parent_id={parent_id}")

# 3. Link user → parent
cur.execute("UPDATE users SET linked_parent_id=%s WHERE user_id=%s", (parent_id, user_id))
print(f"  Linked user.linked_parent_id = {parent_id}")

# 4. Link students → parent
ph = ",".join(["%s"] * len(STUDENT_IDS))
cur.execute(
    f"UPDATE students SET parent_primary_id=%s WHERE student_id IN ({ph})",
    [parent_id] + STUDENT_IDS,
)
print(f"  Linked {cur.rowcount} students to parent_id={parent_id}")

# 5. Reset sequences
cur.execute("SELECT setval(pg_get_serial_sequence('users','user_id'), (SELECT MAX(user_id) FROM users))")
cur.execute("SELECT setval(pg_get_serial_sequence('parents','parent_id'), (SELECT MAX(parent_id) FROM parents))")

conn.commit()
conn.close()

print("\nDone.")
print(f"  Email:    {DEMO_EMAIL}")
print(f"  Password: {DEMO_PASSWORD}")
print(f"  Students: Emma Johnson, Liam Davis, Sofia Martinez (school 2 — Lincoln)")
