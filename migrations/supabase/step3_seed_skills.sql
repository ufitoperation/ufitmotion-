-- 002_seed_skills.sql
-- Seed skill domains, skills, and benchmarks per product spec.
-- Safe to re-run: all inserts use ON CONFLICT DO NOTHING.
-- Uses UNION ALL subqueries (compatible with SQLite and PostgreSQL).

-- ============================================================
-- SKILL DOMAINS
-- ============================================================

INSERT INTO skill_domains (domain_name, domain_type, grade_band, active_status, description) VALUES
    ('Physical / Psychomotor', 'physical_psychomotor', 'K-8', 1,
        'Locomotor, balance, coordination, object control, agility, body control'),
    ('Sports Fundamentals', 'sports_fundamentals', 'K-8', 1,
        'Sport-specific movement skills: dribbling, passing, striking, defense'),
    ('SEL / Behavior', 'sel_behavior', 'K-8', 1,
        'Teamwork, effort, self-control, listening, sportsmanship, confidence')
ON CONFLICT DO NOTHING;


-- ============================================================
-- SKILLS — Physical / Psychomotor K–2
-- ============================================================

INSERT INTO skills (domain_id, skill_name, grade_band, skill_description, assessment_type, active_status)
SELECT d.domain_id, v.skill_name, v.grade_band, v.skill_description, 'observational', 1
FROM skill_domains d
JOIN (
    SELECT 'run_with_control'    AS skill_name, 'K-2' AS grade_band, 'Running with coordinated arm/leg movement and directional control' AS skill_description
    UNION ALL SELECT 'hop_on_one_foot',     'K-2', 'Hopping repeatedly on a single foot with balance and rhythm'
    UNION ALL SELECT 'skip_with_rhythm',    'K-2', 'Skipping with consistent step-hop pattern and rhythmic coordination'
    UNION ALL SELECT 'throw_underhand',     'K-2', 'Throwing an object underhand toward a target with basic accuracy'
    UNION ALL SELECT 'catch_two_hands',     'K-2', 'Catching a tossed object using both hands with eyes tracking the object'
    UNION ALL SELECT 'balance_on_one_foot', 'K-2', 'Holding a one-foot static balance with controlled body posture'
) AS v ON d.domain_name = 'Physical / Psychomotor'
ON CONFLICT DO NOTHING;


-- ============================================================
-- SKILLS — Physical / Psychomotor 3–5
-- ============================================================

INSERT INTO skills (domain_id, skill_name, grade_band, skill_description, assessment_type, active_status)
SELECT d.domain_id, v.skill_name, v.grade_band, v.skill_description, 'observational', 1
FROM skill_domains d
JOIN (
    SELECT 'dribble_with_control'          AS skill_name, '3-5' AS grade_band, 'Dribbling a ball with dominant hand while moving, maintaining possession' AS skill_description
    UNION ALL SELECT 'pass_to_target',               '3-5', 'Throwing or kicking to a designated teammate or target with accuracy'
    UNION ALL SELECT 'strike_with_accuracy',         '3-5', 'Striking a stationary or moving object toward a target using hand or implement'
    UNION ALL SELECT 'defensive_positioning_basic',  '3-5', 'Getting between an opponent and the goal; maintaining athletic stance'
    UNION ALL SELECT 'change_direction_with_control','3-5', 'Cutting or pivoting quickly without losing balance or ball control'
) AS v ON d.domain_name = 'Physical / Psychomotor'
ON CONFLICT DO NOTHING;


-- ============================================================
-- SKILLS — Physical / Psychomotor 6–8
-- ============================================================

INSERT INTO skills (domain_id, skill_name, grade_band, skill_description, assessment_type, active_status)
SELECT d.domain_id, v.skill_name, v.grade_band, v.skill_description, 'observational', 1
FROM skill_domains d
JOIN (
    SELECT 'sport_decision_making' AS skill_name, '6-8' AS grade_band, 'Reading the play and choosing the highest-percentage action in real time' AS skill_description
    UNION ALL SELECT 'offensive_spacing',     '6-8', 'Positioning to create passing lanes and spread the defense'
    UNION ALL SELECT 'defensive_recovery',    '6-8', 'Getting back into defensive position after losing possession'
    UNION ALL SELECT 'combination_skills',    '6-8', 'Linking two or more skills (e.g. receive, dribble, pass) in sequence'
    UNION ALL SELECT 'game_application',      '6-8', 'Applying learned skills within a full game scenario under pressure'
) AS v ON d.domain_name = 'Physical / Psychomotor'
ON CONFLICT DO NOTHING;


-- ============================================================
-- SKILLS — Sports Fundamentals (K–8)
-- ============================================================

INSERT INTO skills (domain_id, skill_name, grade_band, sport_type, skill_description, assessment_type, active_status)
SELECT d.domain_id, v.skill_name, v.grade_band, v.sport_type, v.skill_description, 'observational', 1
FROM skill_domains d
JOIN (
    SELECT 'soccer_fundamentals'     AS skill_name, 'K-8' AS grade_band, 'soccer'     AS sport_type, 'Dribbling, passing, trapping, and shooting with feet' AS skill_description
    UNION ALL SELECT 'basketball_fundamentals',   'K-8', 'basketball', 'Dribbling, passing, layups, and defensive footwork'
    UNION ALL SELECT 'football_fundamentals',     'K-8', 'football',   'Throwing spiral, route running, flag pulling, and catching'
    UNION ALL SELECT 'volleyball_fundamentals',   'K-8', 'volleyball', 'Serve, bump/forearm pass, set, and court positioning'
) AS v ON d.domain_name = 'Sports Fundamentals'
ON CONFLICT DO NOTHING;


-- ============================================================
-- SKILLS — SEL / Behavior (K–8)
-- ============================================================

INSERT INTO skills (domain_id, skill_name, grade_band, skill_description, assessment_type, active_status)
SELECT d.domain_id, v.skill_name, 'K-8', v.skill_description, 'observational', 1
FROM skill_domains d
JOIN (
    SELECT 'teamwork'                       AS skill_name, 'Working cooperatively with teammates; sharing the ball and supporting others' AS skill_description
    UNION ALL SELECT 'effort',                         'Giving full physical and mental effort throughout the activity'
    UNION ALL SELECT 'self_control',                   'Managing emotions and physical actions; no outbursts or unsafe behavior'
    UNION ALL SELECT 'listening_following_directions', 'Following coach instructions on first request without redirection'
    UNION ALL SELECT 'sportsmanship',                  'Responding to wins, losses, and mistakes with respect and positivity'
    UNION ALL SELECT 'confidence_participation',       'Volunteering to try new skills; engaging without excessive hesitation'
) AS v ON d.domain_name = 'SEL / Behavior'
ON CONFLICT DO NOTHING;


-- ============================================================
-- BENCHMARKS — Physical / Psychomotor K-2
-- ============================================================

-- run_with_control
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot maintain forward motion; trips or stops frequently' AS benchmark_description, 'Falls more than once per 10m; arms not used for balance' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Runs but lacks arm/leg coordination; inconsistent pace',             'Arms cross midline OR shuffle step present'
    UNION ALL SELECT 3, 'Proficient',  'Runs with basic arm/leg coordination; maintains pace for 20m',       'Opposite arm/leg pattern present; stays on feet'
    UNION ALL SELECT 4, 'Advanced',    'Runs with good form; can vary speed on cue',                         'Arm drive visible; lean into acceleration; speed change on command'
    UNION ALL SELECT 5, 'Mastery',     'Fluid controlled form at varied speeds; demonstrates agility',       'Demonstrates both sprinting and controlled deceleration; no loss of form'
) AS v ON s.skill_name = 'run_with_control' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;

-- hop_on_one_foot
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot balance on one foot for 1 second' AS benchmark_description, 'Immediately puts foot down; grabs support' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Hops 1-2 times before losing balance',                                'Foot touches ground within 2 hops; wide arm waving'
    UNION ALL SELECT 3, 'Proficient',  'Hops 3-5 times with moderate control on dominant foot',              'Maintains hop rhythm 3-5 reps; slight arm assist OK'
    UNION ALL SELECT 4, 'Advanced',    'Hops 6+ times on dominant foot; attempts non-dominant foot',          'Consistent rhythm 6+ reps; non-dominant attempt visible'
    UNION ALL SELECT 5, 'Mastery',     'Hops continuously on either foot with rhythm; can change direction',  'Both feet equal; direction change mid-sequence without stopping'
) AS v ON s.skill_name = 'hop_on_one_foot' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;

-- skip_with_rhythm
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot produce step-hop pattern; gallops or runs instead' AS benchmark_description, 'No airborne phase; both feet on ground simultaneously' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Inconsistent step-hop; one side only or rhythm breaks',              'Pattern present on dominant side only; breaks after 3-4 steps'
    UNION ALL SELECT 3, 'Proficient',  'Skips on both sides with basic rhythm for 10m',                      'Alternating step-hop pattern 10m; some arm coordination'
    UNION ALL SELECT 4, 'Advanced',    'Skips fluidly with arm swing for 20m+; maintains rhythm',            'Fluid bilateral pattern; arm swing matches leg; no breaks'
    UNION ALL SELECT 5, 'Mastery',     'Skips with full coordination; can vary speed and direction',         'Speed variation on cue; direction change without losing rhythm'
) AS v ON s.skill_name = 'skip_with_rhythm' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;

-- throw_underhand
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Pushes or drops ball; no pendulum swing' AS benchmark_description, 'No backswing; ball released early or late' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Shows pendulum swing but no step; ball misses target by 2+ feet',    'Arm swings back; no weight transfer; inaccurate'
    UNION ALL SELECT 3, 'Proficient',  'Steps with opposite foot; ball reaches target within 2 feet',        'Opposite foot step; follow-through toward target'
    UNION ALL SELECT 4, 'Advanced',    'Consistent step and release; hits target 3 of 5 attempts at 10ft',   'Hip rotation visible; 60%+ accuracy at 10ft'
    UNION ALL SELECT 5, 'Mastery',     'Fluid mechanics; 4 of 5 at 15ft; can adjust for distance',           '80%+ accuracy; adjusts arc and force for distance'
) AS v ON s.skill_name = 'throw_underhand' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;

-- catch_two_hands
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Turns away or closes eyes; does not track ball' AS benchmark_description, 'Head turns away; traps against body or misses entirely' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Eyes on ball but traps against chest; no hand catch',                'Watches ball; uses body/arms to trap rather than hands'
    UNION ALL SELECT 3, 'Proficient',  'Catches with two hands from 5ft; soft toss at chest',               'Hands meet ball before body contact; catches 3 of 5'
    UNION ALL SELECT 4, 'Advanced',    'Catches off-center tosses; adjusts position to ball',                'Moves feet to get under/beside ball; 4 of 5 varied tosses'
    UNION ALL SELECT 5, 'Mastery',     'Catches high/low/wide tosses at 10ft; soft hands',                  'Full range catches; hands give on contact; 4 of 5 at 10ft'
) AS v ON s.skill_name = 'catch_two_hands' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;

-- balance_on_one_foot
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-2', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot hold one-foot balance for 1 second' AS benchmark_description, 'Immediate foot down; grabs wall or coach' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Holds 2-3 seconds with significant wobble and arm waving',           'Wide arm movement to compensate; loses balance by 3 sec'
    UNION ALL SELECT 3, 'Proficient',  'Holds 5 seconds on dominant foot with minor corrections',            'Holds 5 sec; small arm adjustments OK; eyes forward'
    UNION ALL SELECT 4, 'Advanced',    'Holds 8 seconds on both feet; eyes closed attempt on dominant',      'Both feet 8+ sec; eyes-closed attempt shows body awareness'
    UNION ALL SELECT 5, 'Mastery',     'Holds 10 seconds on either foot; eyes closed; slight perturbation',  'Maintains balance when lightly challenged; both feet equal'
) AS v ON s.skill_name = 'balance_on_one_foot' AND s.grade_band = 'K-2'
ON CONFLICT DO NOTHING;


-- ============================================================
-- BENCHMARKS — Physical / Psychomotor 3-5
-- ============================================================

-- dribble_with_control
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '3-5', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Slaps ball; loses control immediately; looks at hand' AS benchmark_description, 'Ball bounces away within 2 dribbles; eyes down' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Controls 3-5 dribbles stationary; loses control when moving',       'Stationary only; ball lost on first step'
    UNION ALL SELECT 3, 'Proficient',  'Dribbles while walking 10m; minimal ball watching',                  'Walking dribble 10m; brief glances down OK'
    UNION ALL SELECT 4, 'Advanced',    'Dribbles at jog speed; changes hand on cue; head mostly up',         'Jog speed; hand switch on command; head up 70% of time'
    UNION ALL SELECT 5, 'Mastery',     'Dribbles at full speed; crossover present; head up; change of pace', 'Full speed; crossover; no ball watching; evades cones'
) AS v ON s.skill_name = 'dribble_with_control' AND s.grade_band = '3-5'
ON CONFLICT DO NOTHING;

-- pass_to_target
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '3-5', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Pass misses target by 5+ feet; no follow-through' AS benchmark_description, 'Wild direction; no weight transfer; wrong foot forward' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Pass in general direction; 1 of 5 on target from 10ft',              'Step present; 20% accuracy; follow-through inconsistent'
    UNION ALL SELECT 3, 'Proficient',  'Hits stationary target 3 of 5 at 15ft with correct mechanics',       'Opposite foot; follow-through; 60% accuracy stationary'
    UNION ALL SELECT 4, 'Advanced',    'Passes to moving teammate; leads the target; 4 of 5',                'Leads target; adjusts force; 80% accuracy moving receiver'
    UNION ALL SELECT 5, 'Mastery',     'Passes under pressure; selects best option; executes under fatigue', 'Decision-making + accuracy under defender/time pressure'
) AS v ON s.skill_name = 'pass_to_target' AND s.grade_band = '3-5'
ON CONFLICT DO NOTHING;

-- strike_with_accuracy
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '3-5', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Misses ball or hits with wrong part of hand/foot' AS benchmark_description, 'Whiff or toe-kick; eyes not on contact point' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Makes contact but no accuracy; ball goes random direction',          'Contact made; 0-1 of 5 on target'
    UNION ALL SELECT 3, 'Proficient',  'Strikes stationary ball toward target 3 of 5; basic technique',      'Eyes on ball; 60% to target from stationary'
    UNION ALL SELECT 4, 'Advanced',    'Strikes slow-rolling ball on target 4 of 5; appropriate force',      '80% accuracy moving ball; adjusts force for distance'
    UNION ALL SELECT 5, 'Mastery',     'Strikes in game context; accuracy + power + timing combined',        'Game-speed strike to target; pressure condition; 4 of 5'
) AS v ON s.skill_name = 'strike_with_accuracy' AND s.grade_band = '3-5'
ON CONFLICT DO NOTHING;

-- defensive_positioning_basic
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '3-5', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Stands upright; does not track ball or opponent' AS benchmark_description, 'No athletic stance; flat-footed; faces wrong direction' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Bends knees when reminded; loses position quickly',                  'Reactive only; stance breaks when opponent moves'
    UNION ALL SELECT 3, 'Proficient',  'Athletic stance without prompting; stays between opponent and goal', 'Consistent stance; gets goal-side of opponent'
    UNION ALL SELECT 4, 'Advanced',    'Moves laterally to mirror; forces direction; delays attacker',       'Slide steps; takes away dominant side; delays 3+ seconds'
    UNION ALL SELECT 5, 'Mastery',     'Anticipates movement; communicates; makes defensive play',           'Reads body language; forces turnover or deflection'
) AS v ON s.skill_name = 'defensive_positioning_basic' AND s.grade_band = '3-5'
ON CONFLICT DO NOTHING;

-- change_direction_with_control
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '3-5', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Stops fully before changing direction; loses balance' AS benchmark_description, 'Full stop required; stumbles or falls on direction change' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Slows significantly; one direction change before balance lost',      'Speed drops to near-zero; single change manageable'
    UNION ALL SELECT 3, 'Proficient',  'Changes direction at moderate speed through a cone course',          'Completes 3-cone course at jogging speed without falling'
    UNION ALL SELECT 4, 'Advanced',    'Sharp cut at 70% speed; body lean into change; minimal slowdown',    'Low center of gravity on cut; 2-3 cones at speed'
    UNION ALL SELECT 5, 'Mastery',     'Explosive cuts at full speed; reacts to visual/verbal cue',          'Reactive cut on coach signal at full speed; no loss of balance'
) AS v ON s.skill_name = 'change_direction_with_control' AND s.grade_band = '3-5'
ON CONFLICT DO NOTHING;


-- ============================================================
-- BENCHMARKS — Physical / Psychomotor 6-8
-- ============================================================

-- sport_decision_making
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '6-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Does not scan; always plays to closest teammate or holds ball' AS benchmark_description, 'No head movement to scan; one-option player' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Looks up after receiving; identifies one option before acting',      'Scans once upon receiving; slow decision'
    UNION ALL SELECT 3, 'Proficient',  'Scans before receiving; selects good option 3 of 5 possessions',    'Pre-scan visible; 60% correct decision under light pressure'
    UNION ALL SELECT 4, 'Advanced',    'Quick decisions under moderate pressure; uses both options',         'Identifies primary + secondary option; executes in 2 sec'
    UNION ALL SELECT 5, 'Mastery',     'Anticipates defense; makes correct decision 4 of 5 under pressure', 'Reads defense before ball arrives; adapts when first option closes'
) AS v ON s.skill_name = 'sport_decision_making' AND s.grade_band = '6-8'
ON CONFLICT DO NOTHING;

-- offensive_spacing
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '6-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Clusters near ball carrier; does not move without ball' AS benchmark_description, 'Ball-watching; stays within 3 feet of action' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Stays on assigned side but does not create passing angles',          'Positional awareness present; no dynamic movement'
    UNION ALL SELECT 3, 'Proficient',  'Moves to open space; creates passing angle on 3 of 5 possessions',  'Recognizes open space; positions before ball arrives 60%'
    UNION ALL SELECT 4, 'Advanced',    'Stretches defense; times run; consistently available for pass',      'Forces defense to choose; available 4 of 5 possessions'
    UNION ALL SELECT 5, 'Mastery',     'Reads defense to create space; communicates spacing to teammates',   'Adjusts based on defensive shape; verbal calls to team'
) AS v ON s.skill_name = 'offensive_spacing' AND s.grade_band = '6-8'
ON CONFLICT DO NOTHING;

-- defensive_recovery
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '6-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Stops after losing possession; does not track back' AS benchmark_description, 'No recovery sprint; watches play from original position' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Jogs back after 2-3 seconds; reaches own half before next play',    'Recovers but late; does not impact play'
    UNION ALL SELECT 3, 'Proficient',  'Sprints back immediately; recovers goal-side on 3 of 5 turnovers',   'Immediate sprint; correct recovery position 60%'
    UNION ALL SELECT 4, 'Advanced',    'Sprints back AND communicates to teammates; delays opponent',        'Recovery + verbal communication; slows attack before help arrives'
    UNION ALL SELECT 5, 'Mastery',     'Anticipates turnover; first to recover; reorganizes team defense',   'Pre-emptive recovery; directs teammates on transition'
) AS v ON s.skill_name = 'defensive_recovery' AND s.grade_band = '6-8'
ON CONFLICT DO NOTHING;

-- combination_skills
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '6-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Executes only one skill at a time; full stop between actions' AS benchmark_description, 'Stops completely between receive and pass; no flow' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Links two skills with noticeable pause between them',                '1-beat pause between actions; sequence present but choppy'
    UNION ALL SELECT 3, 'Proficient',  'Links receive, dribble, pass fluidly at moderate speed',            'Fluid 3-step combination; minimal hesitation; 60% success'
    UNION ALL SELECT 4, 'Advanced',    'Links 3+ skills under light pressure; maintains control',            '4-step combination; executed while defender closes; 4 of 5'
    UNION ALL SELECT 5, 'Mastery',     'Reads defense mid-combination; adjusts action without stopping',     'Changes from pass to dribble or vice versa based on pressure'
) AS v ON s.skill_name = 'combination_skills' AND s.grade_band = '6-8'
ON CONFLICT DO NOTHING;

-- game_application
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, '6-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Skills break down immediately in game; does not engage with play' AS benchmark_description, 'Avoids contact; stands away from action; skills collapse' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Occasional skill application in game; inconsistent engagement',     'Uses 1 skill correctly per full-game observation'
    UNION ALL SELECT 3, 'Proficient',  'Consistently applies 2-3 skills in game; engaged throughout',       'Active participant; uses spacing + passing in same possession'
    UNION ALL SELECT 4, 'Advanced',    'Multiple skills in one possession under pressure; reads play',       'Full skill set visible in live game; influences outcome'
    UNION ALL SELECT 5, 'Mastery',     'Elevates team performance; models all skills under game conditions', 'Teaches or demonstrates to peers; consistently game-ready'
) AS v ON s.skill_name = 'game_application' AND s.grade_band = '6-8'
ON CONFLICT DO NOTHING;


-- ============================================================
-- BENCHMARKS — Sports Fundamentals (K-8)
-- ============================================================

-- soccer_fundamentals
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'No sport-specific technique; does not engage with sport object' AS benchmark_description, 'Avoids or mishandles sport equipment' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Attempts sport skills with significant errors; limited success',     '1-2 correct technique components present'
    UNION ALL SELECT 3, 'Proficient',  'Demonstrates core sport mechanics; performs in isolated drill',      'Key technique present; succeeds in controlled drill'
    UNION ALL SELECT 4, 'Advanced',    'Applies sport skills in small-sided game with consistency',          'Transfers to 3v3 or modified game; technique holds under pressure'
    UNION ALL SELECT 5, 'Mastery',     'Sport skills automatic in full game; models for peers',              'Full game application; no breakdown under competition'
) AS v ON s.skill_name = 'soccer_fundamentals'
ON CONFLICT DO NOTHING;

-- basketball_fundamentals
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'No basketball technique; loses ball immediately' AS benchmark_description, 'Slap dribble or no dribble; double dribble common' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Stationary dribble and chest pass; no game application',            'Controls stationary; can pass to stationary teammate'
    UNION ALL SELECT 3, 'Proficient',  'Dribbles while moving; passes to moving target; attempts layup',    'Walking dribble; moving pass; layup attempt from correct side'
    UNION ALL SELECT 4, 'Advanced',    'Game speed dribble; crossover; consistent layup; defensive stance', '80% layup success; crossover; denies driving lane'
    UNION ALL SELECT 5, 'Mastery',     'All skills in game; makes decisions; coaches peers',                'Full game application; leads fast break; communicates defense'
) AS v ON s.skill_name = 'basketball_fundamentals'
ON CONFLICT DO NOTHING;

-- football_fundamentals
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot throw spiral; no route running concept' AS benchmark_description, 'Wobbly or dropped throw; runs random routes' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Throws short spiral; runs straight route; catches against body',    'Short accurate throw; simple Go route; body catch'
    UNION ALL SELECT 3, 'Proficient',  'Throws 15-yard spiral; runs 2 routes; catches with hands; flag pull','Accurate 15 yards; curl + go routes; hand catch 3 of 5'
    UNION ALL SELECT 4, 'Advanced',    'Leads receiver; runs multiple routes; strips flag cleanly',         'Anticipation throw; 3+ routes; 80% flag pulls'
    UNION ALL SELECT 5, 'Mastery',     'Full game QB/receiver/DB skill set; reads defense; communicates',   'Reads coverage; adjusts route; directs teammates'
) AS v ON s.skill_name = 'football_fundamentals'
ON CONFLICT DO NOTHING;

-- volleyball_fundamentals
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Cannot serve over net; no forearm pass form' AS benchmark_description, 'Serve fails to clear; arms swing rather than platform' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Underhand serve clears net 3 of 5; forearm pass attempt present',   '60% underhand serve; platform attempted with poor form'
    UNION ALL SELECT 3, 'Proficient',  'Consistent underhand serve; forearm pass to setter zone; basic set', '80% serve; bump to target zone; set has height'
    UNION ALL SELECT 4, 'Advanced',    'Overhand serve attempt; controlled set; moves to cover court',      'Overhand serve in play; intentional set direction; covers court'
    UNION ALL SELECT 5, 'Mastery',     'All 3 contacts intentional; serves with strategy; court awareness',  'Targets weak zones; calls ball; 3-contact rally sustained'
) AS v ON s.skill_name = 'volleyball_fundamentals'
ON CONFLICT DO NOTHING;


-- ============================================================
-- BENCHMARKS — SEL / Behavior (K-8)
-- ============================================================

-- teamwork
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Refuses to work with others; takes ball/equipment alone' AS benchmark_description, 'Plays solo only; ignores teammates; refuses partner work' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Works with selected peers only; reluctant with unfamiliar partners', 'Cooperates with friends; disengages with new partner'
    UNION ALL SELECT 3, 'Proficient',  'Works productively with any assigned partner or small group',        'Stays engaged; shares equipment; supports group effort'
    UNION ALL SELECT 4, 'Advanced',    'Encourages teammates; takes on and yields leadership as needed',     'Verbal encouragement; shares leadership; includes all players'
    UNION ALL SELECT 5, 'Mastery',     'Elevates group performance; models cooperation; resolves conflict',  'Mediates peer disagreements; coaches struggling teammates'
) AS v ON s.skill_name = 'teamwork'
ON CONFLICT DO NOTHING;

-- effort
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Stands still; refuses to participate; walks when should run' AS benchmark_description, 'Disengaged; requires multiple redirections per activity' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Participates when directly supervised; effort drops when unobserved','Active only with proximity of coach; minimal self-motivation'
    UNION ALL SELECT 3, 'Proficient',  'Gives consistent effort throughout; attempts challenging tasks',     'Sweating/breathing heavy by mid-class; tries new skills'
    UNION ALL SELECT 4, 'Advanced',    'Pushes through fatigue; chooses more challenging tasks voluntarily', 'Maintains effort when tired; self-selects harder variations'
    UNION ALL SELECT 5, 'Mastery',     'Maximum effort every session; inspires others; sets personal goals', 'Finishes first and helps others; references prior performance'
) AS v ON s.skill_name = 'effort'
ON CONFLICT DO NOTHING;

-- self_control
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Frequent outbursts; unsafe behavior; cannot de-escalate' AS benchmark_description, '3+ redirection events per session; physical contact or yelling' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Reacts emotionally but recovers with coach support within 2 min',   '1-2 incidents; recovers after coach intervention'
    UNION ALL SELECT 3, 'Proficient',  'Manages frustration independently; stays in game after mistakes',   'Self-regulates; no outbursts; continues play after error'
    UNION ALL SELECT 4, 'Advanced',    'Helps regulate teammates; recognizes own triggers and adjusts',     'Calms peers; removes self proactively when needed'
    UNION ALL SELECT 5, 'Mastery',     'Consistent emotional regulation; models composure under pressure',   'Zero incidents all session; composure visible in stressful moments'
) AS v ON s.skill_name = 'self_control'
ON CONFLICT DO NOTHING;

-- listening_following_directions
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Does not respond to directions; continues behavior when told to stop' AS benchmark_description, 'Requires 4+ repetitions; unsafe non-compliance present' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Follows after 2-3 repetitions; distracted during instructions',     '2-3 redirections needed; stops task slowly'
    UNION ALL SELECT 3, 'Proficient',  'Follows first-time directions 80% of sessions; freezes on signal',  '1-repeat compliance; stops on whistle/signal consistently'
    UNION ALL SELECT 4, 'Advanced',    'Anticipates transitions; reminds peers to listen; zero redirections','No redirections; heads up during instructions; helps others'
    UNION ALL SELECT 5, 'Mastery',     'Models listening; self-monitors; can repeat instructions back',      'Restates directions accurately; proactive compliance'
) AS v ON s.skill_name = 'listening_following_directions'
ON CONFLICT DO NOTHING;

-- sportsmanship
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Disputes calls; taunts opponents; refuses to shake hands' AS benchmark_description, 'Verbal or physical negative reaction to outcomes' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Accepts outcome but pouts or disengages after loss',                'No verbal outburst; visible frustration; withdraws from team'
    UNION ALL SELECT 3, 'Proficient',  'Accepts wins and losses without visible negative reaction',          'Neutral response to outcome; participates through end of game'
    UNION ALL SELECT 4, 'Advanced',    'Congratulates opponents; encourages struggling teammates',           'Initiates handshake; positive words to other team or teammates'
    UNION ALL SELECT 5, 'Mastery',     'Models sportsmanship; corrects unfair play even when it benefits team','Calls own fouls; advocates for fair play unprompted'
) AS v ON s.skill_name = 'sportsmanship'
ON CONFLICT DO NOTHING;

-- confidence_participation
INSERT INTO benchmarks (skill_id, grade_band, level_number, level_name, benchmark_description, observable_criteria, active_status)
SELECT s.skill_id, 'K-8', v.level_number, v.level_name, v.benchmark_description, v.observable_criteria, 1
FROM skills s
JOIN (
    SELECT 1 AS level_number, 'Beginning' AS level_name, 'Refuses to try; hides behind teammates; disengages from activity' AS benchmark_description, 'Non-participation; needs coaxing for every task' AS observable_criteria
    UNION ALL SELECT 2, 'Developing',  'Participates when required; hesitates before new tasks',            'Joins when called; 30+ second hesitation on unfamiliar skills'
    UNION ALL SELECT 3, 'Proficient',  'Attempts new skills without excessive hesitation; stays engaged',    'Tries new activities within 10 seconds; does not opt out'
    UNION ALL SELECT 4, 'Advanced',    'Volunteers to demonstrate; asks to try harder variations',           'Raises hand to show skill; requests challenge level'
    UNION ALL SELECT 5, 'Mastery',     'First to try; encourages reluctant peers; sets visible personal bar','Initiates; brings along hesitant classmates; visible self-motivation'
) AS v ON s.skill_name = 'confidence_participation'
ON CONFLICT DO NOTHING;
