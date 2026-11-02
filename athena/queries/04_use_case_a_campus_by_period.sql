-- USE CASE A: campus demand per teaching period (rooms planning)
SELECT calendar_type, location_id, location_name, delivery,
       SUM(headcount) AS unit_seats, SUM(eftsl) AS eftsl, COUNT(DISTINCT unit_code) AS units
FROM mcds_gold.student_load_by_unit_campus
WHERE academic_year = 2026
GROUP BY calendar_type, location_id, location_name, delivery
ORDER BY calendar_type, eftsl DESC;
