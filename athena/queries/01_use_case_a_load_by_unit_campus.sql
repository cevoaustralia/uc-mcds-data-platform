-- USE CASE A: How many students, and how much load (EFTSL), in each unit and campus?
-- HE coursework, load-bearing enrolments only. Headcount is distinct students (not additive across rows).
SELECT academic_year, calendar_type, unit_code, unit_name, owner_faculty_code,
       location_id, location_name, delivery, headcount, eftsl, unit_enrolments
FROM mcds_gold.student_load_by_unit_campus
WHERE academic_year = 2026 AND calendar_type = 'SEM-1'
ORDER BY eftsl DESC
LIMIT 25;
