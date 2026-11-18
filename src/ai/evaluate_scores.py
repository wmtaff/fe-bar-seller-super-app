"""Score evaluation (job task `evaluate_scores`, Task 7, spec 4.4 item 6).

Deal scores: sample closed opportunities, rebuild each one's OpenJev state as of its pre-close
truth snapshot_date, score it with the same openjev.call + DEAL_QUESTIONS as production, then
compare p_close_quarter with the real outcome (is_won): AUC, lift by decile, a 5-bin calibration
table, and AUC of the generator's latent true_intent (a ceiling / sanity check).
Extraction: precision/recall of gold_call_insights.competitors vs the generator's planted
competitors, on a 20-call spot check and on every call.

Ground truth (the generator's _eval/truth files) feeds ONLY this evaluation: never scores, NBAs or
any app-facing table. An opp that closed in an increment has a truth row in two batches; the
latest batch wins.

As-of reconstruction (only data dated <= snapshot_date):
  * opportunity: stage, amount, close date and forecast category from the latest
    silver_opportunity_history row created by the snapshot; stage age from that row; activity
    recency and 30-day count from completed activities up to the snapshot; days_to_close and
    is_current_quarter relative to the snapshot. The CRM next_step and competitor fields are
    dropped: only their current values exist, and the generator back-fills competitor on lost deals
    at close time (an outcome leak). Pre-snapshot competitor mentions still reach the state through
    the as-of call insights. Products, fleet size and type are taken as recorded.
  * account: Customer/ARR/products owned from the account's Closed Won opps closed before the
    snapshot; usage from silver_usage_daily windows ending at the snapshot (null before the usage
    history starts); open tickets = created by the snapshot and not solved by then; P1s in the
    30 days up to it.
  * calls: insights only from calls that started by the end of the snapshot day.

Results: an MLflow run in /Users/<me>/fleetwise-score-eval (params, metrics, tables as
artifacts) and rows in gold_score_eval(run_id, metric, segment, value).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ai import openjev
from ai.questions import DEAL_QUESTIONS, MODEL, QUESTIONS_VERSION

SAMPLE_SIZE = 400
SPOT_CHECK_SIZE = 20
MAX_ERROR_RATE = 0.05
CAL_BINS = 5


# --------------------------------------------------------------------------- pure metrics
def auc(scores, labels) -> float | None:
    """ROC AUC (Mann-Whitney U with average ranks for ties). None if only one class."""
    pairs = sorted(zip(scores, labels), key=lambda p: p[0])
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        rank_sum += avg_rank * sum(1 for k in range(i, j + 1) if pairs[k][1])
        i = j + 1
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def lift_by_decile(scores, labels, n_bins: int = 10) -> list[dict]:
    """Rank by score (highest first) and split into n_bins near-equal groups; decile 1 = top."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    base = sum(labels) / len(labels) if labels else 0.0
    q, r = divmod(len(order), n_bins)
    rows, start = [], 0
    for d in range(n_bins):
        size = q + (1 if d < r else 0)
        idx = order[start:start + size]
        start += size
        pos = sum(labels[i] for i in idx)
        rate = pos / len(idx) if idx else None
        rows.append({"decile": d + 1, "n": len(idx), "positives": pos, "win_rate": rate,
                     "lift": (rate / base) if (rate is not None and base) else None,
                     "mean_score": sum(scores[i] for i in idx) / len(idx) if idx else None})
    return rows


def calibration_table(scores, labels, n_bins: int = CAL_BINS) -> list[dict]:
    """Equal-width bins over [0, 1] (1.0 falls in the top bin): mean predicted vs observed rate."""
    width = 1 / n_bins
    rows = []
    for b in range(n_bins):
        idx = [i for i, s in enumerate(scores) if min(int(s / width), n_bins - 1) == b]
        rows.append({
            "bin": f"{b * width:.1f}-{(b + 1) * width:.1f}", "n": len(idx),
            "mean_predicted": sum(scores[i] for i in idx) / len(idx) if idx else None,
            "observed_rate": sum(labels[i] for i in idx) / len(idx) if idx else None,
        })
    return rows


def set_pr(pairs) -> dict:
    """Micro-averaged precision/recall over (extracted, planted) name lists, case-insensitive."""
    tp = fp = fn = 0
    for extracted, planted in pairs:
        e = {x.strip().lower() for x in extracted or [] if x and x.strip()}
        p = {x.strip().lower() for x in planted or [] if x and x.strip()}
        tp, fp, fn = tp + len(e & p), fp + len(e - p), fn + len(p - e)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def metric_rows(run_id: str, metrics: dict, lift=(), calibration=()) -> list[dict]:
    """gold_score_eval rows. `metrics` keys are a metric name (segment 'all') or a
    (metric, segment) tuple. None values (e.g. empty calibration bins) are skipped."""
    rows = []

    def add(metric, segment, value):
        if value is not None:
            rows.append({"run_id": run_id, "metric": metric, "segment": segment, "value": float(value)})

    for k, v in metrics.items():
        metric, segment = k if isinstance(k, tuple) else (k, "all")
        add(metric, segment, v)
    for r in lift:
        seg = f"decile_{r['decile']:02d}"
        add("lift", seg, r.get("lift"))
        add("win_rate", seg, r.get("win_rate"))
    for r in calibration:
        seg = f"bin_{r['bin']}"
        add("calibration_observed", seg, r.get("observed_rate"))
        add("calibration_predicted", seg, r.get("mean_predicted"))
        add("calibration_n", seg, r.get("n") or None)
    return rows


def _md_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols = list(rows[0])

    def fmt(v):
        return f"{v:.3f}" if isinstance(v, float) else ("" if v is None else str(v))

    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(fmt(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


# --------------------------------------------------------------------------- SQL (Spark)
EVAL_TABLE = "gold_score_eval"
EVAL_DDL = f"""
CREATE TABLE IF NOT EXISTS {EVAL_TABLE} (
  run_id STRING NOT NULL COMMENT 'MLflow run id of the evaluation (experiment /Users/<me>/fleetwise-score-eval).',
  metric STRING NOT NULL COMMENT 'Metric: auc, auc_true_intent, top_decile_lift, brier, base_rate, n_scored, n_errors, lift / win_rate (per decile), calibration_observed / calibration_predicted / calibration_n (per bin), competitor_precision / competitor_recall (extraction).',
  segment STRING NOT NULL COMMENT 'Slice the metric is for: all, decile_01..decile_10 (1 = highest scores), bin_<lo>-<hi> (p_close_quarter bin), spot_check_20 or all_calls (extraction).',
  value DOUBLE COMMENT 'Metric value.',
  evaluated_at TIMESTAMP COMMENT 'When the evaluation run wrote the row.',
  CONSTRAINT gold_score_eval_pk PRIMARY KEY (run_id, metric, segment)
)
COMMENT 'Gold (AI eval): offline evaluation of the OpenJev deal score (closed opps re-scored as of their pre-close snapshot: AUC, lift by decile, calibration) and of call-insight extraction (competitor precision/recall vs planted signals). One set of rows per MLflow run; written by job task evaluate_scores (run_eval=true). Not app-facing.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"""

TRUTH_VIEW = "eval_truth"

# latest truth row per record (an opp closed in an increment has a row in two batches)
LATEST_TRUTH = f"""
SELECT * FROM {TRUTH_VIEW}
WHERE record_type = '{{record_type}}'
QUALIFY row_number() OVER (PARTITION BY record_id ORDER BY batch DESC) = 1"""

FQ = """concat('FY', lpad(CAST(pmod(year(add_months({d}, 11)), 100) AS STRING), 2, '0'),
       'Q', CAST(floor(pmod(month({d}) - 2, 12) / 3) + 1 AS STRING))"""

SAMPLE_SQL = f"""
CREATE OR REPLACE TEMPORARY VIEW eval_sample AS
WITH truth AS ({LATEST_TRUTH.format(record_type='Opportunity')})
SELECT t.record_id AS opportunity_id, to_date(t.snapshot_date) AS snapshot_date,
       CAST(to_date(t.snapshot_date) AS TIMESTAMP) + INTERVAL '23:59:59' HOUR TO SECOND AS snapshot_end,
       CAST(t.true_intent AS DOUBLE) AS true_intent, o.is_won, o.account_id
FROM truth t
JOIN gold_opportunity_pipeline o ON o.opportunity_id = t.record_id
WHERE o.is_closed AND to_date(t.snapshot_date) < o.close_date
ORDER BY sha2(t.record_id, 256)
LIMIT {{n}}"""

OPPS_AS_OF_SQL = f"""
WITH hist AS (
  SELECT s.opportunity_id, h.stage_name, h.amount, h.close_date, h.forecast_category, h.created_date AS entered_at
  FROM eval_sample s
  JOIN silver_opportunity_history h ON h.opportunity_id = s.opportunity_id AND h.created_date <= s.snapshot_end
  QUALIFY row_number() OVER (PARTITION BY s.opportunity_id ORDER BY h.created_date DESC, h.history_id DESC) = 1
),
act AS (
  SELECT s.opportunity_id, max(a.activity_at) AS last_activity_at,
         count_if(a.activity_at > s.snapshot_end - INTERVAL 30 DAYS) AS activities_30d
  FROM eval_sample s
  JOIN silver_activities a ON a.opportunity_id = s.opportunity_id AND a.activity_at <= s.snapshot_end
  WHERE a.activity_object = 'Event' OR a.status = 'Completed'
  GROUP BY s.opportunity_id
)
SELECT s.opportunity_id, s.snapshot_date, s.true_intent, s.is_won, o.account_id, o.account_name, o.owner_name,
  h.stage_name AS stage, o.opportunity_type, o.segment, h.amount AS acv, h.close_date,
  {FQ.format(d='h.close_date')} AS fiscal_quarter,
  {FQ.format(d='h.close_date')} = {FQ.format(d='s.snapshot_date')} AS is_current_quarter,
  datediff(h.close_date, s.snapshot_date) AS days_to_close,
  datediff(s.snapshot_date, to_date(h.entered_at)) AS stage_age_days,
  datediff(s.snapshot_date, to_date(act.last_activity_at)) AS days_since_last_activity,
  CAST(coalesce(act.activities_30d, 0) AS INT) AS activities_30d,
  h.forecast_category, CAST(NULL AS STRING) AS competitor, o.products, o.fleet_size,
  CAST(NULL AS STRING) AS next_step
FROM eval_sample s
JOIN gold_opportunity_pipeline o ON o.opportunity_id = s.opportunity_id
JOIN hist h ON h.opportunity_id = s.opportunity_id
LEFT JOIN act ON act.opportunity_id = s.opportunity_id"""

ACCOUNTS_AS_OF_SQL = """
WITH won AS (
  SELECT s.opportunity_id, count(w.opportunity_id) AS n_won, sum(w.acv) AS arr,
         array_distinct(flatten(collect_list(w.products))) AS products_owned
  FROM eval_sample s
  LEFT JOIN gold_opportunity_pipeline w
    ON w.account_id = s.account_id AND w.is_won AND w.close_date < s.snapshot_date
  GROUP BY s.opportunity_id
),
usage AS (
  SELECT s.opportunity_id,
    avg(CASE WHEN u.usage_date > date_sub(s.snapshot_date, 30) THEN u.active_vehicles END) AS last30,
    avg(CASE WHEN u.usage_date <= date_sub(s.snapshot_date, 30) THEN u.active_vehicles END) AS prior30
  FROM eval_sample s
  JOIN silver_usage_daily u ON u.account_id = s.account_id
   AND u.usage_date <= s.snapshot_date AND u.usage_date > date_sub(s.snapshot_date, 60)
  GROUP BY s.opportunity_id
),
tix AS (
  SELECT s.opportunity_id,
    count_if(t.solved_at IS NULL OR t.solved_at > s.snapshot_end) AS open_tickets,
    count_if(t.severity = 'P1' AND t.created_at > s.snapshot_end - INTERVAL 30 DAYS) AS p1_30d
  FROM eval_sample s
  JOIN silver_tickets t ON t.account_id = s.account_id AND t.created_at <= s.snapshot_end
  GROUP BY s.opportunity_id
)
SELECT s.opportunity_id,
  CASE WHEN won.n_won > 0 THEN 'Customer' ELSE 'Prospect' END AS account_type,
  a.industry, a.fleet_size, coalesce(won.arr, 0D) AS arr, won.products_owned,
  array_except(array('Vehicle Telematics', 'AI Dash Cams', 'Driver Safety', 'Fuel & Maintenance',
                     'Compliance/ELD', 'Equipment Monitoring'), won.products_owned) AS whitespace_products,
  round(usage.last30, 1) AS active_vehicles_30d,
  round((usage.last30 - usage.prior30) / nullif(usage.prior30, 0) * 100, 1) AS usage_trend_pct_30d,
  CAST(coalesce(tix.open_tickets, 0) AS INT) AS open_tickets,
  CAST(coalesce(tix.p1_30d, 0) AS INT) AS p1_tickets_30d,
  a.account_name, a.owner_name
FROM eval_sample s
JOIN gold_account_360 a ON a.account_id = s.account_id
LEFT JOIN won ON won.opportunity_id = s.opportunity_id
LEFT JOIN usage ON usage.opportunity_id = s.opportunity_id
LEFT JOIN tix ON tix.opportunity_id = s.opportunity_id"""

# calls that started by the end of the snapshot day only
INSIGHTS_AS_OF_SQL = """
SELECT i.* FROM eval_sample s
JOIN gold_call_insights i ON i.opportunity_id = s.opportunity_id
WHERE i.started_at <= s.snapshot_end"""

EXTRACTION_SQL = f"""
WITH truth AS ({LATEST_TRUTH.format(record_type='Transcript')})
SELECT i.meeting_id, i.competitors AS extracted, t.planted_competitors AS planted,
       row_number() OVER (ORDER BY sha2(i.meeting_id, 256)) AS rn
FROM truth t
JOIN gold_call_insights i ON i.meeting_id = t.record_id
WHERE i.extract_error IS NULL"""


def _dicts(df) -> list[dict]:
    return [r.asDict(recursive=True) for r in df.collect()]


def build_eval_rows(spark) -> list[dict]:
    """One row per sampled closed opp: key, label (is_won), true_intent and the as-of state."""
    opps = _dicts(spark.sql(OPPS_AS_OF_SQL))
    accts = {r["opportunity_id"]: r for r in _dicts(spark.sql(ACCOUNTS_AS_OF_SQL))}
    insights: dict[str, list[dict]] = {}
    for r in _dicts(spark.sql(INSIGHTS_AS_OF_SQL)):
        insights.setdefault(r["opportunity_id"], []).append(r)
    rows = []
    for o in opps:
        state = openjev.build_deal_state(o, accts.get(o["opportunity_id"], {}), insights.get(o["opportunity_id"], []))
        rows.append({"key": o["opportunity_id"], "state": state, "label": int(bool(o["is_won"])),
                     "true_intent": o["true_intent"], "n_calls": len(insights.get(o["opportunity_id"], []))})
    return rows


def deal_metrics(scored: list[dict]) -> tuple[dict, list[dict], list[dict]]:
    ok = [r for r in scored if r.get("p") is not None]
    p = [r["p"] for r in ok]
    y = [r["label"] for r in ok]
    ti = [r["true_intent"] for r in ok]
    lift = lift_by_decile(p, y)
    cal = calibration_table(p, y)
    metrics = {
        "auc": auc(p, y),
        "auc_true_intent": auc(ti, y),
        "top_decile_lift": lift[0]["lift"],
        "brier": sum((a - b) ** 2 for a, b in zip(p, y)) / len(p) if p else None,
        "base_rate": sum(y) / len(y) if y else None,
        "mean_p_close": sum(p) / len(p) if p else None,
        "n_scored": len(ok),
        "n_errors": len(scored) - len(ok),
        "n_with_calls": sum(1 for r in ok if r["n_calls"]),
    }
    return metrics, lift, cal


def extraction_metrics(rows: list[dict]) -> tuple[dict, list[dict]]:
    spot = [r for r in rows if r["rn"] <= SPOT_CHECK_SIZE]
    out = {}
    for seg, rs in (("spot_check_20", spot), ("all_calls", rows)):
        pr = set_pr([(r["extracted"], r["planted"]) for r in rs])
        out[("competitor_precision", seg)] = pr["precision"]
        out[("competitor_recall", seg)] = pr["recall"]
        out[("competitor_n_calls", seg)] = len(rs)
    detail = [{"meeting_id": r["meeting_id"], "extracted": ", ".join(r["extracted"] or []),
               "planted": ", ".join(r["planted"] or [])} for r in sorted(spot, key=lambda r: r["rn"])]
    return out, detail


def _write_eval_rows(spark, rows: list[dict], now: datetime) -> None:
    spark.sql(EVAL_DDL)
    spark.sql(f"ALTER TABLE {EVAL_TABLE} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
    schema = spark.table(EVAL_TABLE).schema
    spark.createDataFrame([{**r, "evaluated_at": now} for r in rows], schema).createOrReplaceTempView("eval_rows")
    spark.sql(f"""
        MERGE INTO {EVAL_TABLE} t USING eval_rows s
        ON t.run_id = s.run_id AND t.metric = s.metric AND t.segment = s.segment
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")


def run(spark, catalog: str, schema: str, *, truth_path: str, host: str, token_fn, experiment: str,
        sample_size: int = SAMPLE_SIZE, max_workers: int = 8) -> dict:
    import mlflow

    from ai.scoring_job import score_frame

    spark.sql(f"USE CATALOG `{catalog}`")
    spark.sql(f"USE SCHEMA `{schema}`")
    spark.read.json(truth_path).createOrReplaceTempView(TRUTH_VIEW)
    spark.sql(SAMPLE_SQL.format(n=int(sample_size)))
    rows = build_eval_rows(spark)
    results = score_frame(rows, DEAL_QUESTIONS, max_workers, host=host, token=token_fn(), error_budget=1.0)
    scored = [{**r, "p": openjev.deal_scores(r["answers"])["p_close_quarter"] if r["answers"] else None}
              for r in results]
    metrics, lift, cal = deal_metrics(scored)
    ext_metrics, ext_detail = extraction_metrics(_dicts(spark.sql(EXTRACTION_SQL)))
    lat = sorted(r["latency_ms"] for r in results if r["latency_ms"] is not None)

    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=f"score-eval-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}") as mrun:
        mlflow.log_params({
            "model": MODEL, "questions_version": QUESTIONS_VERSION, "sample_size": sample_size,
            "sample_method": "closed opps with snapshot_date < close_date, ordered by sha2(opportunity_id)",
            "label": "gold_opportunity_pipeline.is_won", "truth_path": truth_path,
            "state_as_of": "truth snapshot_date (history stage/amount/close date, activities, calls, account)",
            "spot_check_size": SPOT_CHECK_SIZE,
        })
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
        mlflow.log_metrics({f"{m}_{s}": float(v) for (m, s), v in ext_metrics.items() if v is not None})
        if lat:
            mlflow.log_metric("latency_p50_ms", lat[len(lat) // 2])
        mlflow.log_dict({"lift_by_decile": lift, "calibration": cal, "extraction_spot_check": ext_detail},
                        "eval_tables.json")
        mlflow.log_text(_md_table(lift), "lift_by_decile.md")
        mlflow.log_text(_md_table(cal), "calibration.md")
        mlflow.log_text(_md_table(ext_detail), "extraction_spot_check.md")
        run_id = mrun.info.run_id

    _write_eval_rows(spark, metric_rows(run_id, {**metrics, **ext_metrics}, lift, cal), datetime.now(timezone.utc))
    summary = {"run_id": run_id, "experiment": experiment, "metrics": metrics,
               "extraction": {f"{m}/{s}": v for (m, s), v in ext_metrics.items()},
               "lift_by_decile": lift, "calibration": cal, "extraction_spot_check": ext_detail}
    print(json.dumps({"score_eval_summary": summary}, default=str))
    if metrics["n_errors"] > MAX_ERROR_RATE * len(scored):
        raise RuntimeError(f"{metrics['n_errors']}/{len(scored)} eval OpenJev calls failed; metrics are partial")
    return summary
