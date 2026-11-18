"""Task 6: OpenJev client, state builders and batch scoring (requests.post is mocked).

The fixture tests/unit/fixtures/openjev_response.json is a real System One response for
DEAL_QUESTIONS, recorded from the workspace on 2026-11-18 (same endpoint and model as the
2026-11-17 spike in docs/DECK_POINTS.md).
"""

import json
from pathlib import Path
from unittest import mock

import pytest
import requests

from ai import openjev, scoring_job
from ai.questions import CLOSE_LEVELS, DEAL_QUESTIONS, LEAD_QUESTIONS

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "openjev_response.json").read_text())
HOST = "https://example.cloud.databricks.com"


def _resp(status: int, body: dict | None = None):
    r = mock.Mock(spec=requests.Response)
    r.status_code = status
    r.json.return_value = body if body is not None else {"error_code": "X", "message": "err"}
    r.text = json.dumps(r.json.return_value)
    return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(openjev, "_sleep", lambda s: None)


OPP = {
    "opportunity_id": "0060g000000037aAAA", "account_id": "0010g0000000001AAA", "owner_id": "0050g00000001AAA",
    "opportunity_name": "Acme Haulage - Driver Safety", "account_name": "Acme Haulage", "owner_name": "Jordan Rivera",
    "stage": "Proposal", "opportunity_type": "New Business", "segment": "Mid-Market", "acv": 48000.0,
    "close_date": "2026-12-09", "is_current_quarter": True, "days_to_close": 20, "stage_age_days": 12,
    "days_since_last_activity": 3, "activities_30d": 9, "competitor": "RoadLynx",
    "products": ["Driver Safety"], "fleet_size": 120, "next_step": "Send pricing",
}
ACCOUNT = {"account_type": "Prospect", "industry": "Construction", "usage_trend_pct_30d": -12.5,
           "open_tickets": 2, "p1_tickets_30d": 1, "products_owned": [], "whitespace_products": ["Driver Safety"],
           "account_name": "Acme Haulage", "owner_name": "Jordan Rivera"}


def _insight(day: int, summary: str, stakeholders=()):
    return {"meeting_id": f"m{day}", "started_at": f"2026-11-{day:02d}T15:00:00", "summary": summary,
            "sentiment": "neutral", "competitors": ["RoadLynx"], "objections": ["price"],
            "open_items": ["pilot"], "next_steps": [{"action": "Send proposal", "owner": "X", "due": None}],
            "stakeholders": [{"name": n, "role": "IT Director", "stance": "neutral"} for n in stakeholders],
            "extract_error": None}


def test_build_state_truncates_insights():
    insights = [_insight(d, f"Call on day {d}. " + "x" * 600) for d in range(1, 11)]
    insights.append({**_insight(12, None), "extract_error": "invalid_json"})  # failed extraction: skipped
    state = openjev.build_deal_state(OPP, ACCOUNT, insights)
    calls = state["recent_calls"]
    assert len(json.dumps(calls)) <= 2000
    assert calls[0]["date"] == "2026-11-10"  # newest successful call first
    assert [c["date"] for c in calls] == sorted((c["date"] for c in calls), reverse=True)
    assert len(calls) < 10
    # a single huge insight is cut to fit instead of dropped
    one = openjev.build_deal_state(OPP, ACCOUNT, [_insight(5, "y" * 5000)])["recent_calls"]
    assert len(one) == 1 and len(json.dumps(one)) <= 2000


def test_build_state_has_no_pii_or_ids():
    insight = _insight(3, "Sam Ortiz said the RoadLynx quote is cheaper; Ortiz wants a pilot.",
                       stakeholders=["Sam Ortiz"])
    state = openjev.build_deal_state(OPP, ACCOUNT, [insight])
    text = json.dumps(state)
    for banned in ("Sam", "Ortiz", "Jordan Rivera", "Acme Haulage", "0060g000000037aAAA",
                   "0010g0000000001AAA", "stakeholders", '"owner"'):
        assert banned not in text, banned
    assert state["opportunity"]["stage"] == "Proposal"
    assert state["account"]["usage_trend_pct_30d"] == -12.5


def test_build_lead_state_excludes_outcome_and_pii():
    lead = {"lead_id": "00Q0g0000000000EAA", "first_name": "Ana", "last_name": "Lopez", "name": "Ana Lopez",
            "email": "ana@x.com", "phone": "555-0100", "company": "Willow Bend Dairy", "title": "Fleet Manager",
            "lead_source": "Web", "status": "Working", "is_converted": False, "converted_date": None,
            "industry": "Food & Beverage", "state": "UT", "country": "United States", "fleet_size": 24,
            "products_of_interest": ["Vehicle Telematics"], "description": "Asked about ELD.",
            "owner_id": "0050g00000001AAA", "created_date": "2026-11-01T06:20:00"}
    state = openjev.build_lead_state(lead)
    text = json.dumps(state)
    for banned in ("Ana", "Lopez", "ana@x.com", "555-0100", "Working", "is_converted", "converted",
                   "status", "00Q0g", "0050g"):
        assert banned not in text, banned
    assert state["lead"]["fleet_size"] == 24 and state["lead"]["title"] == "Fleet Manager"


def test_call_parses_answers():
    with mock.patch("requests.post", return_value=_resp(200, FIXTURE)) as post:
        meta: dict = {}
        answers = openjev.call({"opportunity": {}}, DEAL_QUESTIONS, host=HOST, token="t", meta=meta)
    url = post.call_args.args[0]
    kwargs = post.call_args.kwargs
    assert url == HOST + "/ai-gateway/typesafe/v1/systemone"
    assert kwargs["headers"]["Authorization"] == "Bearer t"
    assert kwargs["json"]["model"] == "system.ai.openjev-qwen35-4b"
    assert kwargs["json"]["questions"] is DEAL_QUESTIONS
    assert kwargs["timeout"] == 30
    assert set(answers) == set(DEAL_QUESTIONS)
    assert 0 <= answers["close_this_quarter"]["score"] <= 4
    assert meta["input_tokens"] == FIXTURE["usage"]["input_tokens"] and meta["attempts"] == 1

    row = openjev.deal_scores(answers)
    assert row["p_close_quarter"] == pytest.approx(FIXTURE["answers"]["close_this_quarter"]["score"] / 4)
    assert row["close_label"] in CLOSE_LEVELS
    assert set(row["close_probs"]) == set(CLOSE_LEVELS)
    assert sum(row["close_probs"].values()) == pytest.approx(1.0, abs=1e-6)
    assert row["next_action"] == "send_proposal"
    assert set(row["next_action_probs"]) == set(DEAL_QUESTIONS["next_action"]["criteria"])
    assert 0 <= row["competitive_risk"] <= 1 and 0 <= row["churn_risk"] <= 1


def test_lead_scores_maps_fit_to_unit_interval():
    answers = {"conversion_fit": {"type": "score", "score": 3.0, "confidence": 0.7,
                                  "legend": {str(i): l for i, l in enumerate(LEAD_QUESTIONS["conversion_fit"]["criteria"])},
                                  "probabilities": {"0": 0.0, "1": 0.1, "2": 0.1, "3": 0.7, "4": 0.1}},
               "route_to": {"type": "choice", "choice": "SMB", "confidence": 0.9,
                            "probabilities": {"SMB": 0.95, "Mid-Market": 0.04, "Enterprise": 0.01}}}
    row = openjev.lead_scores(answers)
    assert row == {"fit_score": 0.75, "fit_label": "Good fit", "route_to": "SMB", "route_conf": 0.9}


def test_call_retries_on_429():
    seq = [_resp(429), _resp(429), _resp(200, FIXTURE)]
    with mock.patch("requests.post", side_effect=seq) as post:
        meta: dict = {}
        answers = openjev.call({}, DEAL_QUESTIONS, host=HOST, token="t", meta=meta)
    assert post.call_count == 3 and meta["attempts"] == 3
    assert "close_this_quarter" in answers


def test_call_retries_timeouts_and_5xx():
    seq = [requests.Timeout("slow"), _resp(503), _resp(200, FIXTURE)]
    with mock.patch("requests.post", side_effect=seq) as post:
        openjev.call({}, DEAL_QUESTIONS, host=HOST, token="t")
    assert post.call_count == 3


def test_call_raises_after_max_attempts():
    with mock.patch("requests.post", return_value=_resp(500)) as post:
        with pytest.raises(openjev.OpenJevError, match="500"):
            openjev.call({}, DEAL_QUESTIONS, host=HOST, token="t")
    assert post.call_count == 4


def test_call_does_not_retry_client_errors():
    with mock.patch("requests.post", return_value=_resp(400)) as post:
        with pytest.raises(openjev.OpenJevError, match="400"):
            openjev.call({}, DEAL_QUESTIONS, host=HOST, token="t")
    assert post.call_count == 1


def _batch(n_fail: int, n: int = 100):
    rows = [{"key": f"k{i}", "state": {"i": i}} for i in range(n)]

    def post(url, headers, json, timeout):  # noqa: A002 - mirrors requests.post kwargs
        return _resp(500) if json["state"]["i"] < n_fail else _resp(200, FIXTURE)

    return rows, post


def test_batch_fails_over_error_budget():
    rows, post = _batch(6)
    with mock.patch("requests.post", side_effect=post):
        with pytest.raises(scoring_job.ErrorBudgetExceeded) as exc:
            scoring_job.score_frame(rows, DEAL_QUESTIONS, max_workers=8, host=HOST, token="t")
    # the scored rows travel with the exception so the job can still MERGE them before failing
    assert len(exc.value.results) == 100
    assert sum(r["score_error"] is not None for r in exc.value.results) == 6


def test_batch_tolerates_under_budget():
    rows, post = _batch(4)
    with mock.patch("requests.post", side_effect=post):
        out = scoring_job.score_frame(rows, DEAL_QUESTIONS, max_workers=8, host=HOST, token="t")
    assert [r["key"] for r in out] == [r["key"] for r in rows]  # input order kept
    failed = [r for r in out if r["score_error"] is not None]
    assert len(failed) == 4 and all("500" in r["score_error"] and r["answers"] is None for r in failed)
    ok = [r for r in out if r["score_error"] is None]
    assert all(r["answers"]["next_action"]["choice"] == "send_proposal" for r in ok)
    assert all(r["input_tokens"] == FIXTURE["usage"]["input_tokens"] and r["latency_ms"] >= 0 for r in ok)


def test_state_hash_is_stable_and_order_independent():
    a = {"b": 1, "a": [1, 2]}
    assert scoring_job.state_hash(a) == scoring_job.state_hash({"a": [1, 2], "b": 1})
    assert scoring_job.state_hash(a) != scoring_job.state_hash({"a": [2, 1], "b": 1})


def test_select_pending_scores_only_changed_rows():
    cur = [
        {"key": "new", "state_sha256": "s1", "inputs_changed_at": "2026-11-10T00:00:00"},
        {"key": "same", "state_sha256": "s2", "inputs_changed_at": "2026-11-10T00:00:00"},
        {"key": "state_changed", "state_sha256": "s3b", "inputs_changed_at": "2026-11-10T00:00:00"},
        {"key": "newer_input", "state_sha256": "s4", "inputs_changed_at": "2026-11-12T00:00:00"},
        {"key": "failed_before", "state_sha256": "s5", "inputs_changed_at": "2026-11-10T00:00:00"},
        {"key": "old_questions", "state_sha256": "s6", "inputs_changed_at": "2026-11-10T00:00:00"},
    ]
    prev = {
        "same": {"state_sha256": "s2", "inputs_changed_at": "2026-11-10T00:00:00", "score_error": None, "questions_version": "v1"},
        "state_changed": {"state_sha256": "s3", "inputs_changed_at": "2026-11-10T00:00:00", "score_error": None, "questions_version": "v1"},
        "newer_input": {"state_sha256": "s4", "inputs_changed_at": "2026-11-11T00:00:00", "score_error": None, "questions_version": "v1"},
        "failed_before": {"state_sha256": "s5", "inputs_changed_at": "2026-11-10T00:00:00", "score_error": "OpenJev HTTP 500", "questions_version": "v1"},
        "old_questions": {"state_sha256": "s6", "inputs_changed_at": "2026-11-10T00:00:00", "score_error": None, "questions_version": "v0"},
    }
    pending = scoring_job.select_pending(cur, prev, "v1")
    assert [r["key"] for r in pending] == ["new", "state_changed", "newer_input", "failed_before", "old_questions"]
