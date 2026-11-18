"""Job entrypoint (task `generate_data`): write one generator batch to the UC volume.

Params: --catalog --schema --volume --mode {init,increment} --batch {N|auto} [--seed 42]
        [--dataset-version v3] [--src-dir <bundle files>/src]

Output root: /Volumes/<c>/<s>/<v>/<dataset_version>/ (rulings R10/R12: v3; v1 at the volume root and v2 are
left untouched).
Idempotent: if <root>/_manifest/batch=<NNNN>.json exists the batch
is skipped. Files are generated on local disk, then copied into the volume with
the manifest copied last (so a half-copied batch is redone on re-run).
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _add_src(src_dir: str | None) -> None:
    candidates = [src_dir] if src_dir else []
    try:
        candidates.append(str(Path(__file__).resolve().parent.parent / "src"))
    except NameError:  # __file__ is not always defined for spark_python_task
        pass
    candidates.append(str(Path(os.getcwd()).parent / "src"))
    for c in candidates:
        if c and Path(c, "fleetwise_gen").is_dir():
            sys.path.insert(0, c)
            return
    raise RuntimeError(f"fleetwise_gen not found in {candidates}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--volume", required=True)
    ap.add_argument("--mode", choices=["init", "increment"], default="init")
    ap.add_argument("--batch", default="0")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dataset-version", default="v3")
    ap.add_argument("--src-dir", default=None)
    a = ap.parse_args()
    _add_src(a.src_dir)
    from fleetwise_gen.cli import next_batch
    from fleetwise_gen.generator import generate, manifest_path

    out = Path(f"/Volumes/{a.catalog}/{a.schema}/{a.volume}")
    if a.dataset_version:
        out = out / a.dataset_version
    if a.mode == "init":
        batch = 0
    elif a.batch in ("auto", ""):
        batch = next_batch(out)
    else:
        batch = int(a.batch)
    if a.mode == "increment" and batch < 1:
        raise ValueError("increment needs batch >= 1 (or 'auto')")

    target_manifest = manifest_path(out, batch)
    if target_manifest.exists():
        print(f"batch {batch:04d} already present at {out}; skipping")
        print(target_manifest.read_text())
        return

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        counts = generate(a.mode, tmp, a.seed, batch)
        t_gen = time.time() - t0
        files = [p for p in Path(tmp).rglob("*") if p.is_file()]
        manifest = manifest_path(Path(tmp), batch)
        data_files = [p for p in files if p != manifest]

        def copy(p: Path) -> None:
            dst = out / p.relative_to(tmp)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)

        for d in sorted({(out / p.relative_to(tmp)).parent for p in data_files}):
            d.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(copy, data_files))
        copy(manifest)  # commit marker last
    print(json.dumps({"mode": a.mode, "batch": batch, "out": str(out), "files": len(files),
                      "generate_seconds": round(t_gen, 1),
                      "total_seconds": round(time.time() - t0, 1), "counts": counts}, indent=2))


if __name__ == "__main__":
    # No sys.exit(): serverless Python tasks treat SystemExit (even 0) as a failure.
    main()
