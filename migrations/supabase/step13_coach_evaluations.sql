-- step13_coach_evaluations.sql
-- Head-coach evaluation form for assistant coaches

CREATE TABLE IF NOT EXISTS coach_evaluations (
    evaluation_id           BIGSERIAL PRIMARY KEY,
    school_id               BIGINT REFERENCES schools(school_id) ON DELETE SET NULL,
    evaluator_staff_id      BIGINT REFERENCES staff_profiles(staff_id) ON DELETE SET NULL,
    evaluated_staff_id      BIGINT REFERENCES staff_profiles(staff_id) ON DELETE SET NULL,
    email                   TEXT,
    same_day_calloff        SMALLINT NOT NULL DEFAULT 0,
    -- Attendance
    shows_up_consistently   SMALLINT NOT NULL CHECK (shows_up_consistently BETWEEN 1 AND 5),
    reports_on_time         SMALLINT NOT NULL CHECK (reports_on_time BETWEEN 1 AND 5),
    processes_consistently  SMALLINT NOT NULL CHECK (processes_consistently BETWEEN 1 AND 5),
    -- Continuous Skill Application
    follows_sop             SMALLINT NOT NULL CHECK (follows_sop BETWEEN 1 AND 5),
    problem_solves          SMALLINT NOT NULL CHECK (problem_solves BETWEEN 1 AND 5),
    demonstrates_improvement SMALLINT NOT NULL CHECK (demonstrates_improvement BETWEEN 1 AND 5),
    -- Communication
    apprises_lead_coach     SMALLINT NOT NULL CHECK (apprises_lead_coach BETWEEN 1 AND 5),
    provides_feedback_to_lead SMALLINT NOT NULL CHECK (provides_feedback_to_lead BETWEEN 1 AND 5),
    follows_up_timely       SMALLINT NOT NULL CHECK (follows_up_timely BETWEEN 1 AND 5),
    communicates_regularly  SMALLINT NOT NULL CHECK (communicates_regularly BETWEEN 1 AND 5),
    -- School & Team Interactions
    practices_restorative_justice  SMALLINT NOT NULL CHECK (practices_restorative_justice BETWEEN 1 AND 5),
    creates_inclusive_environment  SMALLINT NOT NULL CHECK (creates_inclusive_environment BETWEEN 1 AND 5),
    teaches_transferable_skills    SMALLINT NOT NULL CHECK (teaches_transferable_skills BETWEEN 1 AND 5),
    maintains_positive_atmosphere  SMALLINT NOT NULL CHECK (maintains_positive_atmosphere BETWEEN 1 AND 5),
    uses_reward_systems            SMALLINT NOT NULL CHECK (uses_reward_systems BETWEEN 1 AND 5),
    implements_activities_fidelity SMALLINT NOT NULL CHECK (implements_activities_fidelity BETWEEN 1 AND 5),
    -- Student Interaction
    learns_student_names    SMALLINT NOT NULL CHECK (learns_student_names BETWEEN 1 AND 5),
    provides_student_feedback SMALLINT NOT NULL CHECK (provides_student_feedback BETWEEN 1 AND 5),
    uses_positive_language  SMALLINT NOT NULL CHECK (uses_positive_language BETWEEN 1 AND 5),
    -- Safety & Compliance
    provides_supervision    SMALLINT NOT NULL CHECK (provides_supervision BETWEEN 1 AND 5),
    uses_designated_spaces  SMALLINT NOT NULL CHECK (uses_designated_spaces BETWEEN 1 AND 5),
    ensures_safe_areas      SMALLINT NOT NULL CHECK (ensures_safe_areas BETWEEN 1 AND 5),
    determines_best_areas   SMALLINT NOT NULL CHECK (determines_best_areas BETWEEN 1 AND 5),
    follows_safety_procedures SMALLINT NOT NULL CHECK (follows_safety_procedures BETWEEN 1 AND 5),
    maintains_equipment     SMALLINT NOT NULL CHECK (maintains_equipment BETWEEN 1 AND 5),
    maintains_orderly_flow  SMALLINT NOT NULL CHECK (maintains_orderly_flow BETWEEN 1 AND 5),
    implements_rules_safeguards SMALLINT NOT NULL CHECK (implements_rules_safeguards BETWEEN 1 AND 5),
    -- Supervisor Summary
    coach_strengths         TEXT,
    coach_weaknesses        TEXT,
    improvement_plan        TEXT,
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ce_evaluator ON coach_evaluations (evaluator_staff_id);
CREATE INDEX IF NOT EXISTS idx_ce_evaluated ON coach_evaluations (evaluated_staff_id);
CREATE INDEX IF NOT EXISTS idx_ce_school ON coach_evaluations (school_id);
CREATE INDEX IF NOT EXISTS idx_ce_submitted_at ON coach_evaluations (submitted_at DESC);
