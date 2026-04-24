# Coach Performance Scoring System — Design
**Date:** 2026-04-23  
**Status:** Approved

---

## Overview

Automatically grade every Ufit coach using data they already generate in the app. Produces a 0–100 score with three sub-pillar breakdown, a performance band label, a rolling 30-day live score, and frozen end-of-cycle snapshots for trend tracking.

---

## Visibility

| Role | Access |
|---|---|
| CEO / Admin | All coaches' scores |
| Coach | Own score only |
| Principal, Coach Overseer, Parent | No access |

---

## Three-Pillar Model

| Pillar | Weight | Source |
|---|---|---|
| Compliance | 35% | EOD reports, sessions, incidents, assessments |
| Student Outcomes | 35% | Growth, participation, SEL at coach's school |
| Observations | 30% | `coach_observations` table (supervisor-led) |

---

## Pillar 1: Compliance (35%)

Each component normalized to 0–100, then weighted within the pillar.

| Component | Weight | Formula | Conditional |
|---|---|---|---|
| EOD on-time rate | 40% | EODs submitted before 6pm ÷ total sessions logged | Always active |
| Session logging rate | 30% | Sessions logged ÷ sessions expected per schedule | Always active |
| Incident filing rate | 15% | Formal reports filed ÷ EODs with `injury_incident_flag = true` | **Excluded if no flagged EODs** |
| Assessment participation | 15% | Students assessed ÷ students enrolled | **Excluded if no active window** |

When a conditional component is excluded, its weight redistributes proportionally among the active components so the pillar always sums to 100%.

---

## Pillar 2: Student Outcomes (35%)

Covers **all students at the coach's assigned school** (not just directly assessed students).

| Component | Weight | Source table |
|---|---|---|
| Average skill growth | 50% | `student_overall_summary.overall_skill_score - baseline` |
| Participation rate | 30% | Present ÷ enrolled across all sessions at school |
| Average SEL score | 20% | `behavior_observations` at school, normalized 1–5 → 0–100 |

---

## Pillar 3: Observations (30%)

Average of 6 dimensions from `coach_observations`, each 1–5 normalized to 0–100:
- transitions_score
- engagement_score
- lesson_fidelity_score
- sel_language_score
- safety_score
- organization_score

If a coach has **zero observations** in the period, this pillar is excluded entirely. Its 30% redistributes evenly: Compliance → 50%, Outcomes → 50%.

---

## Overall Score & Performance Bands

```
Overall = (Compliance × 0.35) + (Outcomes × 0.35) + (Observations × 0.30)
```
Adjusted proportionally when pillars are excluded (see above).

| Score | Band |
|---|---|
| 90–100 | Exceptional |
| 75–89 | Strong |
| 60–74 | Meeting Expectations |
| 45–59 | Developing |
| 0–44 | Needs Improvement |

---

## Two Score Modes

### Rolling (Live)
- Recalculates nightly using trailing **30 days** of data
- What admins and coaches see day-to-day
- Stored in `staff_profiles` as `rolling_score`, `rolling_band`, `score_last_updated`

### Frozen (Historical)
- Saved to new table `coach_performance_snapshots` at close of each assessment window
- Enables trend view: "Fall Cycle 1: 71 → Spring Cycle 1: 79"
- Admin can trigger a manual freeze at any time

---

## New Database Objects

### `coach_performance_snapshots`
```sql
CREATE TABLE coach_performance_snapshots (
    snapshot_id         BIGSERIAL PRIMARY KEY,
    staff_id            BIGINT NOT NULL REFERENCES staff_profiles(staff_id),
    school_id           BIGINT NOT NULL REFERENCES schools(school_id),
    window_id           BIGINT REFERENCES assessment_windows(window_id),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    compliance_score    NUMERIC(5,2),
    outcomes_score      NUMERIC(5,2),
    observations_score  NUMERIC(5,2),
    overall_score       NUMERIC(5,2),
    performance_band    TEXT,
    -- compliance components
    eod_ontime_rate     NUMERIC(5,2),
    session_log_rate    NUMERIC(5,2),
    incident_file_rate  NUMERIC(5,2),
    assessment_part_rate NUMERIC(5,2),
    -- metadata
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Columns added to `staff_profiles`
```sql
ALTER TABLE staff_profiles ADD COLUMN rolling_score       NUMERIC(5,2);
ALTER TABLE staff_profiles ADD COLUMN rolling_band        TEXT;
ALTER TABLE staff_profiles ADD COLUMN score_last_updated  TIMESTAMPTZ;
```

---

## Scoring Engine

New module: `app/routes/_coach_scoring.py`

Key function:
```python
def calculate_coach_score(db, staff_id, school_id, period_start, period_end) -> dict:
    """
    Returns dict with compliance_score, outcomes_score, observations_score,
    overall_score, performance_band, and all component rates.
    """
```

Nightly recalculation: `scripts/recalculate_coach_scores.py` — iterates all active staff assignments, calls engine, updates `staff_profiles`.

---

## UI: Admin Portal

- **Coach roster table** — adds Score column showing `overall_score` + band badge
- **Coach scorecard modal** — triggered by clicking a coach row:
  - Three pillar bars (compliance / outcomes / observations)
  - Component breakdown within each pillar
  - Historical frozen scores table (if any snapshots exist)
  - "Freeze Score Now" button (admin only)

## UI: Coach Portal

- **New "My Performance" page** in coach nav:
  - Own scorecard only — same three-pillar layout
  - Last updated timestamp
  - Historical trend if frozen scores exist
  - No access to other coaches' scores

---

## Out of Scope (this version)

- Weighted score adjustments for extenuating circumstances (manual overrides)
- Coach-to-coach ranking leaderboard
- Automated alerts when a coach drops below a threshold
- Parent or principal visibility into coach scores
