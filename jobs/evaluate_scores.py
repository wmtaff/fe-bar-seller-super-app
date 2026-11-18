"""Job entrypoint (task `evaluate_scores`, Task 7): offline evaluation of the deal score and
call-insight extraction. Runs only when the job parameter run_eval is "true" (condition task).

Params: --catalog --schema --volume [--dataset-version v4] [--sample-size 400] [--max-workers 8]
        [--src-dir <bundle files>/src]

Auth: WorkspaceClient() default auth of the job's run-as identity (host from w.config.host,
Bearer from w.config.authenticate()); the MLflow experiment is /Users/<run-as user>/fleetwise-score-eval.
Nothing is hard-coded. See src/ai/evaluate_scores.py for the method.
"""

import argparse
import os
import sys
from pathlib import Path


def _add_src(src_dir: str | None) -> None:
    candidates = [src_dir] if src_dir else []
    try:
        candidates.append(str(Path(__file__).resolve().parent.parent / "src"))
    except NameError:  # __file__ is not always defined for spark_python_task
        pass
    candidates.append(str(Path(os.getcwd()).parent / "src"))
    for c in candidates:
        if c and Path(c, "ai", "evaluate_scores.py").is_file():
            sys.path.insert(0, c)
            return
    raise RuntimeError(f"src/ai not found in {candidates}")


def _bearer(w) -> str:
    auth = w.config.authenticate().get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise RuntimeError("default auth did not return a Bearer token")
    return auth[len("Bearer "):]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--volume", required=True)
    ap.add_argument("--dataset-version", default="v4")
    ap.add_argument("--sample-size", type=int, default=400)
    ap.add_argument("--max-workers", type=int, default=8)
    ap.add_argument("--src-dir", default=None)
    a = ap.parse_args()
    _add_src(a.src_dir)

    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    from ai.evaluate_scores import run

    w = WorkspaceClient()
    spark = SparkSession.builder.getOrCreate()
    me = w.current_user.me().user_name
    run(spark, a.catalog, a.schema,
        truth_path=f"/Volumes/{a.catalog}/{a.schema}/{a.volume}/{a.dataset_version}/_eval/truth/",
        host=w.config.host, token_fn=lambda: _bearer(w), experiment=f"/Users/{me}/fleetwise-score-eval",
        sample_size=a.sample_size, max_workers=a.max_workers)


if __name__ == "__main__":
    main()
