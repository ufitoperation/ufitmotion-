# UFIT Motion — External Requirements (SOURCE OF TRUTH)

> **This document is the product specification.** It must be loaded at the start of every session
> that touches scoring, assessments, reporting, or schema design.
> Original file: `Copy of Requirements External.docx`

---

## 1. Design Principle — 4 Separation Layers

| Layer | What it tracks |
|-------|---------------|
| A. Who the student is | profile, school, grade, roster |
| B. What UFIT delivered | session, program, coach, attendance, assessment date |
| C. What the student can do | skills, benchmarks, levels, growth over time |
| D. What the student shows behaviorally | engagement, teamwork, effort, SEL/sportsmanship |

---

## 2. Tables (24 total)

TABLE 1: Organizations — org_id, name, type, billing_contact, contract_status
TABLE 2: Schools — school_id, org_id, name, type, address, principal, AP, grades, enrollment, active, start/end w/ UFIT, **contract_id**, bell_schedule, yard_notes, site_rules
TABLE 3: Users — user_id, name, email, phone, role, active, created, last_login, **linked_staff_id**, **linked_parent_id**; roles: ceo/admin/coach_overseer/site_coordinator/head_coach/assistant_coach/principal/school_staff/parent
TABLE 4: Staff_Profiles — staff_id, user_id, employee_type, date_hired, pay_rate, position_title, region, livescan, tb_status, training_level
TABLE 5: Staff_Assignments — assignment_id, staff_id, school_id, program_id, role, dates, active, default_schedule, **supervisor_staff_id**
TABLE 6: Parents — parent_id, name, email, phone, preferred_contact, portal_access_status
TABLE 7: Students — student_id, school_id, name, **local_student_identifier**, grade, homeroom, gender_optional, active, enrollment, parent_primary_id, parent_secondary_id
TABLE 8: Programs — program_id, school_id, name, type, service_model, grade_band, dates, frequency, status, reporting_cycle; types: pe_support/lunch_sports/after_school_sports/psychomotor/middle_school_skill_development/tournament_program/wellness_enrichment
TABLE 9: Sessions — session_id, school_id, program_id, date, times, **coach_lead_staff_id**, assistant_staff_ids, type, location, planned/actual activity, student_group, status, total_present
TABLE 10: Student_Session_Attendance — attendance_id, session_id, student_id, status (present/absent/excused/partial), participation_level (full/moderate/limited/refused)
TABLE 11: Skill_Domains — domain_id, name, type, grade_band, active, description
TABLE 12: Skills — skill_id, domain_id, name, grade_band, sport_type_optional, description, assessment_type, active
TABLE 13: Benchmarks — benchmark_id, skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, **scoring_notes**, active
TABLE 14: Assessment_Windows — window_id, school_id, program_id, name, start_date, end_date, assessment_focus, status
TABLE 15: Assessments — assessment_id, student_id, school_id, program_id, session_id_optional, window_id_optional, assessed_by_staff_id, date, method, notes
TABLE 16: Assessment_Scores — score_id, assessment_id, student_id, skill_id, benchmark_id, raw_level, normalized_score, confidence_rating, observed_independence, observed_consistency, observed_accuracy, growth_flag, notes
TABLE 17: Behavior_Observations — behavior_observation_id, student_id, school_id, session_id, observed_by_staff_id, date, teamwork_score, effort_score, self_control_score, listening_score, sportsmanship_score, confidence_score, notes
TABLE 18: EOD_Reports — eod_id, school_id, staff_id, program_id, session_id, report_date, attendance_summary, activities_completed, student_engagement_summary, behavior_summary, success_story, challenge_summary, injury_incident_flag, followup_needed, principal_communication_needed, submitted_on_time
TABLE 19: Incident_Reports — incident_id, school_id, session_id, date, reported_by, student_id_optional, type, severity, description, action_taken, school_notified, family_notified, escalated, status, resolution
TABLE 20: Coach_Observations — coach_observation_id, observed_staff_id, evaluator_staff_id, school_id, date, **transitions_score**, **engagement_score**, **lesson_fidelity_score**, **sel_language_score**, **safety_score**, **organization_score**, notes, action_plan
TABLE 21: School_Reports — report_id, school_id, program_id, period_start/end, generated_date, generated_by, report_type, average_growth_score, participation_summary, engagement_summary, incident_summary, coach_compliance_summary, **pdf_link**
TABLE 22: Student_Skill_Summary — per student per skill: baseline_score, current_score, highest_score, latest_date, growth_amount, performance_band
TABLE 23: Student_Domain_Summary — per student per domain: baseline, current, growth, latest_update
TABLE 24: Student_Overall_Summary — per student: overall_skill_score, overall_behavior_score, overall_ufit_score, participation_rate, readiness_band

---

## 3. Scoring System

### Performance Scale (1–5)
| Level | Name | Meaning |
|-------|------|---------|
| 1 | Emerging | Needs full guidance; inconsistent; low confidence |
| 2 | Developing | Partial control; can demonstrate sometimes; inconsistent under pressure |
| 3 | Functional | Adequate control; independent; works in simple drills |
| 4 | Proficient | Consistent; controlled; transferable to gameplay |
| 5 | Advanced | Highly consistent; efficient; accurate under challenge |

### Two Scoring Layers
- **Layer A — Skill proficiency**: Physical or sport skill, scored 1–5
- **Layer B — Behavioral readiness**: SEL/engagement, also scored 1–5
- A student can be low skill + high effort, or high skill + poor self-control

### Normalized Score Formula
```
Level 1 = 20
Level 2 = 40
Level 3 = 60
Level 4 = 80
Level 5 = 100
```

### Growth Measurement
```
growth = current_normalized_score - baseline_normalized_score
Example: baseline dribbling=Level2=40, current=Level4=80 → growth=+40
```

### Domain Score Formula
```
domain_score = average of all skill normalized_scores in that domain
Example: basketball domain = avg(dribble_control=80, chest_pass=60, receiving=60, movement=40) = 60
```

### Overall UFIT Student Score (grade-band weighted)
```
K–2:   Physical/Psychomotor 70% + Behavioral/SEL 30%
3–5:   Physical/Sport Fundamentals 60% + Behavioral/SEL 25% + Game Application 15%
6–8:   Sport Fundamentals 45% + Game Application 30% + Behavioral/SEL 25%
```

### Performance Bands
| Score | Band |
|-------|------|
| 20–39 | Emerging |
| 40–59 | Developing |
| 60–79 | On Track |
| 80–89 | Proficient |
| 90–100 | Advanced |

---

## 4. Coach Observation Scoring (TABLE 20)
Evaluators (head_coach, coach_overseer, admin) score coaches on 6 dimensions, each 1–5:
1. **transitions_score** — how smoothly the coach moves students between activities
2. **engagement_score** — student engagement level during the session
3. **lesson_fidelity_score** — how closely the coach followed the planned lesson
4. **sel_language_score** — coach's use of SEL language and positive behavior reinforcement
5. **safety_score** — safety management and environment
6. **organization_score** — setup, materials, time management

---

## 5. Assessment Frequency Rhythms
- **Baseline**: Within first 2–4 weeks of service
- **Progress check**: Monthly or every 6–8 sessions
- **Reporting assessment**: Quarterly / semester-end

### Method by Grade Band
- K–2: Observational rubric only. No overcomplications.
- 3–5: Observational rubric + simple skill challenge/drill
- 6–8: Observational rubric + applied drill + gameplay application scoring

---

## 6. Coach Score Entry Rules (Section 15)
Every score entry screen must force:
1. Selected skill
2. Selected level 1–5
3. Short observation tag (dropdown, NOT free text)
4. Optional note

### Required Observation Tags
- independent
- needs_prompt
- inconsistent
- strong_control
- low_confidence
- gameplay_transfer_observed

---

## 7. Reporting Outputs Required

### Student-level
- baseline vs current
- top strengths
- top growth areas
- behavior readiness
- attendance/participation

### Group-level
- average skill score by class
- average growth by domain
- engagement by grade

### School-level
- total sessions delivered
- student participation rate
- growth trends
- school climate support indicators
- incident trends
- coach reporting compliance

---

## 8. Relationship Map
```
organization → schools → students
                      → programs → sessions → student_session_attendance
                                            → eod_reports
                                            → incident_reports
student → assessments → assessment_scores (per skill)
student → behavior_observations (per session, lightweight SEL)
student → student_skill_summary (calculated)
student → student_domain_summary (calculated)
student → student_overall_summary (calculated)
staff → coach_observations (scored by evaluators)
school → school_reports (generated, PDF)
```
