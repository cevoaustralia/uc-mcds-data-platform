-- PIPELINE MONITORING: latest run per stage, data quality outcome and MCDS conformance
SELECT r.extract_date, r.stage, r.status, r.rules_total, r.rules_passed, r.rules_failed, r.rules_warned, r.finished_at
FROM mcds_ops.pipeline_runs r
ORDER BY r.extract_date DESC, r.stage;

-- SELECT stage, rule_id, status, violations, description FROM mcds_ops.dq_results
-- WHERE extract_date = (SELECT max(extract_date) FROM mcds_ops.dq_results) AND status <> 'PASS';

-- SELECT entity, records_validated, records_invalid FROM mcds_ops.mcds_validation
-- WHERE extract_date = (SELECT max(extract_date) FROM mcds_ops.mcds_validation);
