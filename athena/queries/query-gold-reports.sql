-- UC MCDS - Athena queries for the SOW D5 Reporting Showcase
-- Workgroup: the MDAA athena-workgroup module (results bucket is KMS-encrypted)
-- Databases: mcds_gold (analysts), mcds_silver / mcds_bronze (engineers only)
--
-- Measures
--   headcount = distinct students (SOW: "how many students in each unit")
--   eftsl     = equivalent full-time student load (sum of Callista EFTSU)
-- Headcount is not additive across rows (a student in 3 units counts in all 3 rows).
-- Use the gold tables for totals; never SUM(headcount).

-- 1. Student load by unit, current period (D5 report 1)
SELECT reporting_period, unit_code, unit_name, headcount, eftsl, eftsl_per_student, unit_enrolments
FROM mcds_gold.student_load_by_unit
WHERE reporting_period = '2026-2'
ORDER BY headcount DESC
LIMIT 20;

-- 2. Student load by campus (D5 report 2, facility = MCDS location)
SELECT reporting_period, location_id, location_name, headcount, eftsl, unit_count
FROM mcds_gold.student_load_by_campus
ORDER BY reporting_period, eftsl DESC;

-- 3. Student load by teaching faculty/school (facility = MCDS organisation)
SELECT reporting_period, org_unit_code, org_unit_name, headcount, eftsl, unit_count
FROM mcds_gold.student_load_by_teaching_org_unit
ORDER BY reporting_period, eftsl DESC;

-- 4. Cross-mapping: units x campuses (D5 "cross-mapping to units and facilities")
SELECT reporting_period, unit_code, unit_name, location_name, headcount, eftsl
FROM mcds_gold.student_load_by_unit_campus
WHERE reporting_period = '2026-1'
ORDER BY unit_code, eftsl DESC;

-- 5. Semester comparison by unit
SELECT unit_code,
       max(unit_name) AS unit_name,
       sum(CASE WHEN reporting_period = '2026-1' THEN headcount END) AS s1_headcount,
       sum(CASE WHEN reporting_period = '2026-2' THEN headcount END) AS s2_headcount,
       sum(CASE WHEN reporting_period = '2026-2' THEN eftsl END)
         - sum(CASE WHEN reporting_period = '2026-1' THEN eftsl END) AS eftsl_change
FROM mcds_gold.student_load_by_unit
GROUP BY unit_code
ORDER BY eftsl_change DESC;

-- 6. Campus share of total load per period (EFTSL is additive)
SELECT reporting_period, location_name, eftsl,
       round(100.0 * eftsl / sum(eftsl) OVER (PARTITION BY reporting_period), 1) AS pct_of_period_eftsl
FROM mcds_gold.student_load_by_campus
ORDER BY reporting_period, eftsl DESC;

-- 7. Reconciliation (engineer role): every Gold report has the same EFTSL as Silver
SELECT 'silver' AS source, reporting_period, sum(eftsu) AS eftsl
FROM mcds_silver.student_unit_load GROUP BY reporting_period
UNION ALL SELECT 'by_unit', reporting_period, sum(eftsl) FROM mcds_gold.student_load_by_unit GROUP BY reporting_period
UNION ALL SELECT 'by_campus', reporting_period, sum(eftsl) FROM mcds_gold.student_load_by_campus GROUP BY reporting_period
UNION ALL SELECT 'by_org_unit', reporting_period, sum(eftsl) FROM mcds_gold.student_load_by_teaching_org_unit GROUP BY reporting_period
ORDER BY reporting_period, source;

-- 8. Lineage spot check (engineer role): one student's load traced to Silver
SELECT f.student_id, f.reporting_period, f.unit_code, u.unit_name, l.location_name,
       o.organisation_name AS teaching_org_unit, f.eftsu, f.completion_status, f.completion_status_label,
       f.submission_number
FROM mcds_silver.student_unit_load f
JOIN mcds_silver.unit_of_learning u ON f.unit_of_learning_id = u.unit_of_learning_id
JOIN mcds_silver.location l ON f.location_id = l.location_id
JOIN mcds_silver.organisation o ON f.teaching_organisation_id = o.organisation_id
WHERE f.student_id = 'STU-3100001'
ORDER BY f.reporting_period, f.unit_code;

-- 9. Access-control demo (SOW D4): run as the analyst role - must be denied by Lake Formation
-- SELECT * FROM mcds_silver.student LIMIT 1;
