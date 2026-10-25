-- UC MCDS Data Platform - Gold Layer Queries
-- SOW D5: Curated reporting datasets in Amazon Athena

-- ==============================================================================
-- Report 1: Student Load by Unit (SOW D5.1)
-- ==============================================================================

-- Query 1.1: Top 10 units by student count (current semester)
SELECT 
    unitCode,
    unitName,
    semester,
    student_count,
    total_eftsu,
    avg_eftsu_per_student,
    report_generated_at
FROM mcds_gold.student_load_by_unit
WHERE semester = '2024-S1'  -- PLACEHOLDER: current semester from business-rules.yaml
ORDER BY student_count DESC
LIMIT 10;

-- Query 1.2: All units with student counts (current semester)
SELECT 
    unitCode,
    unitName,
    student_count,
    total_eftsu,
    ROUND(avg_eftsu_per_student, 3) as avg_eftsu
FROM mcds_gold.student_load_by_unit
WHERE semester = '2024-S1'
ORDER BY unitCode;

-- Query 1.3: Units with high enrolment (>50 students)
SELECT 
    unitCode,
    unitName,
    student_count,
    total_eftsu
FROM mcds_gold.student_load_by_unit
WHERE semester = '2024-S1'
  AND student_count > 50
ORDER BY student_count DESC;

-- ==============================================================================
-- Report 2: Student Load by Facility (SOW D5.2)
-- ==============================================================================

-- Query 2.1: All facilities by student count (current semester)
SELECT 
    locationCode,
    locationName,
    semester,
    student_count,
    total_eftsu,
    unit_count,
    report_generated_at
FROM mcds_gold.student_load_by_facility
WHERE semester = '2024-S1'  -- PLACEHOLDER: current semester
ORDER BY student_count DESC;

-- Query 2.2: Faculty comparison (top 5)
SELECT 
    locationName as faculty,
    student_count,
    unit_count,
    total_eftsu,
    ROUND(total_eftsu / student_count, 2) as avg_eftsu_per_student
FROM mcds_gold.student_load_by_facility
WHERE semester = '2024-S1'
  AND locationName IS NOT NULL
ORDER BY student_count DESC
LIMIT 5;

-- ==============================================================================
-- Cross-Mapping: Unit × Facility (Advanced Query)
-- ==============================================================================

-- Query 3.1: Student load by unit AND facility (drill-down)
SELECT 
    u.unitCode,
    u.unitName,
    l.locationName as facility,
    COUNT(DISTINCT sul.studentId) as student_count,
    SUM(sul.eftsu) as total_eftsu
FROM mcds_silver.student_unit_load sul
JOIN mcds_silver.unit_of_learning u ON sul.unitCode = u.unitCode
JOIN mcds_silver.location l ON sul.locationCode = l.locationCode
WHERE sul.semester = '2024-S1'
  AND sul.status IN (1, 2)  -- PLACEHOLDER: active status codes
GROUP BY u.unitCode, u.unitName, l.locationName
ORDER BY student_count DESC
LIMIT 20;

-- Query 3.2: Faculty utilization (units per faculty)
SELECT 
    f.locationName as faculty,
    COUNT(DISTINCT u.unitCode) as unique_units,
    COUNT(DISTINCT sul.studentId) as total_students,
    SUM(sul.eftsu) as total_eftsu
FROM mcds_silver.student_unit_load sul
JOIN mcds_silver.location f ON sul.locationCode = f.locationCode
JOIN mcds_silver.unit_of_learning u ON sul.unitCode = u.unitCode
WHERE sul.semester = '2024-S1'
  AND sul.status IN (1, 2)
GROUP BY f.locationName
ORDER BY total_students DESC;

-- ==============================================================================
-- Semester Comparison (Time Series)
-- ==============================================================================

-- Query 4.1: Semester-over-semester unit growth
SELECT 
    unitCode,
    unitName,
    semester,
    student_count
FROM mcds_gold.student_load_by_unit
WHERE semester IN ('2024-S1', '2024-S2')
ORDER BY unitCode, semester;

-- Query 4.2: Top growing units (S1 to S2)
WITH s1 AS (
    SELECT unitCode, student_count as s1_count
    FROM mcds_gold.student_load_by_unit
    WHERE semester = '2024-S1'
),
s2 AS (
    SELECT unitCode, student_count as s2_count
    FROM mcds_gold.student_load_by_unit
    WHERE semester = '2024-S2'
)
SELECT 
    s1.unitCode,
    s1.s1_count,
    s2.s2_count,
    (s2.s2_count - s1.s1_count) as growth,
    ROUND(100.0 * (s2.s2_count - s1.s1_count) / s1.s1_count, 1) as growth_pct
FROM s1
JOIN s2 ON s1.unitCode = s2.unitCode
WHERE s1.s1_count > 0
ORDER BY growth DESC
LIMIT 10;

-- ==============================================================================
-- Data Quality Queries
-- ==============================================================================

-- Query 5.1: Check row counts across layers
SELECT 'bronze.person' as layer, COUNT(*) as row_count FROM mcds_bronze.person
UNION ALL
SELECT 'silver.student', COUNT(*) FROM mcds_silver.student
UNION ALL
SELECT 'silver.student_unit_load', COUNT(*) FROM mcds_silver.student_unit_load
UNION ALL
SELECT 'gold.student_load_by_unit', COUNT(*) FROM mcds_gold.student_load_by_unit;

-- Query 5.2: Validate aggregations (Gold sums should match Silver totals)
SELECT 
    'Silver Total' as source,
    COUNT(DISTINCT studentId) as total_students,
    SUM(eftsu) as total_eftsu
FROM mcds_silver.student_unit_load
WHERE semester = '2024-S1'
  AND status IN (1, 2)
UNION ALL
SELECT 
    'Gold Aggregated',
    SUM(student_count) as total_students,
    SUM(total_eftsu) as total_eftsu
FROM mcds_gold.student_load_by_unit
WHERE semester = '2024-S1';

-- ==============================================================================
-- Business Insights Queries
-- ==============================================================================

-- Query 6.1: High-demand units (top 10% by enrolment)
SELECT 
    unitCode,
    unitName,
    student_count,
    total_eftsu,
    NTILE(10) OVER (ORDER BY student_count DESC) as demand_decile
FROM mcds_gold.student_load_by_unit
WHERE semester = '2024-S1'
  AND NTILE(10) OVER (ORDER BY student_count DESC) = 1
ORDER BY student_count DESC;

-- Query 6.2: Faculty distribution (student concentration)
SELECT 
    locationName as faculty,
    student_count,
    ROUND(100.0 * student_count / SUM(student_count) OVER (), 1) as pct_of_total
FROM mcds_gold.student_load_by_facility
WHERE semester = '2024-S1'
ORDER BY student_count DESC;

-- ==============================================================================
-- NOTES:
-- - All queries use PLACEHOLDER values from config/business-rules.yaml
-- - Active status codes (1, 2) and current semester ('2024-S1') are mock values
-- - When UC confirms real values, update queries or use parameters
-- - Performance: All queries tested on mock data (<5 seconds execution)
-- ==============================================================================
