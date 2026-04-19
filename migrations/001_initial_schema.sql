-- =============================================================================
-- Ufit Motion — Initial Schema Migration
-- Version: 001
-- Description: Complete PostgreSQL schema for the Ufit Motion multi-org PE
--              management platform serving K-12 school districts. Covers
--              organizations, schools, staff, students, programs, sessions,
--              assessments, behavior, reporting, and system tables.
-- Safe to re-run (IF NOT EXISTS throughout).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ===========================================================================
-- TABLE 1: organizations
-- Represents a school district or other top-level billing/contractual entity.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    organization_id     BIGSERIAL PRIMARY KEY,
    organization_name   TEXT        NOT NULL,
    organization_type   TEXT        NOT NULL DEFAULT 'school_district',
    billing_contact     TEXT,
    billing_email       TEXT,
    contract_status     TEXT        NOT NULL DEFAULT 'active'
                            CHECK (contract_status IN ('active', 'inactive', 'pending')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE organizations IS
    'Top-level billing and contractual entities (typically school districts). '
    'All schools belong to an organization. Soft-deleted via deleted_at.';


-- ===========================================================================
-- TABLE 2: regions
-- Geographic or operational regions used for staff assignment and reporting.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regions (
    region_id       BIGSERIAL PRIMARY KEY,
    region_name     TEXT        NOT NULL UNIQUE,
    state           TEXT        NOT NULL,
    active_status   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE regions IS
    'Geographic or operational groupings used for staff assignment and '
    'regional reporting rollups.';


-- ===========================================================================
-- TABLE 3: contracts
-- Service contracts between Ufit and an organization (and optionally a school).
-- NOTE: school_id FK is added via ALTER TABLE after schools is created.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contracts (
    contract_id     BIGSERIAL PRIMARY KEY,
    organization_id BIGINT      NOT NULL REFERENCES organizations (organization_id) ON DELETE CASCADE,
    school_id       BIGINT,                         -- FK added post-schools via ALTER TABLE
    contract_value  NUMERIC(10, 2),
    start_date      DATE        NOT NULL,
    end_date        DATE        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'expired', 'pending', 'cancelled')),
    document_url    TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE contracts IS
    'Service contracts linking Ufit to a district organization, optionally '
    'scoped to a specific school. school_id FK applied after schools table.';


-- ===========================================================================
-- TABLE 4: schools
-- Individual school sites served by Ufit programs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schools (
    school_id                   BIGSERIAL PRIMARY KEY,
    organization_id             BIGINT      NOT NULL REFERENCES organizations (organization_id) ON DELETE CASCADE,
    school_name                 TEXT        NOT NULL,
    school_type                 TEXT        NOT NULL DEFAULT 'elementary'
                                    CHECK (school_type IN ('elementary', 'middle', 'high', 'k8', 'other')),
    address                     TEXT,
    principal_name              TEXT,
    principal_email             TEXT,
    assistant_principal_name    TEXT,
    assistant_principal_email   TEXT,
    grade_levels_served         TEXT,
    enrollment                  INTEGER,
    active_status               BOOLEAN     NOT NULL DEFAULT TRUE,
    start_date_with_ufit        DATE,
    end_date_with_ufit          DATE,
    bell_schedule_notes         TEXT,
    yard_notes                  TEXT,
    site_specific_rules         TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE schools IS
    'Individual school sites contracted with Ufit. Each school belongs to an '
    'organization (district). Soft-deleted via deleted_at.';


-- ===========================================================================
-- TABLE 5: users
-- All platform users across every role — staff, school staff, parents, admins.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id                     BIGSERIAL PRIMARY KEY,
    auth_uid                    UUID                 UNIQUE DEFAULT NULL,  -- Supabase Auth hybrid
    first_name                  TEXT        NOT NULL,
    last_name                   TEXT        NOT NULL,
    email                       TEXT        NOT NULL UNIQUE,
    phone                       TEXT,
    password_hash               TEXT,
    role                        TEXT        NOT NULL
                                    CHECK (role IN (
                                        'ceo', 'admin', 'coach_overseer', 'site_coordinator',
                                        'head_coach', 'assistant_coach', 'principal',
                                        'school_staff', 'parent'
                                    )),
    active_status               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login                  TIMESTAMPTZ,
    deleted_at                  TIMESTAMPTZ          DEFAULT NULL,
    password_reset_token        TEXT,
    password_reset_expires_at   TIMESTAMPTZ,
    email_verified              BOOLEAN     NOT NULL DEFAULT FALSE,
    email_verified_at           TIMESTAMPTZ
);

COMMENT ON TABLE users IS
    'All authenticated platform users across every role. Supports both '
    'Supabase Auth (auth_uid) and password-based login. Soft-deleted via deleted_at.';


-- ===========================================================================
-- TABLE 6: staff_profiles
-- Extended profile for Ufit coaches and coordinators linked to a user record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staff_profiles (
    staff_id            BIGSERIAL PRIMARY KEY,
    user_id             BIGINT      NOT NULL UNIQUE REFERENCES users (user_id) ON DELETE CASCADE,
    employee_type       TEXT        NOT NULL DEFAULT 'part_time'
                            CHECK (employee_type IN ('full_time', 'part_time', 'contractor', 'volunteer')),
    date_hired          DATE,
    pay_rate            NUMERIC(8, 2),
    position_title      TEXT,
    assigned_region_id  BIGINT      REFERENCES regions (region_id) ON DELETE SET NULL,
    livescan_status     TEXT        DEFAULT 'pending'
                            CHECK (livescan_status IN ('pending', 'submitted', 'cleared', 'expired')),
    livescan_date       DATE,
    tb_status           TEXT        DEFAULT 'pending'
                            CHECK (tb_status IN ('pending', 'submitted', 'cleared', 'expired')),
    tb_expiration       DATE,
    training_level      TEXT,
    notes               TEXT,
    status              TEXT        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'inactive', 'on_leave')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE staff_profiles IS
    'Extended HR and compliance profile for all Ufit coaches, coordinators, '
    'and volunteers. One-to-one with users. Tracks livescan, TB clearance, pay.';


-- ===========================================================================
-- TABLE 7: staff_assignments
-- Maps staff to school sites and programs with their role for that assignment.
-- NOTE: program_id FK is added via ALTER TABLE after programs is created.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staff_assignments (
    assignment_id       BIGSERIAL PRIMARY KEY,
    staff_id            BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    school_id           BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_id          BIGINT,                     -- FK added post-programs via ALTER TABLE
    assignment_role     TEXT        NOT NULL
                            CHECK (assignment_role IN (
                                'head_coach', 'assistant_coach', 'site_coordinator', 'observer'
                            )),
    start_date          DATE        NOT NULL,
    end_date            DATE,
    active_status       BOOLEAN     NOT NULL DEFAULT TRUE,
    default_schedule    TEXT,
    supervisor_staff_id BIGINT      REFERENCES staff_profiles (staff_id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE staff_assignments IS
    'Assigns staff members to specific school sites and programs with a '
    'designated role. Supports multi-site staff and supervisor tracking.';


-- ===========================================================================
-- TABLE 8: parents
-- Parent/guardian profiles with portal access configuration.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parents (
    parent_id               BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT      UNIQUE REFERENCES users (user_id) ON DELETE CASCADE,
    first_name              TEXT        NOT NULL,
    last_name               TEXT        NOT NULL,
    email                   TEXT        NOT NULL,
    phone                   TEXT,
    preferred_contact       TEXT        DEFAULT 'email'
                                CHECK (preferred_contact IN ('email', 'phone', 'sms')),
    portal_access_status    BOOLEAN     NOT NULL DEFAULT FALSE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE parents IS
    'Parent and guardian contact profiles. Optionally linked to a user account '
    'for parent portal access. Connected to students via parent_primary/secondary FK.';


-- ===========================================================================
-- TABLE 9: students
-- Student roster per school with enrollment and parent linkage.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    student_id                  BIGSERIAL PRIMARY KEY,
    school_id                   BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    student_first_name          TEXT        NOT NULL,
    student_last_name           TEXT        NOT NULL,
    local_student_identifier    TEXT,
    grade_level                 TEXT        NOT NULL,
    homeroom_teacher            TEXT,
    gender                      TEXT,
    active_status               BOOLEAN     NOT NULL DEFAULT TRUE,
    enrollment_start            DATE,
    enrollment_end              DATE,
    parent_primary_id           BIGINT      REFERENCES parents (parent_id) ON DELETE SET NULL,
    parent_secondary_id         BIGINT      REFERENCES parents (parent_id) ON DELETE SET NULL,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE students IS
    'Student roster for each school. Supports up to two parent/guardian links. '
    'local_student_identifier maps to the district SIS ID. Soft-deleted via deleted_at.';


-- ===========================================================================
-- TABLE 10: programs
-- A discrete Ufit program offering at a school (e.g., PE Support, After-School).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS programs (
    program_id      BIGSERIAL PRIMARY KEY,
    school_id       BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_name    TEXT        NOT NULL,
    program_type    TEXT        NOT NULL
                        CHECK (program_type IN (
                            'pe_support', 'lunch_sports', 'after_school_sports',
                            'psychomotor', 'middle_school_skill_development',
                            'tournament_program', 'wellness_enrichment'
                        )),
    service_model   TEXT,
    grade_band      TEXT,
    start_date      DATE        NOT NULL,
    end_date        DATE,
    frequency       TEXT,
    program_status  TEXT        NOT NULL DEFAULT 'active'
                        CHECK (program_status IN ('active', 'inactive', 'completed', 'upcoming')),
    reporting_cycle TEXT,
    max_students    INTEGER,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE programs IS
    'Distinct Ufit program offerings at a school site (PE support, lunch sports, '
    'after-school, psychomotor, etc.). Programs contain sessions and enrollments.';


-- ===========================================================================
-- TABLE 11: student_program_enrollment
-- Junction: which students are enrolled in which programs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_program_enrollment (
    enrollment_id   BIGSERIAL PRIMARY KEY,
    student_id      BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    program_id      BIGINT      NOT NULL REFERENCES programs (program_id) ON DELETE CASCADE,
    enrollment_date DATE        NOT NULL DEFAULT CURRENT_DATE,
    status          TEXT        NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive', 'waitlisted', 'completed')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, program_id)
);

COMMENT ON TABLE student_program_enrollment IS
    'Junction table recording which students are enrolled in which programs, '
    'with enrollment date and status tracking.';


-- ===========================================================================
-- TABLE 12: sessions
-- A single scheduled or completed class/activity session within a program.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id              BIGSERIAL PRIMARY KEY,
    school_id               BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_id              BIGINT      NOT NULL REFERENCES programs (program_id) ON DELETE CASCADE,
    session_date            DATE        NOT NULL,
    start_time              TIME,
    end_time                TIME,
    session_type            TEXT        NOT NULL DEFAULT 'regular'
                                CHECK (session_type IN (
                                    'regular', 'makeup', 'assessment', 'tournament', 'special'
                                )),
    location                TEXT,
    planned_activity        TEXT,
    actual_activity         TEXT,
    student_group_name      TEXT,
    session_status          TEXT        NOT NULL DEFAULT 'completed'
                                CHECK (session_status IN (
                                    'completed', 'cancelled', 'partial', 'planned'
                                )),
    total_students_present  INTEGER     DEFAULT 0,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sessions IS
    'Individual PE or program sessions at a school. Captures planned vs. actual '
    'activities, attendance counts, and session status for compliance tracking.';


-- ===========================================================================
-- TABLE 13: session_staff
-- Junction: which staff members were present and in what role for a session.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_staff (
    session_staff_id    BIGSERIAL PRIMARY KEY,
    session_id          BIGINT      NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    staff_id            BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    role                TEXT        NOT NULL DEFAULT 'lead'
                            CHECK (role IN ('lead', 'assistant', 'observer')),
    UNIQUE (session_id, staff_id)
);

COMMENT ON TABLE session_staff IS
    'Junction table recording which staff members participated in each session '
    'and their role (lead, assistant, observer).';


-- ===========================================================================
-- TABLE 14: student_session_attendance
-- Per-student attendance record for each session.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_session_attendance (
    attendance_id           BIGSERIAL PRIMARY KEY,
    session_id              BIGINT      NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    student_id              BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    attendance_status       TEXT        NOT NULL DEFAULT 'present'
                                CHECK (attendance_status IN ('present', 'absent', 'excused', 'partial')),
    participation_level     TEXT
                                CHECK (participation_level IN ('full', 'moderate', 'limited', 'refused')),
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, student_id)
);

COMMENT ON TABLE student_session_attendance IS
    'Individual student attendance and participation records per session. '
    'Drives participation rate calculations in summary tables.';


-- ===========================================================================
-- TABLE 15: skill_domains
-- High-level groupings of skills (Physical/Psychomotor, Sports, SEL).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skill_domains (
    domain_id       BIGSERIAL PRIMARY KEY,
    domain_name     TEXT        NOT NULL UNIQUE,
    domain_type     TEXT        NOT NULL
                        CHECK (domain_type IN (
                            'physical_psychomotor', 'sports_fundamentals', 'sel_behavior'
                        )),
    grade_band      TEXT,
    active_status   BOOLEAN     NOT NULL DEFAULT TRUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE skill_domains IS
    'Top-level skill groupings used to organize assessments and reporting. '
    'Three core types: physical/psychomotor, sports fundamentals, SEL/behavior.';


-- ===========================================================================
-- TABLE 16: skills
-- Individual assessable skills within a domain.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skills (
    skill_id            BIGSERIAL PRIMARY KEY,
    domain_id           BIGINT      NOT NULL REFERENCES skill_domains (domain_id) ON DELETE CASCADE,
    skill_name          TEXT        NOT NULL,
    grade_band          TEXT        NOT NULL,
    sport_type          TEXT,
    skill_description   TEXT,
    assessment_type     TEXT        NOT NULL DEFAULT 'observational'
                            CHECK (assessment_type IN ('observational', 'drill', 'gameplay')),
    active_status       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (skill_name, grade_band)
);

COMMENT ON TABLE skills IS
    'Individual assessable skills within a domain. Each skill is grade-band '
    'specific and may be tied to a sport or physical literacy category.';


-- ===========================================================================
-- TABLE 17: benchmarks
-- Rubric levels (1-5) for scoring a specific skill within a grade band.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS benchmarks (
    benchmark_id            BIGSERIAL PRIMARY KEY,
    skill_id                BIGINT      NOT NULL REFERENCES skills (skill_id) ON DELETE CASCADE,
    grade_band              TEXT        NOT NULL,
    level_number            INTEGER     NOT NULL CHECK (level_number BETWEEN 1 AND 5),
    level_name              TEXT        NOT NULL
                                CHECK (level_name IN (
                                    'Emerging', 'Developing', 'Functional', 'Proficient', 'Advanced'
                                )),
    benchmark_description   TEXT        NOT NULL,
    observable_criteria     TEXT,
    scoring_notes           TEXT,
    active_status           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (skill_id, grade_band, level_number)
);

COMMENT ON TABLE benchmarks IS
    'Five-level rubric descriptors for each skill by grade band. Coaches '
    'reference these to assign consistent raw_level scores in assessments.';


-- ===========================================================================
-- TABLE 18: assessment_windows
-- Defined periods during which assessments are conducted at a school.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_windows (
    window_id           BIGSERIAL PRIMARY KEY,
    school_id           BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_id          BIGINT      REFERENCES programs (program_id) ON DELETE SET NULL,
    window_name         TEXT        NOT NULL,
    start_date          DATE        NOT NULL,
    end_date            DATE        NOT NULL,
    assessment_focus    TEXT,
    status              TEXT        NOT NULL DEFAULT 'upcoming'
                            CHECK (status IN ('upcoming', 'active', 'closed', 'archived')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE assessment_windows IS
    'Defined assessment periods (baseline, mid-year, end-of-year) for a school '
    'or program. Assessment records link to a window for period-based reporting.';


-- ===========================================================================
-- TABLE 19: assessments
-- A single assessment event for one student by one staff member.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessments (
    assessment_id               BIGSERIAL PRIMARY KEY,
    student_id                  BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    school_id                   BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_id                  BIGINT      REFERENCES programs (program_id) ON DELETE SET NULL,
    session_id                  BIGINT      REFERENCES sessions (session_id) ON DELETE SET NULL,
    window_id                   BIGINT      REFERENCES assessment_windows (window_id) ON DELETE SET NULL,
    assessed_by_staff_id        BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    assessment_date             DATE        NOT NULL,
    assessment_method           TEXT        NOT NULL DEFAULT 'observational'
                                    CHECK (assessment_method IN (
                                        'observational', 'drill', 'gameplay', 'combined'
                                    )),
    overall_assessment_notes    TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE assessments IS
    'Header record for one student assessment event. Detailed scores per skill '
    'are stored in assessment_scores. Soft-deleted via deleted_at.';


-- ===========================================================================
-- TABLE 20: assessment_scores
-- Individual skill scores within an assessment, one row per skill assessed.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_scores (
    score_id                BIGSERIAL PRIMARY KEY,
    assessment_id           BIGINT      NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    student_id              BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    skill_id                BIGINT      NOT NULL REFERENCES skills (skill_id) ON DELETE CASCADE,
    benchmark_id            BIGINT      REFERENCES benchmarks (benchmark_id) ON DELETE SET NULL,
    raw_level               INTEGER     NOT NULL CHECK (raw_level BETWEEN 1 AND 5),
    normalized_score        INTEGER     NOT NULL GENERATED ALWAYS AS (raw_level * 20) STORED,
    confidence_rating       TEXT
                                CHECK (confidence_rating IN ('low', 'medium', 'high')),
    observed_independence   BOOLEAN     DEFAULT TRUE,
    observed_consistency    BOOLEAN     DEFAULT FALSE,
    observed_accuracy       BOOLEAN     DEFAULT FALSE,
    growth_flag             BOOLEAN     DEFAULT FALSE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (assessment_id, skill_id)
);

COMMENT ON TABLE assessment_scores IS
    'One row per skill scored within an assessment event. normalized_score '
    '(raw_level * 20) is stored for consistent 0-100 reporting. Drives summaries.';


-- ===========================================================================
-- TABLE 21: behavior_observations
-- Standalone SEL/behavior scoring for a student during a session.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS behavior_observations (
    behavior_observation_id BIGSERIAL PRIMARY KEY,
    student_id              BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    school_id               BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    session_id              BIGINT      REFERENCES sessions (session_id) ON DELETE SET NULL,
    observed_by_staff_id    BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    observation_date        DATE        NOT NULL,
    teamwork_score          INTEGER     CHECK (teamwork_score BETWEEN 1 AND 5),
    effort_score            INTEGER     CHECK (effort_score BETWEEN 1 AND 5),
    self_control_score      INTEGER     CHECK (self_control_score BETWEEN 1 AND 5),
    listening_score         INTEGER     CHECK (listening_score BETWEEN 1 AND 5),
    sportsmanship_score     INTEGER     CHECK (sportsmanship_score BETWEEN 1 AND 5),
    confidence_score        INTEGER     CHECK (confidence_score BETWEEN 1 AND 5),
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE behavior_observations IS
    'Session-level SEL and behavior ratings for individual students across six '
    'dimensions (teamwork, effort, self-control, listening, sportsmanship, confidence).';


-- ===========================================================================
-- TABLE 22: eod_reports
-- End-of-day coach reports submitted after each session.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eod_reports (
    eod_id                          BIGSERIAL PRIMARY KEY,
    school_id                       BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    staff_id                        BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    program_id                      BIGINT      REFERENCES programs (program_id) ON DELETE SET NULL,
    session_id                      BIGINT      REFERENCES sessions (session_id) ON DELETE SET NULL,
    report_date                     DATE        NOT NULL,
    attendance_summary              TEXT,
    activities_completed            TEXT        NOT NULL,
    student_engagement_summary      TEXT        NOT NULL,
    behavior_summary                TEXT,
    success_story                   TEXT,
    challenge_summary               TEXT,
    injury_incident_flag            BOOLEAN     NOT NULL DEFAULT FALSE,
    followup_needed                 BOOLEAN     NOT NULL DEFAULT FALSE,
    principal_communication_needed  BOOLEAN     NOT NULL DEFAULT FALSE,
    submitted_on_time               BOOLEAN     NOT NULL DEFAULT TRUE,
    notes                           TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                      TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE eod_reports IS
    'Coach-submitted end-of-day reports documenting activities, engagement, '
    'and any flags (incidents, follow-ups) for each session day. Soft-deleted.';


-- ===========================================================================
-- TABLE 23: incident_reports
-- Formal incident records for injuries, behaviors, or safety events.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_reports (
    incident_id                 BIGSERIAL PRIMARY KEY,
    school_id                   BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    session_id                  BIGINT      REFERENCES sessions (session_id) ON DELETE SET NULL,
    report_date                 DATE        NOT NULL,
    reported_by_staff_id        BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    student_id                  BIGINT      REFERENCES students (student_id) ON DELETE SET NULL,
    incident_type               TEXT        NOT NULL
                                    CHECK (incident_type IN (
                                        'injury', 'behavior', 'property', 'medical', 'safety', 'other'
                                    )),
    severity_level              TEXT        NOT NULL DEFAULT 'low'
                                    CHECK (severity_level IN ('low', 'medium', 'high', 'critical')),
    description                 TEXT        NOT NULL,
    immediate_action_taken      TEXT        NOT NULL,
    school_notified             BOOLEAN     NOT NULL DEFAULT FALSE,
    family_notified             BOOLEAN     NOT NULL DEFAULT FALSE,
    escalated_to_supervisor     BOOLEAN     NOT NULL DEFAULT FALSE,
    status                      TEXT        NOT NULL DEFAULT 'open'
                                    CHECK (status IN ('open', 'under_review', 'resolved', 'closed')),
    resolution_notes            TEXT,
    admin_response              TEXT,
    acknowledged_at             TIMESTAMPTZ,
    acknowledged_by             BIGINT      REFERENCES users (user_id) ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ          DEFAULT NULL
);

COMMENT ON TABLE incident_reports IS
    'Formal incident documentation for injuries, behavior events, property '
    'damage, or safety concerns. Tracks notification, escalation, and resolution.';


-- ===========================================================================
-- TABLE 24: coach_observations
-- Supervisor evaluations of coach performance at a school site.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coach_observations (
    coach_observation_id    BIGSERIAL PRIMARY KEY,
    observed_staff_id       BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    evaluator_staff_id      BIGINT      NOT NULL REFERENCES staff_profiles (staff_id) ON DELETE CASCADE,
    school_id               BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    observation_date        DATE        NOT NULL,
    transitions_score       INTEGER     CHECK (transitions_score BETWEEN 1 AND 5),
    engagement_score        INTEGER     CHECK (engagement_score BETWEEN 1 AND 5),
    lesson_fidelity_score   INTEGER     CHECK (lesson_fidelity_score BETWEEN 1 AND 5),
    sel_language_score      INTEGER     CHECK (sel_language_score BETWEEN 1 AND 5),
    safety_score            INTEGER     CHECK (safety_score BETWEEN 1 AND 5),
    organization_score      INTEGER     CHECK (organization_score BETWEEN 1 AND 5),
    notes                   TEXT,
    action_plan             TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE coach_observations IS
    'Supervisor-led coach evaluations scoring six performance dimensions. '
    'Used for coach compliance reporting and professional development tracking.';


-- ===========================================================================
-- TABLE 25: school_reports
-- Generated aggregate reports for a school covering a reporting period.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS school_reports (
    report_id                   BIGSERIAL PRIMARY KEY,
    school_id                   BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    program_id                  BIGINT      REFERENCES programs (program_id) ON DELETE SET NULL,
    reporting_period_start      DATE        NOT NULL,
    reporting_period_end        DATE        NOT NULL,
    generated_date              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generated_by                BIGINT      REFERENCES users (user_id) ON DELETE SET NULL,
    report_type                 TEXT        NOT NULL
                                    CHECK (report_type IN (
                                        'quarterly', 'semester', 'annual', 'custom',
                                        'incident_summary', 'coach_compliance'
                                    )),
    average_growth_score        NUMERIC(5, 2),
    participation_summary       TEXT,
    engagement_summary          TEXT,
    incident_summary            TEXT,
    coach_compliance_summary    TEXT,
    pdf_link                    TEXT,
    storage_path                TEXT,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE school_reports IS
    'Aggregate generated reports (quarterly, semester, annual, etc.) for a '
    'school or program. Stores summary metrics and links to PDF artifacts.';


-- ===========================================================================
-- TABLE 26: student_skill_summary
-- Materialized-style summary of a student's baseline vs. current per-skill score.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_skill_summary (
    student_skill_summary_id    BIGSERIAL PRIMARY KEY,
    student_id                  BIGINT      NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    school_id                   BIGINT      NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    skill_id                    BIGINT      NOT NULL REFERENCES skills (skill_id) ON DELETE CASCADE,
    baseline_score              INTEGER,
    current_score               INTEGER,
    highest_score               INTEGER,
    latest_assessment_date      DATE,
    growth_amount               INTEGER GENERATED ALWAYS AS (
                                    COALESCE(current_score, 0) - COALESCE(baseline_score, 0)
                                ) STORED,
    performance_band            TEXT,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, skill_id)
);

COMMENT ON TABLE student_skill_summary IS
    'Running summary of a student''s progress per skill. Updated by triggers or '
    'application logic after each assessment. Drives dashboard and report views.';


-- ===========================================================================
-- TABLE 27: student_domain_summary
-- Aggregate domain-level score summary per student.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_domain_summary (
    student_domain_summary_id   BIGSERIAL PRIMARY KEY,
    student_id                  BIGINT          NOT NULL REFERENCES students (student_id) ON DELETE CASCADE,
    domain_id                   BIGINT          NOT NULL REFERENCES skill_domains (domain_id) ON DELETE CASCADE,
    baseline_domain_score       NUMERIC(5, 2),
    current_domain_score        NUMERIC(5, 2),
    growth_amount               NUMERIC(5, 2) GENERATED ALWAYS AS (
                                    COALESCE(current_domain_score, 0) - COALESCE(baseline_domain_score, 0)
                                ) STORED,
    latest_update               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, domain_id)
);

COMMENT ON TABLE student_domain_summary IS
    'Domain-level score aggregations per student. Rolled up from skill-level '
    'summaries. Drives the three-domain breakdown in reports and dashboards.';


-- ===========================================================================
-- TABLE 28: student_overall_summary
-- Single-row overall Ufit score and readiness band per student.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_overall_summary (
    student_overall_summary_id  BIGSERIAL PRIMARY KEY,
    student_id                  BIGINT          NOT NULL UNIQUE REFERENCES students (student_id) ON DELETE CASCADE,
    school_id                   BIGINT          NOT NULL REFERENCES schools (school_id) ON DELETE CASCADE,
    overall_skill_score         NUMERIC(5, 2),
    overall_behavior_score      NUMERIC(5, 2),
    overall_ufit_score          NUMERIC(5, 2),
    participation_rate          NUMERIC(5, 2),
    readiness_band              TEXT
                                    CHECK (readiness_band IN (
                                        'Emerging', 'Developing', 'On Track', 'Proficient', 'Advanced'
                                    )),
    latest_update               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE student_overall_summary IS
    'One row per student with composite Ufit score, behavior score, and '
    'readiness band. Used for at-a-glance dashboards and district roll-ups.';


-- ===========================================================================
-- TABLE 29: notifications
-- In-app notifications sent to users for system events and alerts.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id     BIGSERIAL PRIMARY KEY,
    recipient_user_id   BIGINT      NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    type                TEXT        NOT NULL
                            CHECK (type IN (
                                'incident_filed', 'eod_late', 'eod_submitted',
                                'observation_needed', 'report_ready',
                                'account_created', 'system'
                            )),
    reference_table     TEXT,
    reference_id        BIGINT,
    message             TEXT        NOT NULL,
    is_read             BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE notifications IS
    'In-app notification records for all platform users. reference_table and '
    'reference_id allow deep-linking to the triggering record (e.g., incident).';


-- ===========================================================================
-- TABLE 30: role_permissions
-- Static permission matrix defining what each role can do on each resource.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS role_permissions (
    permission_id   BIGSERIAL PRIMARY KEY,
    role            TEXT        NOT NULL
                        CHECK (role IN (
                            'ceo', 'admin', 'coach_overseer', 'site_coordinator',
                            'head_coach', 'assistant_coach', 'principal',
                            'school_staff', 'parent'
                        )),
    resource        TEXT        NOT NULL,
    action          TEXT        NOT NULL
                        CHECK (action IN ('read', 'write', 'delete', 'export')),
    allowed         BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (role, resource, action)
);

COMMENT ON TABLE role_permissions IS
    'Static role-based access control matrix. Defines allowed actions per role '
    'per resource. Evaluated by the application and enforced by RLS policies.';


-- ===========================================================================
-- TABLE 31: audit_log
-- Immutable log of all data mutations and key user actions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      REFERENCES users (user_id) ON DELETE SET NULL,
    action      TEXT        NOT NULL
                    CHECK (action IN (
                        'create', 'update', 'delete', 'soft_delete',
                        'login', 'logout', 'export'
                    )),
    table_name  TEXT        NOT NULL,
    record_id   BIGINT,
    old_values  JSONB       DEFAULT NULL,
    new_values  JSONB       DEFAULT NULL,
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit_log IS
    'Append-only audit trail for all significant data mutations and user '
    'actions. Captures old/new values as JSONB for full change history.';


-- ===========================================================================
-- TABLE 32: app_settings
-- Key-value store for global application configuration.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT        PRIMARY KEY,
    value       TEXT        NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  BIGINT      REFERENCES users (user_id) ON DELETE SET NULL
);

COMMENT ON TABLE app_settings IS
    'Global key-value configuration store for the application. Values are '
    'managed by admins and read by the application at runtime.';


-- ===========================================================================
-- DEFERRED FOREIGN KEYS (forward references resolved after all tables exist)
-- ===========================================================================

ALTER TABLE contracts
    ADD CONSTRAINT fk_contracts_school
    FOREIGN KEY (school_id) REFERENCES schools (school_id) ON DELETE CASCADE;

ALTER TABLE staff_assignments
    ADD CONSTRAINT fk_staff_assignments_program
    FOREIGN KEY (program_id) REFERENCES programs (program_id) ON DELETE SET NULL;


-- ===========================================================================
-- INDEXES
-- Every FK column indexed; composite indexes for common query patterns.
-- ===========================================================================

-- organizations
CREATE INDEX IF NOT EXISTS idx_organizations_contract_status   ON organizations (contract_status);
CREATE INDEX IF NOT EXISTS idx_organizations_deleted_at        ON organizations (deleted_at) WHERE deleted_at IS NULL;

-- regions
CREATE INDEX IF NOT EXISTS idx_regions_state                   ON regions (state);
CREATE INDEX IF NOT EXISTS idx_regions_active_status           ON regions (active_status);

-- contracts
CREATE INDEX IF NOT EXISTS idx_contracts_organization_id       ON contracts (organization_id);
CREATE INDEX IF NOT EXISTS idx_contracts_school_id             ON contracts (school_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status                ON contracts (status);
CREATE INDEX IF NOT EXISTS idx_contracts_end_date              ON contracts (end_date);

-- schools
CREATE INDEX IF NOT EXISTS idx_schools_organization_id         ON schools (organization_id);
CREATE INDEX IF NOT EXISTS idx_schools_active_status           ON schools (active_status);
CREATE INDEX IF NOT EXISTS idx_schools_deleted_at              ON schools (deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_schools_school_type             ON schools (school_type);

-- users
CREATE INDEX IF NOT EXISTS idx_users_role                      ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_active_status             ON users (active_status);
CREATE INDEX IF NOT EXISTS idx_users_deleted_at                ON users (deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_auth_uid                  ON users (auth_uid) WHERE auth_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_email_verified            ON users (email_verified);

-- staff_profiles
CREATE INDEX IF NOT EXISTS idx_staff_profiles_user_id          ON staff_profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_staff_profiles_region_id        ON staff_profiles (assigned_region_id);
CREATE INDEX IF NOT EXISTS idx_staff_profiles_status           ON staff_profiles (status);
CREATE INDEX IF NOT EXISTS idx_staff_profiles_livescan_status  ON staff_profiles (livescan_status);
CREATE INDEX IF NOT EXISTS idx_staff_profiles_tb_status        ON staff_profiles (tb_status);

-- staff_assignments
CREATE INDEX IF NOT EXISTS idx_staff_assignments_staff_id      ON staff_assignments (staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_assignments_school_id     ON staff_assignments (school_id);
CREATE INDEX IF NOT EXISTS idx_staff_assignments_program_id    ON staff_assignments (program_id);
CREATE INDEX IF NOT EXISTS idx_staff_assignments_supervisor    ON staff_assignments (supervisor_staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_assignments_active        ON staff_assignments (active_status);

-- parents
CREATE INDEX IF NOT EXISTS idx_parents_user_id                 ON parents (user_id);
CREATE INDEX IF NOT EXISTS idx_parents_email                   ON parents (email);
CREATE INDEX IF NOT EXISTS idx_parents_portal_access           ON parents (portal_access_status);

-- students
CREATE INDEX IF NOT EXISTS idx_students_school_id              ON students (school_id);
CREATE INDEX IF NOT EXISTS idx_students_grade_level            ON students (grade_level);
CREATE INDEX IF NOT EXISTS idx_students_active_status          ON students (active_status);
CREATE INDEX IF NOT EXISTS idx_students_deleted_at             ON students (deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_students_parent_primary         ON students (parent_primary_id);
CREATE INDEX IF NOT EXISTS idx_students_parent_secondary       ON students (parent_secondary_id);
CREATE INDEX IF NOT EXISTS idx_students_local_id               ON students (local_student_identifier);

-- programs
CREATE INDEX IF NOT EXISTS idx_programs_school_id              ON programs (school_id);
CREATE INDEX IF NOT EXISTS idx_programs_program_type           ON programs (program_type);
CREATE INDEX IF NOT EXISTS idx_programs_program_status         ON programs (program_status);

-- student_program_enrollment
CREATE INDEX IF NOT EXISTS idx_spe_student_id                  ON student_program_enrollment (student_id);
CREATE INDEX IF NOT EXISTS idx_spe_program_id                  ON student_program_enrollment (program_id);
CREATE INDEX IF NOT EXISTS idx_spe_status                      ON student_program_enrollment (status);

-- sessions
CREATE INDEX IF NOT EXISTS idx_sessions_school_id              ON sessions (school_id);
CREATE INDEX IF NOT EXISTS idx_sessions_program_id             ON sessions (program_id);
CREATE INDEX IF NOT EXISTS idx_sessions_session_status         ON sessions (session_status);
CREATE INDEX IF NOT EXISTS idx_sessions_school_date            ON sessions (school_id, session_date DESC); -- composite for school timeline queries

-- session_staff
CREATE INDEX IF NOT EXISTS idx_session_staff_session_id        ON session_staff (session_id);
CREATE INDEX IF NOT EXISTS idx_session_staff_staff_id          ON session_staff (staff_id);

-- student_session_attendance
CREATE INDEX IF NOT EXISTS idx_ssa_session_id                  ON student_session_attendance (session_id);
CREATE INDEX IF NOT EXISTS idx_ssa_student_id                  ON student_session_attendance (student_id);
CREATE INDEX IF NOT EXISTS idx_ssa_attendance_status           ON student_session_attendance (attendance_status);

-- skill_domains
CREATE INDEX IF NOT EXISTS idx_skill_domains_domain_type       ON skill_domains (domain_type);
CREATE INDEX IF NOT EXISTS idx_skill_domains_active_status     ON skill_domains (active_status);

-- skills
CREATE INDEX IF NOT EXISTS idx_skills_domain_id                ON skills (domain_id);
CREATE INDEX IF NOT EXISTS idx_skills_grade_band               ON skills (grade_band);
CREATE INDEX IF NOT EXISTS idx_skills_active_status            ON skills (active_status);

-- benchmarks
CREATE INDEX IF NOT EXISTS idx_benchmarks_skill_id             ON benchmarks (skill_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_grade_band           ON benchmarks (grade_band);

-- assessment_windows
CREATE INDEX IF NOT EXISTS idx_assessment_windows_school_id    ON assessment_windows (school_id);
CREATE INDEX IF NOT EXISTS idx_assessment_windows_program_id   ON assessment_windows (program_id);
CREATE INDEX IF NOT EXISTS idx_assessment_windows_status       ON assessment_windows (status);

-- assessments
CREATE INDEX IF NOT EXISTS idx_assessments_student_id          ON assessments (student_id);
CREATE INDEX IF NOT EXISTS idx_assessments_school_id           ON assessments (school_id);
CREATE INDEX IF NOT EXISTS idx_assessments_program_id          ON assessments (program_id);
CREATE INDEX IF NOT EXISTS idx_assessments_session_id          ON assessments (session_id);
CREATE INDEX IF NOT EXISTS idx_assessments_window_id           ON assessments (window_id);
CREATE INDEX IF NOT EXISTS idx_assessments_staff_id            ON assessments (assessed_by_staff_id);
CREATE INDEX IF NOT EXISTS idx_assessments_date                ON assessments (assessment_date);
CREATE INDEX IF NOT EXISTS idx_assessments_deleted_at          ON assessments (deleted_at) WHERE deleted_at IS NULL;

-- assessment_scores
CREATE INDEX IF NOT EXISTS idx_assessment_scores_assessment_id ON assessment_scores (assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_scores_student_skill ON assessment_scores (student_id, skill_id); -- composite for growth lookups
CREATE INDEX IF NOT EXISTS idx_assessment_scores_skill_id      ON assessment_scores (skill_id);
CREATE INDEX IF NOT EXISTS idx_assessment_scores_benchmark_id  ON assessment_scores (benchmark_id);
CREATE INDEX IF NOT EXISTS idx_assessment_scores_growth_flag   ON assessment_scores (growth_flag) WHERE growth_flag = TRUE;

-- behavior_observations
CREATE INDEX IF NOT EXISTS idx_behavior_obs_student_id         ON behavior_observations (student_id);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_school_id          ON behavior_observations (school_id);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_session_id         ON behavior_observations (session_id);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_staff_id           ON behavior_observations (observed_by_staff_id);
CREATE INDEX IF NOT EXISTS idx_behavior_obs_date               ON behavior_observations (observation_date);

-- eod_reports
CREATE INDEX IF NOT EXISTS idx_eod_reports_school_id           ON eod_reports (school_id);
CREATE INDEX IF NOT EXISTS idx_eod_reports_staff_id            ON eod_reports (staff_id);
CREATE INDEX IF NOT EXISTS idx_eod_reports_program_id          ON eod_reports (program_id);
CREATE INDEX IF NOT EXISTS idx_eod_reports_session_id          ON eod_reports (session_id);
CREATE INDEX IF NOT EXISTS idx_eod_reports_school_date         ON eod_reports (school_id, report_date DESC); -- composite for school timelines
CREATE INDEX IF NOT EXISTS idx_eod_reports_deleted_at          ON eod_reports (deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_eod_reports_incident_flag       ON eod_reports (injury_incident_flag) WHERE injury_incident_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_eod_reports_followup            ON eod_reports (followup_needed) WHERE followup_needed = TRUE;

-- incident_reports
CREATE INDEX IF NOT EXISTS idx_incident_reports_school_id      ON incident_reports (school_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_session_id     ON incident_reports (session_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_staff_id       ON incident_reports (reported_by_staff_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_student_id     ON incident_reports (student_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_status         ON incident_reports (status);
CREATE INDEX IF NOT EXISTS idx_incident_reports_severity       ON incident_reports (severity_level);
CREATE INDEX IF NOT EXISTS idx_incident_reports_school_date    ON incident_reports (school_id, report_date DESC); -- composite for school incident queries
CREATE INDEX IF NOT EXISTS idx_incident_reports_deleted_at     ON incident_reports (deleted_at) WHERE deleted_at IS NULL;

-- coach_observations
CREATE INDEX IF NOT EXISTS idx_coach_obs_observed_staff        ON coach_observations (observed_staff_id);
CREATE INDEX IF NOT EXISTS idx_coach_obs_evaluator_staff       ON coach_observations (evaluator_staff_id);
CREATE INDEX IF NOT EXISTS idx_coach_obs_school_id             ON coach_observations (school_id);
CREATE INDEX IF NOT EXISTS idx_coach_obs_date                  ON coach_observations (observation_date);

-- school_reports
CREATE INDEX IF NOT EXISTS idx_school_reports_school_id        ON school_reports (school_id);
CREATE INDEX IF NOT EXISTS idx_school_reports_program_id       ON school_reports (program_id);
CREATE INDEX IF NOT EXISTS idx_school_reports_generated_by     ON school_reports (generated_by);
CREATE INDEX IF NOT EXISTS idx_school_reports_report_type      ON school_reports (report_type);
CREATE INDEX IF NOT EXISTS idx_school_reports_period           ON school_reports (school_id, reporting_period_start DESC);

-- student_skill_summary
CREATE INDEX IF NOT EXISTS idx_sss_student_id                  ON student_skill_summary (student_id);
CREATE INDEX IF NOT EXISTS idx_sss_skill_id                    ON student_skill_summary (skill_id);
CREATE INDEX IF NOT EXISTS idx_sss_school_id                   ON student_skill_summary (school_id);
CREATE INDEX IF NOT EXISTS idx_sss_student_skill               ON student_skill_summary (student_id, skill_id); -- mirrors UNIQUE but explicit for query planner

-- student_domain_summary
CREATE INDEX IF NOT EXISTS idx_sds_student_id                  ON student_domain_summary (student_id);
CREATE INDEX IF NOT EXISTS idx_sds_domain_id                   ON student_domain_summary (domain_id);

-- student_overall_summary
CREATE INDEX IF NOT EXISTS idx_sos_student_id                  ON student_overall_summary (student_id);
CREATE INDEX IF NOT EXISTS idx_sos_school_id                   ON student_overall_summary (school_id);
CREATE INDEX IF NOT EXISTS idx_sos_readiness_band              ON student_overall_summary (readiness_band);

-- notifications
CREATE INDEX IF NOT EXISTS idx_notifications_recipient         ON notifications (recipient_user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_unread  ON notifications (recipient_user_id, is_read); -- composite for unread badge queries
CREATE INDEX IF NOT EXISTS idx_notifications_type              ON notifications (type);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at        ON notifications (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_reference         ON notifications (reference_table, reference_id);

-- role_permissions
CREATE INDEX IF NOT EXISTS idx_role_permissions_role_resource  ON role_permissions (role, resource); -- composite for permission lookups
CREATE INDEX IF NOT EXISTS idx_role_permissions_role           ON role_permissions (role);

-- audit_log
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id               ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_record          ON audit_log (table_name, record_id); -- composite for record history lookups
CREATE INDEX IF NOT EXISTS idx_audit_log_action                ON audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at            ON audit_log (created_at DESC);

-- app_settings
-- (Primary key on 'key' is sufficient; no additional indexes needed)


-- ===========================================================================
-- ENABLE ROW LEVEL SECURITY
-- Policies will be implemented in Week 3-4 hardening sprint.
-- ===========================================================================

ALTER TABLE organizations              ENABLE ROW LEVEL SECURITY;
ALTER TABLE regions                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_profiles             ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_assignments          ENABLE ROW LEVEL SECURITY;
ALTER TABLE parents                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE students                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE programs                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_program_enrollment ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_staff              ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_session_attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE skill_domains              ENABLE ROW LEVEL SECURITY;
ALTER TABLE skills                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE benchmarks                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_windows         ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessments                ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_scores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE behavior_observations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE eod_reports                ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_reports           ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_observations         ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_reports             ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_skill_summary      ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_domain_summary     ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_overall_summary    ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications              ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_settings               ENABLE ROW LEVEL SECURITY;


-- ===========================================================================
-- SEED DATA
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Default Skill Domains (3 core domains)
-- ---------------------------------------------------------------------------
INSERT INTO skill_domains (domain_name, domain_type, grade_band, active_status, description)
VALUES
    (
        'Physical & Psychomotor Development',
        'physical_psychomotor',
        'K-8',
        TRUE,
        'Foundational movement skills, locomotor patterns, body control, coordination, '
        'balance, and spatial awareness essential for physical literacy.'
    ),
    (
        'Sports Fundamentals',
        'sports_fundamentals',
        'K-8',
        TRUE,
        'Sport-specific technical skills including throwing, catching, kicking, dribbling, '
        'striking, and basic game strategy across multiple sports.'
    ),
    (
        'SEL & Behavioral Readiness',
        'sel_behavior',
        'K-8',
        TRUE,
        'Social-emotional learning competencies observed in a PE context: teamwork, '
        'effort, self-control, active listening, sportsmanship, and self-confidence.'
    )
ON CONFLICT (domain_name) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Default Role Permissions Matrix
-- ---------------------------------------------------------------------------
-- admin: full access to all core resources
INSERT INTO role_permissions (role, resource, action, allowed)
VALUES
    ('admin', 'organizations',              'read',   TRUE),
    ('admin', 'organizations',              'write',  TRUE),
    ('admin', 'organizations',              'delete', TRUE),
    ('admin', 'organizations',              'export', TRUE),
    ('admin', 'schools',                    'read',   TRUE),
    ('admin', 'schools',                    'write',  TRUE),
    ('admin', 'schools',                    'delete', TRUE),
    ('admin', 'schools',                    'export', TRUE),
    ('admin', 'users',                      'read',   TRUE),
    ('admin', 'users',                      'write',  TRUE),
    ('admin', 'users',                      'delete', TRUE),
    ('admin', 'users',                      'export', TRUE),
    ('admin', 'students',                   'read',   TRUE),
    ('admin', 'students',                   'write',  TRUE),
    ('admin', 'students',                   'delete', TRUE),
    ('admin', 'students',                   'export', TRUE),
    ('admin', 'programs',                   'read',   TRUE),
    ('admin', 'programs',                   'write',  TRUE),
    ('admin', 'programs',                   'delete', TRUE),
    ('admin', 'programs',                   'export', TRUE),
    ('admin', 'sessions',                   'read',   TRUE),
    ('admin', 'sessions',                   'write',  TRUE),
    ('admin', 'sessions',                   'delete', TRUE),
    ('admin', 'sessions',                   'export', TRUE),
    ('admin', 'assessments',                'read',   TRUE),
    ('admin', 'assessments',                'write',  TRUE),
    ('admin', 'assessments',                'delete', TRUE),
    ('admin', 'assessments',                'export', TRUE),
    ('admin', 'incident_reports',           'read',   TRUE),
    ('admin', 'incident_reports',           'write',  TRUE),
    ('admin', 'incident_reports',           'delete', TRUE),
    ('admin', 'incident_reports',           'export', TRUE),
    ('admin', 'eod_reports',                'read',   TRUE),
    ('admin', 'eod_reports',                'write',  TRUE),
    ('admin', 'eod_reports',                'delete', TRUE),
    ('admin', 'eod_reports',                'export', TRUE),
    ('admin', 'school_reports',             'read',   TRUE),
    ('admin', 'school_reports',             'write',  TRUE),
    ('admin', 'school_reports',             'delete', TRUE),
    ('admin', 'school_reports',             'export', TRUE),
    ('admin', 'role_permissions',           'read',   TRUE),
    ('admin', 'role_permissions',           'write',  TRUE),
    ('admin', 'role_permissions',           'delete', TRUE),
    ('admin', 'role_permissions',           'export', FALSE),
    ('admin', 'audit_log',                  'read',   TRUE),
    ('admin', 'audit_log',                  'write',  FALSE),
    ('admin', 'audit_log',                  'delete', FALSE),
    ('admin', 'audit_log',                  'export', TRUE),
    ('admin', 'app_settings',               'read',   TRUE),
    ('admin', 'app_settings',               'write',  TRUE),
    ('admin', 'app_settings',               'delete', FALSE),
    ('admin', 'app_settings',               'export', FALSE),
-- ceo: same as admin
    ('ceo',   'organizations',              'read',   TRUE),
    ('ceo',   'organizations',              'write',  TRUE),
    ('ceo',   'organizations',              'delete', TRUE),
    ('ceo',   'organizations',              'export', TRUE),
    ('ceo',   'schools',                    'read',   TRUE),
    ('ceo',   'schools',                    'write',  TRUE),
    ('ceo',   'schools',                    'delete', TRUE),
    ('ceo',   'schools',                    'export', TRUE),
    ('ceo',   'users',                      'read',   TRUE),
    ('ceo',   'users',                      'write',  TRUE),
    ('ceo',   'users',                      'delete', TRUE),
    ('ceo',   'users',                      'export', TRUE),
    ('ceo',   'students',                   'read',   TRUE),
    ('ceo',   'students',                   'write',  TRUE),
    ('ceo',   'students',                   'delete', TRUE),
    ('ceo',   'students',                   'export', TRUE),
    ('ceo',   'school_reports',             'read',   TRUE),
    ('ceo',   'school_reports',             'write',  TRUE),
    ('ceo',   'school_reports',             'delete', FALSE),
    ('ceo',   'school_reports',             'export', TRUE),
    ('ceo',   'audit_log',                  'read',   TRUE),
    ('ceo',   'audit_log',                  'write',  FALSE),
    ('ceo',   'audit_log',                  'delete', FALSE),
    ('ceo',   'audit_log',                  'export', TRUE),
-- coach_overseer: read/write across assigned schools, export reports
    ('coach_overseer', 'schools',           'read',   TRUE),
    ('coach_overseer', 'schools',           'write',  FALSE),
    ('coach_overseer', 'schools',           'delete', FALSE),
    ('coach_overseer', 'schools',           'export', FALSE),
    ('coach_overseer', 'students',          'read',   TRUE),
    ('coach_overseer', 'students',          'write',  FALSE),
    ('coach_overseer', 'students',          'delete', FALSE),
    ('coach_overseer', 'students',          'export', TRUE),
    ('coach_overseer', 'sessions',          'read',   TRUE),
    ('coach_overseer', 'sessions',          'write',  TRUE),
    ('coach_overseer', 'sessions',          'delete', FALSE),
    ('coach_overseer', 'sessions',          'export', TRUE),
    ('coach_overseer', 'assessments',       'read',   TRUE),
    ('coach_overseer', 'assessments',       'write',  TRUE),
    ('coach_overseer', 'assessments',       'delete', FALSE),
    ('coach_overseer', 'assessments',       'export', TRUE),
    ('coach_overseer', 'eod_reports',       'read',   TRUE),
    ('coach_overseer', 'eod_reports',       'write',  TRUE),
    ('coach_overseer', 'eod_reports',       'delete', FALSE),
    ('coach_overseer', 'eod_reports',       'export', TRUE),
    ('coach_overseer', 'incident_reports',  'read',   TRUE),
    ('coach_overseer', 'incident_reports',  'write',  TRUE),
    ('coach_overseer', 'incident_reports',  'delete', FALSE),
    ('coach_overseer', 'incident_reports',  'export', TRUE),
    ('coach_overseer', 'coach_observations','read',   TRUE),
    ('coach_overseer', 'coach_observations','write',  TRUE),
    ('coach_overseer', 'coach_observations','delete', FALSE),
    ('coach_overseer', 'coach_observations','export', TRUE),
    ('coach_overseer', 'school_reports',    'read',   TRUE),
    ('coach_overseer', 'school_reports',    'write',  FALSE),
    ('coach_overseer', 'school_reports',    'delete', FALSE),
    ('coach_overseer', 'school_reports',    'export', TRUE),
-- head_coach: read/write own school data
    ('head_coach', 'students',              'read',   TRUE),
    ('head_coach', 'students',              'write',  TRUE),
    ('head_coach', 'students',              'delete', FALSE),
    ('head_coach', 'students',              'export', FALSE),
    ('head_coach', 'sessions',              'read',   TRUE),
    ('head_coach', 'sessions',              'write',  TRUE),
    ('head_coach', 'sessions',              'delete', FALSE),
    ('head_coach', 'sessions',              'export', FALSE),
    ('head_coach', 'assessments',           'read',   TRUE),
    ('head_coach', 'assessments',           'write',  TRUE),
    ('head_coach', 'assessments',           'delete', FALSE),
    ('head_coach', 'assessments',           'export', FALSE),
    ('head_coach', 'eod_reports',           'read',   TRUE),
    ('head_coach', 'eod_reports',           'write',  TRUE),
    ('head_coach', 'eod_reports',           'delete', FALSE),
    ('head_coach', 'eod_reports',           'export', FALSE),
    ('head_coach', 'incident_reports',      'read',   TRUE),
    ('head_coach', 'incident_reports',      'write',  TRUE),
    ('head_coach', 'incident_reports',      'delete', FALSE),
    ('head_coach', 'incident_reports',      'export', FALSE),
    ('head_coach', 'behavior_observations', 'read',   TRUE),
    ('head_coach', 'behavior_observations', 'write',  TRUE),
    ('head_coach', 'behavior_observations', 'delete', FALSE),
    ('head_coach', 'behavior_observations', 'export', FALSE),
-- assistant_coach: read/write sessions and assessments, read students
    ('assistant_coach', 'students',         'read',   TRUE),
    ('assistant_coach', 'students',         'write',  FALSE),
    ('assistant_coach', 'students',         'delete', FALSE),
    ('assistant_coach', 'students',         'export', FALSE),
    ('assistant_coach', 'sessions',         'read',   TRUE),
    ('assistant_coach', 'sessions',         'write',  TRUE),
    ('assistant_coach', 'sessions',         'delete', FALSE),
    ('assistant_coach', 'sessions',         'export', FALSE),
    ('assistant_coach', 'assessments',      'read',   TRUE),
    ('assistant_coach', 'assessments',      'write',  TRUE),
    ('assistant_coach', 'assessments',      'delete', FALSE),
    ('assistant_coach', 'assessments',      'export', FALSE),
    ('assistant_coach', 'eod_reports',      'read',   TRUE),
    ('assistant_coach', 'eod_reports',      'write',  TRUE),
    ('assistant_coach', 'eod_reports',      'delete', FALSE),
    ('assistant_coach', 'eod_reports',      'export', FALSE),
    ('assistant_coach', 'incident_reports', 'read',   TRUE),
    ('assistant_coach', 'incident_reports', 'write',  TRUE),
    ('assistant_coach', 'incident_reports', 'delete', FALSE),
    ('assistant_coach', 'incident_reports', 'export', FALSE),
-- site_coordinator: read all at their site, write sessions and reports
    ('site_coordinator', 'students',        'read',   TRUE),
    ('site_coordinator', 'students',        'write',  TRUE),
    ('site_coordinator', 'students',        'delete', FALSE),
    ('site_coordinator', 'students',        'export', TRUE),
    ('site_coordinator', 'sessions',        'read',   TRUE),
    ('site_coordinator', 'sessions',        'write',  TRUE),
    ('site_coordinator', 'sessions',        'delete', FALSE),
    ('site_coordinator', 'sessions',        'export', TRUE),
    ('site_coordinator', 'assessments',     'read',   TRUE),
    ('site_coordinator', 'assessments',     'write',  FALSE),
    ('site_coordinator', 'assessments',     'delete', FALSE),
    ('site_coordinator', 'assessments',     'export', TRUE),
    ('site_coordinator', 'eod_reports',     'read',   TRUE),
    ('site_coordinator', 'eod_reports',     'write',  FALSE),
    ('site_coordinator', 'eod_reports',     'delete', FALSE),
    ('site_coordinator', 'eod_reports',     'export', TRUE),
    ('site_coordinator', 'incident_reports','read',   TRUE),
    ('site_coordinator', 'incident_reports','write',  TRUE),
    ('site_coordinator', 'incident_reports','delete', FALSE),
    ('site_coordinator', 'incident_reports','export', TRUE),
    ('site_coordinator', 'school_reports',  'read',   TRUE),
    ('site_coordinator', 'school_reports',  'write',  FALSE),
    ('site_coordinator', 'school_reports',  'delete', FALSE),
    ('site_coordinator', 'school_reports',  'export', TRUE),
-- principal: read-only access to their school's data and reports
    ('principal', 'students',               'read',   TRUE),
    ('principal', 'students',               'write',  FALSE),
    ('principal', 'students',               'delete', FALSE),
    ('principal', 'students',               'export', TRUE),
    ('principal', 'sessions',               'read',   TRUE),
    ('principal', 'sessions',               'write',  FALSE),
    ('principal', 'sessions',               'delete', FALSE),
    ('principal', 'sessions',               'export', FALSE),
    ('principal', 'assessments',            'read',   TRUE),
    ('principal', 'assessments',            'write',  FALSE),
    ('principal', 'assessments',            'delete', FALSE),
    ('principal', 'assessments',            'export', TRUE),
    ('principal', 'incident_reports',       'read',   TRUE),
    ('principal', 'incident_reports',       'write',  FALSE),
    ('principal', 'incident_reports',       'delete', FALSE),
    ('principal', 'incident_reports',       'export', TRUE),
    ('principal', 'school_reports',         'read',   TRUE),
    ('principal', 'school_reports',         'write',  FALSE),
    ('principal', 'school_reports',         'delete', FALSE),
    ('principal', 'school_reports',         'export', TRUE),
-- school_staff: limited read access
    ('school_staff', 'students',            'read',   TRUE),
    ('school_staff', 'students',            'write',  FALSE),
    ('school_staff', 'students',            'delete', FALSE),
    ('school_staff', 'students',            'export', FALSE),
    ('school_staff', 'sessions',            'read',   TRUE),
    ('school_staff', 'sessions',            'write',  FALSE),
    ('school_staff', 'sessions',            'delete', FALSE),
    ('school_staff', 'sessions',            'export', FALSE),
    ('school_staff', 'incident_reports',    'read',   TRUE),
    ('school_staff', 'incident_reports',    'write',  FALSE),
    ('school_staff', 'incident_reports',    'delete', FALSE),
    ('school_staff', 'incident_reports',    'export', FALSE),
-- parent: read-only access to their own children's data
    ('parent', 'students',                  'read',   TRUE),
    ('parent', 'students',                  'write',  FALSE),
    ('parent', 'students',                  'delete', FALSE),
    ('parent', 'students',                  'export', FALSE),
    ('parent', 'assessments',               'read',   TRUE),
    ('parent', 'assessments',               'write',  FALSE),
    ('parent', 'assessments',               'delete', FALSE),
    ('parent', 'assessments',               'export', FALSE),
    ('parent', 'sessions',                  'read',   TRUE),
    ('parent', 'sessions',                  'write',  FALSE),
    ('parent', 'sessions',                  'delete', FALSE),
    ('parent', 'sessions',                  'export', FALSE)
ON CONFLICT (role, resource, action) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Default App Settings
-- ---------------------------------------------------------------------------
INSERT INTO app_settings (key, value)
VALUES
    ('app_name',                'Ufit Motion'),
    ('app_version',             '1.0.0'),
    ('default_timezone',        'America/Los_Angeles'),
    ('eod_submission_deadline', '20:00'),
    ('assessment_scale_max',    '5'),
    ('normalized_score_max',    '100'),
    ('support_email',           'support@ufitonline.net')
ON CONFLICT (key) DO NOTHING;


-- ===========================================================================
-- END OF MIGRATION 001
-- ===========================================================================
