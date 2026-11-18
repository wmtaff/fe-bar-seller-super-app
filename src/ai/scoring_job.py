"""Deal and lead scoring with OpenJev (job task `ai_scoring`, Task 6).

Pure helpers (unit tested): score_frame, state_hash, select_pending.
Spark orchestration: run() reads the gold inputs, scores only what changed, MERGEs into
gold_deal_scores / gold_lead_scores and deletes scores of opps/leads that are no longer open.

Incremental and rebuild-safe (ruling R17). An open opp/lead is (re)scored when:
  * it has no score row yet, or its last attempt failed (score_error set);
  * its OpenJev state changed (state_sha256: opp fields, account health, call insights);
  * an input timestamp moved past the one it was scored from (inputs_changed_at =
    greatest(opp last_modified_date, last_activity_at, newest insight extracted_at); leads:
    last_modified_date). It is stored on the row, so synthetic CRM clocks that run ahead of
    the wall clock cannot cause endless re-scoring the way a comparison with scored_at would;
  * QUESTIONS_VERSION changed.
Failed calls keep the previous good score and only set score_error, so a transient outage
never blanks the app's ranking; the row is retried on the next run.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ai import openjev
from ai.questions import DEAL_QUESTIONS, LEAD_QUESTIONS, MODEL, QUESTIONS_VERSION

ERROR_BUDGET = 0.05


class ErrorBudgetExceeded(RuntimeError):
    """More than ERROR_BUDGET of the rows failed. `results` holds every row (scored or not)."""

    def __init__(self, msg: str, results: list[dict]):
        super().__init__(msg)
        self.results = results


def state_hash(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def select_pending(current: list[dict], previous: dict[str, dict], questions_version: str) -> list[dict]:
    """Rows of `current` (key, state_sha256, inputs_changed_at) that need (re)scoring.

    `previous` maps key -> the stored score row (state_sha256, inputs_changed_at,
    score_error, questions_version).
    """
    out = []
    for r in current:
        p = previous.get(r["key"])
        newer = r.get("inputs_changed_at") is not None and (
            p is not None and (p.get("inputs_changed_at") is None or r["inputs_changed_at"] > p["inputs_changed_at"]))
        if (p is None or p.get("score_error") is not None or p.get("state_sha256") != r["state_sha256"]
                or p.get("questions_version") != questions_version or newer):
            out.append(r)
    return out


def score_frame(rows: list[dict], questions, max_workers=16, *, host: str, token: str,
                error_budget: float = ERROR_BUDGET) -> list[dict]:
    """Call OpenJev for each row's `state` in a thread pool; keep input order.

    Each output row is the input row plus answers (None on failure), score_error,
    latency_ms, input_tokens and attempts. Raises ErrorBudgetExceeded (carrying all
    results) when more than `error_budget` of the rows failed.
    """

    def one(row: dict) -> dict:
        meta: dict = {}
        try:
            answers = openjev.call(row["state"], questions, host=host, token=token, meta=meta)
            err = None
        except openjev.OpenJevError as e:
            answers, err = None, str(e)[:500]
        return {**row, "answers": answers, "score_error": err, "latency_ms": meta.get("latency_ms"),
                "input_tokens": meta.get("input_tokens"), "attempts": meta.get("attempts")}

    if not rows:
        return []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(one, rows))
    failed = sum(r["score_error"] is not None for r in results)
    if failed / len(results) > error_budget:
        raise ErrorBudgetExceeded(
            f"{failed}/{len(results)} OpenJev calls failed (> {error_budget:.0%} budget); "
            f"first error: {next(r['score_error'] for r in results if r['score_error'])}", results)
    return results


# --------------------------------------------------------------------------- Spark / Delta
DEAL_TABLE = "gold_deal_scores"
LEAD_TABLE = "gold_lead_scores"

_COMMON_COLS = """
  scored_at TIMESTAMP COMMENT 'When the row was last scored (or, for a row that never scored successfully, last attempted).',
  score_error STRING COMMENT 'Null when the last OpenJev call succeeded. Otherwise the error of the last attempt (HTTP status, timeout); the previous good scores are kept and the row is retried next run.',
  model STRING COMMENT 'OpenJev model used (system.ai.openjev-qwen35-4b).',
  questions_version STRING COMMENT 'Version of the question map in src/ai/questions.py. A new version re-scores every row.',
  state_sha256 STRING COMMENT 'SHA-256 of the OpenJev state sent. A different state on the next run triggers re-scoring.',
  inputs_changed_at TIMESTAMP COMMENT 'Newest input timestamp the score was computed from. A newer input timestamp triggers re-scoring.',
  latency_ms INT COMMENT 'Latency of the successful OpenJev call in milliseconds.',
  input_tokens INT COMMENT 'OpenJev input tokens of the successful call (OpenJev returns no output tokens).',"""

DEAL_DDL = f"""
CREATE TABLE IF NOT EXISTS {DEAL_TABLE} (
  opportunity_id STRING NOT NULL COMMENT 'Salesforce Opportunity Id (18-char). Primary key; joins gold_opportunity_pipeline. Open opportunities only.',
  p_close_quarter DOUBLE COMMENT 'Calibrated probability-weighted likelihood (0..1) that the deal closes won this fiscal quarter: OpenJev close_this_quarter score / 4.',
  close_label STRING COMMENT 'Most probable close_this_quarter level: Very unlikely, Unlikely, Possible, Likely, Very likely.',
  close_confidence DOUBLE COMMENT 'OpenJev confidence (0..1) of the close_this_quarter answer.',
  close_probs MAP<STRING, DOUBLE> COMMENT 'Probability of each close_this_quarter level (sums to 1).',
  next_action STRING COMMENT 'Recommended next seller action: send_proposal, multithread, schedule_demo, exec_sponsor, address_risk or nurture.',
  next_action_conf DOUBLE COMMENT 'OpenJev confidence (0..1) of next_action.',
  next_action_probs MAP<STRING, DOUBLE> COMMENT 'Probability of each next action (sums to 1).',
  competitive_risk DOUBLE COMMENT 'Probability (0..1) that a competitor is actively in the deal with a real chance to win.',
  churn_risk DOUBLE COMMENT 'Probability (0..1) that the account is at risk of churning or shrinking.',{_COMMON_COLS}
  CONSTRAINT gold_deal_scores_pk PRIMARY KEY (opportunity_id)
)
COMMENT 'Gold (AI): OpenJev deal scores for every open opportunity - calibrated P(close this quarter), next best action, competitive and churn risk, with full probabilities. Incremental MERGE by job task ai_scoring; feeds the app priority ranking and next-best-actions. No PII.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"""

LEAD_DDL = f"""
CREATE TABLE IF NOT EXISTS {LEAD_TABLE} (
  lead_id STRING NOT NULL COMMENT 'Salesforce Lead Id (18-char). Primary key; joins silver_leads. Open leads only (not converted, status not Qualified/Unqualified).',
  fit_score DOUBLE COMMENT 'Calibrated probability-weighted conversion fit (0..1): OpenJev conversion_fit score / 4.',
  fit_label STRING COMMENT 'Most probable conversion_fit level: Very poor fit, Poor fit, Moderate fit, Good fit, Excellent fit.',
  route_to STRING COMMENT 'Recommended sales segment to work the lead: SMB, Mid-Market or Enterprise.',
  route_conf DOUBLE COMMENT 'OpenJev confidence (0..1) of route_to.',{_COMMON_COLS}
  CONSTRAINT gold_lead_scores_pk PRIMARY KEY (lead_id)
)
COMMENT 'Gold (AI): OpenJev lead fit and routing for every open lead. Scored from non-PII profile fields only, without the outcome fields status/is_converted/converted_date (ruling R11). Incremental MERGE by job task ai_scoring.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"""

OPEN_OPPS = "SELECT * FROM gold_opportunity_pipeline WHERE NOT is_closed"
# Ruling R11: open leads only (not converted, status not Qualified/Unqualified).
OPEN_LEAD_WHERE = """
WHERE NOT coalesce(is_converted, false)
  AND coalesce(status, '') NOT IN ('Qualified', 'Unqualified')"""
# Only non-PII columns are read: no names, email, phone, company or owner (and no outcome fields).
OPEN_LEADS = f"""
SELECT lead_id, title, lead_source, industry, state, country, fleet_size, products_of_interest,
       description, created_date, last_modified_date
FROM silver_leads{OPEN_LEAD_WHERE}"""
OPEN_LEAD_KEYS = f"SELECT lead_id FROM silver_leads{OPEN_LEAD_WHERE}"


def _max_ts(*vals):
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _deal_inputs(spark) -> list[dict]:
    opps = [r.asDict(recursive=True) for r in spark.sql(OPEN_OPPS).collect()]
    accts = {r["account_id"]: r.asDict(recursive=True) for r in spark.sql(
        f"SELECT a.* FROM gold_account_360 a WHERE a.account_id IN (SELECT account_id FROM ({OPEN_OPPS}))").collect()}
    insights: dict[str, list[dict]] = {}
    for r in spark.sql(f"""
            SELECT i.* FROM gold_call_insights i
            WHERE i.opportunity_id IN (SELECT opportunity_id FROM ({OPEN_OPPS}))""").collect():
        insights.setdefault(r["opportunity_id"], []).append(r.asDict(recursive=True))
    rows = []
    for o in opps:
        ins = insights.get(o["opportunity_id"], [])
        state = openjev.build_deal_state(o, accts.get(o["account_id"], {}), ins)
        rows.append({"key": o["opportunity_id"], "state": state, "state_sha256": state_hash(state),
                     "inputs_changed_at": _max_ts(o.get("last_modified_date"), o.get("last_activity_at"),
                                                  *(i.get("extracted_at") for i in ins))})
    return rows


def _lead_inputs(spark) -> list[dict]:
    rows = []
    for r in spark.sql(OPEN_LEADS).collect():
        lead = r.asDict(recursive=True)
        state = openjev.build_lead_state(lead)
        rows.append({"key": lead["lead_id"], "state": state, "state_sha256": state_hash(state),
                     "inputs_changed_at": lead.get("last_modified_date")})
    return rows


def _previous(spark, table: str, key: str) -> dict[str, dict]:
    return {r[key]: r.asDict() for r in spark.sql(
        f"SELECT {key}, state_sha256, inputs_changed_at, score_error, questions_version FROM {table}").collect()}


def _merge(spark, table: str, key: str, records: list[dict]) -> None:
    if not records:
        return
    schema = spark.table(table).schema
    view = f"tmp_{table}_batch"
    spark.createDataFrame(records, schema).createOrReplaceTempView(view)
    spark.sql(f"""
        MERGE INTO {table} t USING {view} s ON t.{key} = s.{key}
        WHEN MATCHED AND s.score_error IS NOT NULL THEN UPDATE SET t.score_error = s.score_error
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")


def _records(results: list[dict], key: str, to_cols, empty_cols: dict, now: datetime) -> list[dict]:
    out = []
    for r in results:
        cols = to_cols(r["answers"]) if r["answers"] is not None else dict(empty_cols)
        out.append({key: r["key"], **cols, "scored_at": now, "score_error": r["score_error"], "model": MODEL,
                    "questions_version": QUESTIONS_VERSION, "state_sha256": r["state_sha256"],
                    "inputs_changed_at": r["inputs_changed_at"], "latency_ms": r["latency_ms"],
                    "input_tokens": r["input_tokens"]})
    return out


EMPTY_DEAL = dict.fromkeys(["p_close_quarter", "close_label", "close_confidence", "close_probs", "next_action",
                            "next_action_conf", "next_action_probs", "competitive_risk", "churn_risk"])
EMPTY_LEAD = dict.fromkeys(["fit_score", "fit_label", "route_to", "route_conf"])


def _score_kind(spark, *, table, key, open_keys_sql, inputs, questions, to_cols, empty, host, token_fn,
                max_workers) -> dict:
    deleted = spark.sql(f"""
        DELETE FROM {table} t WHERE NOT EXISTS (
          SELECT 1 FROM ({open_keys_sql}) k WHERE k.{key} = t.{key})""").collect()
    current = inputs(spark)
    pending = select_pending(current, _previous(spark, table, key), QUESTIONS_VERSION)
    budget_error = None
    try:
        results = score_frame(pending, questions, max_workers, host=host, token=token_fn())
    except ErrorBudgetExceeded as e:
        results, budget_error = e.results, e
    _merge(spark, table, key, _records(results, key, to_cols, empty, datetime.now(timezone.utc)))
    lat = sorted(r["latency_ms"] for r in results if r["latency_ms"] is not None)
    return {
        "table": table, "open": len(current), "pending": len(pending),
        "deleted": int(deleted[0][0]) if deleted and len(deleted[0]) else None,
        "scored_ok": sum(r["score_error"] is None for r in results),
        "errors": sum(r["score_error"] is not None for r in results),
        "retried_calls": sum((r["attempts"] or 1) > 1 for r in results),
        "latency_p50_ms": lat[len(lat) // 2] if lat else None,
        "latency_p95_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
        "input_tokens": sum(r["input_tokens"] or 0 for r in results),
        "budget_error": str(budget_error) if budget_error else None,
    }


def run(spark, catalog: str, schema: str, *, host: str, token_fn, max_workers: int = 16) -> list[dict]:
    """Score open deals then open leads. Raises ErrorBudgetExceeded after both are written
    if either went over the error budget."""
    spark.sql(f"USE CATALOG `{catalog}`")
    spark.sql(f"USE SCHEMA `{schema}`")
    for ddl, table in ((DEAL_DDL, DEAL_TABLE), (LEAD_DDL, LEAD_TABLE)):
        spark.sql(ddl)
        spark.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
    summary = [
        _score_kind(spark, table=DEAL_TABLE, key="opportunity_id",
                    open_keys_sql="SELECT opportunity_id FROM gold_opportunity_pipeline WHERE NOT is_closed",
                    inputs=_deal_inputs, questions=DEAL_QUESTIONS, to_cols=openjev.deal_scores, empty=EMPTY_DEAL,
                    host=host, token_fn=token_fn, max_workers=max_workers),
        _score_kind(spark, table=LEAD_TABLE, key="lead_id", open_keys_sql=OPEN_LEAD_KEYS,
                    inputs=_lead_inputs, questions=LEAD_QUESTIONS, to_cols=openjev.lead_scores, empty=EMPTY_LEAD,
                    host=host, token_fn=token_fn, max_workers=max_workers),
    ]
    print(json.dumps({"ai_scoring_summary": summary}, default=str))
    over = [s for s in summary if s["budget_error"]]
    if over:
        raise ErrorBudgetExceeded("; ".join(f"{s['table']}: {s['budget_error']}" for s in over), [])
    return summary
