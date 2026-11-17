"""File writers for the raw layout (JSON lines, CSV, one-JSON-per-file)."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


def part_dir(out: Path, dataset: str, batch: int) -> Path:
    d = out / dataset / f"batch={batch:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_jsonl(out: Path, dataset: str, batch: int, rows: list[dict]) -> None:
    path = part_dir(out, dataset, batch) / "part-0.json"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(_dumps(r) + "\n")


def write_csv(out: Path, dataset: str, batch: int, header: list[str], rows: list[list]) -> None:
    path = part_dir(out, dataset, batch) / "part-0.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_documents(out: Path, dataset: str, batch: int, docs: list[dict], key: str) -> None:
    d = part_dir(out, dataset, batch)
    for doc in docs:
        (d / f"{doc[key]}.json").write_text(_dumps(doc) + "\n", encoding="utf-8")


def write_manifest(out: Path, batch: int, payload: dict) -> Path:
    d = out / "_manifest"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"batch={batch:04d}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
