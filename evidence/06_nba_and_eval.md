# 06 - Next best actions and score evaluation (Task 7)

Two job tasks in `seller_superapp_daily`, after `ai_scoring`:

| Task | Type | What |
|---|---|---|
| `next_best_actions` | SQL file on the warehouse (`src/ai/next_best_actions.sql`) | MERGEs `gold_opportunity_app` (pipeline LEFT JOIN deal scores, 15,000 opps) and `gold_next_best_actions` |
| `check_run_eval` -> `evaluate_scores` | condition task (`{{job.parameters.run_eval}} == "true"`, default `"false"`) -> serverless `spark_python_task` (`jobs/evaluate_scores.py` -> `src/ai/evaluate_scores.py`) | as-of re-scoring of 400 closed opps with OpenJev, extraction P/R, MLflow run + `gold_score_eval` |

All three tables: regular Delta, CDF on, primary key, table and column comments (checked by
`tests/integration/test_nba.py::test_tables_have_cdf_pk_and_comments`).

## Runs (2026-11-18, partial runs with `--only`)

| Run | run_id | Result | Notes |
|---|---|---|---|
| NBA build 1 | 1103738891452054 | SUCCESS (19 s) | first build: 4,045 actions inserted; `gold_opportunity_app` 15,000 rows |
| NBA re-run (no input change) | 152607038282231 | SUCCESS | MERGE: 0 inserted / 0 updated / 0 deleted; see rebuild safety |
| NBA with a temporary feedback table | (run after creating a fixture `gold_nba_feedback`) | SUCCESS | multiplier check, then the fixture was dropped and NBAs rebuilt |
| NBA after quote-expiry regex fix | (2026-11-18 11:55) | SUCCESS | MERGE 0 / 0 / 0 (no output change) |
| Eval 1, `run_eval=true` (superseded: leaky) | 984000213128722 | SUCCESS (evaluate_scores 82 s) | MLflow run `f50df91209ae423ba9fd797b5d954e40`; passed the post-close CRM competitor (see below) |
| **Eval 2, `run_eval=true` (current)** | 153643270603211 | SUCCESS | `check_run_eval` outcome `true`; MLflow run `cfc43607c7264bf5a0106174f92bf175` |
| Eval gate, default `run_eval=false` | 325763278933493 | SUCCESS | `check_run_eval` outcome `false`, `evaluate_scores` EXCLUDED |

Earlier failed attempts while building (fixed before commit): the SQL file task runs statement by
statement, so a `BEGIN ... END` block and a `DECLARE ... DEFAULT (subquery)` both failed; the file now
uses `DECLARE VARIABLE` + `SET VAR` + `EXECUTE IMMEDIATE`. One ambiguous-column error in the final SELECT.

## Next best actions

Sources (spec 4.4 item 4, brief values verbatim):

| source | action_type | rule | actions |
|---|---|---|---|
| call | call_next_step | each `next_steps` item of the opp's latest successful call insight | 1,046 |
| model | send_proposal / schedule_demo / address_risk / multithread / nurture | `next_action` when `next_action_conf >= 0.5` | 969 / 670 / 289 / 14 / 1 |
| rule | competitor_expiring | competitor in the CRM field or on any call, and the deal closes this quarter | 523 |
| rule | stale_opp | no completed activity for 21+ days | 512 |
| rule | p1_ticket | Open/Pending P1 ticket on the account (attached to its largest open opp) | 21 |
| rule | usage_drop | account 30-day usage trend < -15% (largest open opp) | 0 (no account in the v4 data is below -15%) |

Total 4,045 open actions; Jordan Rivera: 61 (34 call, 19 model, 8 rule).

`priority_score = acv * p_close * urgency * feedback`; p_close = `p_close_quarter` (CRM stage
probability if a deal has no score); urgency 1.5 if due within 7 days of the data as-of date
(2026-11-16, overdue included) or `competitor_expiring`, 1.2 within 14 days, else 1.0. Rule due dates:
competitor = earliest of close date and any competitor quote expiry in the call objections; stale =
as-of + 7; usage drop = as-of + 14; P1 = as-of + 2. Call due dates come from the call; model actions
have none.

Top 5 open actions for Jordan Rivera (by priority_score):

| # | title | why | source | due | priority |
|---|---|---|---|---|---|
| 1 | Set up time with the Solis leadership team to review the proposal | Agreed on the 2026-10-29 call (owner: Frances Gonzalez (customer, VP Operations)), due 2026-11-05. | call | 2026-11-05 | 222,681 |
| 2 | Schedule a call between Albert Harris and the Solis IT team | Agreed on the 2026-10-29 call (owner: Jordan Rivera (Fleetwise AE)), due 2026-11-12. | call | 2026-11-12 | 222,681 |
| 3 | Counter RoadLynx before the quarter closes | Competitor RoadLynx is in the deal and it closes 2026-12-30 (this quarter); a competitor quote expires 2026-12-04. | rule | 2026-12-04 | 222,681 |
| 4 | Send a side-by-side comparison against the RoadLynx quote, including coaching and insurance savings | Agreed on the 2026-10-29 call (owner: Jordan Rivera (Fleetwise AE)), due 2026-11-04. | call | 2026-11-04 | 222,681 |
| 5 | Set up the integration with the customer's maintenance system during onboarding | Agreed on the 2026-10-29 call (owner: Albert Harris (Fleetwise Sales Engineer)). | call | - | 148,454 |

All five are on one deal (Solis Construction, ACV $173,100): priority is per-deal ACV x P(close), so a
big, likely deal fills the top of the queue. Jordan's other competitor rules: "Counter FleetCore before
the quarter closes" (121,348), "Counter Trackwell before the quarter closes" (96,104).

### Rebuild safety (ruling R17)

- `action_id = sha2(concat_ws('|', opportunity_id, action_type, source_key), 256)`; source_key is
  `<meeting_id>#<position>` for call steps, `model`, or the rule name.
- Re-run test: snapshot of all action ids, one action set to `status = 'accepted'` (simulated app
  write-back), job re-run, compare: 4,045 before / 4,045 after, **0 new ids, 0 gone ids, 0 rows
  rewritten** (`updated_at` unchanged), MERGE metrics 0 inserted / 0 updated / 0 deleted, and the
  `accepted` status was kept (the MERGE never updates `status`). The test row was then set back to `open`.
- Deletes: `WHEN NOT MATCHED BY SOURCE THEN DELETE` drops actions whose source disappeared (closed opp,
  newer call, model confidence below 0.5, rule no longer true). The table is never dropped or recreated.
- `gold_opportunity_app` uses a row hash: the re-run MERGE touched 0 of 15,000 rows.

### Feedback multiplier (Task 8 contract)

`gold_nba_feedback` does not exist yet. The SQL checks `information_schema.tables` and only then reads
it via `EXECUTE IMMEDIATE`; otherwise the factor is 1.0. Expected contract for Task 8: one row (or more,
averaged) per `action_type` with `acceptance_rate` in 0..1; factor = clamp(0.5 + rate, 0.5, 1.5).
Check: a temporary fixture with `call_next_step` 0.9 and `stale_opp` 1.5 gave factors exactly 1.4 for
every call action, 1.5 (clamped) for every stale action and 1.0 for all others. The fixture was then
dropped and the NBAs rebuilt (factor 1.0 again; `test_priority_score_formula` passes).

## Score evaluation

### Method

- Ground truth `/Volumes/<catalog>/<schema>/raw/v4/_eval/truth/batch=*/part-0.json`, latest batch per
  record_id (`QUALIFY row_number() OVER (PARTITION BY record_id ORDER BY batch DESC) = 1`). Truth is
  read only by `src/ai/evaluate_scores.py` (unit test `test_truth_never_feeds_app_tables` checks the NBA,
  scoring and insight code never reference it).
- Sample: 400 closed opps whose snapshot_date is before the close date, ordered by
  `sha2(opportunity_id)` (deterministic, the same sample every run). Label = `is_won`.
- State as of snapshot_date, built with the production `openjev.build_deal_state` and scored with the
  production `openjev.call` + `DEAL_QUESTIONS` (v1, `system.ai.openjev-qwen35-4b`):
  - opportunity: stage, amount, close date, forecast category from the latest `silver_opportunity_history`
    row created by the snapshot; stage age from that row; activities (completed Tasks, Events) up to the
    snapshot; days to close and "closes this quarter" relative to the snapshot;
  - account: Customer / ARR / products owned from the account's Closed Won opps closed before the snapshot;
    usage from `silver_usage_daily` 30-day windows ending at the snapshot; tickets created by the snapshot
    and not solved by then, P1s in the 30 days before it;
  - calls: insights from calls that started by the end of the snapshot day.
- Approximations (documented, simplest defensible): the CRM `next_step` and `competitor` fields are
  dropped (null in the state). Only their current values exist, and the generator back-fills the CRM
  competitor on lost deals at close time (`src/fleetwise_gen/entities.py`; ~82% of lost vs ~55% of won
  opps have it), which would leak the outcome. Pre-snapshot competitor mentions still reach the state via
  the as-of call insights. Products, fleet size and opportunity type are taken as recorded; a Task's Completed status is its current status; ARR ignores churn. Usage history starts
  2026-08-19, so most snapshots have no usage (null in the state, no leakage).

### Results (MLflow run `cfc43607c7264bf5a0106174f92bf175`, experiment `/Users/will.taff@databricks.com/fleetwise-score-eval`)

| Metric | Value |
|---|---|
| **AUC, p_close_quarter vs is_won** | **0.695** |
| AUC, generator true_intent vs is_won (sanity ceiling) | 0.731 |
| **Top-decile lift** | **2.06x** (win rate 0.80 vs base 0.3875) |
| Brier score | 0.255 |
| Mean p_close_quarter | 0.586 |
| Scored / errors | 400 / 0 |
| Sampled opps with a call before the snapshot | 2 |

AUC is above the 0.65 bar, so no tuning question arises (ruling R20: not tuned either way). The
score reaches 95% of the AUC of the generator's own latent intent.

Review fix (round 1): eval 1 passed the CRM `competitor` field, which the generator back-fills on lost
deals at close (a post-snapshot, outcome-correlated value). With it removed, AUC went from the leaky
**0.697** to **0.695**; top-decile lift is unchanged at 2.06x. The leak was real but its effect on this
sample was small. Both runs stay in MLflow and `gold_score_eval` (47 rows each).

Lift by decile (decile 1 = highest p_close_quarter; 40 opps each):

| decile | won | win_rate | lift | mean p_close |
|---|---|---|---|---|
| 1 | 32 | 0.800 | 2.06 | 0.793 |
| 2 | 24 | 0.600 | 1.55 | 0.756 |
| 3 | 20 | 0.500 | 1.29 | 0.726 |
| 4 | 15 | 0.375 | 0.97 | 0.692 |
| 5 | 8 | 0.200 | 0.52 | 0.641 |
| 6 | 13 | 0.325 | 0.84 | 0.587 |
| 7 | 13 | 0.325 | 0.84 | 0.524 |
| 8 | 15 | 0.375 | 0.97 | 0.463 |
| 9 | 6 | 0.150 | 0.39 | 0.384 |
| 10 | 9 | 0.225 | 0.58 | 0.291 |

Calibration (5 equal-width bins):

| p_close_quarter bin | n | mean predicted | observed win rate |
|---|---|---|---|
| 0.0-0.2 | 0 | - | - |
| 0.2-0.4 | 68 | 0.324 | 0.162 |
| 0.4-0.6 | 120 | 0.506 | 0.350 |
| 0.6-0.8 | 201 | 0.710 | 0.453 |
| 0.8-1.0 | 11 | 0.813 | 1.000 |

Ranking is useful (monotone at the top and bottom, flat in the middle deciles); the absolute
probabilities are optimistic by roughly 0.15-0.26 below 0.8. p_close_quarter is score / 4 of a 5-level
question, not a fitted probability; a Platt/isotonic recalibration would be the next step (not done:
"don't tune").

### Extraction quality (gold_call_insights.competitors vs planted_competitors)

| Slice | Calls | Precision | Recall |
|---|---|---|---|
| **Spot check (20 calls, sha2 order)** | 20 | **1.00** | **1.00** |
| All calls with insights | 640 | 1.00 | 1.00 (287 planted mentions in 257 calls, 287 extracted) |

The 20-call spot check contains only 2 planted competitors (RoadLynx, Trackwell; both found, no false
positives on the other 18), so the all-calls row is the stronger evidence.

### Where the results live

- MLflow: params (model, question version, sample method, label, as-of rule), 16 metrics, artifacts
  `lift_by_decile.md`, `calibration.md`, `extraction_spot_check.md`, `eval_tables.json`.
- `gold_score_eval` (run_id, metric, segment, value, evaluated_at): 47 rows for this run (auc, lift and
  win_rate per decile, calibration per bin, competitor precision/recall per slice, counts).
  The superseded leaky run's 47 rows are kept under its own run_id.

## Tests

- Unit (`.venv/bin/pytest tests/unit -q`): 80 passed (17 new, incl. a check that the eval state drops the CRM competitor/next_step: metrics, as-of discipline, truth isolation,
  NBA SQL rebuild-safety and feedback optionality, job wiring; plus `openjev.call` retrying any
  `requests.RequestException`).
- Integration (`.venv/bin/pytest tests/integration/test_nba.py -m integration`): 12 passed, all
  expectations derived with SQL (R14): unique and correctly derived ids, only open opps, model actions
  == confident scores, call actions == latest-call next steps, Jordan >= 10 open actions, Jordan's
  competitor rules == his current-quarter opps with a competitor, priority formula, `gold_opportunity_app`
  == pipeline joined with scores, CDF/PK/comments on all three tables, eval AUC/lift/extraction rows.
