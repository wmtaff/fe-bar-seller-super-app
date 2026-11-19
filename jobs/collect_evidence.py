"""Job entrypoint (task `collect_evidence`, last task): write a run's evidence bundle.

Params: --catalog --schema --serving-schema --volume --run-id {{job.run_id}} [--job-id ...]

Writes /Volumes/<catalog>/<schema>/<volume>/evidence/run_<run_id>/evidence.json with:
  - row_counts: COUNT(*) for every table/view in <schema> and <serving_schema> (pipeline-internal
    `__*` / `event_log_*` tables skipped; errors recorded and the run continues)
  - lineage: distinct source -> target edges from system.access.table_lineage touching the schemas
  - tasks: per-task state and duration for this run (earlier tasks are finished by now)
  - manifests: the generator's _manifest/batch=*.json files (landed_at = freshness t0)

A copy is committed under evidence/runs/ (downloaded with `databricks fs cp`).
Auth: default auth of the job's run-as identity; nothing is hard-coded.
"""

import argparse
import io
import json
from datetime import datetime, timezone


def _row_counts(spark, catalog: str, schemas: list[str]) -> dict:
    tables = spark.sql(f"""
        SELECT table_schema, table_name, table_type FROM `{catalog}`.information_schema.tables
        WHERE table_schema IN ({", ".join(f"'{s}'" for s in schemas)})
        ORDER BY table_schema, table_name""").collect()
    # Skip pipeline-internal tables (materializations, synced-table staging, event logs). Filtered
    # in Python: the SQL startswith() filter matched nothing on serverless job compute.
    tables = [t for t in tables if not t.table_name.startswith(("__", "event_log_"))]
    if not tables:
        raise RuntimeError(f"no tables found in {catalog}.{schemas}: refusing to write empty evidence")
    out = {}
    for t in tables:
        fq = f"`{catalog}`.`{t.table_schema}`.`{t.table_name}`"
        key = f"{t.table_schema}.{t.table_name}"
        try:
            out[key] = {"type": t.table_type, "rows": spark.sql(f"SELECT count(*) AS n FROM {fq}").first().n}
        except Exception as e:  # noqa: BLE001 - record and continue (e.g. synced tables)
            out[key] = {"type": t.table_type, "rows": None, "error": str(e).splitlines()[0][:200]}
    return out


def _lineage(spark, catalog: str, schemas: list[str]) -> list[dict]:
    in_list = ", ".join(f"'{s}'" for s in schemas)
    rows = spark.sql(f"""
        SELECT DISTINCT source_table_full_name AS source, source_type,
                        target_table_full_name AS target, target_type
        FROM system.access.table_lineage
        WHERE event_date >= date_sub(current_date(), 7)
          AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
          AND source_table_full_name <> target_table_full_name
          AND ((source_table_catalog = '{catalog}' AND source_table_schema IN ({in_list}))
            OR (target_table_catalog = '{catalog}' AND target_table_schema IN ({in_list})))
        ORDER BY source, target""").collect()
    return [r.asDict() for r in rows]


def _tasks(w, run_id: int) -> list[dict]:
    run = w.jobs.get_run(run_id)
    out = []
    for t in sorted(run.tasks or [], key=lambda t: t.start_time or 0):
        st = t.state
        dur = None
        if t.start_time and t.end_time:
            dur = round((t.end_time - t.start_time) / 1000, 1)
        out.append({
            "task_key": t.task_key,
            "life_cycle_state": st.life_cycle_state.value if st and st.life_cycle_state else None,
            "result_state": st.result_state.value if st and st.result_state else None,
            "start": datetime.fromtimestamp(t.start_time / 1000, timezone.utc).isoformat() if t.start_time else None,
            "duration_s": dur,
        })
    return out


def _manifests(w, base: str, dataset_version: str) -> list[dict]:
    d = f"{base}/{dataset_version}/_manifest"
    out = []
    for f in w.files.list_directory_contents(d):
        if f.path.endswith(".json"):
            m = json.loads(w.files.download(f.path).contents.read())
            out.append({k: m.get(k) for k in ("batch", "mode", "landed_at", "data_timestamp")})
    return sorted(out, key=lambda m: m["batch"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--serving-schema", required=True)
    ap.add_argument("--volume", required=True)
    ap.add_argument("--dataset-version", required=True)
    ap.add_argument("--run-id", type=int, required=True)
    ap.add_argument("--job-params", default="", help="mode/batch string, for the record only")
    a = ap.parse_args()

    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    w = WorkspaceClient()
    spark = SparkSession.builder.getOrCreate()
    schemas = [a.schema, a.serving_schema]
    base = f"/Volumes/{a.catalog}/{a.schema}/{a.volume}"

    evidence = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": a.run_id,
        "job_params": a.job_params,
        "tasks": _tasks(w, a.run_id),
        "manifests": _manifests(w, base, a.dataset_version),
        "row_counts": _row_counts(spark, a.catalog, schemas),
        "lineage": _lineage(spark, a.catalog, schemas),
    }
    path = f"{base}/evidence/run_{a.run_id}/evidence.json"
    w.files.upload(path, io.BytesIO(json.dumps(evidence, indent=2).encode()), overwrite=True)
    print(f"wrote {path}: {len(evidence['row_counts'])} tables, {len(evidence['lineage'])} lineage edges, "
          f"{len(evidence['tasks'])} tasks")


if __name__ == "__main__":
    main()
