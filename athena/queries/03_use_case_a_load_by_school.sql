-- USE CASE A (staffing view): EFTSL split to teaching schools by TEACHING_RESPONSIBILITY percentage
SELECT calendar_type, teaching_org_code, teaching_org_name, eftsl, headcount_unsplit
FROM mcds_gold.student_load_by_school
WHERE academic_year = 2026
ORDER BY eftsl DESC
LIMIT 25;
