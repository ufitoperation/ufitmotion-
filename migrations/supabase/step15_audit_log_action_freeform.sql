-- step15: relax audit_log.action CHECK constraint to allow free-form action verbs.
-- The application code uses verbs beyond the original allowlist
-- ('INSERT', 'UPDATE', 'DELETE', 'READ', 'LOGIN_FAILED', 'parent_self_register', etc.)
-- which would otherwise fail the CHECK and roll back every state-changing transaction.

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_action_check;
