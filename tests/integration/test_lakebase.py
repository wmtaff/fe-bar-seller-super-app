"""Task 8: Lakebase serving (UC -> Postgres synced tables) and write-back (Postgres -> Delta).

Ruling R14: no hard-coded counts or ids. Expected counts come from the UC source tables; the
lookup ids and the write-back action are sampled from the live data.

Measured numbers (lookup latency, write-back round trip) are merged into
evidence/07_lakebase_metrics.json so the evidence file quotes what the tests measured.
"""

import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from databricks.sdk.errors import NotFound
from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState
from databricks.sdk.service.postgres import SyncedTableState

from _lakebase_helpers import connect
from lakebase import setup_lakebase as lb

pytestmark = pytest.mark.integration

METRICS = Path(__file__).resolve().parents[2] / "evidence" / "07_lakebase_metrics.json"
LOOKUPS = 100
P95_BUDGET_MS = 50.0
ONLINE = {
    SyncedTableState.SYNCED_TABLE_ONLINE,
    SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE,
    SyncedTableState.SYNCED_TABLE_ONLINE_TRIGGERED_UPDATE,
    SyncedTableState.SYNCED_TABLE_ONLINE_CONTINUOUS_UPDATE,
}
TEST_PERSONA = "integration-test"
CDC_WAIT_S = 900
JOB_NAME = "seller_superapp_daily"


@pytest.fixture(scope="module")
def cfg(names) -> lb.Config:
    return lb.Config(catalog=names["catalog"], schema=names["schema"])


@pytest.fixture(scope="module")
def pg(ws, cfg):
    conn = connect(ws, cfg.branch_path)
    yield conn
    conn.close()


def _record(**kv) -> None:
    data = json.loads(METRICS.read_text()) if METRICS.exists() else {}
    data.update(kv)
    data["measured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    METRICS.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _pg_scalar(pg, q, params=None):
    with pg.cursor() as cur:
        cur.execute(q, params)
        return cur.fetchone()[0]


@pytest.mark.parametrize("table", [t.pg_table for t in lb.SYNCED_TABLES])
def test_synced_tables_online(ws, cfg, table):
    st = ws.postgres.get_synced_table(name=cfg.synced_table_name(table))
    assert st.status and st.status.detailed_state in ONLINE, (table, st.status)
    assert st.spec.branch == cfg.branch_path


@pytest.mark.parametrize("spec", lb.SYNCED_TABLES, ids=lambda s: s.pg_table)
def test_pg_row_counts_match_uc(sql, pg, cfg, spec):
    uc = int(sql(f"SELECT count(*) AS n FROM {cfg.source_full_name(spec)}")[0]["n"])
    pgn = _pg_scalar(pg, f'SELECT count(*) FROM "{cfg.pg_schema}"."{spec.pg_table}"')
    assert uc > 0 and pgn == uc, (spec.pg_table, uc, pgn)


def test_pg_point_lookup_fast(pg, cfg):
    with pg.cursor() as cur:
        cur.execute(f'SELECT opportunity_id FROM "{cfg.pg_schema}".opportunity_pipeline '
                    f"ORDER BY md5(opportunity_id) LIMIT %s", (LOOKUPS,))
        ids = [r[0] for r in cur.fetchall()]
        assert len(ids) == LOOKUPS
        q = (f'SELECT opportunity_id, stage, acv, p_close_quarter, next_action '
             f'FROM "{cfg.pg_schema}".opportunity_pipeline WHERE opportunity_id = %s')
        cur.execute(q, (ids[0],), prepare=True)  # warm the connection and the plan
        cur.fetchall()
        times = []
        for oid in ids:
            t0 = time.perf_counter()
            cur.execute(q, (oid,), prepare=True)
            row = cur.fetchone()
            times.append((time.perf_counter() - t0) * 1000)
            assert row and row[0] == oid
    q = statistics.quantiles(times, n=100)
    p50, p95, p99 = q[49], q[94], q[98]
    _record(lookup_latency_ms={"n": LOOKUPS, "p50": round(p50, 2), "p95": round(p95, 2),
                               "p99": round(p99, 2), "max": round(max(times), 2),
                               "client": "test runner (developer laptop) -> Lakebase over the internet"})
    assert p95 < P95_BUDGET_MS, (p50, p95, p99)


# --------------------------------------------------------------------------- write-back (after Task 10)
def _app_table_exists(pg) -> bool:
    return _pg_scalar(pg, "SELECT to_regclass('app.seller_actions') IS NOT NULL")


def _run_writeback_task(ws) -> None:
    jobs = list(ws.jobs.list(name=JOB_NAME))
    assert len(jobs) == 1, f"expected one deployed job named {JOB_NAME}"
    run = ws.jobs.run_now(job_id=jobs[0].job_id, only=["writeback_merge"]).result(
        timeout=timedelta(minutes=20))
    assert run.state.life_cycle_state == RunLifeCycleState.TERMINATED
    assert run.state.result_state == RunResultState.SUCCESS, run.state


def _wait_in_history(sql, cfg, row_id: int, change_type: str) -> float:
    """Seconds until the Lakehouse Sync history table holds the change (primary path only)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < CDC_WAIT_S:
        try:
            n = int(sql(f"SELECT count(*) AS n FROM {cfg.fq}.lb_seller_actions_history "
                        f"WHERE id = :id AND _pg_change_type = :ct",
                        {"id": (row_id, "BIGINT"), "ct": change_type})[0]["n"])
        except RuntimeError as e:  # history table not created yet
            if "TABLE_OR_VIEW_NOT_FOUND" not in str(e):
                raise
            n = 0
        if n:
            return time.monotonic() - t0
        time.sleep(10)
    raise TimeoutError(f"{change_type} of id {row_id} not in lb_seller_actions_history after {CDC_WAIT_S}s")


@pytest.mark.after_app
def test_writeback_roundtrip(ws, sql, pg, cfg):
    if not _app_table_exists(pg):
        pytest.skip("app.seller_actions does not exist yet (created by the app SP in Task 10)")
    try:
        lakehouse_sync = bool(list(ws.postgres.list_cdf_configs(parent=lb.database_path(ws, cfg))))
    except NotFound:
        lakehouse_sync = False
    action = sql(f"SELECT action_id, opportunity_id FROM {cfg.fq}.gold_next_best_actions "
                 f"ORDER BY action_id LIMIT 1")[0]
    t0 = time.monotonic()
    row_id = _pg_scalar(pg, """
        INSERT INTO app.seller_actions (action_id, opportunity_id, persona_user_id, decision, reason)
        VALUES (%s, %s, %s, 'dismissed', 'integration test round trip') RETURNING id""",
        (action["action_id"], action["opportunity_id"], TEST_PERSONA))
    try:
        cdc_s = _wait_in_history(sql, cfg, row_id, "insert") if lakehouse_sync else None
        _run_writeback_task(ws)
        got = sql(f"SELECT decision, action_type FROM {cfg.fq}.silver_seller_actions WHERE id = :id",
                  {"id": (row_id, "BIGINT")})
        roundtrip_s = time.monotonic() - t0
        assert got and got[0]["decision"] == "dismissed" and got[0]["action_type"], got
        _record(writeback={"path": "lakehouse_sync" if lakehouse_sync else "federated_merge",
                           "cdc_seconds": round(cdc_s, 1) if cdc_s is not None else None,
                           "roundtrip_seconds": round(roundtrip_s, 1)})
    finally:
        # clean up: a Postgres DELETE must also remove the row from silver
        _pg_scalar(pg, "WITH d AS (DELETE FROM app.seller_actions WHERE id = %s RETURNING 1) "
                       "SELECT count(*) FROM d", (row_id,))
    if lakehouse_sync:
        _wait_in_history(sql, cfg, row_id, "delete")
    _run_writeback_task(ws)
    gone = sql(f"SELECT count(*) AS n FROM {cfg.fq}.silver_seller_actions WHERE id = :id",
               {"id": (row_id, "BIGINT")})
    assert int(gone[0]["n"]) == 0


def test_nba_feedback_contract(sql, cfg):
    # Task 7 consumes gold_nba_feedback(action_type STRING, acceptance_rate DOUBLE in 0..1)
    cols = {r["col_name"]: r["data_type"] for r in sql(f"DESCRIBE TABLE {cfg.fq}.gold_nba_feedback")
            if r["col_name"] and not r["col_name"].startswith("#")}
    assert cols.get("action_type") == "string" and cols.get("acceptance_rate") == "double", cols
    assert {"shown", "accepted", "done", "dismissed"} <= cols.keys(), cols
    r = sql(f"""SELECT count_if(acceptance_rate < 0 OR acceptance_rate > 1) AS bad,
                       count(*) - count(DISTINCT action_type) AS dup
                FROM {cfg.fq}.gold_nba_feedback""")[0]
    assert int(r["bad"]) == 0 and int(r["dup"]) == 0, r
