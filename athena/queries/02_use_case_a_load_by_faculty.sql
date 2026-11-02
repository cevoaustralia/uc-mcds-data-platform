-- USE CASE A: load by owning faculty, onshore vs offshore delivery
SELECT owner_faculty_code, owner_faculty_name,
       SUM(CASE WHEN delivery = 'ONSHORE'  THEN eftsl ELSE 0 END) AS onshore_eftsl,
       SUM(CASE WHEN delivery = 'OFFSHORE' THEN eftsl ELSE 0 END) AS offshore_eftsl,
       SUM(eftsl) AS total_eftsl
FROM mcds_gold.student_load_by_faculty
WHERE academic_year = 2026
GROUP BY owner_faculty_code, owner_faculty_name
ORDER BY total_eftsl DESC;
