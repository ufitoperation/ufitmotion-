-- step14: expand staff_assignments assignment_role check constraint to include
-- principal and school_staff roles so school admins can be assigned to schools.

ALTER TABLE staff_assignments
    DROP CONSTRAINT IF EXISTS staff_assignments_assignment_role_check;

ALTER TABLE staff_assignments
    ADD CONSTRAINT staff_assignments_assignment_role_check
    CHECK (assignment_role IN (
        'head_coach', 'assistant_coach', 'site_coordinator', 'observer',
        'principal', 'school_staff'
    ));
