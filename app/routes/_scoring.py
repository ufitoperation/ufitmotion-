"""
_scoring.py — UFIT scoring engine per docs/requirements-external.md

Normalized scale:  Level 1=20, 2=40, 3=60, 4=80, 5=100
Performance bands: 20-39=Emerging, 40-59=Developing, 60-79=On Track,
                   80-89=Proficient, 90-100=Advanced

Grade-band overall weights:
  K-2:  Physical/Psychomotor 70% + SEL/Behavior 30%
  3-5:  Physical/Sport 60% + SEL 25% + Game Application 15%
  6-8:  Sport Fundamentals 45% + Game Application 30% + SEL 25%

"Game Application" = game_application skill score when it exists (6-8 only).
For 3-5 students without a game_application score, Physical domain fills
that 15% component (effectively making Physical worth 75%).
"""

from app.routes._helpers import now_utc

VALID_OBSERVATION_TAGS = (
    "independent",
    "needs_prompt",
    "inconsistent",
    "strong_control",
    "low_confidence",
    "gameplay_transfer_observed",
)


def normalized_score(raw_level: int) -> int:
    return raw_level * 20


def performance_band(score) -> str:
    if score is None:
        return "Emerging"
    s = float(score)
    if s >= 90:
        return "Advanced"
    if s >= 80:
        return "Proficient"
    if s >= 60:
        return "On Track"
    if s >= 40:
        return "Developing"
    return "Emerging"


def _grade_band(grade_level: str) -> str:
    """Map a student grade_level string to K-2 / 3-5 / 6-8."""
    gl = (grade_level or "").strip().upper()
    if gl in ("K", "KG", "KINDERGARTEN", "1", "1ST", "2", "2ND"):
        return "K-2"
    if gl in ("3", "3RD", "4", "4TH", "5", "5TH"):
        return "3-5"
    return "6-8"


def recalculate_student_summaries(db, student_id: int, school_id: int) -> None:
    """
    Recalculate student_skill_summary, student_domain_summary, and
    student_overall_summary for one student after an assessment is saved.
    Called synchronously inside POST /api/assessments.
    """
    ts = now_utc()

    # ------------------------------------------------------------------ #
    # 1. student_skill_summary — one row per (student, skill)             #
    # ------------------------------------------------------------------ #
    scored_skills = db.execute(
        """
        SELECT DISTINCT a_sc.skill_id
        FROM assessment_scores a_sc
        JOIN assessments a ON a.assessment_id = a_sc.assessment_id
        WHERE a_sc.student_id = ? AND a.deleted_at IS NULL
        """,
        (student_id,),
    ).fetchall()

    for row in scored_skills:
        skill_id = row["skill_id"]

        agg = db.execute(
            """
            SELECT
                (SELECT a2.normalized_score
                 FROM assessment_scores a2
                 JOIN assessments aa ON aa.assessment_id = a2.assessment_id
                 WHERE a2.student_id = ? AND a2.skill_id = ?
                   AND aa.deleted_at IS NULL
                 ORDER BY a2.created_at ASC LIMIT 1)                  AS baseline,
                MAX(a_sc.normalized_score)                            AS highest,
                (SELECT a2.normalized_score
                 FROM assessment_scores a2
                 JOIN assessments aa ON aa.assessment_id = a2.assessment_id
                 WHERE a2.student_id = ? AND a2.skill_id = ?
                   AND aa.deleted_at IS NULL
                 ORDER BY a2.created_at DESC LIMIT 1)                 AS current,
                (SELECT aa.assessment_date
                 FROM assessment_scores a2
                 JOIN assessments aa ON aa.assessment_id = a2.assessment_id
                 WHERE a2.student_id = ? AND a2.skill_id = ?
                   AND aa.deleted_at IS NULL
                 ORDER BY a2.created_at DESC LIMIT 1)                 AS latest_date
            FROM assessment_scores a_sc
            JOIN assessments a ON a.assessment_id = a_sc.assessment_id
            WHERE a_sc.student_id = ? AND a_sc.skill_id = ? AND a.deleted_at IS NULL
            """,
            (student_id, skill_id, student_id, skill_id, student_id, skill_id, student_id, skill_id),
        ).fetchone()

        if not agg or agg["current"] is None:
            continue

        baseline = agg["baseline"]
        current = agg["current"]
        highest = agg["highest"]
        growth = current - baseline if baseline is not None else 0
        band = performance_band(current)

        existing = db.execute(
            "SELECT student_skill_summary_id, baseline_score FROM student_skill_summary WHERE student_id = ? AND skill_id = ?",
            (student_id, skill_id),
        ).fetchone()

        if existing:
            # Preserve baseline once set; only update if NULL
            new_baseline = existing["baseline_score"] if existing["baseline_score"] is not None else baseline
            db.execute(
                """
                UPDATE student_skill_summary
                SET baseline_score = ?, current_score = ?, highest_score = ?,
                    latest_assessment_date = ?, growth_amount = ?,
                    performance_band = ?, updated_at = ?
                WHERE student_id = ? AND skill_id = ?
                """,
                (new_baseline, current, highest, agg["latest_date"],
                 current - new_baseline, band, ts, student_id, skill_id),
            )
        else:
            db.execute(
                """
                INSERT INTO student_skill_summary
                    (student_id, school_id, skill_id, baseline_score, current_score,
                     highest_score, latest_assessment_date, growth_amount,
                     performance_band, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, school_id, skill_id, baseline, current,
                 highest, agg["latest_date"], growth, band, ts),
            )

    # ------------------------------------------------------------------ #
    # 2. student_domain_summary — one row per (student, domain)           #
    # ------------------------------------------------------------------ #
    domains = db.execute(
        """
        SELECT DISTINCT sk.domain_id
        FROM assessment_scores a_sc
        JOIN assessments a ON a.assessment_id = a_sc.assessment_id
        JOIN skills sk ON sk.skill_id = a_sc.skill_id
        WHERE a_sc.student_id = ? AND a.deleted_at IS NULL
        """,
        (student_id,),
    ).fetchall()

    for d_row in domains:
        domain_id = d_row["domain_id"]

        domain_scores = db.execute(
            """
            SELECT sss.skill_id, sss.baseline_score, sss.current_score
            FROM student_skill_summary sss
            JOIN skills sk ON sk.skill_id = sss.skill_id
            WHERE sss.student_id = ? AND sk.domain_id = ?
              AND sss.current_score IS NOT NULL
            """,
            (student_id, domain_id),
        ).fetchall()

        if not domain_scores:
            continue

        current_scores = [r["current_score"] for r in domain_scores if r["current_score"] is not None]
        # Use only paired rows (both baseline and current set) for growth so the
        # numerator and denominator are consistent — prevents inflated growth when
        # some skills lack a baseline.
        paired = [r for r in domain_scores if r["current_score"] is not None and r["baseline_score"] is not None]
        baseline_scores = [r["baseline_score"] for r in paired]

        current_domain = sum(current_scores) / len(current_scores) if current_scores else None
        baseline_domain = sum(baseline_scores) / len(baseline_scores) if baseline_scores else None
        domain_growth = (current_domain - baseline_domain) if (current_domain is not None and baseline_domain is not None) else 0

        existing_d = db.execute(
            "SELECT student_domain_summary_id, baseline_domain_score FROM student_domain_summary WHERE student_id = ? AND domain_id = ?",
            (student_id, domain_id),
        ).fetchone()

        if existing_d:
            saved_baseline = existing_d["baseline_domain_score"] if existing_d["baseline_domain_score"] is not None else baseline_domain
            db.execute(
                """
                UPDATE student_domain_summary
                SET baseline_domain_score = ?, current_domain_score = ?,
                    growth_amount = ?, latest_update = ?
                WHERE student_id = ? AND domain_id = ?
                """,
                (saved_baseline, current_domain,
                 (current_domain - saved_baseline) if (current_domain is not None and saved_baseline is not None) else 0,
                 ts, student_id, domain_id),
            )
        else:
            db.execute(
                """
                INSERT INTO student_domain_summary
                    (student_id, domain_id, baseline_domain_score, current_domain_score,
                     growth_amount, latest_update)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (student_id, domain_id, baseline_domain, current_domain, domain_growth, ts),
            )

    # ------------------------------------------------------------------ #
    # 3. student_overall_summary — one row per student                    #
    # ------------------------------------------------------------------ #
    student = db.execute(
        "SELECT grade_level FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not student:
        return

    grade_band = _grade_band(student["grade_level"])

    def domain_avg(domain_name: str):
        row = db.execute(
            """
            SELECT sds.current_domain_score
            FROM student_domain_summary sds
            JOIN skill_domains sd ON sd.domain_id = sds.domain_id
            WHERE sds.student_id = ? AND sd.domain_name = ?
            LIMIT 1
            """,
            (student_id, domain_name),
        ).fetchone()
        return row["current_domain_score"] if row and row["current_domain_score"] is not None else None

    def skill_avg(skill_name: str):
        row = db.execute(
            """
            SELECT sss.current_score
            FROM student_skill_summary sss
            JOIN skills sk ON sk.skill_id = sss.skill_id
            WHERE sss.student_id = ? AND sk.skill_name = ?
            LIMIT 1
            """,
            (student_id, skill_name),
        ).fetchone()
        return row["current_score"] if row and row["current_score"] is not None else None

    physical = domain_avg("Physical / Psychomotor")
    sports = domain_avg("Sports Fundamentals")
    sel = domain_avg("SEL / Behavior")
    game_app = skill_avg("game_application")

    overall_skill = None
    overall_behavior = sel

    if grade_band == "K-2":
        # Physical 70% + SEL 30%
        if physical is not None and sel is not None:
            overall_skill = physical
            overall_ufit = round(physical * 0.70 + sel * 0.30, 1)
        elif physical is not None:
            overall_skill = physical
            overall_ufit = physical
        else:
            overall_ufit = sel

    elif grade_band == "3-5":
        # Physical/Sport 60% + SEL 25% + Game Application 15%
        phys_sport = None
        if physical is not None and sports is not None:
            phys_sport = (physical + sports) / 2
        elif physical is not None:
            phys_sport = physical
        elif sports is not None:
            phys_sport = sports

        # For 3-5, game_application skill doesn't exist yet — use phys_sport as proxy
        game_component = game_app if game_app is not None else phys_sport

        overall_skill = phys_sport
        if phys_sport is not None and sel is not None and game_component is not None:
            overall_ufit = round(phys_sport * 0.60 + sel * 0.25 + game_component * 0.15, 1)
        elif phys_sport is not None and sel is not None:
            overall_ufit = round(phys_sport * 0.75 + sel * 0.25, 1)
        elif phys_sport is not None:
            overall_ufit = phys_sport
        else:
            overall_ufit = sel

    else:  # 6-8
        # Sport Fundamentals 45% + Game Application 30% + SEL 25%
        overall_skill = sports

        # If no sports score, fall back to physical
        sports_component = sports if sports is not None else physical
        game_component = game_app if game_app is not None else sports_component

        if sports_component is not None and sel is not None and game_component is not None:
            overall_ufit = round(sports_component * 0.45 + game_component * 0.30 + sel * 0.25, 1)
        elif sports_component is not None and sel is not None:
            overall_ufit = round(sports_component * 0.70 + sel * 0.30, 1)
        elif sports_component is not None:
            overall_ufit = sports_component
        else:
            overall_ufit = sel

    readiness = performance_band(overall_ufit)

    existing_o = db.execute(
        "SELECT student_overall_summary_id FROM student_overall_summary WHERE student_id = ?",
        (student_id,),
    ).fetchone()

    if existing_o:
        db.execute(
            """
            UPDATE student_overall_summary
            SET overall_skill_score = ?, overall_behavior_score = ?,
                overall_ufit_score = ?, readiness_band = ?, latest_update = ?
            WHERE student_id = ?
            """,
            (overall_skill, overall_behavior, overall_ufit, readiness, ts, student_id),
        )
    else:
        db.execute(
            """
            INSERT INTO student_overall_summary
                (student_id, school_id, overall_skill_score, overall_behavior_score,
                 overall_ufit_score, readiness_band, latest_update)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (student_id, school_id, overall_skill, overall_behavior, overall_ufit, readiness, ts),
        )
