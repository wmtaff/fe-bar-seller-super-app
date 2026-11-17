"""CLI: python -m fleetwise_gen.cli --mode {init,increment} --out <dir> --seed 42 [--batch N]"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .generator import generate


def next_batch(out_dir: Path) -> int:
    """Next increment number after the highest existing manifest (min 1)."""
    d = Path(out_dir) / "_manifest"
    done = [int(p.stem.split("=")[1]) for p in d.glob("batch=*.json")] if d.exists() else []
    return max([0, *done]) + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fleetwise_gen", description=__doc__)
    ap.add_argument("--mode", choices=["init", "increment"], required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch", default=None,
                    help="increment number (>=1), or 'auto' for the next one after existing manifests")
    a = ap.parse_args(argv)
    if a.mode == "init":
        batch = 0
    elif a.batch in (None, "auto"):
        batch = next_batch(a.out)
    else:
        batch = int(a.batch)
    t0 = time.time()
    counts = generate(a.mode, a.out, a.seed, batch)
    print(json.dumps({"mode": a.mode, "batch": batch, "seconds": round(time.time() - t0, 1),
                      "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
