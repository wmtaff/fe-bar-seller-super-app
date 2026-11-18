# 05 - OpenJev deal and lead scoring (Task 6)

Job task `ai_scoring` (serverless `spark_python_task`, `jobs/run_scoring.py` ->
`src/ai/scoring_job.py`) in job `seller_superapp_daily`, after `ai_call_insights`.
Model `system.ai.openjev-qwen35-4b` via `POST {host}/ai-gateway/typesafe/v1/systemone`,
auth from `WorkspaceClient()` default auth (host `w.config.host`, Bearer from
`w.config.authenticate()`), 16 worker threads. Questions: `src/ai/questions.py` (v1).

## Runs (2026-11-18, partial runs `only: [ai_scoring]`)

| Run | run_id | Result | Duration | Deals open / scored / errors | Leads open / scored / errors |
|---|---|---|---|---|---|
| 1 (first build) | 498197180425604 | SUCCESS | 183 s (task 179 s) | 2,979 / 2,979 / 0 | 2,566 / 2,566 / 0 |
| 2 (re-run, no input change) | 613279755508931 | SUCCESS | 38 s | 2,979 / **0 pending** / 0 | 2,566 / **0 pending** / 0 |

Task summary printed by run 1:

```json
{"ai_scoring_summary": [
 {"table": "gold_deal_scores", "open": 2979, "pending": 2979, "deleted": 0, "scored_ok": 2979, "errors": 0,
  "retried_calls": 237, "latency_p50_ms": 104, "latency_p95_ms": 698, "input_tokens": 4241681, "budget_error": null},
 {"table": "gold_lead_scores", "open": 2566, "pending": 2566, "deleted": 0, "scored_ok": 2566, "errors": 0,
  "retried_calls": 0, "latency_p50_ms": 90, "latency_p95_ms": 718, "input_tokens": 928078, "budget_error": null}]}
```

Run 2 printed `"pending": 0` for both tables: nothing is sent to OpenJev unless an input changed
(state hash, input watermark, previous failure, or question version).

- 237 deal calls (8%) needed a retry (429/5xx/timeout) and then succeeded; 0 rows ended with `score_error`.
- Latency is per successful HTTP attempt, measured in the client.

## Volume, latency and tokens (from the tables)

| Table | Rows | score_error | p50 latency | p95 latency | Input tokens | Avg tokens/row | Output tokens |
|---|---|---|---|---|---|---|---|
| gold_deal_scores | 2,979 | 0 | 104 ms | 693 ms | 4,241,681 | 1,424 | 0 |
| gold_lead_scores | 2,566 | 0 | 90 ms | 718 ms | 928,078 | 362 | 0 |

Total input tokens: 5,169,759.

## p_close_quarter distribution (gold_deal_scores)

Mean 0.620, stddev 0.175.

| p_close_quarter | Deals | |
|---|---|---|
| 0.1-0.2 | 1 | |
| 0.2-0.3 | 87 | # |
| 0.3-0.4 | 346 | ##### |
| 0.4-0.5 | 428 | ###### |
| 0.5-0.6 | 430 | ###### |
| 0.6-0.7 | 428 | ###### |
| 0.7-0.8 | 781 | ########### |
| 0.8-0.9 | 459 | ###### |
| 0.9-1.0 | 19 | |

| close_label | Deals | | next_action | Deals |
|---|---|---|---|---|
| Possible | 1,264 | | send_proposal | 1,600 |
| Likely | 968 | | schedule_demo | 909 |
| Very likely | 504 | | address_risk | 325 |
| Very unlikely | 219 | | multithread | 101 |
| Unlikely | 24 | | nurture | 38 |
| | | | exec_sponsor | 6 |

Sanity (directional, not tuned): mean p_close rises with stage (Discovery 0.559, Qualification 0.577,
Demo 0.625, Proposal 0.642, Negotiation 0.745) and is higher for deals whose close date is in the
current quarter (0.728, n=1,776) than for later ones (0.460, n=1,203).

Leads: fit_score mean 0.840, stddev 0.109; route_to SMB 1,310, Mid-Market 1,021, Enterprise 235.

## 5 sample Jordan Rivera deals (most calls, then ACV)

Jordan has 25 open deals, all scored (mean p_close 0.675).

| Opportunity | Stage | ACV | Close | p_close | Label (conf) | close_probs | Next action (conf) | Comp. risk | Churn risk |
|---|---|---|---|---|---|---|---|---|---|
| Solis Construction - Vehicle Telematics + 1 | Negotiation | 173,100 | 2026-12-30 | 0.858 | Likely (0.56) | VU 0.000, U 0.001, P 0.044, L 0.477, VL 0.477 | address_risk (0.97) | 0.84 | 0.04 |
| Blue Heron Distribution - Vehicle Telematics + 1 | Negotiation | 109,300 | 2026-12-12 | 0.740 | Likely (0.65) | VU 0.001, U 0.005, P 0.216, L 0.587, VL 0.191 | address_risk (0.89) | 0.87 | 0.11 |
| Mcdonald Logistics - Driver Safety + 1 | Proposal | 81,100 | 2027-01-21 | 0.850 | Likely (0.55) | VU 0.001, U 0.001, P 0.063, L 0.468, VL 0.468 | address_risk (0.68) | 0.10 | 0.03 |
| Nash Brewing Distribution - Vehicle Telematics | Proposal | 68,500 | 2026-12-21 | 0.956 | Very likely (0.85) | VU 0.000, U 0.000, P 0.006, L 0.163, VL 0.830 | send_proposal (0.52) | 0.07 | 0.03 |
| Reid Cartage - Compliance/ELD | Negotiation | 37,100 | 2026-12-09 | 0.930 | Very likely (0.77) | VU 0.000, U 0.000, P 0.006, L 0.267, VL 0.726 | address_risk (0.78) | 0.06 | 0.02 |

(VU/U/P/L/VL = Very unlikely / Unlikely / Possible / Likely / Very likely. All five are fictional
synthetic accounts.)

## Integration tests (`pytest tests/integration/test_scores.py`)

```
9 passed in 17.53s
```

Covers: >= 99% of open opps have p_close_quarter (actual 100%), stddev > 0.1 (actual 0.175),
only open opps/leads and one row per key, valid labels/actions/probabilities, >= 99% of open
leads scored, CDF on + PK + table and column comments on both tables, all of Jordan's open deals scored.
