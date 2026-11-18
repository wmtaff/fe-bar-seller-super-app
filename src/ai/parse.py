"""Normalize one ai_query call-insight response (Python mirror of src/ai/call_insights.sql).

`databricks-claude-sonnet-5-5` rejects `responseFormat` (structured output needs forced tool
use), so the JSON schema in insights_schema.json is sent inside the prompt and the model's
text is validated after the fact. The SQL job does that with try_parse_json/from_json; this
module applies the same rules in Python for unit tests and the Task 7 extraction spot-check.

normalize_insights(raw) -> (insights, None) on success, (None, error_code) otherwise, where
error_code is one of: empty_response, invalid_json, missing_summary.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("insights_schema.json")
LIST_KEYS = ("open_items", "competitors", "objections")


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _enum(*path: str) -> tuple[str, ...]:
    node = load_schema()
    for key in path:
        node = node[key]
    return tuple(node["enum"])


PRODUCTS = _enum("properties", "interests", "items")
SENTIMENTS = _enum("properties", "sentiment")
STANCES = _enum("properties", "stakeholders", "items", "properties", "stance")

_OBJECT = re.compile(r"\{.*\}", re.S)


def _str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strings(value) -> list[str]:
    """Trimmed, non-empty, de-duplicated (first occurrence wins) strings."""
    out: list[str] = []
    for item in value if isinstance(value, list) else []:
        text = _str(item)
        if text and text not in out:
            out.append(text)
    return out


def _iso_date(value) -> str | None:
    text = _str(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text).isoformat() if len(text) == 10 else None
    except ValueError:
        return None


def _lower_enum(value, allowed: tuple[str, ...]) -> str | None:
    text = _str(value)
    return text.lower() if text and text.lower() in allowed else None


def _objects(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def normalize_insights(raw: str | None) -> tuple[dict | None, str | None]:
    if raw is None or not raw.strip():
        return None, "empty_response"
    match = _OBJECT.search(raw)  # first "{" to last "}": drops prose and ``` fences
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return None, "invalid_json"
    summary = _str(data.get("summary"))
    if summary is None:
        return None, "missing_summary"

    out = {
        "summary": summary,
        "next_steps": [
            {"action": _str(s.get("action")), "owner": _str(s.get("owner")), "due": _iso_date(s.get("due"))}
            for s in _objects(data.get("next_steps"))
            if _str(s.get("action"))
        ],
        "interests": [i for i in _strings(data.get("interests")) if i in PRODUCTS],
        "sentiment": _lower_enum(data.get("sentiment"), SENTIMENTS),
        "stakeholders": [
            {"name": _str(s.get("name")), "role": _str(s.get("role")),
             "stance": _lower_enum(s.get("stance"), STANCES)}
            for s in _objects(data.get("stakeholders"))
            if _str(s.get("name"))
        ],
    }
    for key in LIST_KEYS:
        out[key] = _strings(data.get(key))
    order = ["summary", "next_steps", "open_items", "interests", "competitors", "objections",
             "sentiment", "stakeholders"]
    return {k: out[k] for k in order}, None
