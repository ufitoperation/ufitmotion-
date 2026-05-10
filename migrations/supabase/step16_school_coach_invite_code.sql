-- step16: schools get a public invite code so coaches can self-register
-- without an admin manually adding them first ("Path 3" in the design doc).
--
-- The code is shareable by school staff or HR; redemption creates a PENDING
-- user (no password) + active assignment + emailed set-password link.
-- Regeneration immediately invalidates the previous code.

ALTER TABLE schools
  ADD COLUMN IF NOT EXISTS coach_invite_code TEXT;

ALTER TABLE schools
  ADD COLUMN IF NOT EXISTS coach_invite_code_expires_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_coach_invite_code
  ON schools (coach_invite_code)
  WHERE coach_invite_code IS NOT NULL;

-- Backfill: generate a code for any existing schools.
-- Format: <first-3-letters-of-name>-<8-char-hash>-<year>, uppercase.
UPDATE schools
SET coach_invite_code = UPPER(
        REGEXP_REPLACE(SUBSTRING(school_name FROM 1 FOR 3), '[^A-Za-z]', 'X', 'g')
        || '-'
        || SUBSTRING(MD5(school_id::TEXT || EXTRACT(EPOCH FROM NOW())::TEXT) FOR 8)
        || '-'
        || EXTRACT(YEAR FROM NOW())::TEXT
    ),
    coach_invite_code_expires_at = NOW() + INTERVAL '180 days'
WHERE coach_invite_code IS NULL;
