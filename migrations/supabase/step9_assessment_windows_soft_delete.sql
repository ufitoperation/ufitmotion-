-- step9: Add deleted_at soft-delete column to assessment_windows.
--
-- Run this in Supabase SQL Editor after step8.

ALTER TABLE assessment_windows
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_assessment_windows_deleted_at
  ON assessment_windows (deleted_at) WHERE deleted_at IS NULL;
