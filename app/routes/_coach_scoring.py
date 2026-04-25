"""
_coach_scoring.py — Coach performance scoring engine.

Three-pillar model (weights adjustable if pillars are excluded):
  Compliance   35%  — EOD timeliness, session logging, incident filing, assessment participation
  Outcomes     35%  — Student skill growth, attendance, SEL at coach's school
  Observations 30%  — Supervisor coach_observations scores (1-5 -> 0-100)

Returns a dict with overall_score (0-100), performance_band, and all component rates.
"""

from datetime import date, timedelta
from typing import Optional


def _get_today() -> date:
    """Return today's date. Module-level so tests can monkeypatch."""
    return date.today()


PILLAR_WEIGHTS = {"compliance": 0.35, "outcomes": 0.35, "observations": 0.30}


def coach_performance_band(score) -> str:
    if score is None:
        return "Needs Improvement"
    s = float(score)
    if s >= 90:
        return "Exceptional"
    if s >= 75:
        return "Strong"
    if s >= 60:
        return "Meeting Expectations"
    if s >= 45:
        return "Developing"
    return "Needs Improvement"


def _safe_rate(numerator, denominator) -> Optional[float]:
    """Returns numerator/denominator * 100, or None if denominator is 0."""
    if not denominator:
        return None
    return round(min(100.0, (numerator / denominator) * 100), 2)


def _weighted_average(components: dict, weights: dict) -> Optional[float]:
    """Weighted average that redistributes when some keys are None."""
    active = {k: v for k, v in components.items() if v is not None}
    if not active:
        return None
    total_w = sum(weights[k] for k in active)
    if total_w == 0:
        return None
    return round(sum(active[k] * weights[k] / total_w for k in active), 2)


def _compliance_pillar(db, staff_id: int, school_id: int,
                        period_start: date, period_end: date) -> dict:
    ps, pe = period_start.isoformat(), period_end.isoformat()

    # EOD on-time rate
    eod_row = db.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN submitted_on_time=1 THEN 1 ELSE 0 END) AS ontime"
        " FROM eod_reports WHERE staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    total_eods = (eod_row["total"] or 0) if eod_row else 0
    ontime_eods = (eod_row["ontime"] or 0) if eod_row else 0
    eod_ontime_rate = _safe_rate(ontime_eods, total_eods)

    # Session logging rate: distinct session dates led / distinct EOD report dates
    session_days_row = db.execute(
        "SELECT COUNT(DISTINCT s.session_date) AS session_days"
        " FROM sessions s"
        " JOIN session_staff ss ON ss.session_id = s.session_id"
        "  AND ss.staff_id=? AND ss.role='lead'"
        " WHERE s.school_id=? AND s.session_date BETWEEN ? AND ?"
        " AND s.deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    eod_days_row = db.execute(
        "SELECT COUNT(DISTINCT report_date) AS eod_days FROM eod_reports"
        " WHERE staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    session_days = (session_days_row["session_days"] or 0) if session_days_row else 0
    eod_days = (eod_days_row["eod_days"] or 0) if eod_days_row else 0
    session_log_rate = _safe_rate(session_days, eod_days)

    # Incident filing rate (conditional)
    flagged_row = db.execute(
        "SELECT COUNT(*) AS flagged FROM eod_reports"
        " WHERE staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND injury_incident_flag=1 AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    flagged = (flagged_row["flagged"] or 0) if flagged_row else 0
    filed_row = db.execute(
        "SELECT COUNT(*) AS filed FROM incident_reports"
        " WHERE reported_by_staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    filed = (filed_row["filed"] or 0) if filed_row else 0
    incident_file_rate = _safe_rate(filed, flagged) if flagged > 0 else None

    # Assessment participation rate (conditional — only during active windows)
    window_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM assessment_windows"
        " WHERE school_id=? AND status IN ('active','closed')"
        " AND start_date <= ? AND end_date >= ?",
        (school_id, pe, ps),
    ).fetchone()
    has_window = ((window_row["cnt"] or 0) if window_row else 0) > 0
    if has_window:
        enrolled_row = db.execute(
            "SELECT COUNT(*) AS enrolled FROM students"
            " WHERE school_id=? AND active_status=1 AND deleted_at IS NULL",
            (school_id,),
        ).fetchone()
        assessed_row = db.execute(
            "SELECT COUNT(DISTINCT student_id) AS assessed FROM assessments"
            " WHERE school_id=? AND assessment_date BETWEEN ? AND ? AND deleted_at IS NULL",
            (school_id, ps, pe),
        ).fetchone()
        enrolled = (enrolled_row["enrolled"] or 0) if enrolled_row else 0
        assessed = (assessed_row["assessed"] or 0) if assessed_row else 0
        assessment_part_rate = _safe_rate(assessed, enrolled)
    else:
        assessment_part_rate = None

    components = {
        "eod": eod_ontime_rate,
        "session": session_log_rate,
        "incident": incident_file_rate,
        "assessment": assessment_part_rate,
    }
    weights = {"eod": 0.40, "session": 0.30, "incident": 0.15, "assessment": 0.15}
    score = _weighted_average(components, weights)

    return {
        "score": score,
        "eod_ontime_rate": eod_ontime_rate,
        "session_log_rate": session_log_rate,
        "incident_file_rate": incident_file_rate,
        "assessment_part_rate": assessment_part_rate,
    }


def _outcomes_pillar(db, school_id: int,
                      period_start: date, period_end: date) -> dict:
    ps, pe = period_start.isoformat(), period_end.isoformat()

    # Average skill growth — scoped to students assessed within the period
    growth_row = db.execute(
        "SELECT AVG(sds.current_domain_score - sds.baseline_domain_score) AS avg_growth"
        " FROM student_domain_summary sds"
        " JOIN students s ON s.student_id = sds.student_id"
        " WHERE s.school_id=? AND s.deleted_at IS NULL"
        " AND sds.baseline_domain_score IS NOT NULL AND sds.current_domain_score IS NOT NULL"
        " AND EXISTS ("
        "   SELECT 1 FROM assessments a"
        "   WHERE a.student_id = sds.student_id"
        "     AND a.assessment_date BETWEEN ? AND ?"
        "     AND a.deleted_at IS NULL"
        " )",
        (school_id, ps, pe),
    ).fetchone()
    avg_growth = growth_row["avg_growth"] if growth_row else None
    if avg_growth is not None:
        growth_score = round(min(100.0, max(0.0, 50.0 + (float(avg_growth) / 40.0) * 50.0)), 2)
    else:
        growth_score = None

    # Participation rate
    att_row = db.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(CASE WHEN ssa.attendance_status='present' THEN 1 ELSE 0 END) AS present"
        " FROM student_session_attendance ssa"
        " JOIN sessions s ON s.session_id = ssa.session_id"
        " WHERE s.school_id=? AND s.session_date BETWEEN ? AND ?"
        " AND s.deleted_at IS NULL",
        (school_id, ps, pe),
    ).fetchone()
    total_att = (att_row["total"] or 0) if att_row else 0
    present_att = (att_row["present"] or 0) if att_row else 0
    participation_rate = _safe_rate(present_att, total_att)

    # Average SEL score (normalize 1-5 to 0-100)
    sel_row = db.execute(
        "SELECT AVG(CAST(teamwork_score + effort_score + self_control_score"
        " + listening_score + sportsmanship_score + confidence_score AS REAL) / 6.0) AS avg_sel"
        " FROM behavior_observations"
        " WHERE school_id=? AND observation_date BETWEEN ? AND ?",
        (school_id, ps, pe),
    ).fetchone()
    avg_sel = sel_row["avg_sel"] if sel_row else None
    sel_score = round(((float(avg_sel) - 1.0) / 4.0) * 100.0, 2) if avg_sel else None

    components = {"growth": growth_score, "participation": participation_rate, "sel": sel_score}
    weights = {"growth": 0.50, "participation": 0.30, "sel": 0.20}
    score = _weighted_average(components, weights)

    return {
        "score": score,
        "avg_growth": round(float(avg_growth), 2) if avg_growth is not None else None,
        "participation_rate": participation_rate,
        "avg_sel_score": round(float(avg_sel), 2) if avg_sel is not None else None,
    }


def _observations_pillar(db, staff_id: int, school_id: int,
                           period_start: date, period_end: date) -> dict:
    ps, pe = period_start.isoformat(), period_end.isoformat()

    row = db.execute(
        "SELECT AVG(transitions_score) AS t, AVG(engagement_score) AS e,"
        " AVG(lesson_fidelity_score) AS l, AVG(sel_language_score) AS s,"
        " AVG(safety_score) AS sa, AVG(organization_score) AS o,"
        " COUNT(*) AS cnt"
        " FROM coach_observations"
        " WHERE observed_staff_id=? AND school_id=? AND observation_date BETWEEN ? AND ?",
        (staff_id, school_id, ps, pe),
    ).fetchone()

    if not row or not row["cnt"]:
        return {"score": None, "observation_count": 0, "dimension_scores": {}}

    dims = {
        "transitions": row["t"], "engagement": row["e"],
        "lesson_fidelity": row["l"], "sel_language": row["s"],
        "safety": row["sa"], "organization": row["o"],
    }
    active_dims = {k: float(v) for k, v in dims.items() if v is not None}
    if not active_dims:
        return {"score": None, "observation_count": row["cnt"], "dimension_scores": {}}

    avg_raw = sum(active_dims.values()) / len(active_dims)
    obs_score = round(((avg_raw - 1.0) / 4.0) * 100.0, 2)

    return {
        "score": obs_score,
        "observation_count": row["cnt"],
        "dimension_scores": {k: round(((v - 1.0) / 4.0) * 100.0, 2) for k, v in active_dims.items()},
    }


def calculate_coach_score(db, staff_id: int, school_id: int,
                           period_start: date, period_end: date) -> dict:
    """
    Returns full scorecard dict for a coach over the given period.
    All scores are 0-100. None means insufficient data for that pillar.
    """
    if period_start > period_end:
        raise ValueError(f"period_start ({period_start}) must be <= period_end ({period_end})")
    c   = _compliance_pillar(db, staff_id, school_id, period_start, period_end)
    o   = _outcomes_pillar(db, school_id, period_start, period_end)
    obs = _observations_pillar(db, staff_id, school_id, period_start, period_end)

    pillars = {
        "compliance":   c["score"],
        "outcomes":     o["score"],
        "observations": obs["score"],
    }
    overall = _weighted_average(pillars, PILLAR_WEIGHTS)

    return {
        "overall_score":        overall,
        "performance_band":     coach_performance_band(overall),
        "compliance_score":     c["score"],
        "outcomes_score":       o["score"],
        "observations_score":   obs["score"],
        "eod_ontime_rate":      c["eod_ontime_rate"],
        "session_log_rate":     c["session_log_rate"],
        "incident_file_rate":   c["incident_file_rate"],
        "assessment_part_rate": c["assessment_part_rate"],
        "avg_growth":           o["avg_growth"],
        "participation_rate":   o["participation_rate"],
        "avg_sel_score":        o["avg_sel_score"],
        "observation_count":    obs["observation_count"],
        "dimension_scores":     obs["dimension_scores"],
        "period_start":         period_start.isoformat(),
        "period_end":           period_end.isoformat(),
    }


def rolling_period() -> tuple:
    """Returns (start, end) for the trailing 30-day window."""
    end = _get_today()
    start = end - timedelta(days=30)
    return start, end
