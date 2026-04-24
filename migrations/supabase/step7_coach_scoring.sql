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
