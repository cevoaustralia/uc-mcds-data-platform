-- RECONCILIATION: every unit enrolment by cohort and load decision. In-scope total = HE_COURSEWORK + COUNTS_AS_LOAD.
-- HDR and ELICOS are reported separately; withdrawals before census and invalid statuses carry no load.
SELECT cohort, load_exclusion_reason, unit_enrolments, headcount, eftsl
FROM mcds_gold.student_load_by_cohort
WHERE academic_year = 2026
ORDER BY cohort, load_exclusion_reason;
