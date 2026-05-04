-- step10: Add duration_minutes to sessions table.
--
-- Run this in Supabase SQL Editor after step9.

ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT NULL;
