"""Task 11: end-to-end checks across every layer (live workspace).

- lineage: raw volume -> bronze -> silver -> gold -> app gold -> Lakebase synced table
- increment: the latest increment batch's opportunity stages are what Postgres (and so the app) serves
- rerun: re-running a batch changes no row counts (compared across collect_evidence runs) and no
  table gets duplicate keys

No hard-coded counts or ids: everything is read from the volume, UC and Postgres.
"""

import json
from collections import defaultdict, deque

import pytest
import requests

from _lakebase_helpers import connect
from lakebase import setup_lakebase as lb

pytestmark = pytest.mark.integration

DATASET_VERSION = "v4"
APP_NAME = "fleetwise-seller-hub"
# (table, key) pairs that must be unique after any number of re-runs
KEYS = [
    ("silver_opportunities", "opportunity_id"),
    ("gold_opportunity_pipeline", "opportunity_id"),
    ("gold_deal_scores", "opportunity_id"),
    ("gold_opportunity_app", "opportunity_id"),
    ("gold_call_insights", "meeting_id"),
    ("gold_next_best_actions", "action_id"),
    ("gold_lead_scores", "lead_id"),
]


@pytest.fixture(scope="module")
def fq(names):
    return lambda t: f"`{names['catalog']}`.`{names['schema']}`.`{t}`"


@pytest.fixture(scope="module")
def pg(ws, names):
    conn = connect(ws, lb.Config(catalog=names["catalog"], schema=names["schema"]).branch_path)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def base(names):
    return f"/Volumes/{names['catalog']}/{names['schema']}/{names['volume']}"


@pytest.fixture(scope="module")
def edges(sql, names):
    rows = sql(
        """SELECT DISTINCT source_table_full_name AS s, target_table_full_name AS t
           FROM system.access.table_lineage
           WHERE event_date >= date_sub(current_date(), 7)
             AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
             AND source_table_catalog = :cat""",
        {"cat": names["catalog"]},
    )
    g = defaultdict(set)
    for r in rows:
        g[r["s"]].add(r["t"])
    return g


def _path(g, src, dst):
    prev, q = {src: None}, deque([src])
    while q:
        n = q.popleft()
        if n == dst:
            out = []
            while n:
                out.append(n)
                n = prev[n]
            return out[::-1]
        for m in g.get(n, ()):
            if m not in prev:
                prev[m] = n
                q.append(m)
    return None


def _pg_one(pg, q, params=()):
    with pg.cursor() as c:
        c.execute(q, params)
        return c.fetchone()


def test_lineage_connects_volume_to_synced_table(edges, sql, names, fq, base):
    c, s = names["catalog"], names["schema"]
    t = lambda n: f"{c}.{s}.{n}"  # noqa: E731
    synced = f"{c}.serving.opportunity_pipeline"
    path = _path(edges, t("bronze_opportunity"), synced)
    assert path, "no lineage path bronze_opportunity -> serving.opportunity_pipeline"
    for hop in ("silver_opportunities", "gold_opportunity_pipeline", "gold_opportunity_app"):
        assert t(hop) in path, (hop, path)
    # deal scores feed the app table (scoring itself runs on the driver against OpenJev, so UC
    # lineage does not record gold_opportunity_pipeline -> gold_deal_scores; check it in data)
    assert t("gold_opportunity_app") in edges[t("gold_deal_scores")]
    orphan = sql(f"""SELECT count(*) AS n FROM {fq('gold_deal_scores')} d
                     LEFT ANTI JOIN {fq('gold_opportunity_pipeline')} p USING (opportunity_id)""")
    assert int(orphan[0]["n"]) == 0
    # the volume -> bronze hop: Auto Loader file reads are not table lineage; every bronze row
    # carries its source file, which must be under the raw volume
    bad = sql(f"""SELECT count(*) AS n FROM {fq('bronze_opportunity')}
                  WHERE NOT startswith(_source_file, :p) AND NOT startswith(_source_file, :p2)""",
              {"p": f"{base}/{DATASET_VERSION}/", "p2": f"dbfs:{base}/{DATASET_VERSION}/"})
    assert int(bad[0]["n"]) == 0


def test_synced_table_count_parity(sql, fq, pg):
    uc = int(sql(f"SELECT count(*) AS n FROM {fq('gold_opportunity_app')}")[0]["n"])
    assert _pg_one(pg, "SELECT count(*) FROM serving.opportunity_pipeline")[0] == uc


def _latest_increment(ws, base):
    d = f"{base}/{DATASET_VERSION}/_manifest"
    batches = sorted(int(f.path.rsplit("=", 1)[1].split(".")[0])
                     for f in ws.files.list_directory_contents(d) if f.path.endswith(".json"))
    if not batches or batches[-1] < 1:
        pytest.skip("no increment batch landed yet")
    b = batches[-1]
    manifest = json.loads(ws.files.download(f"{d}/batch={b:04d}.json").contents.read())
    opps = []
    for f in ws.files.list_directory_contents(f"{base}/{DATASET_VERSION}/salesforce/Opportunity/batch={b:04d}"):
        opps += [json.loads(line) for line in ws.files.download(f.path).contents.read().decode().splitlines() if line]
    return b, manifest, opps


def test_increment_changed_app_data(ws, base, pg):
    b, manifest, opps = _latest_increment(ws, base)
    assert opps, f"batch {b} has no Opportunity rows"
    with pg.cursor() as cur:
        cur.execute("SELECT opportunity_id, stage FROM serving.opportunity_pipeline WHERE opportunity_id = ANY(%s)",
                    ([o["Id"] for o in opps],))
        served = dict(cur.fetchall())
    matches = [o["Id"] for o in opps if served.get(o["Id"]) == o["StageName"]]
    assert len(matches) == len(opps), (
        f"batch {b}: {len(opps) - len(matches)} of {len(opps)} opps not at their batch stage in Postgres")

    # and the deployed app reports data at least as fresh as the batch
    a = ws.apps.get(APP_NAME)
    if not (a.app_status and a.app_status.state and a.app_status.state.value == "RUNNING"):
        pytest.skip("app not RUNNING")
    r = requests.get(a.url.rstrip("/") + "/api/home", timeout=120,
                     headers={"Authorization": f"Bearer {ws.config.oauth_token().access_token}"})
    r.raise_for_status()
    fresh = r.json()["freshness_ts"]
    assert fresh[:19] >= manifest["data_timestamp"][:19], (fresh, manifest["data_timestamp"])


def test_no_duplicate_keys(sql, fq):
    for table, key in KEYS:
        r = sql(f"SELECT count(*) AS n, count(DISTINCT {key}) AS d FROM {fq(table)}")[0]
        assert r["n"] == r["d"], (table, r)


def _volatile(key: str) -> bool:
    """Tables whose counts legitimately move without new data: pipeline internals, event logs,
    staging tables, and the Lakehouse Sync history of live app clicks."""
    name = key.split(".", 1)[1]
    return name.startswith(("__", "event_log_", "tmp_", "lb_"))


def test_rerun_no_duplicates(ws, base):
    """The two most recent collect_evidence runs with the same job params have identical counts."""
    d = f"{base}/evidence"
    runs = []
    try:
        for f in ws.files.list_directory_contents(d):
            ev = json.loads(ws.files.download(f"{f.path}/evidence.json").contents.read())
            runs.append(ev)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no evidence runs yet: {e}")
    runs.sort(key=lambda e: e["collected_at"])
    by_params = defaultdict(list)
    for ev in runs:
        if ev["job_params"].startswith("mode=increment"):
            by_params[ev["job_params"]].append(ev)
    pairs = [v[-2:] for v in by_params.values() if len(v) >= 2]
    if not pairs:
        pytest.skip("no increment batch has been run twice yet")
    first, second = max(pairs, key=lambda p: p[1]["collected_at"])
    counts = lambda ev: {k: v["rows"] for k, v in ev["row_counts"].items()  # noqa: E731
                         if v["rows"] is not None and not _volatile(k)}
    a, b = counts(first), counts(second)
    diff = {k: (a.get(k), b.get(k)) for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    assert not diff, f"row counts changed on rerun ({first['run_id']} -> {second['run_id']}): {diff}"
