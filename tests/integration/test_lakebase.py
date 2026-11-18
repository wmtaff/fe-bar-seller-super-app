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
    assert st.status.project == cfg.project_path


@pytest.mark.parametrize("spec", lb.SYNCED_TABLES, ids=lambda s: s.pg_table)
def test_pg_row_counts_match_uc(sql, pg, cfg, spec):
    uc = int(sql(f"SELECT count(*) AS n FROM {cfg.source_full_name(spec)}")[0]["n"])
    pgn = _pg_scalar(pg, f'SELECT count(*) FROM "{cfg.pg_schema}"."{spec.pg_table}"')
    assert uc > 0 and pgn == uc, (spec.pg_table, uc, pgn)


def _pcts(xs: list[float]) -> dict:
    q = statistics.quantiles(xs, n=100)
    return {"p50": round(q[49], 2), "p95": round(q[94], 2), "p99": round(q[98], 2), "max": round(max(xs), 2)}


def test_pg_point_lookup_fast(pg, cfg):
    """100 primary-key lookups of serving.opportunity_pipeline.

    Three numbers are recorded: the client round trip (what the test runner sees), the network
    baseline (`SELECT 1` interleaved on the same connection) and the server execution time
    (EXPLAIN ANALYZE). The budget p95 < 50 ms applies to the latency Lakebase adds on top of the
    network (lookup p95 - baseline p50): a laptop far from the region pays tens of ms of RTT that
    the in-region app does not. The raw client p95 is recorded as-is.
    """
    with pg.cursor() as cur:
        cur.execute(f'SELECT opportunity_id FROM "{cfg.pg_schema}".opportunity_pipeline '
                    f"ORDER BY md5(opportunity_id) LIMIT %s", (LOOKUPS,))
        ids = [r[0] for r in cur.fetchall()]
        assert len(ids) == LOOKUPS
        q = (f'SELECT opportunity_id, stage, acv, p_close_quarter, next_action '
             f'FROM "{cfg.pg_schema}".opportunity_pipeline WHERE opportunity_id = %s')
        cur.execute(q, (ids[0],), prepare=True)  # warm the connection and the plan
        cur.fetchall()
        lookup, base = [], []
        for oid in ids:
            t0 = time.perf_counter()
            cur.execute("SELECT 1", prepare=True)
            cur.fetchone()
            t1 = time.perf_counter()
            cur.execute(q, (oid,), prepare=True)
            row = cur.fetchone()
            t2 = time.perf_counter()
            base.append((t1 - t0) * 1000)
            lookup.append((t2 - t1) * 1000)
            assert row and row[0] == oid
        server = []
        for oid in ids[:20]:
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {q}", (oid,))
            plan = cur.fetchone()[0][0]
            server.append(float(plan["Execution Time"]))
            assert "Index" in json.dumps(plan["Plan"]), plan  # served by the primary-key index
    client, net = _pcts(lookup), _pcts(base)
    added_p95 = round(client["p95"] - net["p50"], 2)
    _record(lookup_latency_ms={
        "n": LOOKUPS, "client": client, "network_baseline_select1": net,
        "server_execution": _pcts(server) | {"n": len(server)},
        "added_over_network_p95": added_p95,
        "runner": "developer laptop -> Lakebase endpoint over the internet"})
    assert added_p95 < P95_BUDGET_MS, (client, net)


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


def _history_exists(sql, cfg) -> bool:
    return int(sql(f"""SELECT count(*) AS n FROM `{cfg.catalog}`.information_schema.tables
                       WHERE table_schema = :s AND table_name = 'lb_seller_actions_history'""",
                   {"s": cfg.schema})[0]["n"]) > 0


def test_writeback_merge_on_simulated_history(ws, sql, cfg):
    """Exercises writeback.sql's Lakehouse Sync path before the app exists: a temporary test double
    of lb_seller_actions_history (same CDC columns as the real one, verified on a probe schema)
    with insert / update pre+post image / insert+delete, then deletes that clean everything up.
    Skipped once the real history table exists (Task 10); test_writeback_roundtrip covers it then."""
    if _history_exists(sql, cfg):
        pytest.skip("the real lb_seller_actions_history exists; covered by test_writeback_roundtrip")
    a, b = sql(f"""SELECT action_id, opportunity_id, action_type FROM (
                     SELECT *, row_number() OVER (PARTITION BY action_type ORDER BY action_id) AS rn
                     FROM {cfg.fq}.gold_next_best_actions WHERE status = 'open')
                   WHERE rn = 1 ORDER BY action_type LIMIT 2""")
    ids = (a["action_id"], b["action_id"])

    def rows(*changes):
        return ", ".join(
            f"('{ct}', {lsn}, 0, current_timestamp(), {lsn}, {i}, '{r['action_id']}', "
            f"'{r['opportunity_id']}', '{TEST_PERSONA}', '{dec}', 'simulation', TIMESTAMP'2026-01-01 00:00:{i % 60:02d}')"
            for ct, lsn, i, r, dec in changes)

    def state():
        silver = sql(f"SELECT id, decision, action_type FROM {cfg.fq}.silver_seller_actions "
                     f"WHERE persona_user_id = :p ORDER BY id", {"p": TEST_PERSONA})
        fb = {r["action_type"]: r for r in sql(f"SELECT * FROM {cfg.fq}.gold_nba_feedback "
                                               f"WHERE accepted + done + dismissed > 0")}
        st = {r["action_id"]: r["status"] for r in sql(
            f"SELECT action_id, status FROM {cfg.fq}.gold_next_best_actions WHERE action_id IN (:a, :b)",
            {"a": ids[0], "b": ids[1]})}
        return silver, fb, st

    hist = f"{cfg.fq}.lb_seller_actions_history"
    sql(f"""CREATE TABLE {hist} (_pg_change_type STRING, _pg_lsn BIGINT, _pg_xid INT,
              _timestamp TIMESTAMP_NTZ, _sort_by BIGINT, id BIGINT, action_id STRING, opportunity_id STRING,
              persona_user_id STRING, decision STRING, reason STRING, created_at TIMESTAMP)
            COMMENT 'TEMPORARY test double of the Lakehouse Sync history (test_lakebase); dropped by the test.'""")
    try:
        sql(f"INSERT INTO {hist} VALUES " + rows(
            ("insert", 100, 1, a, "accepted"), ("insert", 110, 2, b, "dismissed"),
            ("update_preimage", 120, 2, b, "dismissed"), ("update_postimage", 120, 2, b, "done"),
            ("insert", 130, 3, a, "dismissed"), ("delete", 140, 3, a, "dismissed")))
        _run_writeback_task(ws)
        silver, fb, st = state()
        assert [(r["id"], r["decision"]) for r in silver] == [("1", "accepted"), ("2", "done")], silver
        assert [r["action_type"] for r in silver] == [a["action_type"], b["action_type"]]
        assert float(fb[a["action_type"]]["acceptance_rate"]) == 1.0 and fb[a["action_type"]]["accepted"] == "1"
        assert float(fb[b["action_type"]]["acceptance_rate"]) == 1.0 and fb[b["action_type"]]["done"] == "1"
        assert st == {ids[0]: "accepted", ids[1]: "done"}, st
        _run_writeback_task(ws)  # idempotent re-run
        assert state()[0] == silver
        # deletes upstream remove the rows downstream and reset the NBA status
        sql(f"INSERT INTO {hist} VALUES " + rows(("delete", 150, 1, a, "accepted"), ("delete", 160, 2, b, "done")))
        _run_writeback_task(ws)
        silver, fb, st = state()
        assert silver == [] and a["action_type"] not in fb and b["action_type"] not in fb, (silver, fb)
        assert set(st.values()) == {"open"}, st
    finally:
        sql(f"DROP TABLE IF EXISTS {hist}")
    _run_writeback_task(ws)  # no source again: no-op path


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
