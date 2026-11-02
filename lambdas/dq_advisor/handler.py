"""
Bedrock DQ advisor (advisory only).

Invoked by the Step Function after the Gold stage with {"extract_date": "YYYY-MM-DD"}. It:
  1. reads this run's results from mcds_ops (dq_results, table_counts, mcds_validation) via Athena,
     plus the previous extract's row counts for drift;
  2. sends ONLY metadata and aggregates (rule ids, statuses, counts, drift %) to Amazon Bedrock;
  3. writes the model's plain-English issue summary to s3://<gold>/ops/dq_advisor/extract_date=<d>/summary.md
     and returns it.
It never changes data, rules or pass/fail outcomes - deterministic rules decide; the model explains.
"""

import json
import os
import time

import boto3

athena = boto3.client("athena")
bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")

DB = os.environ.get("OPS_DATABASE", "mcds_ops")
WG = os.environ["ATHENA_WORKGROUP"]
MODEL = os.environ["MODEL_ID"]
OUT = os.environ["OUTPUT_BUCKET"]

PROMPT = """You are a data quality analyst for a university student-load data pipeline
(Callista student system -> MCDS-standard Silver tables -> Gold reporting datasets).
Below are deterministic data quality results for extract {extract_date}, row counts per table with the
change versus the previous extract, and MCDS schema conformance results. Write a short report for the
data engineering lead:
1. Overall status in one sentence.
2. Failed rules first, then warnings: what each means in plain English, the likely cause, and the next
   check to make. Do not speculate beyond the evidence given.
3. Row-count changes above 10% that need explaining.
Use only the facts provided. Do not invent numbers.

DATA QUALITY RESULTS:
{dq}

ROW COUNTS (current vs previous extract):
{counts}

MCDS CONFORMANCE:
{mcds}
"""


def query(sql):
    qid = athena.start_query_execution(QueryString=sql, QueryExecutionContext={"Database": DB},
                                       WorkGroup=WG)["QueryExecutionId"]
    while True:
        st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]["State"]
        if st in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if st != "SUCCEEDED":
        raise RuntimeError(f"Athena query {st}: {sql}")
    rows = athena.get_query_results(QueryExecutionId=qid, MaxResults=500)["ResultSet"]["Rows"]
    head = [c["VarCharValue"] for c in rows[0]["Data"]]
    return [dict(zip(head, [c.get("VarCharValue") for c in r["Data"]])) for r in rows[1:]]


def lambda_handler(event, _context):
    d = event["extract_date"]
    dq = query(f"SELECT stage, rule_id, status, severity, violations, description FROM dq_results "
               f"WHERE extract_date = '{d}' AND status <> 'PASS' ORDER BY status, stage")
    counts = query(f"""
        WITH cur AS (SELECT stage, table_name, row_count FROM table_counts WHERE extract_date = '{d}'),
             prev AS (SELECT stage, table_name, row_count FROM table_counts
                      WHERE extract_date = (SELECT max(extract_date) FROM table_counts WHERE extract_date < '{d}'))
        SELECT cur.stage, cur.table_name, cur.row_count, prev.row_count AS previous_row_count
        FROM cur LEFT JOIN prev ON cur.stage = prev.stage AND cur.table_name = prev.table_name
        ORDER BY cur.stage, cur.table_name""")
    mcds = query(f"SELECT entity, records_validated, records_invalid, first_error FROM mcds_validation "
                 f"WHERE extract_date = '{d}'")
    prompt = PROMPT.format(extract_date=d, dq=json.dumps(dq, indent=1) or "all rules passed",
                           counts=json.dumps(counts, indent=1), mcds=json.dumps(mcds, indent=1))
    resp = bedrock.converse(modelId=MODEL, messages=[{"role": "user", "content": [{"text": prompt}]}],
                            inferenceConfig={"maxTokens": 1500, "temperature": 0})
    summary = resp["output"]["message"]["content"][0]["text"]
    key = f"ops/dq_advisor/extract_date={d}/summary.md"
    s3.put_object(Bucket=OUT, Key=key, Body=summary.encode("utf-8"), ContentType="text/markdown")
    return {"extract_date": d, "issues": len(dq), "summary_s3": f"s3://{OUT}/{key}", "summary": summary}
