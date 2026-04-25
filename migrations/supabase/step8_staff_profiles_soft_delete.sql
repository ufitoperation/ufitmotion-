-- step8: Add deleted_at to staff_profiles and UNIQUE constraint on coach_performance_snapshots.
--
-- Run this in Supabase SQL Editor after step7.

-- 1. Soft-delete support on staff_profiles
ALTER TABLE staff_profiles
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_staff_profiles_deleted_at
  ON staff_profiles (deleted_at) WHERE deleted_at IS NULL;

-- 2. Prevent duplicate coach performance snapshots for the same period.
CREATE UNIQUE INDEX IF NOT EXISTS uq_coach_snapshots_period
  ON coach_performance_snapshots (staff_id, school_id, period_start, period_end);
