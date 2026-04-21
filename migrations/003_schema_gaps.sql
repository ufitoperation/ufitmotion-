-- 003_schema_gaps.sql
-- Closes spec gaps vs docs/requirements-external.md.
-- Safe to re-run on existing installs: each ALTER silently fails if column exists.

-- schools.contract_id (TABLE 2 spec field)
ALTER TABLE schools ADD COLUMN contract_id INTEGER REFERENCES contracts(contract_id) ON DELETE SET NULL;

-- users.linked_staff_id / linked_parent_id (TABLE 3 spec fields)
ALTER TABLE users ADD COLUMN linked_staff_id INTEGER REFERENCES staff_profiles(staff_id) ON DELETE SET NULL;
ALTER TABLE users ADD COLUMN linked_parent_id INTEGER REFERENCES parents(parent_id) ON DELETE SET NULL;

-- assessment_scores.observation_tag — required dropdown per spec Section 15
-- Valid values: independent | needs_prompt | inconsistent | strong_control | low_confidence | gameplay_transfer_observed
ALTER TABLE assessment_scores ADD COLUMN observation_tag TEXT;

-- ============================================================
-- INDEXES — add before production, critical for query performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_schools_org ON schools(organization_id);
CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_id, active_status);
CREATE INDEX IF NOT EXISTS idx_sessions_school_date ON sessions(school_id, session_date);
CREATE INDEX IF NOT EXISTS idx_sessions_program ON sessions(program_id);
CREATE INDEX IF NOT EXISTS idx_assessment_scores_student ON assessment_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_assessment_scores_skill ON assessment_scores(skill_id);
CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id, assessment_date);
CREATE INDEX IF NOT EXISTS idx_assessments_school ON assessments(school_id);
CREATE INDEX IF NOT EXISTS idx_eod_reports_school_date ON eod_reports(school_id, report_date);
CREATE INDEX IF NOT EXISTS idx_eod_reports_staff ON eod_reports(staff_id, report_date);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_student ON behavior_observations(student_id);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_session ON behavior_observations(session_id);
CREATE INDEX IF NOT EXISTS idx_coach_obs_staff ON coach_observations(observed_staff_id);
CREATE INDEX IF NOT EXISTS idx_student_skill_summary ON student_skill_summary(student_id, skill_id);
CREATE INDEX IF NOT EXISTS idx_student_domain_summary ON student_domain_summary(student_id, domain_id);
CREATE INDEX IF NOT EXISTS idx_incidents_school ON incident_reports(school_id, report_date);
CREATE INDEX IF NOT EXISTS idx_staff_assignments_school ON staff_assignments(school_id, active_status);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role, active_status);
