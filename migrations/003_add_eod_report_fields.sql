-- Migration 003: Add Google Form fields to eod_reports
-- Phase 2B v5 — maps all 26 Google Form questions to database columns.
-- ufit_standards_notes is enforced NOT NULL at the application layer;
-- DEFAULT NULL here allows this migration to run against existing rows.

ALTER TABLE eod_reports ADD COLUMN incident_report_filed BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN school_concerns TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN school_concerns_resolved BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN school_concerns_notes TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN schedule_changes TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN coaches_clocked_in BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN late_arrivals TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN coaches_in_uniform BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN verbal_warnings TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN hr_app_issues TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN coaches_setup_ready BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN equipment_accounted BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN transitions_orderly BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN safety_hazards TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN yard_supervised BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN curriculum_followed BOOLEAN DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN equipment_requests TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN principal_communication_notes TEXT DEFAULT NULL;
ALTER TABLE eod_reports ADD COLUMN ufit_standards_notes TEXT DEFAULT NULL;

-- Rollback:
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS incident_report_filed;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS school_concerns;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS school_concerns_resolved;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS school_concerns_notes;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS schedule_changes;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS coaches_clocked_in;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS late_arrivals;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS coaches_in_uniform;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS verbal_warnings;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS hr_app_issues;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS coaches_setup_ready;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS equipment_accounted;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS transitions_orderly;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS safety_hazards;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS yard_supervised;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS curriculum_followed;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS equipment_requests;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS principal_communication_notes;
-- ALTER TABLE eod_reports DROP COLUMN IF EXISTS ufit_standards_notes;
