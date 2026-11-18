"""Task 7: offline checks of next best actions SQL, the score-eval metrics and job wiring."""

import re
from pathlib import Path

import pytest
import yaml

from ai import evaluate_scores as ev

ROOT = Path(__file__).resolve().parents[2]
NBA_SQL = (ROOT / "src" / "ai" / "next_best_actions.sql").read_text()
EVAL_PY = (ROOT / "src" / "ai" / "evaluate_scores.py").read_text()
JOB = ROOT / "resources" / "seller_superapp_daily.job.yml"


def _job():
    return yaml.safe_load(JOB.read_text())["resources"]["jobs"]["seller_superapp_daily"]


def _tasks():
    return {t["task_key"]: t for t in _job()["tasks"]}


def _deps(task):
    return {d["task_key"]: d.get("outcome") for d in task.get("depends_on", [])}


# --------------------------------------------------------------------------- metrics
def test_auc_perfect_random_and_ties():
    assert ev.auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert ev.auc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0
    assert ev.auc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == 0.5  # ties count half
    assert ev.auc([0.9, 0.4, 0.6, 0.1], [1, 1, 0, 0]) == 0.75
    assert ev.auc([0.3, 0.4], [1, 1]) is None  # one class only


def test_lift_by_decile():
    scores = [i / 100 for i in range(100)]
    labels = [1 if i >= 80 else 0 for i in range(100)]  # top 20 are the winners
    rows = ev.lift_by_decile(scores, labels)
    assert [r["decile"] for r in rows] == list(range(1, 11))
    assert sum(r["n"] for r in rows) == 100
    assert rows[0]["win_rate"] == 1.0 and rows[0]["lift"] == pytest.approx(5.0)
    assert rows[2]["positives"] == 0 and rows[-1]["lift"] == 0.0
    assert rows[0]["mean_score"] > rows[-1]["mean_score"]


def test_lift_handles_sizes_not_divisible_by_ten():
    rows = ev.lift_by_decile([0.5] * 23, [1] * 10 + [0] * 13)
    assert sum(r["n"] for r in rows) == 23 and all(r["n"] in (2, 3) for r in rows)


def test_calibration_table_five_equal_width_bins():
    rows = ev.calibration_table([0.05, 0.1, 0.5, 0.55, 0.95, 1.0], [0, 0, 1, 0, 1, 1])
    assert [r["bin"] for r in rows] == ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    by = {r["bin"]: r for r in rows}
    assert by["0.0-0.2"]["n"] == 2 and by["0.0-0.2"]["observed_rate"] == 0.0
    assert by["0.4-0.6"]["observed_rate"] == 0.5 and by["0.4-0.6"]["mean_predicted"] == pytest.approx(0.525)
    assert by["0.8-1.0"]["n"] == 2  # 1.0 falls in the top bin
    assert by["0.2-0.4"]["n"] == 0 and by["0.2-0.4"]["observed_rate"] is None


def test_set_precision_recall_is_case_insensitive_micro_average():
    r = ev.set_pr([(["RoadLynx", "fleetcore"], ["roadlynx"]), ([], ["Trackwell"]), ([], [])])
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 1)
    assert r["precision"] == 0.5 and r["recall"] == 0.5
    assert ev.set_pr([([], [])])["precision"] is None


def test_metric_rows_shape():
    rows = ev.metric_rows("run1", {"auc": 0.7}, lift=[{"decile": 1, "lift": 2.0, "win_rate": 0.8}],
                          calibration=[{"bin": "0.0-0.2", "observed_rate": None, "mean_predicted": 0.1, "n": 0}])
    assert {"run_id": "run1", "metric": "auc", "segment": "all", "value": 0.7} in rows
    assert {"run_id": "run1", "metric": "lift", "segment": "decile_01", "value": 2.0} in rows
    assert all(r["value"] is not None for r in rows)  # empty bins are skipped, never written as null


# --------------------------------------------------------------------------- eval as-of discipline
def test_eval_reads_latest_truth_per_record_and_builds_as_of_snapshot():
    assert "_eval/truth" in EVAL_PY
    assert re.search(r"PARTITION BY record_id ORDER BY batch DESC", EVAL_PY)
    # stage / amount / close date from history as of the snapshot, calls only up to it
    assert "silver_opportunity_history" in EVAL_PY
    assert re.search(r"started_at\s*<=", EVAL_PY) and "snapshot_date" in EVAL_PY
    assert "DEAL_QUESTIONS" in EVAL_PY and "build_deal_state" in EVAL_PY


def test_truth_never_feeds_app_tables():
    for path in [ROOT / "src" / "ai" / "next_best_actions.sql", ROOT / "src" / "ai" / "scoring_job.py",
                 ROOT / "src" / "ai" / "call_insights.sql"]:
        text = path.read_text().lower()
        assert "_eval" not in text and "truth" not in text, path


# --------------------------------------------------------------------------- NBA SQL
def test_nba_sql_is_rebuild_safe_merge_with_stable_ids():
    assert "MERGE INTO gold_next_best_actions" in NBA_SQL
    assert re.search(r"WHEN NOT MATCHED BY SOURCE THEN DELETE", NBA_SQL)
    assert re.search(r"sha2\(concat_ws\('\|', opportunity_id, action_type, source_key\), 256\)", NBA_SQL)
    assert "DROP TABLE" not in NBA_SQL.upper() and "CREATE OR REPLACE TABLE gold_" not in NBA_SQL
    # the app's status is never overwritten by a re-run
    update = NBA_SQL.split("MERGE INTO gold_next_best_actions", 1)[1].split("WHEN NOT MATCHED THEN", 1)[0]
    assert "status" not in update.split("UPDATE SET", 1)[1]


def test_nba_sources_rules_and_priority():
    for v in ["'call'", "'model'", "'rule'", "'stale_opp'", "'competitor_expiring'", "'usage_drop'",
              "'p1_ticket'", "next_action_conf >= 0.5", "1.5", "1.2", "-15", "21"]:
        assert v in NBA_SQL, v
    assert re.search(r"acv.*p_close.*urgency", NBA_SQL, re.S)


def test_nba_feedback_is_optional():
    # gold_nba_feedback (Task 8) may not exist: only referenced through dynamic SQL after a check
    assert "information_schema.tables" in NBA_SQL and "EXECUTE IMMEDIATE" in NBA_SQL
    static = re.sub(r"'[^']*'", "''", NBA_SQL)
    assert "gold_nba_feedback" not in re.sub(r"--[^\n]*", "", static)
    assert re.search(r"least\(1\.5, greatest\(0\.5", NBA_SQL)


@pytest.mark.parametrize("table", ["gold_next_best_actions", "gold_opportunity_app"])
def test_app_tables_cdf_pk_merge(table):
    ddl = NBA_SQL.split(f"CREATE TABLE IF NOT EXISTS {table}", 1)[1].split(";", 1)[0]
    assert "PRIMARY KEY" in ddl and "'delta.enableChangeDataFeed' = 'true'" in ddl
    assert re.search(rf"MERGE INTO {table}", NBA_SQL)


# --------------------------------------------------------------------------- job wiring
def test_job_runs_nba_after_scoring():
    t = _tasks()["next_best_actions"]
    assert _deps(t) == {"ai_scoring": None}
    assert t["sql_task"]["file"]["path"] == "../src/ai/next_best_actions.sql"
    assert t["sql_task"]["parameters"] == {"catalog": "${var.catalog}", "schema": "${var.schema}"}


def test_eval_runs_only_when_run_eval_true():
    params = {p["name"]: p["default"] for p in _job()["parameters"]}
    assert params["run_eval"] == "false"
    t = _tasks()
    cond = t["check_run_eval"]["condition_task"]
    assert cond == {"op": "EQUAL_TO", "left": "{{job.parameters.run_eval}}", "right": "true"}
    assert _deps(t["check_run_eval"]) == {"next_best_actions": None}
    assert _deps(t["evaluate_scores"]) == {"check_run_eval": "true"}
    assert t["evaluate_scores"]["spark_python_task"]["python_file"] == "../jobs/evaluate_scores.py"
