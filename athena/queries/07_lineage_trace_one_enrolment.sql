-- LINEAGE: trace one Gold row back to its MCDS Silver records and Callista keys
-- (column-level lineage is also on every Silver column comment in the Glue Data Catalog)
SELECT f.unit_of_learning_enrolment_id   AS gold_key,
       e.unit_of_learning_availability_id AS mcds_availability,
       e.programme_of_learning_enrolment_id AS mcds_programme_enrolment,
       e.callista_unit_attempt_status, e.administrative_unit_status, e.eftsl, e.load_exclusion_reason,
       e.extract_date
FROM mcds_gold.fact_student_load f
JOIN mcds_silver.unit_of_learning_enrolment e ON e.unit_of_learning_enrolment_id = f.unit_of_learning_enrolment_id
LIMIT 10;
