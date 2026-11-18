"""OpenJev (System One) client and state builders for deal and lead scoring (Task 6).

System One: POST {host}/ai-gateway/typesafe/v1/systemone with a Bearer token and
{"model": ..., "state": {...}, "questions": {...}}. It returns calibrated answers with no
generated text (0 output tokens):
  score  -> {"score": 0..N-1 (probability-weighted), "confidence", "legend", "probabilities"}
  choice -> {"choice", "confidence", "probabilities"}
  noul   -> {"noul": 0..1}

Privacy: states are built from an explicit allow-list of fields. They never carry Salesforce
ids, account/seller/contact names, emails or phones; contact names that the call-insight
summaries mention are redacted. Lead states also drop the outcome fields (status,
is_converted, converted_date; ruling R11).

Task 7 reuses build_deal_state and call for the score evaluation: keep their signatures.
"""

from __future__ import annotations

import json
import random
import re
import time
from datetime import date, datetime

import requests

from ai.questions import MODEL

PATH = "/ai-gateway/typesafe/v1/systemone"
MAX_ATTEMPTS = 4
INSIGHT_BUDGET_CHARS = 2000
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_sleep = time.sleep  # patched in unit tests


class OpenJevError(RuntimeError):
    """OpenJev call failed: non-retryable HTTP error, bad response, or retries exhausted."""


# --------------------------------------------------------------------------- state builders
def _iso(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _pick(row: dict, fields: tuple[str, ...]) -> dict:
    return {f: _iso(row.get(f)) for f in fields}


OPP_FIELDS = ("stage", "opportunity_type", "segment", "acv", "close_date", "fiscal_quarter",
              "days_to_close", "stage_age_days", "days_since_last_activity", "activities_30d",
              "forecast_category", "competitor", "products", "fleet_size", "next_step")
ACCOUNT_FIELDS = ("account_type", "industry", "fleet_size", "arr", "products_owned",
                  "whitespace_products", "active_vehicles_30d", "usage_trend_pct_30d",
                  "open_tickets", "p1_tickets_30d")
LEAD_FIELDS = ("title", "lead_source", "industry", "state", "country", "fleet_size",
               "products_of_interest", "description")


def _redactor(names: set[str]):
    """Replace each full name, then each name part of 3+ letters, as whole words."""
    terms = set()
    for n in names:
        if n and n.strip():
            terms.add(n.strip())
            terms.update(p for p in re.split(r"\s+", n.strip()) if len(p) >= 3)
    if not terms:
        return lambda s: s
    rx = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")\b")
    return lambda s: rx.sub("[contact]", s) if isinstance(s, str) else s


def _compact_insight(ins: dict, redact) -> dict:
    def texts(v):
        return [redact(x) for x in (v or []) if x][:5]

    return {
        "date": str(_iso(ins.get("started_at")) or "")[:10],
        "sentiment": ins.get("sentiment"),
        "summary": redact(ins.get("summary") or ""),
        "competitors": list(ins.get("competitors") or []),
        "objections": texts(ins.get("objections")),
        "open_items": texts(ins.get("open_items")),
        "next_steps": texts([s.get("action") for s in (ins.get("next_steps") or []) if isinstance(s, dict)]),
    }


def _size(x) -> int:
    return len(json.dumps(x))


def _fit(entries: list[dict], e: dict, budget: int) -> dict | None:
    """Return e (shortened if needed) so that entries + [e] fits the budget, else None."""
    over = _size(entries + [e]) - budget
    if over <= 0:
        return e
    e = dict(e)
    for key in ("next_steps", "open_items", "objections"):  # drop detail lists first
        if over <= 0:
            break
        if e[key]:
            e[key] = []
            over = _size(entries + [e]) - budget
    if over > 0 and len(e["summary"]) > over + 40:
        e["summary"] = e["summary"][: len(e["summary"]) - over - 3].rstrip() + "..."
        over = _size(entries + [e]) - budget
    return e if over <= 0 else None


def build_deal_state(opp: dict, account: dict, insights: list[dict]) -> dict:
    """Compact OpenJev state for one open opportunity.

    opportunity + account fields from an allow-list, plus `recent_calls`: successful call
    insights newest first, at most INSIGHT_BUDGET_CHARS of JSON (the oldest are dropped, the
    last one that does not fit is shortened).
    """
    o = _pick(opp, OPP_FIELDS)
    o["closes_this_quarter"] = opp.get("is_current_quarter")
    names = {n.get("name") for ins in insights for n in (ins.get("stakeholders") or []) if isinstance(n, dict)}
    redact = _redactor(names)
    other = [(account or {}).get("account_name") or opp.get("account_name"),
             opp.get("owner_name"), (account or {}).get("owner_name")]
    rx_other = [re.compile(re.escape(n)) for n in other if n]

    def redact_all(s):
        s = redact(s)
        for rx in rx_other:
            s = rx.sub("[company]", s) if isinstance(s, str) else s
        return s

    ok = [i for i in insights if not i.get("extract_error") and i.get("summary")]
    ok.sort(key=lambda i: str(_iso(i.get("started_at")) or ""), reverse=True)
    calls: list[dict] = []
    for ins in ok:
        e = _fit(calls, _compact_insight(ins, redact_all), INSIGHT_BUDGET_CHARS)
        if e is None:
            break
        calls.append(e)
    return {"opportunity": o, "account": _pick(account or {}, ACCOUNT_FIELDS), "recent_calls": calls}


def build_lead_state(lead: dict) -> dict:
    """OpenJev state for one open lead: non-PII profile fields only (no names, email, phone,
    company, owner, ids or outcome fields)."""
    s = _pick(lead, LEAD_FIELDS)
    s["created_date"] = str(_iso(lead.get("created_date")) or "")[:10] or None
    return {"lead": s}


# --------------------------------------------------------------------------- client
def _backoff(attempt: int) -> float:
    return min(30.0, 2.0 ** (attempt - 1)) + random.uniform(0, 0.5)


def call(state: dict, questions: dict, *, host: str, token: str, timeout=30, meta: dict | None = None) -> dict:
    """Ask OpenJev `questions` about `state`; return the `answers` map.

    Retries HTTP 429/5xx, timeouts and connection errors with exponential backoff
    (MAX_ATTEMPTS in total); other 4xx and malformed responses fail at once. Raises
    OpenJevError. If `meta` is given it receives attempts, latency_ms and input_tokens.
    """
    url = host.rstrip("/") + PATH
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"model": MODEL, "state": state, "questions": questions}
    last = "no attempt"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        t0 = time.monotonic()
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as e:
            last = f"OpenJev {type(e).__name__}: {str(e)[:200]}"
        else:
            if r.status_code == 200:
                try:
                    payload = r.json()
                    answers = payload["answers"]
                except (ValueError, KeyError, TypeError) as e:
                    raise OpenJevError(f"OpenJev bad response: {type(e).__name__}") from e
                missing = set(questions) - set(answers or {})
                if missing:
                    raise OpenJevError(f"OpenJev response missing answers: {sorted(missing)}")
                if meta is not None:
                    meta.update(attempts=attempt, latency_ms=int((time.monotonic() - t0) * 1000),
                                input_tokens=(payload.get("usage") or {}).get("input_tokens"))
                return answers
            last = f"OpenJev HTTP {r.status_code}: {(r.text or '')[:200]}"
            if r.status_code not in RETRYABLE_STATUS:
                raise OpenJevError(last)
        if attempt < MAX_ATTEMPTS:
            _sleep(_backoff(attempt))
    raise OpenJevError(f"{last} (after {MAX_ATTEMPTS} attempts)")


# --------------------------------------------------------------------------- answers -> columns
def _score(ans: dict) -> tuple[float, str, float, dict]:
    legend = {int(k): v for k, v in ans["legend"].items()}
    probs = {int(k): float(v) for k, v in ans["probabilities"].items()}
    top = max(sorted(probs), key=lambda k: probs[k])  # ties -> the lower level
    unit = float(ans["score"]) / (len(legend) - 1)
    return unit, legend[top], float(ans["confidence"]), {legend[k]: p for k, p in sorted(probs.items())}


def deal_scores(answers: dict) -> dict:
    """Map DEAL_QUESTIONS answers to gold_deal_scores columns (p_close_quarter = score / 4)."""
    p, label, conf, probs = _score(answers["close_this_quarter"])
    na = answers["next_action"]
    return {
        "p_close_quarter": p,
        "close_label": label,
        "close_confidence": conf,
        "close_probs": probs,
        "next_action": na["choice"],
        "next_action_conf": float(na["confidence"]),
        "next_action_probs": {k: float(v) for k, v in na["probabilities"].items()},
        "competitive_risk": float(answers["competitive_risk"]["noul"]),
        "churn_risk": float(answers["churn_risk"]["noul"]),
    }


def lead_scores(answers: dict) -> dict:
    """Map LEAD_QUESTIONS answers to gold_lead_scores columns (fit_score = score / 4)."""
    fit, label, _, _ = _score(answers["conversion_fit"])
    rt = answers["route_to"]
    return {"fit_score": fit, "fit_label": label, "route_to": rt["choice"], "route_conf": float(rt["confidence"])}
