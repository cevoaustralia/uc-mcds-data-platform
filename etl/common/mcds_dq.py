"""
Deterministic data quality for every layer (SOW D2 / D4).

Generated rules come from the configs themselves (keys, NOT NULL, foreign keys, file headers);
custom rules come from pipeline/dq/<layer>.yaml as SQL returning a violation count (0 = pass).
Every result is a plain dict so it can be printed, written to the ops table and read by
QuickSight / the Bedrock advisor.
"""

import datetime as dt

from mcds_config import layer_sql


def _result(rule_id, layer, severity, description, violations, error=None, table=""):
    if error is not None:
        status = "ERROR"
    elif violations == 0:
        status = "PASS"
    else:
        status = "FAIL" if severity == "fail" else "WARN"
    return {"rule_id": rule_id, "layer": layer, "table_name": table, "severity": severity,
            "description": description, "violations": -1 if violations is None else int(violations),
            "status": status, "error": (error or "")[:500],
            "run_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}


def _count(spark, sql):
    return int(spark.sql(layer_sql(sql)).collect()[0][0] or 0)


def _safe(spark, rule_id, layer, severity, description, sql, table=""):
    try:
        return _result(rule_id, layer, severity, description, _count(spark, sql), table=table)
    except Exception as exc:        # a broken rule is reported, never silently skipped
        return _result(rule_id, layer, severity, description, None, error=str(exc), table=table)


# ------------------------------------------------------------------------------------------------
# generated rules
# ------------------------------------------------------------------------------------------------
def bronze_file_checks(table, n_rows, missing, unexpected, parse_failures):
    out = [
        _result(f"landing_{table}_rows", "landing", "fail", f"{table}: extract file has rows", 0 if n_rows > 0 else 1, table=table),
        _result(f"landing_{table}_unexpected_columns", "landing", "warn",
                f"{table}: file columns not in source config: {', '.join(unexpected) or 'none'}", len(unexpected), table=table),
        _result(f"landing_{table}_missing_columns", "landing", "warn",
                f"{table}: configured columns absent from file (loaded as NULL): {', '.join(missing) or 'none'}",
                len(missing), table=table),
    ]
    detail = ", ".join(f"{c}={n}" for c, n in sorted(parse_failures.items())) or "none"
    out.append(_result(f"bronze_{table}_type_parse", "bronze", "fail",
                       f"{table}: values that failed type conversion ({detail})", sum(parse_failures.values()), table=table))
    return out


def run_generated_bronze(spark, cfg, absent=None):
    absent = absent or {}
    out = []
    for table, src in cfg.sources.items():
        key = ", ".join(src["primary_key"])
        out.append(_safe(spark, f"bronze_{table}_pk_unique", "bronze", "fail",
                         f"{table}: natural key ({key}) is unique",
                         f"SELECT COUNT(*) FROM (SELECT {key} FROM bronze.{table} GROUP BY {key} HAVING COUNT(*) > 1)", table))
        notnull = [c for c, s in src["columns"].items() if s.get("nullable") is False and c not in absent.get(table, [])]
        if notnull:
            cond = " OR ".join(f"{c} IS NULL" for c in notnull)
            out.append(_safe(spark, f"bronze_{table}_not_null", "bronze", "warn",
                             f"{table}: NOT NULL columns per source metadata are populated ({len(notnull)} columns)",
                             f"SELECT COUNT(*) FROM bronze.{table} WHERE {cond}", table))
        # Bronze keeps every row as received; rows without a key are reported here and excluded in Silver
        pk_cond = " OR ".join(f"{c} IS NULL" for c in src["primary_key"])
        out.append(_safe(spark, f"bronze_{table}_pk_not_null", "bronze", "warn",
                         f"{table}: key columns are populated (rows without a key are excluded in Silver)",
                         f"SELECT COUNT(*) FROM bronze.{table} WHERE {pk_cond}", table))
    return out


def run_generated_silver(spark, cfg):
    out = []
    for name, e in cfg.entities.items():
        key = ", ".join(f"`{c}`" for c in e["primary_key"])
        out.append(_safe(spark, f"silver_{name}_pk_unique", "silver", "fail", f"{name}: primary key is unique and not null",
                         f"SELECT (SELECT COUNT(*) FROM (SELECT {key} FROM silver.{name} GROUP BY {key} HAVING COUNT(*) > 1))"
                         f" + (SELECT COUNT(*) FROM silver.{name} WHERE " +
                         " OR ".join(f"`{c}` IS NULL" for c in e["primary_key"]) + ")", name))
        for col, ref in (e.get("foreign_keys") or {}).items():
            ent, _, refcol = ref.partition(".")
            out.append(_safe(spark, f"silver_{name}_fk_{col}", "silver", "fail",
                             f"{name}.{col} resolves to {ref}",
                             f"SELECT COUNT(*) FROM silver.{name} a LEFT ANTI JOIN silver.{ent} b ON a.`{col}` = b.`{refcol}` "
                             f"WHERE a.`{col}` IS NOT NULL", name))
    return out


def run_custom(spark, cfg, layer):
    return [_safe(spark, r["id"], layer, r.get("severity", "fail"), r["description"], cfg.resolve(r["sql"]))
            for r in cfg.dq.get(layer, [])]


# ------------------------------------------------------------------------------------------------
def summarise(results):
    failed = [r for r in results if r["status"] in ("FAIL", "ERROR")]
    return {"total": len(results), "passed": sum(r["status"] == "PASS" for r in results),
            "failed": len(failed), "warnings": sum(r["status"] == "WARN" for r in results), "ok": not failed}


def print_results(results, title):
    print("=" * 78 + f"\n{title}\n" + "=" * 78)
    for r in results:
        extra = f" ({r['violations']})" if r["violations"] not in (0, -1) else ""
        extra = f" ({r['error']})" if r["error"] else extra
        print(f"  [{r['status']:<5}] {r['rule_id']}: {r['description']}{extra}")
    s = summarise(results)
    print(f"  -> {s['passed']}/{s['total']} passed, {s['failed']} failed, {s['warnings']} warnings")
    return s
