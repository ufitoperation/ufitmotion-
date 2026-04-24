-- step6_sessions_soft_delete.sql
-- Adds soft-delete column to sessions table (already present in SQLite dev schema).
-- Run once against Supabase before deploying session soft-delete logic.

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_deleted_at ON sessions (deleted_at) WHERE deleted_at IS NULL;
