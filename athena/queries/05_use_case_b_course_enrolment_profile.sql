-- USE CASE B: enrolled and commencing students per course
SELECT course_code,
       SUM(enrolled_students) AS enrolled_students_by_segment,
       SUM(commencing_students) AS commencing_students_by_segment,
       SUM(eftsl) AS eftsl
FROM mcds_gold.course_enrolment_profile
WHERE academic_year = 2026
GROUP BY course_code
ORDER BY eftsl DESC
LIMIT 25;
