"""Job entrypoint (task `ai_scoring`): OpenJev deal and lead scoring.

Params: --catalog --schema [--max-workers 16] [--src-dir <bundle files>/src]

Auth: WorkspaceClient() default auth of the job's run-as identity; the host comes from
w.config.host and the Bearer token from w.config.authenticate() (fetched per phase so it
is fresh). No host or token is hard-coded. See src/ai/scoring_job.py for the incremental rules.
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
        if c and Path(c, "ai", "openjev.py").is_file():
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
    ap.add_argument("--max-workers", type=int, default=16)
    ap.add_argument("--src-dir", default=None)
    a = ap.parse_args()
    _add_src(a.src_dir)

    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    from ai.scoring_job import run

    w = WorkspaceClient()
    spark = SparkSession.builder.getOrCreate()
    run(spark, a.catalog, a.schema, host=w.config.host, token_fn=lambda: _bearer(w), max_workers=a.max_workers)


if __name__ == "__main__":
    main()
