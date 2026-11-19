"""Run one increment batch of seller_superapp_daily and measure end-to-end freshness.

t0 = the batch manifest's `landed_at` (written last by generate_data, so all raw files are in place).
t1 = first poll at which the deployed app's GET /api/home returns freshness_ts >= the batch's
     data_timestamp AND the sampled changed opportunity shows the new stage in Postgres.
Polls every 5 s; also records the job run's task timeline. Writes a JSON result to --out.

Usage: .venv/bin/python scripts/measure_freshness.py --batch 2 --opp 0060g000000038lAAA \
         --expect-stage Proposal --out evidence/runs/freshness_batch2.json
Auth: the CLI profile (user OAuth); nothing is hard-coded except the profile/app names.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests" / "integration")]
from _lakebase_helpers import connect  # noqa: E402
from lakebase import setup_lakebase as lb  # noqa: E402

PROFILE = "fevm-serverless-stable-s1omq8"
CATALOG, SCHEMA, VOLUME = "serverless_stable_s1omq8_catalog", "seller_superapp", "raw"
JOB, APP = "seller_superapp_daily", "fleetwise-seller-hub"


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc) if ms else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--expect-stage", required=True)
    ap.add_argument("--dataset-version", default="v4")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    w = WorkspaceClient(profile=PROFILE)
    job_id = next(j.job_id for j in w.jobs.list(name=JOB))
    app_url = w.apps.get(APP).url.rstrip("/")
    pg = connect(w, lb.Config(catalog=CATALOG, schema=SCHEMA).branch_path)
    sess = requests.Session()

    def home():
        sess.headers["Authorization"] = f"Bearer {w.config.oauth_token().access_token}"
        r = sess.get(app_url + "/api/home", timeout=120)
        r.raise_for_status()
        return r.json()["freshness_ts"]

    def pg_stage():
        with pg.cursor() as c:
            c.execute("SELECT stage FROM serving.opportunity_pipeline WHERE opportunity_id = %s", (a.opp,))
            row = c.fetchone()
            return row[0] if row else None

    before = {"freshness_ts": home(), "stage": pg_stage()}
    print("before", before, flush=True)
    started = datetime.now(timezone.utc)
    run_id = w.jobs.run_now(job_id=job_id, job_parameters={
        "mode": "increment", "batch": str(a.batch), "dataset_version": a.dataset_version,
        "run_eval": "false"}).run_id
    print("run_id", run_id, flush=True)

    mpath = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/{a.dataset_version}/_manifest/batch={a.batch:04d}.json"
    manifest, t1, seen = None, None, {}
    while True:
        run = w.jobs.get_run(run_id)
        if manifest is None:
            try:
                manifest = json.loads(w.files.download(mpath).contents.read())
                print("manifest", manifest["landed_at"], manifest["data_timestamp"], flush=True)
            except Exception:  # noqa: BLE001 - not landed yet
                pass
        if manifest and t1 is None:
            f, s = home(), pg_stage()
            if f != seen.get("f"):
                print(datetime.now(timezone.utc).isoformat(timespec="seconds"), "freshness_ts", f, flush=True)
            if s != seen.get("s"):
                print(datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage", s, flush=True)
            seen = {"f": f, "s": s}
            data_ts = datetime.fromisoformat(manifest["data_timestamp"].replace("Z", "+00:00"))
            if f and datetime.fromisoformat(f.replace("Z", "+00:00")) >= data_ts and s == a.expect_stage:
                t1 = datetime.now(timezone.utc)
                print("t1", t1.isoformat(), flush=True)
        done = run.state.life_cycle_state.value in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED")
        if done and (t1 is not None or run.state.result_state.value != "SUCCESS"):
            break
        if done and t1 is None and (datetime.now(timezone.utc) - started).total_seconds() > 3600:
            break
        time.sleep(5)

    run = w.jobs.get_run(run_id)
    tasks = sorted(({"task_key": t.task_key, "result_state": t.state.result_state.value if t.state.result_state else None,
                     "start": ts(t.start_time).isoformat() if t.start_time else None,
                     "end": ts(t.end_time).isoformat() if t.end_time else None,
                     "duration_s": round((t.end_time - t.start_time) / 1000, 1) if t.start_time and t.end_time else None}
                    for t in run.tasks), key=lambda t: t["start"] or "")
    t0 = datetime.fromisoformat(manifest["landed_at"].replace("Z", "+00:00")) if manifest else None
    out = {
        "run_id": run_id, "job_id": job_id, "result_state": run.state.result_state.value,
        "run_page_url": run.run_page_url, "run_start": ts(run.start_time).isoformat(),
        "run_end": ts(run.end_time).isoformat() if run.end_time else None,
        "before": before, "manifest": manifest and {k: manifest[k] for k in ("batch", "landed_at", "data_timestamp")},
        "probe_opp": a.opp, "expect_stage": a.expect_stage,
        "t0_landed_at": t0.isoformat() if t0 else None, "t1_app_visible": t1.isoformat() if t1 else None,
        "freshness_s": round((t1 - t0).total_seconds(), 1) if t0 and t1 else None,
        "after": {"freshness_ts": home(), "stage": pg_stage()}, "tasks": tasks,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("run_id", "result_state", "freshness_s")}))


if __name__ == "__main__":
    main()
