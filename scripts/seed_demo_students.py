"""
seed_demo_students.py — Bulk-create demo students for parent self-registration demos.

Run:
  DATABASE_URL="postgresql://..." python3 scripts/seed_demo_students.py

This adds a large pool of demo students (both parent slots empty) at the first
active school in the database. Prints a table of "Student ID | First | Last"
that you can reference live during the demo.

Each parent registration fills ONE slot (primary first, then secondary).
30 students = 60 successful parent registrations possible before any student
has both slots filled.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL not set")

try:
    import psycopg
except ImportError:
    sys.exit("pip install psycopg[binary]")

DEMO_STUDENTS = [
    ("Emma",    "Anderson",  "3"),
    ("Liam",    "Bennett",   "4"),
    ("Olivia",  "Carter",    "5"),
    ("Noah",    "Dawson",    "2"),
    ("Ava",     "Ellis",     "6"),
    ("Ethan",   "Foster",    "7"),
    ("Sophia",  "Gibson",    "1"),
    ("Mason",   "Hayes",     "3"),
    ("Isabella","Ingram",    "5"),
    ("Logan",   "Jenkins",   "8"),
    ("Mia",     "Kennedy",   "4"),
    ("Lucas",   "Larson",    "2"),
    ("Charlotte","Mitchell", "6"),
    ("Aiden",   "Nelson",    "5"),
    ("Amelia",  "Owens",     "3"),
    ("Caleb",   "Patel",     "7"),
    ("Harper",  "Quinn",     "4"),
    ("Jackson", "Rivera",    "8"),
    ("Evelyn",  "Sanchez",   "2"),
    ("Sebastian","Turner",   "5"),
    ("Avery",   "Underwood", "1"),
    ("Daniel",  "Vargas",    "6"),
    ("Scarlett","Walker",    "3"),
    ("Henry",   "Xiong",     "4"),
    ("Layla",   "Young",     "7"),
    ("Jacob",   "Zimmerman", "5"),
    ("Penelope","Adams",     "2"),
    ("Owen",    "Brooks",    "6"),
    ("Riley",   "Castillo",  "8"),
    ("Wyatt",   "Diaz",      "3"),
]

conn = psycopg.connect(DATABASE_URL, autocommit=False, connect_timeout=30)
conn.prepare_threshold = None
cur = conn.cursor()

cur.execute(
    "SELECT school_id, school_name FROM schools "
    "WHERE active_status = TRUE AND deleted_at IS NULL "
    "ORDER BY school_id LIMIT 1"
)
row = cur.fetchone()
if not row:
    sys.exit("ERROR: no active school found. Add a school first.")
school_id, school_name = row
print(f"Adding {len(DEMO_STUDENTS)} demo students to school: {school_name} (id={school_id})\n")

inserted = []
for first, last, grade in DEMO_STUDENTS:
    # Skip if a student with the same name already exists at this school
    cur.execute(
        """SELECT student_id FROM students
           WHERE school_id = %s
             AND LOWER(student_first_name) = LOWER(%s)
             AND LOWER(student_last_name) = LOWER(%s)
             AND deleted_at IS NULL""",
        (school_id, first, last),
    )
    existing = cur.fetchone()
    if existing:
        inserted.append((existing[0], first, last, grade, "EXISTS"))
        continue

    cur.execute(
        """INSERT INTO students
           (school_id, student_first_name, student_last_name, grade_level,
            active_status, created_at)
           VALUES (%s, %s, %s, %s, TRUE, NOW())
           RETURNING student_id""",
        (school_id, first, last, grade),
    )
    sid = cur.fetchone()[0]
    inserted.append((sid, first, last, grade, "NEW"))

conn.commit()
conn.close()

print(f"{'Status':<8} {'Student ID':<12} {'First':<12} {'Last':<14} {'Grade':<6}")
print("-" * 60)
for sid, first, last, grade, status in inserted:
    print(f"{status:<8} {sid:<12} {first:<12} {last:<14} {grade:<6}")

print(f"\nDone. {sum(1 for _,_,_,_,s in inserted if s == 'NEW')} new, {sum(1 for _,_,_,_,s in inserted if s == 'EXISTS')} already existed.")
print(f"\nDuring the demo, parents register by entering:")
print(f"   • Student First Name (case-insensitive)")
print(f"   • Student Last Name  (case-insensitive)")
print(f"   • Student ID         (the integer above)")
