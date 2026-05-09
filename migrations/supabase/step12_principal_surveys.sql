-- step12: principal_satisfaction_surveys table.
-- Referenced by app/routes/admin_routes.py:2773 but missing from production schema.
-- Mirrors the SQLite dev definition with Postgres-native types.

CREATE TABLE IF NOT EXISTS principal_satisfaction_surveys (
    survey_id                       BIGSERIAL PRIMARY KEY,
    school_id                       BIGINT      REFERENCES schools (school_id) ON DELETE SET NULL,
    submitted_by_user_id            BIGINT      REFERENCES users (user_id) ON DELETE SET NULL,
    respondent_name                 TEXT        NOT NULL,
    respondent_position             TEXT        NOT NULL,
    school_name                     TEXT        NOT NULL,
    email                           TEXT,
    satisfaction_rating             INTEGER     NOT NULL CHECK (satisfaction_rating BETWEEN 1 AND 5),
    yard_safety_rating              INTEGER     NOT NULL CHECK (yard_safety_rating BETWEEN 1 AND 5),
    coach_performance_rating        INTEGER     NOT NULL CHECK (coach_performance_rating BETWEEN 1 AND 5),
    communication_rating            INTEGER     NOT NULL CHECK (communication_rating BETWEEN 1 AND 5),
    wellbeing_effectiveness_rating  INTEGER              CHECK (wellbeing_effectiveness_rating BETWEEN 1 AND 5),
    improvements_suggestions        TEXT,
    contributions_description       TEXT,
    additional_services             TEXT,
    submitted_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                      TIMESTAMPTZ          DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_principal_surveys_school
    ON principal_satisfaction_surveys (school_id);
CREATE INDEX IF NOT EXISTS idx_principal_surveys_submitted_at
    ON principal_satisfaction_surveys (submitted_at);
