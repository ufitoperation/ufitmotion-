-- migrations/004_rls_policies.sql
-- Phase 3B: Row-Level Security for all Ufit Motion tables
--
-- APPLY TO: Supabase SQL Editor only (Postgres). Do NOT run in SQLite dev.
--
-- Design:
--   * security-definer helper functions resolve role/school/org from users table
--     so policies never trigger recursive RLS evaluation.
--   * anon is denied for ALL tables (no unauthenticated data access).
--   * service_role bypasses RLS — used only by the Flask backend. Never expose
--     the service_role key to the frontend or client-side code.
--   * org boundary is always validated via DB join, never trusted from JWT claims.
--
-- Rollback:
--   DROP FUNCTION IF EXISTS _ufit_user_id, _ufit_user_role, _ufit_school_id, _ufit_org_id CASCADE;
--   -- Then for each table:  ALTER TABLE <table> DISABLE ROW LEVEL SECURITY;

-------------------------------------------------------------------------------
-- 0. Security-definer helper functions
--    These avoid recursive RLS: they look up the users table directly without
--    going through any RLS-protected path. SECURITY DEFINER means they run
--    with the function owner's privileges (postgres/service_role), bypassing
--    RLS on the users table itself.
-------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION _ufit_user_id()
RETURNS INTEGER LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT user_id
  FROM users
  WHERE auth_uid = auth.uid()
    AND active_status = TRUE
    AND deleted_at IS NULL
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION _ufit_user_role()
RETURNS TEXT LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role
  FROM users
  WHERE auth_uid = auth.uid()
    AND active_status = TRUE
    AND deleted_at IS NULL
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION _ufit_school_id()
RETURNS INTEGER LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT sa.school_id
  FROM users u
  JOIN staff_profiles sp ON sp.user_id = u.user_id
  JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
  WHERE u.auth_uid = auth.uid()
    AND u.active_status = TRUE
    AND u.deleted_at IS NULL
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION _ufit_org_id()
RETURNS INTEGER LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT sc.organization_id
  FROM users u
  JOIN staff_profiles sp ON sp.user_id = u.user_id
  JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
  JOIN schools sc ON sc.school_id = sa.school_id
  WHERE u.auth_uid = auth.uid()
    AND u.active_status = TRUE
    AND u.deleted_at IS NULL
  LIMIT 1
$$;

-- Returns the set of school_ids a site_coordinator is actively assigned to.
CREATE OR REPLACE FUNCTION _ufit_coordinator_school_ids()
RETURNS SETOF INTEGER LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT sa.school_id
  FROM users u
  JOIN staff_profiles sp ON sp.user_id = u.user_id
  JOIN staff_assignments sa ON sa.staff_id = sp.staff_id AND sa.active_status = TRUE
  WHERE u.auth_uid = auth.uid()
    AND u.active_status = TRUE
    AND u.deleted_at IS NULL
$$;

-- Returns all school_ids in the current user's org (for overseers / admins).
CREATE OR REPLACE FUNCTION _ufit_org_school_ids()
RETURNS SETOF INTEGER LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT sc.school_id
  FROM schools sc
  WHERE sc.organization_id = _ufit_org_id()
    AND sc.active_status = TRUE
    AND sc.deleted_at IS NULL
$$;

-------------------------------------------------------------------------------
-- 1. organizations
--    ceo/admin: full access
--    coach_overseer/coaches/coordinator: read their own org only
--    principal/school_staff: read their own org only
--    parent: no access
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_anon_deny" ON organizations
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "org_admin_full" ON organizations
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "org_staff_read_own" ON organizations
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN (
      'coach_overseer', 'head_coach', 'assistant_coach',
      'site_coordinator', 'principal', 'school_staff'
    )
    AND organization_id = _ufit_org_id()
  );

-------------------------------------------------------------------------------
-- 2. regions
--    All staff can read regions. Only ceo/admin can modify.
-------------------------------------------------------------------------------

ALTER TABLE regions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "regions_anon_deny" ON regions
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "regions_admin_full" ON regions
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "regions_staff_read" ON regions
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);

-------------------------------------------------------------------------------
-- 3. schools
--    ceo/admin: full access to all schools
--    coach_overseer: read/write schools in their org
--    coaches/coordinator/principal/school_staff: read their own school(s) only
--    parent: no direct school access
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE schools ENABLE ROW LEVEL SECURITY;

CREATE POLICY "schools_anon_deny" ON schools
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "schools_admin_full" ON schools
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "schools_overseer_org" ON schools
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND organization_id = _ufit_org_id()
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND organization_id = _ufit_org_id()
  );

CREATE POLICY "schools_coach_read_own" ON schools
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "schools_coordinator_read" ON schools
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "schools_principal_read_own" ON schools
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
  );

-------------------------------------------------------------------------------
-- 4. users
--    ceo/admin: full access
--    coach_overseer: read users in their org
--    coaches: read own user record
--    principal/school_staff: read own user record
--    parent: read own user record
--    anon: denied
--    NOTE: password_hash and auth_uid must never be returned to clients.
--          App-level serializers (serialize_user) already strip these.
-------------------------------------------------------------------------------

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_anon_deny" ON users
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "users_admin_full" ON users
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "users_overseer_org_read" ON users
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND user_id IN (
      SELECT u2.user_id
      FROM users u2
      JOIN staff_profiles sp ON sp.user_id = u2.user_id
      JOIN staff_assignments sa ON sa.staff_id = sp.staff_id
      JOIN schools sc ON sc.school_id = sa.school_id
      WHERE sc.organization_id = _ufit_org_id()
    )
  );

CREATE POLICY "users_self_read" ON users
  FOR SELECT TO authenticated
  USING (user_id = _ufit_user_id());

-------------------------------------------------------------------------------
-- 5. staff_profiles
--    ceo/admin: full access
--    coach_overseer: read profiles in their org
--    coaches: read own profile
--    coordinator: read own profile
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE staff_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "staff_profiles_anon_deny" ON staff_profiles
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "staff_profiles_admin_full" ON staff_profiles
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "staff_profiles_overseer_org_read" ON staff_profiles
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND user_id IN (
      SELECT u2.user_id FROM users u2
      JOIN staff_profiles sp2 ON sp2.user_id = u2.user_id
      JOIN staff_assignments sa ON sa.staff_id = sp2.staff_id
      JOIN schools sc ON sc.school_id = sa.school_id
      WHERE sc.organization_id = _ufit_org_id()
    )
  );

CREATE POLICY "staff_profiles_self_read_write" ON staff_profiles
  FOR ALL TO authenticated
  USING (user_id = _ufit_user_id())
  WITH CHECK (user_id = _ufit_user_id());

-------------------------------------------------------------------------------
-- 6. parents
--    ceo/admin: full access
--    parent: read own record
--    principal/school_staff: read parents of students at their school
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE parents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "parents_anon_deny" ON parents
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "parents_admin_full" ON parents
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "parents_self_read" ON parents
  FOR SELECT TO authenticated
  USING (user_id = _ufit_user_id());

CREATE POLICY "parents_principal_read" ON parents
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND parent_id IN (
      SELECT DISTINCT COALESCE(parent_primary_id, parent_secondary_id)
      FROM students
      WHERE school_id = _ufit_school_id()
        AND active_status = TRUE
        AND deleted_at IS NULL
    )
  );

-------------------------------------------------------------------------------
-- 7. programs
--    ceo/admin: full access
--    coach_overseer: read/write programs in their org's schools
--    coaches/coordinator: read programs at their school(s)
--    principal/school_staff: read programs at their school
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE programs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "programs_anon_deny" ON programs
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "programs_admin_full" ON programs
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "programs_overseer_org" ON programs
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "programs_coach_read_own_school" ON programs
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "programs_coordinator_read" ON programs
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "programs_principal_read" ON programs
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
  );

-------------------------------------------------------------------------------
-- 8. students  [FERPA — most sensitive]
--    ceo/admin: full access
--    coach_overseer: read students in their org
--    coaches: read students at their school only
--    site_coordinator: read students at their assigned schools
--    principal/school_staff: read students at their school
--    parent: read only their own children
--    anon: DENIED — HARD BLOCK
-------------------------------------------------------------------------------

ALTER TABLE students ENABLE ROW LEVEL SECURITY;

CREATE POLICY "students_anon_deny" ON students
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "students_admin_full" ON students
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "students_overseer_org" ON students
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "students_coach_read_own_school" ON students
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

CREATE POLICY "students_coordinator_read" ON students
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    AND deleted_at IS NULL
  );

CREATE POLICY "students_principal_read" ON students
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

CREATE POLICY "students_parent_read_own_children" ON students
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND (
      parent_primary_id IN (
        SELECT parent_id FROM parents WHERE user_id = _ufit_user_id()
      )
      OR parent_secondary_id IN (
        SELECT parent_id FROM parents WHERE user_id = _ufit_user_id()
      )
    )
    AND deleted_at IS NULL
  );

-------------------------------------------------------------------------------
-- 9. staff_assignments
--    ceo/admin: full access
--    coach_overseer: read/write in their org
--    coaches: read own assignments
--    coordinator: read own assignments
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE staff_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "staff_assignments_anon_deny" ON staff_assignments
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "staff_assignments_admin_full" ON staff_assignments
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "staff_assignments_overseer_org" ON staff_assignments
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "staff_assignments_self_read" ON staff_assignments
  FOR SELECT TO authenticated
  USING (
    staff_id IN (
      SELECT staff_id FROM staff_profiles WHERE user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 10. contracts
--    ceo/admin: full access
--    coach_overseer: read contracts for their org
--    others: no access
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "contracts_anon_deny" ON contracts
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "contracts_admin_full" ON contracts
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "contracts_overseer_org_read" ON contracts
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND organization_id = _ufit_org_id()
  );

-------------------------------------------------------------------------------
-- 11. sessions
--    ceo/admin: full access
--    coach_overseer: read/write sessions in their org
--    coaches: read/write sessions at their school
--    coordinator: read sessions at their assigned schools
--    principal/school_staff: read sessions at their school
--    parent: no access (aggregate data only, via portal routes)
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sessions_anon_deny" ON sessions
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "sessions_admin_full" ON sessions
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "sessions_overseer_org" ON sessions
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "sessions_coach_own_school" ON sessions
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "sessions_coordinator_read" ON sessions
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    AND deleted_at IS NULL
  );

CREATE POLICY "sessions_principal_read" ON sessions
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

-------------------------------------------------------------------------------
-- 12. session_staff
--    Same scoping as sessions, via school_id join.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE session_staff ENABLE ROW LEVEL SECURITY;

CREATE POLICY "session_staff_anon_deny" ON session_staff
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "session_staff_admin_full" ON session_staff
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "session_staff_coach_own_school" ON session_staff
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND session_id IN (
      SELECT session_id FROM sessions WHERE school_id = _ufit_school_id()
    )
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND session_id IN (
      SELECT session_id FROM sessions WHERE school_id = _ufit_school_id()
    )
  );

CREATE POLICY "session_staff_overseer_org" ON session_staff
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND session_id IN (
      SELECT session_id FROM sessions
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    )
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND session_id IN (
      SELECT session_id FROM sessions
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    )
  );

CREATE POLICY "session_staff_coordinator_read" ON session_staff
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND session_id IN (
      SELECT session_id FROM sessions
      WHERE school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    )
  );

-------------------------------------------------------------------------------
-- 13. student_program_enrollment  [FERPA — student data]
--    Same scoping as students.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE student_program_enrollment ENABLE ROW LEVEL SECURITY;

CREATE POLICY "spe_anon_deny" ON student_program_enrollment
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "spe_admin_full" ON student_program_enrollment
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "spe_coach_school" ON student_program_enrollment
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  );

CREATE POLICY "spe_overseer_org" ON student_program_enrollment
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids()) AND deleted_at IS NULL
    )
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids()) AND deleted_at IS NULL
    )
  );

CREATE POLICY "spe_coordinator_read" ON student_program_enrollment
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids()) AND deleted_at IS NULL
    )
  );

CREATE POLICY "spe_principal_read" ON student_program_enrollment
  FOR SELECT TO authenticated
  USING (
    student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
    AND _ufit_user_role() IN ('principal', 'school_staff')
  );

CREATE POLICY "spe_parent_own_child" ON student_program_enrollment
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 14. student_session_attendance  [FERPA — individual student records]
--    Coach/coordinator: read/write at their school.
--    Principal: read at their school.
--    Parent: read own children only.
--    anon: DENIED — HARD BLOCK
-------------------------------------------------------------------------------

ALTER TABLE student_session_attendance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ssa_anon_deny" ON student_session_attendance
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "ssa_admin_full" ON student_session_attendance
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "ssa_coach_own_school" ON student_session_attendance
  FOR ALL TO authenticated
  USING (
    session_id IN (
      SELECT session_id FROM sessions WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
    AND _ufit_user_role() IN ('head_coach', 'assistant_coach', 'coach_overseer', 'site_coordinator')
  )
  WITH CHECK (
    session_id IN (
      SELECT session_id FROM sessions WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
    AND _ufit_user_role() IN ('head_coach', 'assistant_coach', 'coach_overseer', 'site_coordinator')
  );

CREATE POLICY "ssa_principal_read" ON student_session_attendance
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  );

CREATE POLICY "ssa_parent_own_child" ON student_session_attendance
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 15. skill_domains
--    All authenticated: read. Admin: write.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE skill_domains ENABLE ROW LEVEL SECURITY;

CREATE POLICY "skill_domains_anon_deny" ON skill_domains
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "skill_domains_admin_write" ON skill_domains
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "skill_domains_staff_read" ON skill_domains
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);

-------------------------------------------------------------------------------
-- 16. skills
--    All authenticated: read. Admin: write.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE skills ENABLE ROW LEVEL SECURITY;

CREATE POLICY "skills_anon_deny" ON skills
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "skills_admin_write" ON skills
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "skills_staff_read" ON skills
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);

-------------------------------------------------------------------------------
-- 17. benchmarks
--    All authenticated: read. Admin: write.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE benchmarks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "benchmarks_anon_deny" ON benchmarks
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "benchmarks_admin_write" ON benchmarks
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "benchmarks_staff_read" ON benchmarks
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);

-------------------------------------------------------------------------------
-- 18. assessment_windows
--    ceo/admin/overseer: full access
--    coaches/coordinator: read windows for their school(s)
--    principal: read windows for their school
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE assessment_windows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "assessment_windows_anon_deny" ON assessment_windows
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "assessment_windows_admin_full" ON assessment_windows
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "assessment_windows_overseer_org" ON assessment_windows
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "assessment_windows_coach_read" ON assessment_windows
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "assessment_windows_coordinator_read" ON assessment_windows
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "assessment_windows_principal_read" ON assessment_windows
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
  );

-------------------------------------------------------------------------------
-- 19. assessments  [FERPA — student educational records]
--    Similar to students.
--    anon: DENIED — HARD BLOCK
-------------------------------------------------------------------------------

ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "assessments_anon_deny" ON assessments
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "assessments_admin_full" ON assessments
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "assessments_overseer_org" ON assessments
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "assessments_coach_own_school" ON assessments
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "assessments_coordinator_read" ON assessments
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    AND deleted_at IS NULL
  );

CREATE POLICY "assessments_principal_read" ON assessments
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

CREATE POLICY "assessments_parent_own_child" ON assessments
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id() AND s.deleted_at IS NULL
    )
    AND deleted_at IS NULL
  );

-------------------------------------------------------------------------------
-- 20. assessment_scores  [FERPA]
--    Scoped via assessments.school_id join chain.
--    anon: DENIED
-------------------------------------------------------------------------------

ALTER TABLE assessment_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "assessment_scores_anon_deny" ON assessment_scores
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "assessment_scores_admin_full" ON assessment_scores
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "assessment_scores_coach_school" ON assessment_scores
  FOR ALL TO authenticated
  USING (
    assessment_id IN (
      SELECT assessment_id FROM assessments
      WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
    AND _ufit_user_role() IN ('head_coach', 'assistant_coach', 'coach_overseer', 'site_coordinator')
  )
  WITH CHECK (
    assessment_id IN (
      SELECT assessment_id FROM assessments
      WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
    AND _ufit_user_role() IN ('head_coach', 'assistant_coach', 'coach_overseer', 'site_coordinator')
  );

CREATE POLICY "assessment_scores_principal_read" ON assessment_scores
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND assessment_id IN (
      SELECT assessment_id FROM assessments WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  );

CREATE POLICY "assessment_scores_parent_own_child" ON assessment_scores
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 21. behavior_observations  [FERPA — individual student]
--    Same scoping as assessment_scores.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE behavior_observations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "behavior_obs_anon_deny" ON behavior_observations
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "behavior_obs_admin_full" ON behavior_observations
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "behavior_obs_coach_school" ON behavior_observations
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "behavior_obs_overseer_org" ON behavior_observations
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "behavior_obs_coordinator_read" ON behavior_observations
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "behavior_obs_principal_read" ON behavior_observations
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "behavior_obs_parent_own_child" ON behavior_observations
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 22. eod_reports
--    ceo/admin/overseer: full access
--    coaches: read/write own school's reports
--    coordinator: read assigned school reports
--    principal: read their school's reports
--    parent: no access
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE eod_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "eod_reports_anon_deny" ON eod_reports
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "eod_reports_admin_full" ON eod_reports
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "eod_reports_overseer_org" ON eod_reports
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "eod_reports_coach_own_school" ON eod_reports
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "eod_reports_coordinator_read" ON eod_reports
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    AND deleted_at IS NULL
  );

CREATE POLICY "eod_reports_principal_read" ON eod_reports
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

-------------------------------------------------------------------------------
-- 23. incident_reports
--    Same scoping as eod_reports.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE incident_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "incident_reports_anon_deny" ON incident_reports
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "incident_reports_admin_full" ON incident_reports
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "incident_reports_overseer_org" ON incident_reports
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "incident_reports_coach_own_school" ON incident_reports
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "incident_reports_coordinator_read" ON incident_reports
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
    AND deleted_at IS NULL
  );

CREATE POLICY "incident_reports_principal_read" ON incident_reports
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND school_id = _ufit_school_id()
    AND deleted_at IS NULL
  );

-------------------------------------------------------------------------------
-- 24. coach_observations
--    ceo/admin: full access
--    coach_overseer: read/write in their org
--    coaches: read observations about themselves only
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE coach_observations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "coach_obs_anon_deny" ON coach_observations
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "coach_obs_admin_full" ON coach_observations
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "coach_obs_overseer_org" ON coach_observations
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "coach_obs_self_read" ON coach_observations
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND observed_staff_id IN (
      SELECT staff_id FROM staff_profiles WHERE user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 25. school_reports
--    ceo/admin/overseer: full access (org-scoped for overseer)
--    principal/school_staff: read own school
--    coaches: read own school
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE school_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "school_reports_anon_deny" ON school_reports
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "school_reports_admin_full" ON school_reports
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "school_reports_overseer_org" ON school_reports
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "school_reports_school_read" ON school_reports
  FOR SELECT TO authenticated
  USING (
    school_id = _ufit_school_id()
    AND _ufit_user_role() IN ('principal', 'school_staff', 'head_coach', 'assistant_coach', 'site_coordinator')
  );

-------------------------------------------------------------------------------
-- 26-28. student summary tables  [FERPA]
--    Same scoping as students.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE student_skill_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sss_anon_deny" ON student_skill_summary
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "sss_admin_full" ON student_skill_summary
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "sss_coach_school" ON student_skill_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "sss_overseer_org" ON student_skill_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "sss_coordinator_read" ON student_skill_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "sss_principal_read" ON student_skill_summary
  FOR SELECT TO authenticated
  USING (school_id = _ufit_school_id() AND _ufit_user_role() IN ('principal', 'school_staff'));

CREATE POLICY "sss_parent_own" ON student_skill_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );


ALTER TABLE student_domain_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sds_anon_deny" ON student_domain_summary
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "sds_admin_full" ON student_domain_summary
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "sds_coach_school" ON student_domain_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  );

CREATE POLICY "sds_overseer_org" ON student_domain_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids()) AND deleted_at IS NULL
    )
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_org_school_ids()) AND deleted_at IS NULL
    )
  );

CREATE POLICY "sds_coordinator_read" ON student_domain_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND student_id IN (
      SELECT student_id FROM students
      WHERE school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids()) AND deleted_at IS NULL
    )
  );

CREATE POLICY "sds_principal_read" ON student_domain_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() IN ('principal', 'school_staff')
    AND student_id IN (
      SELECT student_id FROM students WHERE school_id = _ufit_school_id() AND deleted_at IS NULL
    )
  );

CREATE POLICY "sds_parent_own" ON student_domain_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );


ALTER TABLE student_overall_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sos_anon_deny" ON student_overall_summary
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "sos_admin_full" ON student_overall_summary
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "sos_coach_school" ON student_overall_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  )
  WITH CHECK (
    _ufit_user_role() IN ('head_coach', 'assistant_coach')
    AND school_id = _ufit_school_id()
  );

CREATE POLICY "sos_overseer_org" ON student_overall_summary
  FOR ALL TO authenticated
  USING (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  )
  WITH CHECK (
    _ufit_user_role() = 'coach_overseer'
    AND school_id = ANY(SELECT * FROM _ufit_org_school_ids())
  );

CREATE POLICY "sos_coordinator_read" ON student_overall_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'site_coordinator'
    AND school_id = ANY(SELECT * FROM _ufit_coordinator_school_ids())
  );

CREATE POLICY "sos_principal_read" ON student_overall_summary
  FOR SELECT TO authenticated
  USING (school_id = _ufit_school_id() AND _ufit_user_role() IN ('principal', 'school_staff'));

CREATE POLICY "sos_parent_own" ON student_overall_summary
  FOR SELECT TO authenticated
  USING (
    _ufit_user_role() = 'parent'
    AND student_id IN (
      SELECT s.student_id FROM students s
      JOIN parents p ON p.parent_id = s.parent_primary_id OR p.parent_id = s.parent_secondary_id
      WHERE p.user_id = _ufit_user_id()
    )
  );

-------------------------------------------------------------------------------
-- 29. notifications
--    Users can only read their own notifications.
--    Admin can read all.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "notifications_anon_deny" ON notifications
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "notifications_admin_full" ON notifications
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "notifications_self_read" ON notifications
  FOR SELECT TO authenticated
  USING (recipient_user_id = _ufit_user_id());

CREATE POLICY "notifications_self_mark_read" ON notifications
  FOR UPDATE TO authenticated
  USING (recipient_user_id = _ufit_user_id())
  WITH CHECK (recipient_user_id = _ufit_user_id());

-------------------------------------------------------------------------------
-- 30. role_permissions
--    Admin: full access. Staff: read only.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "role_permissions_anon_deny" ON role_permissions
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "role_permissions_admin_full" ON role_permissions
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "role_permissions_staff_read" ON role_permissions
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);

-------------------------------------------------------------------------------
-- 31. audit_log  [FERPA — must NEVER allow UPDATE or DELETE]
--    Admin/ceo: read only.
--    Service_role: INSERT (via backend — bypasses RLS anyway).
--    No other role can read, insert, update, or delete.
--    UPDATE and DELETE policies set to DENY for all — even admins must not
--    alter audit history (FERPA §99.2(b) requires intact records).
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_log_anon_deny" ON audit_log
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "audit_log_admin_read" ON audit_log
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'));

-- Explicitly block INSERT, UPDATE, and DELETE for all authenticated users.
-- Inserts happen only via service_role (which bypasses RLS) — block here
-- to prevent any future edge function or trigger using authenticated key.
CREATE POLICY "audit_log_no_insert" ON audit_log
  FOR INSERT TO authenticated WITH CHECK (false);

CREATE POLICY "audit_log_no_update" ON audit_log
  FOR UPDATE TO authenticated USING (false) WITH CHECK (false);

CREATE POLICY "audit_log_no_delete" ON audit_log
  FOR DELETE TO authenticated USING (false);

-------------------------------------------------------------------------------
-- 32. app_settings
--    Admin: full access. Staff: read only.
--    anon: denied
-------------------------------------------------------------------------------

ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "app_settings_anon_deny" ON app_settings
  FOR ALL TO anon USING (false) WITH CHECK (false);

CREATE POLICY "app_settings_admin_full" ON app_settings
  FOR ALL TO authenticated
  USING (_ufit_user_role() IN ('ceo', 'admin'))
  WITH CHECK (_ufit_user_role() IN ('ceo', 'admin'));

CREATE POLICY "app_settings_staff_read" ON app_settings
  FOR SELECT TO authenticated
  USING (_ufit_user_role() IS NOT NULL);
