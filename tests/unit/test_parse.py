"""Task 5: normalizer for ai_query call-insight output (mirrors src/ai/call_insights.sql).

The Task 7 extraction spot-check reuses `normalize_insights`, so its rules must match the
SQL: strip prose/code fences, parse JSON, keep only product-list interests, coerce
sentiment/stance to the schema enums, keep `due` only when it is an ISO date.
"""

import json

from ai.parse import PRODUCTS, normalize_insights

VALID = {
    "summary": "Ryan liked the demo but a reorg slows things down. Timothy offered a small pilot. "
    "Install planning is the next step.",
    "next_steps": [
        {"action": "Schedule the install planning call", "owner": "Timothy Ibarra (Fleetwise AE)",
         "due": "2026-11-23"},
        {"action": "Review the ROI model with leadership", "owner": "Ryan Webster (customer)",
         "due": None},
    ],
    "open_items": ["Hardware replacement fees"],
    "interests": ["Vehicle Telematics", "Fuel & Maintenance"],
    "competitors": ["RoadLynx"],
    "objections": ["Timing: mid-reorg"],
    "sentiment": "neutral",
    "stakeholders": [{"name": "Ryan Webster", "role": "Operations lead", "stance": "neutral"}],
}


def test_parse_valid():
    out, err = normalize_insights(json.dumps(VALID))
    assert err is None
    assert out == VALID


def test_parse_strips_code_fences_and_prose():
    raw = "Here are the insights:\n```json\n" + json.dumps(VALID) + "\n```"
    out, err = normalize_insights(raw)
    assert err is None and out["summary"] == VALID["summary"]


def test_parse_insights_handles_invalid_json():
    assert normalize_insights('{"summary": "cut off mid-') == (None, "invalid_json")
    assert normalize_insights("no json here at all") == (None, "invalid_json")


def test_parse_null_or_empty_response():
    assert normalize_insights(None) == (None, "empty_response")
    assert normalize_insights("   ") == (None, "empty_response")


def test_parse_requires_summary_object():
    assert normalize_insights("[1, 2]") == (None, "invalid_json")
    assert normalize_insights(json.dumps({**VALID, "summary": ""})) == (None, "missing_summary")


def test_interests_filtered_to_products():
    raw = json.dumps({**VALID, "interests": ["AI Dash Cams", "Bananas", "AI Dash Cams", "Compliance/ELD"]})
    out, _ = normalize_insights(raw)
    assert out["interests"] == ["AI Dash Cams", "Compliance/ELD"]
    assert set(out["interests"]) <= set(PRODUCTS)


def test_sentiment_and_stance_coerced_to_enums():
    raw = json.dumps({**VALID, "sentiment": "Positive",
                      "stakeholders": [{"name": "A", "role": "CFO", "stance": "Champion"},
                                       {"name": "B", "role": "IT", "stance": "lukewarm"}]})
    out, _ = normalize_insights(raw)
    assert out["sentiment"] == "positive"
    assert [s["stance"] for s in out["stakeholders"]] == ["champion", None]
    bad, _ = normalize_insights(json.dumps({**VALID, "sentiment": "ecstatic"}))
    assert bad["sentiment"] is None


def test_due_kept_only_when_iso_date():
    steps = [{"action": "a", "owner": "o", "due": "next Monday"},
             {"action": "b", "owner": "o", "due": "2026-12-01"},
             {"action": "c", "owner": "o"}]
    out, _ = normalize_insights(json.dumps({**VALID, "next_steps": steps}))
    assert [s["due"] for s in out["next_steps"]] == [None, "2026-12-01", None]


def test_missing_lists_default_empty():
    out, err = normalize_insights(json.dumps({"summary": "Short call.", "sentiment": "neutral"}))
    assert err is None
    for key in ["next_steps", "open_items", "interests", "competitors", "objections", "stakeholders"]:
        assert out[key] == []


def test_products_match_schema_enum():
    assert PRODUCTS == ("Vehicle Telematics", "AI Dash Cams", "Driver Safety",
                        "Fuel & Maintenance", "Compliance/ELD", "Equipment Monitoring")
