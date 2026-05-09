"""
seed_demo_assessments.py — Generate assessment scores for demo students so the
parent portal shows real progress data after registration.

Run:
  DATABASE_URL="postgresql://..." python3 scripts/seed_demo_assessments.py

For every active student at the first active school whose summary table is
empty, this:
  1. Creates a baseline assessment ~30 days ago with mid-range scores (raw 2-3)
  2. Creates a current assessment ~3 days ago with higher scores (raw 3-5),
     so growth_amount renders positive in the parent portal
  3. Skips students who already have assessment_scores rows

Idempotent — re-running does nothing for already-assessed students.
"""
import os, sys, random, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL not set")

try:
    import psycopg
except ImportError:
    sys.exit("pip install psycopg[binary]")

# Deterministic randomness so re-runs produce the same demo numbers.
random.seed(42)

# Map grade_level (str) -> grade_band (str) used in skills table.
def grade_band_for(grade: str) -> str:
    try:
        g = int(grade)
    except (ValueError, TypeError):
        return "K-2"
    if g <= 2: return "K-2"
    if g <= 5: return "3-5"
    return "6-8"

def perf_band(score: int) -> str:
    # Used for student_skill_summary.performance_band (TEXT, no CHECK constraint).
    if score >= 80: return "Exceeding"
    if score >= 60: return "Meeting"
    if score >= 40: return "Approaching"
    return "Beginning"

def readiness_band_for(score: float) -> str:
    # student_overall_summary.readiness_band CHECK ('Emerging', 'Developing',
    # 'On Track', 'Proficient', 'Advanced')
    if score >= 90: return "Advanced"
    if score >= 75: return "Proficient"
    if score >= 60: return "On Track"
    if score >= 40: return "Developing"
    return "Emerging"

conn = psycopg.connect(DATABASE_URL, autocommit=False, connect_timeout=30)
conn.prepare_threshold = None
cur = conn.cursor()

# Pick the first active school
cur.execute(
    "SELECT school_id, school_name FROM schools "
    "WHERE active_status=TRUE AND deleted_at IS NULL ORDER BY school_id LIMIT 1"
)
school_row = cur.fetchone()
if not school_row:
    sys.exit("ERROR: no active school found.")
school_id, school_name = school_row
print(f"Target school: {school_name} (id={school_id})\n")

# Find an assessor staff_id at this school (head_coach preferred, then any staff)
cur.execute(
    """SELECT sp.staff_id FROM staff_profiles sp
       JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
       WHERE sa.school_id = %s AND sa.active_status = TRUE
         AND sp.deleted_at IS NULL
       ORDER BY CASE WHEN sa.assignment_role = 'head_coach' THEN 0 ELSE 1 END
       LIMIT 1""",
    (school_id,),
)
staff_row = cur.fetchone()
if not staff_row:
    sys.exit("ERROR: no staff assigned to this school. Add a coach first.")
staff_id = staff_row[0]
print(f"Assessor staff_id={staff_id}")

# Pull all active students at this school
cur.execute(
    """SELECT student_id, student_first_name, student_last_name, grade_level
       FROM students
       WHERE school_id = %s AND active_status = TRUE AND deleted_at IS NULL
       ORDER BY student_id""",
    (school_id,),
)
students = cur.fetchall()
print(f"Found {len(students)} active students.\n")

# Group skills by grade_band
cur.execute(
    "SELECT skill_id, domain_id, grade_band FROM skills WHERE active_status = TRUE"
)
skills_rows = cur.fetchall()
skills_by_band: dict = {}
for sid, did, band in skills_rows:
    skills_by_band.setdefault(band, []).append((sid, did))
print(f"Skills loaded: {sum(len(v) for v in skills_by_band.values())} total across {len(skills_by_band)} grade bands")

today = datetime.date.today()
baseline_date = (today - datetime.timedelta(days=30)).isoformat()
current_date = (today - datetime.timedelta(days=3)).isoformat()

scored = 0
skipped = 0
errors = 0

for student_id, first, last, grade in students:
    # Skip if already has assessment_scores rows for this student
    cur.execute(
        "SELECT 1 FROM assessment_scores WHERE student_id = %s LIMIT 1",
        (student_id,),
    )
    if cur.fetchone():
        skipped += 1
        continue

    band = grade_band_for(grade)
    available_skills = skills_by_band.get(band, [])
    if not available_skills:
        # Fallback to any band
        available_skills = next(iter(skills_by_band.values()), [])
    if not available_skills:
        errors += 1
        continue

    # Sample 6-10 skills for this student
    sample_size = min(len(available_skills), random.randint(6, 10))
    chosen_skills = random.sample(available_skills, sample_size)

    # Create baseline + current assessments (two rows in `assessments`)
    try:
        # ---- Baseline assessment (~30 days ago) ----
        cur.execute(
            """INSERT INTO assessments (student_id, school_id, assessed_by_staff_id,
                                        assessment_date, assessment_method,
                                        overall_assessment_notes, created_at)
               VALUES (%s, %s, %s, %s, 'observational',
                       'Baseline assessment for new student.', NOW())
               RETURNING assessment_id""",
            (student_id, school_id, staff_id, baseline_date),
        )
        baseline_aid = cur.fetchone()[0]

        # Add 6-10 baseline scores (raw_level 2-3, mid-range)
        for skill_id, _domain_id in chosen_skills:
            raw_baseline = random.randint(2, 3)
            cur.execute(
                """INSERT INTO assessment_scores
                   (assessment_id, student_id, skill_id, raw_level, benchmark_id,
                    observed_independence, observed_consistency, observed_accuracy,
                    growth_flag, observation_tag, created_at)
                   VALUES (%s, %s, %s, %s, NULL,
                           TRUE, FALSE, FALSE, FALSE, 'consistent', NOW())""",
                (baseline_aid, student_id, skill_id, raw_baseline),
            )

        # ---- Current assessment (~3 days ago) ----
        cur.execute(
            """INSERT INTO assessments (student_id, school_id, assessed_by_staff_id,
                                        assessment_date, assessment_method,
                                        overall_assessment_notes, created_at)
               VALUES (%s, %s, %s, %s, 'observational',
                       'Most recent assessment showing growth.', NOW())
               RETURNING assessment_id""",
            (student_id, school_id, staff_id, current_date),
        )
        current_aid = cur.fetchone()[0]

        # Add current scores (raw_level 3-5, showing growth) for the same skills
        skill_to_baseline_raw = {}
        for skill_id, _domain_id in chosen_skills:
            base = random.randint(2, 3)  # not used; we want consistency
            # Actually re-randomize each loop with bias toward growth:
            current_raw = random.randint(3, 5)
            growth_flag = current_raw > 3  # rough proxy
            cur.execute(
                """INSERT INTO assessment_scores
                   (assessment_id, student_id, skill_id, raw_level, benchmark_id,
                    observed_independence, observed_consistency, observed_accuracy,
                    growth_flag, observation_tag, created_at)
                   VALUES (%s, %s, %s, %s, NULL,
                           TRUE, TRUE, %s, %s, 'consistent', NOW())""",
                (current_aid, student_id, skill_id, current_raw,
                 current_raw >= 4, growth_flag),
            )

        # ---- Recalculate summaries for this student (Postgres-safe) ----
        # student_skill_summary
        for skill_id, _domain_id in chosen_skills:
            cur.execute(
                """SELECT
                     MIN(asco.normalized_score) FILTER (WHERE a.assessment_date = (SELECT MIN(assessment_date) FROM assessments WHERE student_id = %s AND deleted_at IS NULL)) AS baseline,
                     (SELECT a2_sc.normalized_score
                      FROM assessment_scores a2_sc
                      JOIN assessments a2 ON a2.assessment_id = a2_sc.assessment_id
                      WHERE a2_sc.student_id = %s AND a2_sc.skill_id = %s AND a2.deleted_at IS NULL
                      ORDER BY a2.assessment_date DESC LIMIT 1) AS current_score,
                     MAX(asco.normalized_score) AS highest,
                     MAX(a.assessment_date) AS latest_date
                   FROM assessment_scores asco
                   JOIN assessments a ON a.assessment_id = asco.assessment_id
                   WHERE asco.student_id = %s AND asco.skill_id = %s AND a.deleted_at IS NULL""",
                (student_id, student_id, skill_id, student_id, skill_id),
            )
            agg = cur.fetchone()
            if not agg or agg[1] is None:
                continue
            baseline_norm, current_norm, highest, latest_date = agg
            band_label = perf_band(current_norm)
            cur.execute(
                """INSERT INTO student_skill_summary
                     (student_id, school_id, skill_id, baseline_score, current_score,
                      highest_score, latest_assessment_date, performance_band, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (student_id, skill_id) DO UPDATE SET
                     baseline_score = COALESCE(student_skill_summary.baseline_score, EXCLUDED.baseline_score),
                     current_score = EXCLUDED.current_score,
                     highest_score = EXCLUDED.highest_score,
                     latest_assessment_date = EXCLUDED.latest_assessment_date,
                     performance_band = EXCLUDED.performance_band,
                     updated_at = NOW()""",
                (student_id, school_id, skill_id, baseline_norm, current_norm,
                 highest, latest_date, band_label),
            )

        # student_domain_summary (rolled up)
        cur.execute(
            """SELECT sk.domain_id,
                      AVG(sss.baseline_score)::NUMERIC(5,2) AS baseline_avg,
                      AVG(sss.current_score)::NUMERIC(5,2)  AS current_avg
               FROM student_skill_summary sss
               JOIN skills sk ON sk.skill_id = sss.skill_id
               WHERE sss.student_id = %s
               GROUP BY sk.domain_id""",
            (student_id,),
        )
        for domain_id, baseline_avg, current_avg in cur.fetchall():
            cur.execute(
                """INSERT INTO student_domain_summary
                     (student_id, domain_id, baseline_domain_score, current_domain_score, latest_update)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (student_id, domain_id) DO UPDATE SET
                     baseline_domain_score = COALESCE(student_domain_summary.baseline_domain_score, EXCLUDED.baseline_domain_score),
                     current_domain_score = EXCLUDED.current_domain_score,
                     latest_update = NOW()""",
                (student_id, domain_id, baseline_avg, current_avg),
            )

        # student_overall_summary
        cur.execute(
            """SELECT AVG(current_score)::NUMERIC(5,2) FROM student_skill_summary WHERE student_id = %s""",
            (student_id,),
        )
        overall_skill = cur.fetchone()[0] or 0
        readiness = readiness_band_for(float(overall_skill))
        cur.execute(
            """INSERT INTO student_overall_summary
                 (student_id, school_id, overall_skill_score, overall_behavior_score, overall_ufit_score,
                  participation_rate, readiness_band, latest_update)
               VALUES (%s, %s, %s, 75, %s, 92, %s, NOW())
               ON CONFLICT (student_id) DO UPDATE SET
                 overall_skill_score = EXCLUDED.overall_skill_score,
                 overall_ufit_score = EXCLUDED.overall_ufit_score,
                 readiness_band = EXCLUDED.readiness_band,
                 latest_update = NOW()""",
            (student_id, school_id, overall_skill, (overall_skill + 75) / 2, readiness),
        )

        # Commit per-student so a single bad row doesn't roll back everything
        conn.commit()
        scored += 1
        print(f"  Scored: id={student_id} {first} {last} (grade {grade}, band {band}, {sample_size} skills)")
    except Exception as e:
        conn.rollback()
        print(f"  ERROR student id={student_id} {first} {last}: {e}")
        errors += 1
        continue
conn.close()
print(f"\nDone. {scored} scored, {skipped} already had data, {errors} errors.")
