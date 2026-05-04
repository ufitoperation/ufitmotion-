-- step11_obs_soft_delete.sql
-- Adds soft-delete support to behavior_observations and coach_observations.
-- Matches the deleted_at column added to 001_sqlite_dev.sql.

ALTER TABLE behavior_observations
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

ALTER TABLE coach_observations
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_behavior_obs_deleted_at
  ON behavior_observations (deleted_at)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_coach_obs_deleted_at
  ON coach_observations (deleted_at)
  WHERE deleted_at IS NULL;
