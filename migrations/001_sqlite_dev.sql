-- SQLite development schema for Ufit Motion
-- Used automatically when DATABASE_URL is not set (local dev only).
-- Production uses migrations/001_initial_schema.sql (PostgreSQL/Supabase).

CREATE TABLE IF NOT EXISTS organizations (
    organization_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_name TEXT NOT NULL,
    organization_type TEXT NOT NULL DEFAULT 'school_district',
    billing_contact TEXT,
    billing_email TEXT,
    contract_status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS regions (
    region_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    active_status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schools (
    school_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    region_id INTEGER REFERENCES regions(region_id) ON DELETE SET NULL,
    school_name TEXT NOT NULL,
    school_type TEXT NOT NULL DEFAULT 'elementary',
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    principal_name TEXT,
    principal_email TEXT,
    assistant_principal_name TEXT,
    assistant_principal_email TEXT,
    grade_levels_served TEXT,
    enrollment INTEGER,
    active_status INTEGER NOT NULL DEFAULT 1,
    start_date_with_ufit TEXT,
    end_date_with_ufit TEXT,
    bell_schedule_notes TEXT,
    yard_notes TEXT,
    site_specific_rules TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    auth_uid TEXT UNIQUE DEFAULT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'admin',
    active_status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TEXT,
    deleted_at TEXT DEFAULT NULL,
    password_reset_token TEXT,
    password_reset_expires_at TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    email_verified_at TEXT
);

CREATE TABLE IF NOT EXISTS staff_profiles (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    employee_type TEXT NOT NULL DEFAULT 'part_time',
    date_hired TEXT,
    pay_rate REAL,
    position_title TEXT,
    assigned_region_id INTEGER REFERENCES regions(region_id) ON DELETE SET NULL,
    livescan_status TEXT DEFAULT 'pending',
    livescan_date TEXT,
    tb_status TEXT DEFAULT 'pending',
    tb_expiration TEXT,
    training_level TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parents (
    parent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    preferred_contact TEXT DEFAULT 'email',
    portal_access_status INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_name TEXT NOT NULL,
    program_type TEXT NOT NULL DEFAULT 'pe_support',
    service_model TEXT,
    grade_band TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT,
    frequency TEXT,
    program_status TEXT NOT NULL DEFAULT 'active',
    reporting_cycle TEXT,
    max_students INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    student_first_name TEXT NOT NULL,
    student_last_name TEXT NOT NULL,
    local_student_identifier TEXT,
    grade_level TEXT NOT NULL,
    homeroom_teacher TEXT,
    gender TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    enrollment_start TEXT,
    enrollment_end TEXT,
    parent_primary_id INTEGER REFERENCES parents(parent_id) ON DELETE SET NULL,
    parent_secondary_id INTEGER REFERENCES parents(parent_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS staff_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_id INTEGER REFERENCES programs(program_id) ON DELETE SET NULL,
    assignment_role TEXT NOT NULL DEFAULT 'head_coach',
    start_date TEXT NOT NULL,
    end_date TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    default_schedule TEXT,
    supervisor_staff_id INTEGER REFERENCES staff_profiles(staff_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    school_id INTEGER REFERENCES schools(school_id) ON DELETE CASCADE,
    contract_value REAL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    document_url TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_id INTEGER NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
    session_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    session_type TEXT NOT NULL DEFAULT 'regular',
    location TEXT,
    planned_activity TEXT,
    actual_activity TEXT,
    student_group_name TEXT,
    session_status TEXT NOT NULL DEFAULT 'completed',
    total_students_present INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS session_staff (
    session_staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'lead',
    UNIQUE(session_id, staff_id)
);

CREATE TABLE IF NOT EXISTS student_program_enrollment (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    program_id INTEGER NOT NULL REFERENCES programs(program_id) ON DELETE CASCADE,
    enrollment_date TEXT NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, program_id)
);

CREATE TABLE IF NOT EXISTS student_session_attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    attendance_status TEXT NOT NULL DEFAULT 'present',
    participation_level TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, student_id)
);

CREATE TABLE IF NOT EXISTS skill_domains (
    domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT NOT NULL UNIQUE,
    domain_type TEXT NOT NULL,
    grade_band TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES skill_domains(domain_id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    grade_band TEXT NOT NULL,
    sport_type TEXT,
    skill_description TEXT,
    assessment_type TEXT NOT NULL DEFAULT 'observational',
    active_status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(skill_name, grade_band)
);

CREATE TABLE IF NOT EXISTS benchmarks (
    benchmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    grade_band TEXT NOT NULL,
    level_number INTEGER NOT NULL CHECK(level_number BETWEEN 1 AND 5),
    level_name TEXT NOT NULL,
    benchmark_description TEXT NOT NULL,
    observable_criteria TEXT,
    scoring_notes TEXT,
    active_status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(skill_id, grade_band, level_number)
);

CREATE TABLE IF NOT EXISTS assessment_windows (
    window_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_id INTEGER REFERENCES programs(program_id) ON DELETE SET NULL,
    window_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    assessment_focus TEXT,
    status TEXT NOT NULL DEFAULT 'upcoming',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_id INTEGER REFERENCES programs(program_id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(session_id) ON DELETE SET NULL,
    window_id INTEGER REFERENCES assessment_windows(window_id) ON DELETE SET NULL,
    assessed_by_staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    assessment_date TEXT NOT NULL,
    assessment_method TEXT NOT NULL DEFAULT 'observational',
    overall_assessment_notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS assessment_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    benchmark_id INTEGER REFERENCES benchmarks(benchmark_id) ON DELETE SET NULL,
    raw_level INTEGER NOT NULL CHECK(raw_level BETWEEN 1 AND 5),
    normalized_score INTEGER NOT NULL,
    confidence_rating TEXT,
    observed_independence INTEGER DEFAULT 1,
    observed_consistency INTEGER DEFAULT 0,
    observed_accuracy INTEGER DEFAULT 0,
    growth_flag INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assessment_id, skill_id)
);

CREATE TABLE IF NOT EXISTS behavior_observations (
    behavior_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES sessions(session_id) ON DELETE SET NULL,
    observed_by_staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    observation_date TEXT NOT NULL,
    teamwork_score INTEGER CHECK(teamwork_score BETWEEN 1 AND 5),
    effort_score INTEGER CHECK(effort_score BETWEEN 1 AND 5),
    self_control_score INTEGER CHECK(self_control_score BETWEEN 1 AND 5),
    listening_score INTEGER CHECK(listening_score BETWEEN 1 AND 5),
    sportsmanship_score INTEGER CHECK(sportsmanship_score BETWEEN 1 AND 5),
    confidence_score INTEGER CHECK(confidence_score BETWEEN 1 AND 5),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eod_reports (
    eod_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    program_id INTEGER REFERENCES programs(program_id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(session_id) ON DELETE SET NULL,
    report_date TEXT NOT NULL,
    attendance_summary TEXT,
    activities_completed TEXT NOT NULL,
    student_engagement_summary TEXT NOT NULL,
    behavior_summary TEXT,
    success_story TEXT,
    challenge_summary TEXT,
    injury_incident_flag INTEGER NOT NULL DEFAULT 0,
    followup_needed INTEGER NOT NULL DEFAULT 0,
    principal_communication_needed INTEGER NOT NULL DEFAULT 0,
    submitted_on_time INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    incident_report_filed INTEGER DEFAULT NULL,
    school_concerns TEXT DEFAULT NULL,
    school_concerns_resolved INTEGER DEFAULT NULL,
    school_concerns_notes TEXT DEFAULT NULL,
    schedule_changes TEXT DEFAULT NULL,
    coaches_clocked_in INTEGER DEFAULT NULL,
    late_arrivals TEXT DEFAULT NULL,
    coaches_in_uniform INTEGER DEFAULT NULL,
    verbal_warnings TEXT DEFAULT NULL,
    hr_app_issues TEXT DEFAULT NULL,
    coaches_setup_ready INTEGER DEFAULT NULL,
    equipment_accounted INTEGER DEFAULT NULL,
    transitions_orderly INTEGER DEFAULT NULL,
    safety_hazards TEXT DEFAULT NULL,
    yard_supervised INTEGER DEFAULT NULL,
    curriculum_followed INTEGER DEFAULT NULL,
    equipment_requests TEXT DEFAULT NULL,
    principal_communication_notes TEXT DEFAULT NULL,
    ufit_standards_notes TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS incident_reports (
    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES sessions(session_id) ON DELETE SET NULL,
    report_date TEXT NOT NULL,
    reported_by_staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    student_id INTEGER REFERENCES students(student_id) ON DELETE SET NULL,
    incident_type TEXT NOT NULL DEFAULT 'other',
    severity_level TEXT NOT NULL DEFAULT 'low',
    description TEXT NOT NULL,
    immediate_action_taken TEXT NOT NULL,
    school_notified INTEGER NOT NULL DEFAULT 0,
    family_notified INTEGER NOT NULL DEFAULT 0,
    escalated_to_supervisor INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    resolution_notes TEXT,
    admin_response TEXT,
    acknowledged_at TEXT,
    acknowledged_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS coach_observations (
    coach_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    evaluator_staff_id INTEGER NOT NULL REFERENCES staff_profiles(staff_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    observation_date TEXT NOT NULL,
    transitions_score INTEGER CHECK(transitions_score BETWEEN 1 AND 5),
    engagement_score INTEGER CHECK(engagement_score BETWEEN 1 AND 5),
    lesson_fidelity_score INTEGER CHECK(lesson_fidelity_score BETWEEN 1 AND 5),
    sel_language_score INTEGER CHECK(sel_language_score BETWEEN 1 AND 5),
    safety_score INTEGER CHECK(safety_score BETWEEN 1 AND 5),
    organization_score INTEGER CHECK(organization_score BETWEEN 1 AND 5),
    notes TEXT,
    action_plan TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS school_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    program_id INTEGER REFERENCES programs(program_id) ON DELETE SET NULL,
    reporting_period_start TEXT NOT NULL,
    reporting_period_end TEXT NOT NULL,
    generated_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    generated_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    report_type TEXT NOT NULL DEFAULT 'quarterly',
    average_growth_score REAL,
    participation_summary TEXT,
    engagement_summary TEXT,
    incident_summary TEXT,
    coach_compliance_summary TEXT,
    pdf_link TEXT,
    storage_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_skill_summary (
    student_skill_summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    baseline_score INTEGER,
    current_score INTEGER,
    highest_score INTEGER,
    latest_assessment_date TEXT,
    growth_amount INTEGER,
    performance_band TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS student_domain_summary (
    student_domain_summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    domain_id INTEGER NOT NULL REFERENCES skill_domains(domain_id) ON DELETE CASCADE,
    baseline_domain_score REAL,
    current_domain_score REAL,
    growth_amount REAL,
    latest_update TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, domain_id)
);

CREATE TABLE IF NOT EXISTS student_overall_summary (
    student_overall_summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE REFERENCES students(student_id) ON DELETE CASCADE,
    school_id INTEGER NOT NULL REFERENCES schools(school_id) ON DELETE CASCADE,
    overall_skill_score REAL,
    overall_behavior_score REAL,
    overall_ufit_score REAL,
    participation_rate REAL,
    readiness_band TEXT,
    latest_update TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT,
    body TEXT NOT NULL DEFAULT '',
    notification_type TEXT NOT NULL DEFAULT 'system',
    related_table TEXT,
    related_id INTEGER,
    is_read INTEGER NOT NULL DEFAULT 0,
    read_at TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role, resource, action)
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id INTEGER,
    old_values TEXT DEFAULT NULL,
    new_values TEXT DEFAULT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL
);

-- Seed skill domains
INSERT OR IGNORE INTO skill_domains (domain_name, domain_type, description) VALUES
    ('Physical / Psychomotor', 'physical_psychomotor', 'Locomotor, balance, coordination, object control, body awareness'),
    ('Sports Fundamentals', 'sports_fundamentals', 'Sport-specific movement skills: dribbling, passing, striking, defense'),
    ('SEL / Behavior', 'sel_behavior', 'Teamwork, effort, self-control, listening, sportsmanship, confidence');

-- Default app settings
INSERT OR IGNORE INTO app_settings (key, value) VALUES
    ('app_name', 'Ufit Motion'),
    ('app_version', '1.0.0'),
    ('support_email', 'support@ufitonline.net');
