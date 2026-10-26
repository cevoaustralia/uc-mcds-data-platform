"""
Config-driven data quality runner (SOW D2 / D4 auditable data management).

Rules live in config/data-quality-rules.yaml. Each rule is a SQL query returning the number
of violating rows; 0 means pass. Rules run against Spark views registered by pipeline.py.
"""

import datetime as _dt

from pipeline import resolve_tokens


def run_rules(spark, dq_cfg, rules, layers):
    """Run every rule whose layer is in `layers`. Returns list of result dicts."""
    results = []
    run_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for rule in dq_cfg["rules"]:
        if rule["layer"] not in layers:
            continue
        sql = resolve_tokens(rule["sql"], rules)
        try:
            violations = int(spark.sql(sql).collect()[0][0] or 0)
            status = "PASS" if violations == 0 else ("FAIL" if rule["severity"] == "fail" else "WARN")
            error = None
        except Exception as exc:  # a broken rule is itself a failure
            violations, status, error = None, "ERROR", str(exc)[:500]
        results.append({"rule_id": rule["id"], "layer": rule["layer"], "severity": rule["severity"],
                        "description": rule["description"], "violations": violations,
                        "status": status, "error": error, "run_at": run_at})
    return results


def summarise(results):
    failed = [r for r in results if r["status"] in ("FAIL", "ERROR")]
    warned = [r for r in results if r["status"] == "WARN"]
    return {"total": len(results), "passed": sum(r["status"] == "PASS" for r in results),
            "failed": len(failed), "warnings": len(warned), "ok": not failed}


def print_results(results, title="DATA QUALITY"):
    print("=" * 72)
    print(title)
    print("=" * 72)
    for r in results:
        mark = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "ERROR": "ERR "}[r["status"]]
        extra = f" ({r['violations']} rows)" if r["violations"] else ""
        if r["error"]:
            extra = f" ({r['error']})"
        print(f"  [{mark}] {r['rule_id']}: {r['description']}{extra}")
    s = summarise(results)
    print(f"  -> {s['passed']}/{s['total']} passed, {s['failed']} failed, {s['warnings']} warnings")
    return s


def results_dataframe(spark, results):
    rows = [dict(r, violations=-1 if r["violations"] is None else r["violations"], error=r["error"] or "")
            for r in results]
    return spark.createDataFrame(rows)
