# Coach Performance Scoring System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans (if available) or follow manually to implement this plan task-by-task.

**Goal:** Automatically grade every Ufit coach 0–100 using compliance, student outcomes, and supervisor observation data already in the app.

**Architecture:** New `_coach_scoring.py` engine with three pillar functions. API routes in `admin_routes.py` and `coach_routes.py`. Nightly recalculation script persists rolling scores to `staff_profiles`. Admin scorecard modal + coach "My Performance" page in `app.js`.

**Tech Stack:** Python/Flask, SQLite (dev) / PostgreSQL (prod), Vanilla JS

**Design doc:** `docs/plans/2026-04-23-coach-scoring-design.md`

---

## Task 1: Database Migration

**Files:**
- Create: `migrations/supabase/step7_coach_scoring.sql`

**Step 1: Write migration SQL**

```sql
-- step7_coach_scoring.sql
-- Adds rolling score columns to staff_profiles and creates coach_performance_snapshots.

ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS rolling_score      NUMERIC(5,2);
ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS rolling_band       TEXT;
ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS score_last_updated TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS coach_performance_snapshots (
    snapshot_id          BIGSERIAL PRIMARY KEY,
    staff_id             BIGINT      NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    school_id            BIGINT      NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    window_id            BIGINT      REFERENCES assessment_windows(window_id) ON DELETE SET NULL,
    period_start         DATE        NOT NULL,
    period_end           DATE        NOT NULL,
    compliance_score     NUMERIC(5,2),
    outcomes_score       NUMERIC(5,2),
    observations_score   NUMERIC(5,2),
    overall_score        NUMERIC(5,2),
    performance_band     TEXT,
    eod_ontime_rate      NUMERIC(5,2),
    session_log_rate     NUMERIC(5,2),
    incident_file_rate   NUMERIC(5,2),
    assessment_part_rate NUMERIC(5,2),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coach_snapshots_staff    ON coach_performance_snapshots (staff_id);
CREATE INDEX IF NOT EXISTS idx_coach_snapshots_school   ON coach_performance_snapshots (school_id);
CREATE INDEX IF NOT EXISTS idx_coach_snapshots_window   ON coach_performance_snapshots (window_id);
CREATE INDEX IF NOT EXISTS idx_coach_snapshots_period   ON coach_performance_snapshots (period_end DESC);
```

**Step 2: Apply to local SQLite dev DB**

Open `migrations/001_sqlite_dev.sql`, append the SQLite-compatible equivalent (no `IF NOT EXISTS` on ALTER, use INTEGER instead of BIGSERIAL/NUMERIC):

```sql
-- At the end of 001_sqlite_dev.sql:
ALTER TABLE staff_profiles ADD COLUMN rolling_score      REAL;
ALTER TABLE staff_profiles ADD COLUMN rolling_band       TEXT;
ALTER TABLE staff_profiles ADD COLUMN score_last_updated TEXT;

CREATE TABLE IF NOT EXISTS coach_performance_snapshots (
    snapshot_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id             INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    school_id            INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    window_id            INTEGER REFERENCES assessment_windows(window_id) ON DELETE SET NULL,
    period_start         TEXT NOT NULL,
    period_end           TEXT NOT NULL,
    compliance_score     REAL,
    outcomes_score       REAL,
    observations_score   REAL,
    overall_score        REAL,
    performance_band     TEXT,
    eod_ontime_rate      REAL,
    session_log_rate     REAL,
    incident_file_rate   REAL,
    assessment_part_rate REAL,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Step 3: Apply to local dev DB**

```bash
cd /Users/jahleel/Desktop/ufit-motion
UFIT_SECRET_KEY=local-dev-key python -c "
from app import create_app; from app.database import get_db
app = create_app()
with app.app_context():
    db = get_db()
    db.execute('ALTER TABLE staff_profiles ADD COLUMN rolling_score REAL')
    db.execute('ALTER TABLE staff_profiles ADD COLUMN rolling_band TEXT')
    db.execute('ALTER TABLE staff_profiles ADD COLUMN score_last_updated TEXT')
    db.execute('''CREATE TABLE IF NOT EXISTS coach_performance_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL, school_id INTEGER NOT NULL,
        window_id INTEGER, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        compliance_score REAL, outcomes_score REAL, observations_score REAL,
        overall_score REAL, performance_band TEXT,
        eod_ontime_rate REAL, session_log_rate REAL,
        incident_file_rate REAL, assessment_part_rate REAL,
        created_at TEXT NOT NULL DEFAULT (datetime(\"now\")))''')
    db.commit(); print('OK')
"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add migrations/supabase/step7_coach_scoring.sql migrations/001_sqlite_dev.sql
git commit -m "feat(db): add coach performance scoring tables and staff_profiles columns"
```

---

## Task 2: Scoring Engine

**Files:**
- Create: `app/routes/_coach_scoring.py`
- Test: `tests/test_coach_scoring.py`

**Step 1: Write the failing test**

Create `tests/test_coach_scoring.py`:

```python
"""Tests for the coach scoring engine."""
import pytest
from datetime import date
from unittest.mock import MagicMock


def make_db(rows_by_query):
    """Returns a mock db where execute().fetchone/fetchall returns preset values."""
    db = MagicMock()
    def execute_side(sql, params=None):
        cursor = MagicMock()
        # Simple key: first 40 chars of stripped sql
        key = sql.strip()[:40]
        result = rows_by_query.get(key)
        if isinstance(result, list):
            cursor.fetchall.return_value = result
            cursor.fetchone.return_value = result[0] if result else None
        else:
            cursor.fetchone.return_value = result
            cursor.fetchall.return_value = [result] if result else []
        return cursor
    db.execute.side_effect = execute_side
    return db


def test_coach_performance_band_boundaries():
    from app.routes._coach_scoring import coach_performance_band
    assert coach_performance_band(95) == "Exceptional"
    assert coach_performance_band(90) == "Exceptional"
    assert coach_performance_band(89) == "Strong"
    assert coach_performance_band(75) == "Strong"
    assert coach_performance_band(74) == "Meeting Expectations"
    assert coach_performance_band(60) == "Meeting Expectations"
    assert coach_performance_band(59) == "Developing"
    assert coach_performance_band(45) == "Developing"
    assert coach_performance_band(44) == "Needs Improvement"
    assert coach_performance_band(0)  == "Needs Improvement"


def test_calculate_returns_none_overall_when_no_data():
    from app.routes._coach_scoring import calculate_coach_score
    # db returns nothing for all queries
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    db.execute.return_value.fetchall.return_value = []
    result = calculate_coach_score(
        db, staff_id=1, school_id=1,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31)
    )
    assert result["overall_score"] is None
    assert result["performance_band"] == "Needs Improvement"


def test_overall_score_excludes_observations_pillar_when_no_observations():
    from app.routes._coach_scoring import calculate_coach_score
    db = MagicMock()
    cursor = MagicMock()
    # All queries return 0/empty so only observations missing matters
    cursor.fetchone.return_value = {"cnt": 0, "avg_score": None, "total": 0,
                                     "ontime": 0, "flagged": 0, "filed": 0,
                                     "sessions_led": 0, "eod_days": 0,
                                     "enrolled": 0, "assessed": 0,
                                     "present": 0, "total_att": 0,
                                     "avg_sel": None, "avg_growth": None,
                                     "t": None, "e": None, "l": None,
                                     "s": None, "sa": None, "o": None}
    cursor.fetchall.return_value = []
    db.execute.return_value = cursor
    result = calculate_coach_score(
        db, staff_id=1, school_id=1,
        period_start=date(2026, 3, 1), period_end=date(2026, 3, 31)
    )
    # With no data in any pillar, overall should be None
    assert result["observations_score"] is None
```

**Step 2: Run to verify it fails**

```bash
cd /Users/jahleel/Desktop/ufit-motion
python -m pytest tests/test_coach_scoring.py -v 2>&1 | head -20
```

Expected: `ImportError` — `_coach_scoring` doesn't exist yet.

**Step 3: Implement `app/routes/_coach_scoring.py`**

```python
"""
_coach_scoring.py — Coach performance scoring engine.

Three-pillar model (weights adjustable if pillars are excluded):
  Compliance   35%  — EOD timeliness, session logging, incident filing, assessment participation
  Outcomes     35%  — Student skill growth, attendance, SEL at coach's school
  Observations 30%  — Supervisor coach_observations scores (1–5 → 0–100)

Returns a dict with overall_score (0–100), performance_band, and all component rates.
"""

from datetime import date, timedelta
from typing import Optional


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
    """Weighted average that redistributes when some keys are missing."""
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
    total_eods = eod_row["total"] if eod_row else 0
    ontime_eods = eod_row["ontime"] if eod_row else 0
    eod_ontime_rate = _safe_rate(ontime_eods, total_eods)

    # Session logging rate: distinct session dates logged as lead / distinct EOD report dates
    session_days_row = db.execute(
        "SELECT COUNT(DISTINCT session_date) AS session_days FROM sessions"
        " WHERE coach_lead_staff_id=? AND school_id=? AND session_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    eod_days_row = db.execute(
        "SELECT COUNT(DISTINCT report_date) AS eod_days FROM eod_reports"
        " WHERE staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    session_days = session_days_row["session_days"] if session_days_row else 0
    eod_days = eod_days_row["eod_days"] if eod_days_row else 0
    session_log_rate = _safe_rate(session_days, eod_days)

    # Incident filing rate (conditional — only if EODs flagged incidents)
    flagged_row = db.execute(
        "SELECT COUNT(*) AS flagged FROM eod_reports"
        " WHERE staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND injury_incident_flag=1 AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    flagged = flagged_row["flagged"] if flagged_row else 0
    filed_row = db.execute(
        "SELECT COUNT(*) AS filed FROM incident_reports"
        " WHERE reported_by_staff_id=? AND school_id=? AND report_date BETWEEN ? AND ?"
        " AND deleted_at IS NULL",
        (staff_id, school_id, ps, pe),
    ).fetchone()
    filed = filed_row["filed"] if filed_row else 0
    incident_file_rate = _safe_rate(filed, flagged) if flagged > 0 else None

    # Assessment participation rate (conditional — only during active windows)
    window_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM assessment_windows"
        " WHERE school_id=? AND status IN ('active','closed')"
        " AND start_date <= ? AND end_date >= ?",
        (school_id, pe, ps),
    ).fetchone()
    has_window = (window_row["cnt"] if window_row else 0) > 0
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
        enrolled = enrolled_row["enrolled"] if enrolled_row else 0
        assessed = assessed_row["assessed"] if assessed_row else 0
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

    # Average skill growth across all students at school
    growth_row = db.execute(
        "SELECT AVG(sds.current_domain_score - sds.baseline_domain_score) AS avg_growth"
        " FROM student_domain_summary sds"
        " JOIN students s ON s.student_id = sds.student_id"
        " WHERE s.school_id=? AND s.deleted_at IS NULL"
        " AND sds.baseline_domain_score IS NOT NULL AND sds.current_domain_score IS NOT NULL",
        (school_id,),
    ).fetchone()
    avg_growth = growth_row["avg_growth"] if growth_row else None
    if avg_growth is not None:
        # Normalize: 0 growth = 50, +40 pts growth = 100, -40 pts = 0
        growth_score = round(min(100.0, max(0.0, 50.0 + (float(avg_growth) / 40.0) * 50.0)), 2)
    else:
        growth_score = None

    # Participation rate: present attendances / total attendances
    att_row = db.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(CASE WHEN ssa.attendance_status='present' THEN 1 ELSE 0 END) AS present"
        " FROM student_session_attendance ssa"
        " JOIN sessions s ON s.session_id = ssa.session_id"
        " WHERE s.school_id=? AND s.session_date BETWEEN ? AND ?"
        " AND s.deleted_at IS NULL",
        (school_id, ps, pe),
    ).fetchone()
    total_att = att_row["total"] if att_row else 0
    present_att = att_row["present"] if att_row else 0
    participation_rate = _safe_rate(present_att, total_att)

    # Average SEL score (normalize 1–5 → 0–100)
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
    All scores are 0–100. None means insufficient data for that pillar.
    """
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


def rolling_period() -> tuple[date, date]:
    """Returns (start, end) for the trailing 30-day window."""
    end = date.today()
    start = end - timedelta(days=30)
    return start, end
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_coach_scoring.py -v
```

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add app/routes/_coach_scoring.py tests/test_coach_scoring.py
git commit -m "feat(scoring): add coach performance scoring engine with three-pillar model"
```

---

## Task 3: Backend API Routes

**Files:**
- Modify: `app/routes/admin_routes.py` — add 3 new endpoints
- Modify: `app/routes/coach_routes.py` — add 1 new endpoint

**Step 1: Add to `admin_routes.py` imports**

At the top of `admin_routes.py`, add to existing imports:

```python
from app.routes._coach_scoring import calculate_coach_score, rolling_period, coach_performance_band
from datetime import date as _date, timedelta as _timedelta
```

**Step 2: Add coach score endpoints to `admin_routes.py`**

Add after the existing `/api/admin/coaches` GET route (around line 760):

```python
@admin_bp.route("/api/admin/coaches/<int:staff_id>/score", methods=["GET"])
@admin_required
def get_coach_score(staff_id: int):
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    from_str = request.args.get("from")
    to_str   = request.args.get("to")
    try:
        period_start = _date.fromisoformat(from_str) if from_str else rolling_period()[0]
        period_end   = _date.fromisoformat(to_str)   if to_str   else rolling_period()[1]
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        # Verify staff belongs to this org
        staff = db.execute(
            "SELECT sp.staff_id, sp.user_id, sa.school_id"
            " FROM staff_profiles sp"
            " JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status=1"
            " JOIN schools sc ON sc.school_id = sa.school_id"
            " WHERE sp.staff_id=? AND sp.deleted_at IS NULL"
            + (" AND sc.organization_id=?" if org_id else ""),
            (staff_id, org_id) if org_id else (staff_id,),
        ).fetchone()
        if not staff:
            return jsonify({"error": "Coach not found."}), 404

        school_id = staff["school_id"]
        scorecard = calculate_coach_score(db, staff_id, school_id, period_start, period_end)

        # Include frozen snapshots for history
        snapshots = db.execute(
            "SELECT * FROM coach_performance_snapshots"
            " WHERE staff_id=? AND school_id=? ORDER BY period_end DESC LIMIT 12",
            (staff_id, school_id),
        ).fetchall()

        return jsonify({
            "ok": True,
            "scorecard": scorecard,
            "snapshots": [dict(r) for r in snapshots],
        })
    finally:
        db.close()


@admin_bp.route("/api/admin/coaches/<int:staff_id>/score/freeze", methods=["POST"])
@admin_required
def freeze_coach_score(staff_id: int):
    """Save a point-in-time snapshot of a coach's score (manual or end-of-window)."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    try:
        period_start = _date.fromisoformat(data.get("period_start") or rolling_period()[0].isoformat())
        period_end   = _date.fromisoformat(data.get("period_end")   or rolling_period()[1].isoformat())
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400
    window_id = data.get("window_id")

    db = get_db()
    try:
        org_id = _get_org_scope(db, user)
        staff = db.execute(
            "SELECT sp.staff_id, sa.school_id FROM staff_profiles sp"
            " JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status=1"
            " JOIN schools sc ON sc.school_id = sa.school_id"
            " WHERE sp.staff_id=? AND sp.deleted_at IS NULL"
            + (" AND sc.organization_id=?" if org_id else ""),
            (staff_id, org_id) if org_id else (staff_id,),
        ).fetchone()
        if not staff:
            return jsonify({"error": "Coach not found."}), 404

        school_id = staff["school_id"]
        sc = calculate_coach_score(db, staff_id, school_id, period_start, period_end)

        cur = db.execute(
            "INSERT INTO coach_performance_snapshots"
            " (staff_id, school_id, window_id, period_start, period_end,"
            "  compliance_score, outcomes_score, observations_score, overall_score,"
            "  performance_band, eod_ontime_rate, session_log_rate,"
            "  incident_file_rate, assessment_part_rate)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (staff_id, school_id, window_id,
             period_start.isoformat(), period_end.isoformat(),
             sc["compliance_score"], sc["outcomes_score"], sc["observations_score"],
             sc["overall_score"], sc["performance_band"],
             sc["eod_ontime_rate"], sc["session_log_rate"],
             sc["incident_file_rate"], sc["assessment_part_rate"]),
        )
        db.commit()
        return jsonify({"ok": True, "snapshot_id": cur.lastrowid, "scorecard": sc}), 201
    finally:
        db.close()
```

**Step 3: Add coach self-score endpoint to `coach_routes.py`**

Add after the existing `/api/my-students` route:

```python
@coach_bp.route("/api/coach/my-score", methods=["GET"])
@coach_required
def my_score():
    """Returns the requesting coach's rolling 30-day scorecard."""
    user = current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    staff_id  = user.get("staff_id")
    school_id = user.get("school_id")
    if not staff_id or not school_id:
        return jsonify({"error": "No active staff assignment."}), 403

    from app.routes._coach_scoring import calculate_coach_score, rolling_period
    period_start, period_end = rolling_period()

    db = get_db()
    try:
        scorecard = calculate_coach_score(db, staff_id, school_id, period_start, period_end)
        snapshots = db.execute(
            "SELECT * FROM coach_performance_snapshots"
            " WHERE staff_id=? AND school_id=? ORDER BY period_end DESC LIMIT 12",
            (staff_id, school_id),
        ).fetchall()
        return jsonify({
            "ok": True,
            "scorecard": scorecard,
            "snapshots": [dict(r) for r in snapshots],
        })
    finally:
        db.close()
```

**Step 4: Smoke test endpoints**

```bash
# Start dev server
UFIT_SECRET_KEY=local-dev-key python run.py &
# Login as admin, then:
curl -s -b cookies.txt http://localhost:5000/api/admin/coaches | python3 -m json.tool | head -20
```

**Step 5: Commit**

```bash
git add app/routes/admin_routes.py app/routes/coach_routes.py
git commit -m "feat(api): add coach score GET/freeze endpoints for admin and coach portals"
```

---

## Task 4: Nightly Recalculation Script

**Files:**
- Create: `scripts/recalculate_coach_scores.py`

**Step 1: Write the script**

```python
"""
recalculate_coach_scores.py — Updates rolling_score/rolling_band on all active staff.

Usage:
    UFIT_SECRET_KEY=<key> python scripts/recalculate_coach_scores.py

Run nightly via cron or Render cron job.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.database import get_db
from app.routes._coach_scoring import calculate_coach_score, rolling_period
from app.routes._helpers import now_utc


def run():
    app = create_app()
    with app.app_context():
        db = get_db()
        period_start, period_end = rolling_period()

        assignments = db.execute(
            "SELECT sa.staff_id, sa.school_id FROM staff_assignments sa"
            " JOIN staff_profiles sp ON sp.staff_id = sa.staff_id"
            " WHERE sa.active_status=1 AND sp.deleted_at IS NULL"
        ).fetchall()

        updated = 0
        for row in assignments:
            try:
                sc = calculate_coach_score(
                    db, row["staff_id"], row["school_id"], period_start, period_end
                )
                db.execute(
                    "UPDATE staff_profiles SET rolling_score=?, rolling_band=?, score_last_updated=?"
                    " WHERE staff_id=?",
                    (sc["overall_score"], sc["performance_band"], now_utc(), row["staff_id"]),
                )
                updated += 1
            except Exception as exc:
                print(f"  ERROR staff_id={row['staff_id']}: {exc}")

        db.commit()
        print(f"✓ Updated rolling scores for {updated} coaches ({period_start} → {period_end})")


if __name__ == "__main__":
    run()
```

**Step 2: Test run**

```bash
UFIT_SECRET_KEY=local-dev-key python scripts/recalculate_coach_scores.py
```

Expected: `✓ Updated rolling scores for N coaches (2026-03-24 → 2026-04-23)`

**Step 3: Commit**

```bash
git add scripts/recalculate_coach_scores.py
git commit -m "feat(scripts): add nightly coach score recalculation script"
```

---

## Task 5: Admin UI — Coach Scorecard

**Files:**
- Modify: `static/app.js` — update `loadCoachesPage`, add `openCoachScorecardModal`

**Step 1: Update `loadCoachesPage` table to include Score column**

Replace the existing table `thead` and `tbody` in `loadCoachesPage` (around line 748):

```javascript
// Replace thead:
<thead><tr><th>Coach</th><th>Role</th><th>School</th><th>Score</th><th>EODs This Week</th><th>Late</th><th>Incidents</th><th></th></tr></thead>

// Replace each tbody row (add score badge and View button):
coaches.map(c => {
  const late = c.late_submissions_this_week ?? 0;
  const band = c.rolling_band || '';
  const score = c.rolling_score != null ? Math.round(c.rolling_score) : null;
  const bandClass = {
    'Exceptional': 'badge-success', 'Strong': 'badge-success',
    'Meeting Expectations': '', 'Developing': 'badge-warning',
    'Needs Improvement': 'badge-error',
  }[band] || '';
  const _sid = _modalStore.set(c);
  return `<tr>
    <td><strong>${esc(c.first_name)} ${esc(c.last_name)}</strong>
        <div class="text-caption">${esc(c.email)}</div></td>
    <td><span class="badge">${esc(c.role)}</span></td>
    <td>${esc(c.school_name || '—')}</td>
    <td>${score != null
      ? `<span class="badge ${bandClass}">${score} · ${esc(band)}</span>`
      : '<span class="text-muted">—</span>'}</td>
    <td>${c.eod_submissions_this_week ?? 0}</td>
    <td class="${late > 0 ? 'text-error' : ''}">${late}</td>
    <td>${c.incidents_filed_this_week ?? 0}</td>
    <td><button class="btn btn-ghost btn-sm"
          onclick="openCoachScorecardModal(_modalStore.get(${_sid}))">Scorecard</button></td>
  </tr>`;
}).join('')
```

**Step 2: Add `rolling_score` and `rolling_band` to the admin coaches API query**

In `admin_routes.py`, find the `/api/admin/coaches` GET query (around line 734) and add `sp.rolling_score, sp.rolling_band` to the SELECT:

```python
# In the SELECT for list_coaches, add:
" sp.rolling_score, sp.rolling_band,"
```

**Step 3: Add `openCoachScorecardModal` to `app.js`**

Add after `loadCoachesPage`:

```javascript
async function openCoachScorecardModal(coach) {
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">${esc(coach.first_name)} ${esc(coach.last_name)} — Scorecard</h2>
      <button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body">
      <div id="scorecard-content">${renderSkeleton(3)}</div>
    </div>`);

  try {
    const d = await api('GET', `/api/admin/coaches/${coach.staff_id}/score`);
    const sc = d.scorecard || {};
    const snaps = d.snapshots || [];
    const el = document.getElementById('scorecard-content');
    if (!el) return;

    const overall = sc.overall_score != null ? Math.round(sc.overall_score) : null;
    const bandClass = {
      'Exceptional':'badge-success','Strong':'badge-success',
      'Meeting Expectations':'','Developing':'badge-warning','Needs Improvement':'badge-error'
    }[sc.performance_band] || '';

    const pillarBar = (label, score, detail) => {
      const pct = score != null ? Math.round(score) : 0;
      const color = pct >= 75 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `
        <div style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-weight:600;">${label}</span>
            <span>${score != null ? Math.round(score) + '/100' : 'N/A'}</span>
          </div>
          <div style="background:var(--color-border);border-radius:4px;height:8px;">
            <div style="width:${pct}%;background:${color};border-radius:4px;height:8px;transition:width 0.4s;"></div>
          </div>
          ${detail ? `<div class="text-caption" style="margin-top:4px;">${detail}</div>` : ''}
        </div>`;
    };

    const fmtRate = r => r != null ? Math.round(r) + '%' : 'N/A';

    const complianceDetail = [
      `EOD on-time: ${fmtRate(sc.eod_ontime_rate)}`,
      `Sessions logged: ${fmtRate(sc.session_log_rate)}`,
      sc.incident_file_rate != null ? `Incident filing: ${fmtRate(sc.incident_file_rate)}` : null,
      sc.assessment_part_rate != null ? `Assessment participation: ${fmtRate(sc.assessment_part_rate)}` : null,
    ].filter(Boolean).join(' · ');

    const outcomesDetail = [
      sc.avg_growth != null ? `Avg skill growth: ${sc.avg_growth > 0 ? '+' : ''}${sc.avg_growth}pts` : null,
      `Participation: ${fmtRate(sc.participation_rate)}`,
      sc.avg_sel_score != null ? `Avg SEL: ${sc.avg_sel_score.toFixed(1)}/5` : null,
    ].filter(Boolean).join(' · ');

    const obsDetail = sc.observation_count
      ? `Based on ${sc.observation_count} observation${sc.observation_count > 1 ? 's' : ''}`
      : 'No observations in this period';

    const historyRows = snaps.length ? snaps.map(s => `
      <tr>
        <td>${esc(s.period_start)} – ${esc(s.period_end)}</td>
        <td>${s.overall_score != null ? Math.round(s.overall_score) : '—'}</td>
        <td><span class="badge">${esc(s.performance_band || '—')}</span></td>
      </tr>`).join('') : `<tr><td colspan="3" class="text-muted">No frozen snapshots yet.</td></tr>`;

    el.innerHTML = `
      <div style="text-align:center;padding:16px 0 24px;">
        <div style="font-size:2.5rem;font-weight:700;color:var(--color-primary);">
          ${overall != null ? overall : '—'}
        </div>
        <span class="badge ${bandClass}" style="font-size:0.9rem;">${esc(sc.performance_band || 'No data')}</span>
        <div class="text-caption" style="margin-top:4px;">Rolling 30 days · ${esc(sc.period_start||'')} → ${esc(sc.period_end||'')}</div>
      </div>
      <div style="border-top:1px solid var(--color-border);padding-top:20px;">
        ${pillarBar('Compliance', sc.compliance_score, complianceDetail)}
        ${pillarBar('Student Outcomes', sc.outcomes_score, outcomesDetail)}
        ${pillarBar('Observations', sc.observations_score, obsDetail)}
      </div>
      <div style="border-top:1px solid var(--color-border);padding-top:16px;margin-top:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <strong>Frozen Score History</strong>
          <button class="btn btn-ghost btn-sm" id="freeze-score-btn">Freeze Now</button>
        </div>
        <table class="data-table">
          <thead><tr><th>Period</th><th>Score</th><th>Band</th></tr></thead>
          <tbody>${historyRows}</tbody>
        </table>
      </div>`;

    document.getElementById('freeze-score-btn')?.addEventListener('click', async () => {
      const btn = document.getElementById('freeze-score-btn');
      btn.disabled = true; btn.textContent = 'Saving…';
      try {
        await api('POST', `/api/admin/coaches/${coach.staff_id}/score/freeze`, {});
        showAlert('Score snapshot saved.', 'success');
        openCoachScorecardModal(coach); // refresh
      } catch (err) {
        showAlert(err.message, 'error');
        btn.disabled = false; btn.textContent = 'Freeze Now';
      }
    });
  } catch (err) {
    const el = document.getElementById('scorecard-content');
    if (el) el.innerHTML = errorCard(err.message);
  }
}
```

**Step 4: Verify JS syntax**

```bash
node --check static/app.js && echo OK
```

Expected: `OK`

**Step 5: Commit**

```bash
git add static/app.js app/routes/admin_routes.py
git commit -m "feat(ui): add coach scorecard modal with three-pillar breakdown and freeze history"
```

---

## Task 6: Coach Portal — My Performance Page

**Files:**
- Modify: `static/app.js` — add nav item, route case, page function

**Step 1: Add "Performance" to coach `navConfig`**

Find the `if (portal === 'coach')` block in `navConfig` (around line 353). Add a new entry — use a trophy/star icon:

```javascript
// Add to coach navConfig (after 'behavior' entry):
{ page: 'performance', label: 'My Score', icon: iconPerformance },
```

**Step 2: Add `iconPerformance` icon function**

In the icons section (near line 61), add:

```javascript
const iconPerformance = () => icon('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>');
```

**Step 3: Add route case to `renderPage`**

In the `coach` section of `renderPage`'s switch statement (around line 226), add:

```javascript
case 'performance': loadMyPerformancePage(main); break;
```

**Step 4: Add `PAGE_TITLES` entry**

Find `PAGE_TITLES` object (search for `'dashboard': 'Dashboard'`) and add:

```javascript
'performance': 'My Performance',
```

**Step 5: Add `loadMyPerformancePage` function**

Add after `loadBehaviorObsPage`:

```javascript
async function loadMyPerformancePage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">My Performance</div>
           <div class="text-caption">Your rolling 30-day score</div></div>
    </div>
    <div id="my-score-content">${renderSkeleton(3)}</div>`;

  try {
    const d = await api('GET', '/api/coach/my-score');
    const sc = d.scorecard || {};
    const snaps = d.snapshots || [];
    const el = document.getElementById('my-score-content');
    if (!el) return;

    const overall = sc.overall_score != null ? Math.round(sc.overall_score) : null;
    const bandClass = {
      'Exceptional':'badge-success','Strong':'badge-success',
      'Meeting Expectations':'','Developing':'badge-warning','Needs Improvement':'badge-error'
    }[sc.performance_band] || '';

    const pillarBar = (label, score, detail) => {
      const pct = score != null ? Math.round(score) : 0;
      const color = pct >= 75 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `
        <div class="card" style="padding:16px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:600;font-size:1rem;">${label}</span>
            <span style="font-size:1.25rem;font-weight:700;">${score != null ? Math.round(score) : 'N/A'}<span style="font-size:0.75rem;color:var(--color-text-secondary)">/100</span></span>
          </div>
          <div style="background:var(--color-border);border-radius:6px;height:10px;">
            <div style="width:${pct}%;background:${color};border-radius:6px;height:10px;transition:width 0.5s;"></div>
          </div>
          ${detail ? `<div class="text-caption" style="margin-top:6px;">${detail}</div>` : ''}
        </div>`;
    };

    const fmtRate = r => r != null ? Math.round(r) + '%' : 'N/A';
    const complianceDetail = [
      `EOD on-time: ${fmtRate(sc.eod_ontime_rate)}`,
      `Sessions logged: ${fmtRate(sc.session_log_rate)}`,
      sc.incident_file_rate != null ? `Incidents filed: ${fmtRate(sc.incident_file_rate)}` : null,
      sc.assessment_part_rate != null ? `Assessment: ${fmtRate(sc.assessment_part_rate)}` : null,
    ].filter(Boolean).join(' · ');

    const outcomesDetail = [
      sc.avg_growth != null ? `Avg student growth: ${sc.avg_growth > 0 ? '+' : ''}${sc.avg_growth}pts` : null,
      `Attendance: ${fmtRate(sc.participation_rate)}`,
    ].filter(Boolean).join(' · ');

    const historyRows = snaps.length ? snaps.map(s => `
      <tr>
        <td>${esc(s.period_start)} – ${esc(s.period_end)}</td>
        <td><strong>${s.overall_score != null ? Math.round(s.overall_score) : '—'}</strong></td>
        <td><span class="badge">${esc(s.performance_band || '—')}</span></td>
      </tr>`).join('')
      : `<tr><td colspan="3" class="text-muted" style="padding:12px;">No history yet.</td></tr>`;

    el.innerHTML = `
      <div class="card" style="text-align:center;padding:32px 16px;margin-bottom:20px;">
        <div style="font-size:3.5rem;font-weight:800;color:var(--color-primary);line-height:1;">
          ${overall != null ? overall : '—'}
        </div>
        <div style="margin-top:8px;"><span class="badge ${bandClass}" style="font-size:1rem;padding:6px 16px;">${esc(sc.performance_band || 'No data yet')}</span></div>
        <div class="text-caption" style="margin-top:8px;">Last 30 days · updated ${sc.period_end || 'today'}</div>
      </div>
      ${pillarBar('Compliance', sc.compliance_score, complianceDetail)}
      ${pillarBar('Student Outcomes', sc.outcomes_score, outcomesDetail)}
      ${pillarBar('Supervisor Observations', sc.observations_score,
          sc.observation_count ? `Based on ${sc.observation_count} observation${sc.observation_count>1?'s':''}` : 'No observations on record yet')}
      ${snaps.length ? `
        <div class="card" style="padding:16px;margin-top:8px;">
          <div style="font-weight:600;margin-bottom:12px;">Score History</div>
          <table class="data-table">
            <thead><tr><th>Period</th><th>Score</th><th>Band</th></tr></thead>
            <tbody>${historyRows}</tbody>
          </table>
        </div>` : ''}`;
  } catch (err) {
    const el = document.getElementById('my-score-content');
    if (el) el.innerHTML = errorCard(err.message);
  }
}
```

**Step 6: Verify JS syntax**

```bash
node --check static/app.js && echo OK
```

Expected: `OK`

**Step 7: Commit**

```bash
git add static/app.js
git commit -m "feat(ui): add coach My Performance page with pillar bars and score history"
```

---

## Task 7: Wire Up `reported_by_staff_id` in Incident Reports

The compliance pillar queries `incident_reports.reported_by_staff_id` but the schema uses `reported_by_staff_id` — verify the column name matches exactly.

**Step 1: Check schema**

```bash
grep -n "reported_by" /Users/jahleel/Desktop/ufit-motion/migrations/001_initial_schema.sql | head -5
```

If column is `reported_by_staff_id` — no change needed. If it's different (e.g., just `reported_by`), update the query in `_coach_scoring.py` `_compliance_pillar` accordingly.

**Step 2: Commit if any fix needed**

```bash
git add app/routes/_coach_scoring.py
git commit -m "fix(scoring): align incident_reports column name in compliance pillar"
```

---

## Task 8: Smoke Test End-to-End

**Step 1: Run seed data if not already present**

```bash
UFIT_SECRET_KEY=local-dev-key python scripts/seed_demo.py
```

**Step 2: Run recalculation**

```bash
UFIT_SECRET_KEY=local-dev-key python scripts/recalculate_coach_scores.py
```

Expected: `✓ Updated rolling scores for N coaches`

**Step 3: Start server and verify**

```bash
UFIT_SECRET_KEY=local-dev-key python run.py
```

- Log in as admin → Coaches page → Score column shows scores or "—"
- Click "Scorecard" on a coach → modal opens with three pillar bars
- Click "Freeze Now" → success alert, snapshot appears in history table
- Log in as a coach → "My Score" appears in sidebar → page shows their scorecard

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: coach performance scoring system — engine, API, admin scorecard, coach My Score page"
```
