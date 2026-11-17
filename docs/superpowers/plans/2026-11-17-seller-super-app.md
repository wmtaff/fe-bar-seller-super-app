# Seller Super App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Fleetwise Seller Super App. Synthetic Salesforce + Meet transcript + usage + ticket data flows Lakeflow → UC → GenAI/OpenJev → Lakebase → Genie → Databricks App, with text-readable execution evidence committed.

**Architecture:**
1. A deterministic Python generator lands SFDC-shaped files in a UC Volume.
2. A Lakeflow Spark Declarative Pipeline builds bronze/silver/gold.
3. Lakeflow Job tasks add AI tables: `ai_query` extraction and OpenJev scoring.
4. Lakebase synced tables serve the app. App writes go to Lakebase `app.*` and flow back to Delta via Lakehouse Sync.
5. A Genie space sits over gold. An AppKit app reads Lakebase and embeds Genie.

**Tech Stack:**
- Python 3.11 (generator, scoring, tests: pytest, faker, numpy, requests, scikit-learn, mlflow)
- Databricks SQL (pipeline, governance)
- Databricks Asset Bundles
- Lakebase Autoscaling (`databricks postgres`)
- AppKit (TypeScript/React) with `lakebase`, `genie`, `serving` plugins

**Spec:** `docs/superpowers/specs/2026-11-17-seller-super-app-design.md` (read it first; section 6 overrides earlier sections).

## Global Constraints
- CLI profile: `fevm-serverless-stable-s1omq8`. Never use another profile.
- Catalog `serverless_stable_s1omq8_catalog`, schema `seller_superapp`, volume `raw`. All names are bundle variables; no hard-coded workspace URL/IDs in code.
- SQL warehouse: Demo Warehouse `9a6db1d12e2ee6d3`. Never the RT Warehouse (`0000000000bb17db`) or the Starter Warehouse.
- Serverless compute only.
- GenAI endpoint `databricks-claude-sonnet-5-5`. Classifier: OpenJev via `POST {host}/ai-gateway/typesafe/v1/systemone`, body `{"model":"system.ai.openjev-qwen35-4b","state":…,"questions":…}`.
- Fictional company "Fleetwise". No real customer names, people, or data anywhere in the repo (grep for the real customer name before every push).
- Lakehouse RT: not used, not mentioned as part of the build.
- Generator seed `42`. Same seed means byte-identical `--init` output.
- Salesforce field API names in raw files: `Id` (18-char), `OwnerId`, `AccountId`, `StageName`, `Amount`, `CloseDate`, `IsClosed`, `IsWon`, `CreatedDate`, `LastModifiedDate`.
- Product list (exact): `Vehicle Telematics`, `AI Dash Cams`, `Driver Safety`, `Fuel & Maintenance`, `Compliance/ELD`, `Equipment Monitoring`.
- Demo personas: seller `Jordan Rivera` (AE, Mid-Market West), manager `Morgan Lee` (Jordan's manager).
- App name `fleetwise-seller-hub`. Lakebase project `seller-superapp`. Genie space title `Fleetwise Revenue Copilot`. Job `seller_superapp_daily`.
- Every Databricks product task loads its skill first: `databricks-pipelines`, `databricks-jobs`, `databricks-dabs`, `databricks-lakebase`, `databricks-unity-catalog`, `databricks-ai-functions`, `databricks-genie-agents`, `databricks-apps` + `databricks-app-design`.
- Evidence is text: every task that runs something on Databricks writes its proof into `evidence/` (markdown/JSON), committed.
- Commits end with `Co-authored-by: Isaac <no-reply@databricks.com>`.

## Review Focus
1. **Malformed or null `ai_query` output** for a transcript. The row is kept in `gold_call_insights` with `extract_error` set; the job does not fail. Test: Task 5 `test_parse_insights_handles_invalid_json`.
2. **OpenJev 429/5xx/timeout.** Retried with exponential backoff (max 4). Rows that still fail are written with `score_error` set. The task fails only if more than 5% of rows fail. Tests: Task 6 `test_call_retries_on_429` and `test_batch_fails_over_error_budget`.
3. **Job or increment re-run.** Idempotent: no duplicate opps, insights, scores, or NBAs (MERGE on keys; generator increments named by batch number and skipped if present). Tests: Task 2 `test_increment_is_idempotent`, plus a Task 11 rerun check.
4. **Persona with no open deals, insights, or NBAs.** App pages render explicit empty states, not errors. Test: Task 10 smoke test with persona `empty-demo` (a seller with zero open opps, created by the generator).
5. **Lakebase idle and token expiry** (scale-to-zero, 1 h OAuth). The app recovers on the next request. Test: Task 10 `GET /api/health/db` after the endpoint scales to zero (wait at least 6 min), with the result recorded in evidence.

---

## File Structure
```
README.md                          # business-first narrative (Task 12)
databricks.yml                     # bundle: vars, pipeline, job, app (Task 1, extended later)
pyproject.toml / requirements-dev.txt
src/fleetwise_gen/                 # synthetic generator (Task 2)
  config.py  entities.py  transcripts.py  usage.py  writer.py  cli.py
src/pipeline/                      # Lakeflow SDP SQL (Task 3)
  bronze.sql  silver.sql  gold.sql
src/governance/                    # UC DDL (Task 4)
  setup.sql  row_filters.sql  masks.sql  comments_tags.sql
src/ai/                            # Task 5–7
  call_insights.sql  insights_schema.json  parse.py
  openjev.py  scoring_job.py  questions.py
  next_best_actions.sql  evaluate_scores.py
src/lakebase/                      # Task 8
  setup_lakebase.py  app_schema.sql  writeback.sql
src/genie/                         # Task 9
  space.json  create_space.py  benchmark.py
app/fleetwise-seller-hub/          # AppKit app (Task 10)
jobs/                              # thin job entrypoints (generate_data.py, run_scoring.py, collect_evidence.py …)
notebooks/                         # executed .ipynb with outputs (Task 11–12)
tests/unit/  tests/integration/
evidence/                          # committed text proof
docs/VALUE_MODEL.md  docs/DECK_POINTS.md  docs/BACKLOG.md
```

---

### Task 1: Repo, bundle skeleton, UC schema & volume

**Files:** Create `.gitignore`, `pyproject.toml`, `requirements-dev.txt`, `databricks.yml`, `.env.example`, `tests/integration/conftest.py`.

**Interfaces — Produces:**
- Bundle variables `catalog`, `schema`, `volume`, `warehouse_id`, `profile`.
- `tests/integration/conftest.py` fixture `sql(query: str) -> list[dict]`, which runs via Statement Execution on the warehouse with profile `fevm-serverless-stable-s1omq8`.

- [ ] **Step 1:** `git init`. Create a private GitHub repo `will-taff_data/fe-bar-seller-super-app` with `gh repo create --private`. Add the remote.
- [ ] **Step 2:** Write `databricks.yml` with target `dev` (workspace host from profile, mode development) and the variables above.
- [ ] **Step 3:** Create schema `seller_superapp` and volume `raw` (bundle `schemas`/`volumes` resources).
- [ ] **Step 4:** Run `databricks bundle validate -t dev -p fevm-serverless-stable-s1omq8`, then `deploy`. Expected: success.
- [ ] **Step 5:** Write `tests/integration/test_setup.py::test_schema_and_volume_exist` (asserts `information_schema.schemata` and `volumes` rows). Run `pytest tests/integration/test_setup.py -v`. Expected: PASS.
- [ ] **Step 6:** Commit and push.

### Task 2: Synthetic data generator

**Files:** Create `src/fleetwise_gen/*`, `jobs/generate_data.py`, and `tests/unit/test_generator.py`.

**Interfaces — Produces:**
- CLI: `python -m fleetwise_gen.cli --mode {init,increment} --out <dir> --seed 42 [--batch N]`
- Output layout under `<dir>`:
  - `salesforce/{User,UserRole,Account,Contact,Opportunity,OpportunityHistory,Lead,Task,Event}/batch=<NNNN>/part-0.json` (JSON lines)
  - `meet_transcripts/batch=<NNNN>/*.json`
  - `product_usage/batch=<NNNN>/part-0.csv`
  - `support_tickets/batch=<NNNN>/part-0.json`
  - `_eval/truth/batch=<NNNN>/part-0.json` (cols: `record_type`, `record_id`, `true_intent` in [0,1], `planted_competitors` [], `planted_next_steps` [], `will_win` bool, `snapshot_date`)
- Transcript JSON: `{meeting_id, opportunity_id, account_id, started_at, duration_min, attendees:[{name,email,role,company}], turns:[{speaker,ts,text}]}`
- `generate(mode, out_dir, seed, batch) -> dict[str,int]` (row counts per dataset)

**Sizes for `--init`:** about 600 sellers, 60 managers, 8 RVPs; 5,000 accounts; 20,000 contacts; 15,000 opps (≈3,000 open); 4,000 leads; 60,000 tasks/events; 600 transcripts; 90 days × customer accounts of usage; 8,000 tickets.

**Each `--increment`** (batch ≥ 1): stage changes on ≈150 open opps, ≈1,000 new activities, 40 new transcripts, 1 new usage day, 100 new tickets, and 50 new leads. All IDs are stable and derived from the seed + entity index. `LastModifiedDate` = batch timestamp.

**Persona seeding:**
- Seller `Jordan Rivera` has 25 open opps; at least 8 have transcripts, including at least 2 with a competitor quote expiring this quarter.
- Seller `empty-demo` (`Taylor Empty`) owns 0 open opps.
- `Morgan Lee` manages Jordan plus 7 others.

**Transcripts:** template + phrase-bank generator (my call: no LLM, so it's deterministic and testable; documented in trade-offs). Each opp's `true_intent` controls buying-signal density, objections, competitor mentions (all **fictional**: `RoadLynx`, `FleetCore`, `Trackwell`), next steps said aloud, and sentiment. Planted signals go to `_eval/truth`. Closed opps get a `snapshot_date` at about 60% of their lifecycle; transcripts and activities exist both before and after it.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_generator.py`:
  - `test_init_is_deterministic`: two runs with seed 42 → identical file hashes.
  - `test_ids_are_18_char_and_unique`
  - `test_referential_integrity` (every `Opportunity.AccountId` in Account, `OwnerId` in User, transcript `opportunity_id` in Opportunity)
  - `test_truth_not_in_raw`: no `true_intent`/`will_win` keys in any non-`_eval` file.
  - `test_jordan_persona`: ≥25 open opps, ≥8 with transcripts.
  - `test_empty_persona_has_no_open_opps`
  - `test_increment_stable_ids`: batch 1 opp IDs ⊆ init opp IDs, plus only the new leads.
  - `test_increment_is_idempotent`: running batch 1 twice leaves the directory unchanged (skip if present).
  - `test_win_rate_tracks_intent`: top-quintile `true_intent` win rate > bottom quintile + 0.3.
- [ ] **Step 2:** Run `pytest tests/unit/test_generator.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement the `fleetwise_gen` modules and `generate(...)`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Write `jobs/generate_data.py` (params `mode`, `batch`; writes to `/Volumes/{catalog}/{schema}/{volume}/`).
- [ ] **Step 6:** Add a job resource `seller_superapp_daily` to the bundle with task `generate_data` only (params default `mode=init`). Deploy and run it. Save the run output to `evidence/01_generate_data.md` (row counts + file listing from `databricks fs ls -r`).
- [ ] **Step 7:** Commit.

### Task 3: Lakeflow Spark Declarative Pipeline (bronze → silver → gold)

**Files:** Create `src/pipeline/{bronze,silver,gold}.sql`, a pipeline resource in `databricks.yml`, and `tests/integration/test_pipeline.py`.

**Interfaces:**
- Consumes the Task 2 layout.
- Produces these tables in `{catalog}.seller_superapp`:
  - `bronze_<object>` (streaming, Auto Loader `read_files` with `_source_file`, `_ingested_at`)
  - `silver_users`, `silver_accounts`, `silver_contacts`, `silver_opportunities` (latest by `Id` via AUTO CDC on `LastModifiedDate`), `silver_opportunity_history`, `silver_leads`, `silver_activities`, `silver_transcripts` (one row per meeting with `transcript_text` = concatenated turns), `silver_usage_daily`, `silver_tickets`
  - Gold MVs:
    - `gold_user_hierarchy(user_id, name, email, role, segment, region, manager_id, rvp_id)`
    - `gold_account_360(account_id, …, arr, products_owned array, whitespace_products array, active_vehicles_30d, usage_trend_pct_30d, open_tickets, p1_tickets_30d, last_activity_at)`
    - `gold_opportunity_pipeline(opportunity_id, account_id, owner_id, stage, acv, close_date, fiscal_quarter, is_closed, is_won, stage_age_days, days_to_close, last_activity_at, competitor, products array)`
    - `gold_seller_kpis(owner_id, fiscal_quarter, quota, closed_won_acv, attainment_pct, open_pipeline_acv, commit_acv, coverage_ratio)`
    - `gold_contacts_masked` (email/phone masked inline, for Lakebase)
- Fiscal year starts Feb 1 (fiscal quarter = `FYyyQn`).
- Expectations: `expect_or_drop` on non-null `Id`; `expect` `Amount >= 0`; `expect_or_drop` `CloseDate` not null on opps.

- [ ] **Step 1: Write failing tests** in `tests/integration/test_pipeline.py`:
  - `test_gold_tables_exist`
  - `test_silver_opps_unique_ids`
  - `test_jordan_open_pipeline` (`gold_opportunity_pipeline` has ≥25 open rows for Jordan's user_id)
  - `test_contacts_masked_has_no_raw_email` (no value matching `^[^*]+@` in `gold_contacts_masked.email`)
  - `test_expectations_recorded` (the event log has `flow_progress` with expectation metrics)
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement the SQL and the bundle pipeline resource (serverless, catalog/schema from vars). Enable CDF (`delta.enableChangeDataFeed=true`) on all gold tables (needed for synced tables).
- [ ] **Step 4:** Deploy and run the pipeline. Run the tests. Expected: PASS.
- [ ] **Step 5:** Write `evidence/02_pipeline.md`: update ID, row counts per table, expectation pass/fail counts from the event log.
- [ ] **Step 6:** Add `pipeline_refresh` as a task after `generate_data` in the job. Commit.

### Task 4: Unity Catalog governance

**Files:** Create `src/governance/{setup,row_filters,masks,comments_tags}.sql`, a job task `apply_governance` (sql_task on the warehouse), and `tests/integration/test_governance.py`.

**Interfaces — Produces:**
- Table `demo_identity_map(workspace_email STRING, persona_user_id STRING, persona_role STRING)`. It's seeded with the current user → Jordan. `persona_role` ∈ {`seller`,`manager`,`admin`}.
- Function `fn_can_see_owner(owner_id STRING) RETURNS BOOLEAN`: TRUE if the caller is an admin (`is_account_group_member('admins')`); or the caller's persona is the owner; or the persona is the owner's `manager_id`/`rvp_id`. Applied as the row filter on `gold_opportunity_pipeline(owner_id)` and `gold_seller_kpis(owner_id)`.
- Function `fn_mask_pii(v STRING) RETURNS STRING`: unmasked if `is_account_group_member('superapp_revops')`, else masked. Applied to `silver_contacts.email` and `.phone`.
- Tag `pii=true` on those columns. Table and column comments on every gold/AI table (Genie relies on them).

Note: gold MVs that carry row filters can't be the source of synced tables if sync rejects them. If so, put the row filter on secure views `v_opportunity_pipeline` and `v_seller_kpis` (Genie uses the views; Lakebase syncs the base tables), and document it.

- [ ] **Step 1: Write failing tests:**
  - `test_row_filter_scopes_to_persona`: with the map set to Jordan, as the current user (non-admin path), `SELECT count(DISTINCT owner_id)` on the governed object = 1.
  - `test_manager_persona_sees_team`: set the map to Morgan → 8 owners.
  - `test_email_masked`
  - `test_pii_tags_present`

  If the executing user is a workspace admin, test the filter logic through `fn_can_see_owner` with an explicit persona argument variant `fn_can_see_owner_for(persona_user_id, owner_id)`, which the main function wraps.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement the SQL. Run the `apply_governance` task.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Write `evidence/03_governance.md`: DESCRIBE output showing the filter and masks, before/after query results per persona, and tags.
- [ ] **Step 6:** Commit.

### Task 5: GenAI call insights (`ai_query`)

**Files:** Create `src/ai/call_insights.sql`, `src/ai/insights_schema.json`, `src/ai/parse.py`, `tests/unit/test_parse.py`, and `tests/integration/test_insights.py`.

**Interfaces — Produces:** Table `gold_call_insights(meeting_id PK, opportunity_id, account_id, started_at, summary, next_steps ARRAY<STRUCT<action,owner,due>>, open_items ARRAY<STRING>, interests ARRAY<STRING>, competitors ARRAY<STRING>, objections ARRAY<STRING>, sentiment STRING, stakeholders ARRAY<STRUCT<name,role,stance>>, model STRING, extracted_at TIMESTAMP, extract_error STRING)`.
- `interests` values are restricted to the product list.
- `sentiment` ∈ {positive, neutral, negative}.

**Approach:** Incremental MERGE: only `silver_transcripts` rows not yet in the target. Use `ai_query('databricks-claude-sonnet-5-5', prompt, responseFormat => <insights_schema.json>, failOnError => false)`. Parse `.result`. When `.errorMessage` is non-null, store it in `extract_error`.

- [ ] **Step 1:** Write failing unit tests for `parse.py`. `normalize_insights(raw: str|None) -> tuple[dict|None, str|None]`:
  - `test_parse_valid`
  - `test_parse_insights_handles_invalid_json` → `(None, "invalid_json")`
  - `test_interests_filtered_to_products` (drops "Bananas")

  (`parse.py` is used by the eval spot-check and mirrors the SQL schema.)
- [ ] **Step 2:** Run. FAIL. Implement. Run. PASS.
- [ ] **Step 3:** Write the integration test `test_insights_coverage`: ≥95% of transcripts have non-null `summary`, and Jordan's opps have ≥8 insight rows.
- [ ] **Step 4:** Add job task `ai_call_insights` (sql_task, warehouse) after `pipeline_refresh`. Run it. The test passes.
- [ ] **Step 5:** Write `evidence/04_call_insights.md`: counts, error count, 3 full sample rows (one of Jordan's), and the prompt text.
- [ ] **Step 6:** Commit.

### Task 6: OpenJev deal & lead scoring

**Files:** Create `src/ai/questions.py`, `src/ai/openjev.py`, `src/ai/scoring_job.py`, `jobs/run_scoring.py`, `tests/unit/test_openjev.py`, and `tests/integration/test_scores.py`.

**Interfaces:**
- `questions.DEAL_QUESTIONS: dict` (System One question map):
  - `close_this_quarter`: score, `["Very unlikely","Unlikely","Possible","Likely","Very likely"]`
  - `next_action`: choice, keys `send_proposal`, `multithread`, `schedule_demo`, `exec_sponsor`, `address_risk`, `nurture`, each with a description
  - `competitive_risk`: noul
  - `churn_risk`: noul
- `questions.LEAD_QUESTIONS`:
  - `conversion_fit`: score, 5 levels
  - `route_to`: choice `SMB`/`Mid-Market`/`Enterprise`
- `openjev.build_deal_state(opp: dict, account: dict, insights: list[dict]) -> dict` (compact; ≤2,000 chars of insight text, newest first)
- `openjev.call(state: dict, questions: dict, *, host: str, token: str, timeout=30) -> dict` (returns `answers`; retries 429/5xx/timeout with exponential backoff, max 4 attempts; raises `OpenJevError` after that)
- `scoring_job.score_frame(rows: list[dict], questions, max_workers=16) -> list[dict]` (adds `score_error` per failed row; raises `ErrorBudgetExceeded` if failures > 5%)
- Output tables:
  - `gold_deal_scores(opportunity_id PK, p_close_quarter DOUBLE (= score/4), close_label, close_confidence, close_probs MAP<STRING,DOUBLE>, next_action, next_action_conf, next_action_probs MAP, competitive_risk DOUBLE, churn_risk DOUBLE, scored_at, score_error)`
  - `gold_lead_scores(lead_id PK, fit_score DOUBLE (0–1), fit_label, route_to, route_conf, scored_at, score_error)`
- Auth in the job: `WorkspaceClient()` → `config.host`, and the token via `config.authenticate()` header.

- [ ] **Step 1: Write failing unit tests** (mock `requests.post`):
  - `test_build_state_truncates_insights`
  - `test_call_parses_answers` (use the real response recorded on 2026-11-17 from `docs/DECK_POINTS.md` as fixture `tests/unit/fixtures/openjev_response.json`)
  - `test_call_retries_on_429` (two 429s, then 200 → success, 3 posts)
  - `test_call_raises_after_max_attempts`
  - `test_batch_fails_over_error_budget` (6/100 fail → raises)
  - `test_batch_tolerates_under_budget` (4/100 → returns, with 4 `score_error`)
- [ ] **Step 2:** Run. FAIL. Implement. Run. PASS.
- [ ] **Step 3:** `jobs/run_scoring.py` reads open opps + account_360 + insights. It scores only rows whose inputs changed since `scored_at` (compare to `last_activity_at`/insight `extracted_at`), MERGEs into the score tables, and does the same for leads.
- [ ] **Step 4:** Write integration tests `test_all_open_opps_scored` (≥99% non-null `p_close_quarter`) and `test_scores_vary` (stddev of `p_close_quarter` > 0.1).
- [ ] **Step 5:** Add job task `ai_scoring` after `ai_call_insights`. Run it. Tests PASS.
- [ ] **Step 6:** Write `evidence/05_scoring.md`: rows scored, latency p50/p95 per call, total input tokens, the distribution histogram as a text table, and 5 sample Jordan deals with probabilities.
- [ ] **Step 7:** Commit.

### Task 7: Next best actions + score evaluation

**Files:** Create `src/ai/next_best_actions.sql`, `src/ai/evaluate_scores.py`, `jobs/evaluate_scores.py`, and `tests/integration/test_nba.py`.

**Interfaces — Produces:**
- `gold_next_best_actions(action_id PK = sha2(opportunity_id||action_type||source_key), opportunity_id, account_id, owner_id, action_type, title, why, source ENUM('call','model','rule'), due_date, priority_score DOUBLE, status DEFAULT 'open', created_at)`.
- Sources:
  - **call:** each `next_steps` item from the latest insights
  - **model:** `next_action` when `next_action_conf ≥ 0.5`
  - **rules:** stale opp (no activity 21+ days), competitor mentioned + close this quarter, usage drop < −15% over 30d, P1 ticket open
- `priority_score = acv * p_close_quarter * urgency`, where urgency = 1.5 if due ≤7d or the rule is competitor-expiring, 1.2 if ≤14d, else 1.0.
- Feedback (if Task 8's write-back exists): multiply by `(0.5 + acceptance_rate_by_action_type)`, clamped [0.5, 1.5]. This is cut #2 in the spec's cut order.
- `gold_score_eval(run_id, metric, segment, value)` + an MLflow experiment `/Users/<me>/fleetwise-score-eval`.

**Eval method:**
1. Sample 400 closed opps.
2. Build the state using only data dated ≤ `snapshot_date`.
3. Score with the same `openjev.call`.
4. Compute AUC of `p_close_quarter` vs `IsWon`, lift by decile, a calibration table (5 bins), and AUC vs `true_intent` (sanity).
5. Spot-check 20 insight rows: precision/recall of extracted `competitors` vs `planted_competitors`.

- [ ] **Step 1:** Write failing integration tests:
  - `test_nba_ids_unique`
  - `test_jordan_has_actions` (≥10 open)
  - `test_rule_competitor_expiring_present` (≥1 Jordan NBA with `source='rule'` and a competitor `why`)
  - `test_eval_auc_logged` (a `gold_score_eval` row with metric `auc` exists)
- [ ] **Step 2:** Implement. Add job tasks `next_best_actions` (sql) and `evaluate_scores` (python, run on init only via job param `run_eval=true`). Run. PASS.
- [ ] **Step 3:** Write `evidence/06_nba_and_eval.md`: AUC, decile lift table, calibration table, spot-check P/R, and 5 Jordan NBAs. **Record the real numbers whatever they are.** If AUC < 0.65, note it and tune the prompt/state once (document both runs). Copy the headline metrics into `docs/DECK_POINTS.md`.
- [ ] **Step 4:** Commit.

### Task 8: Lakebase serving + write-back

**Files:** Create `src/lakebase/setup_lakebase.py`, `src/lakebase/app_schema.sql`, `src/lakebase/writeback.sql`, and `tests/integration/test_lakebase.py`.

**Interfaces — Produces:**
- Project `seller-superapp`, branch `production`, database `databricks_postgres`, UC catalog `fleetwise_lakebase` (`databricks postgres create-catalog`).
- Synced tables (`databricks postgres create-synced-table`, `scheduling_policy: TRIGGERED`, storage_catalog = main catalog, storage_schema `seller_superapp`) into Postgres schema `serving`. PKs:
  - `account_360` (`account_id`)
  - `opportunity_pipeline` → source is a gold join view `gold_opportunity_app` = pipeline ⨝ deal_scores (`opportunity_id`). If views can't be TRIGGERED, make it a pipeline MV in Task 3's `gold.sql`.
  - `next_best_actions` (`action_id`)
  - `call_insights` (`meeting_id`)
  - `seller_kpis` (`owner_id`, `fiscal_quarter`)
  - `user_hierarchy` (`user_id`)
  - `contacts` ← `gold_contacts_masked` (`contact_id`)
  - `lead_scores` (`lead_id`)
- App schema `app`, created and owned by the **app SP** at app startup (Task 10 runs `app_schema.sql`):
  - `seller_actions(id bigserial PK, action_id text, opportunity_id text, persona_user_id text, decision text CHECK IN ('accepted','done','dismissed'), reason text, created_at timestamptz default now())`
  - `notes(id bigserial PK, opportunity_id text, persona_user_id text, body text, created_at)`
  - `email_drafts(id bigserial PK, opportunity_id text, persona_user_id text, subject text, body text, created_at)`
  - Each has `REPLICA IDENTITY FULL`.
- Write-back, primary: Lakehouse Sync CDF config on Postgres schema `app` → UC `{catalog}.seller_superapp` → `lb_seller_actions_history`, etc. Then `writeback.sql` builds `silver_seller_actions` (latest state per id) and `gold_nba_feedback(action_type, shown, accepted, done, dismissed, acceptance_rate)`.
- Write-back, fallback (if Lakehouse Sync is unsupported on this catalog, e.g. "default storage"): a job task MERGEs `fleetwise_lakebase.app.seller_actions` (federated read via the Lakebase UC catalog) into `silver_seller_actions`. Record which path was used in `evidence/07_lakebase.md` and in the README trade-offs.
- Job task `lakebase_sync`: triggers a refresh of each synced table's pipeline and waits. Job task `writeback_merge` runs `writeback.sql`.

- [ ] **Step 1:** Write failing tests:
  - `test_synced_tables_online` (all ONLINE)
  - `test_pg_row_counts_match_uc` (for each synced table, Postgres count = UC count)
  - `test_pg_point_lookup_fast` (100 lookups of `opportunity_pipeline` by id, p95 < 50 ms from the test runner, recorded)
  - `test_writeback_roundtrip` (insert into `app.seller_actions` via psycopg as the project owner → after sync/merge, the row appears in `silver_seller_actions`; record the elapsed seconds)
- [ ] **Step 2:** Implement `setup_lakebase.py` (idempotent: create-if-missing for the project, catalog, and synced tables; enable CDF on sources first). Run it.
- [ ] **Step 3:** Run the tests (the write-back test runs after Task 10 creates the `app` schema; mark it `@pytest.mark.after_app` and re-run then). The others PASS now.
- [ ] **Step 4:** Add job tasks `lakebase_sync` and `writeback_merge`. Write `evidence/07_lakebase.md`: synced table statuses, count parity, latency numbers, write-back path + round-trip time.
- [ ] **Step 5:** Commit.

### Task 9: Genie Agent

**Files:** Create `src/genie/space.json`, `src/genie/create_space.py`, `src/genie/benchmark.py`, and `src/genie/benchmark_questions.yaml`.

**Interfaces — Produces:**
- Genie space `Fleetwise Revenue Copilot` on warehouse `9a6db1d12e2ee6d3`. Tables: the governed opportunity object (row-filtered table or `v_opportunity_pipeline`), `gold_account_360`, `gold_call_insights`, `gold_deal_scores`, `gold_next_best_actions`, `gold_seller_kpis` / view, `gold_user_hierarchy`, `gold_lead_scores`, `gold_nba_feedback`.
- Instructions:
  - Fiscal year starts Feb 1.
  - ACV = `acv`.
  - "my"/"I" = the caller's persona via `demo_identity_map`. The row filter already scopes it, so never filter by name.
  - "at risk" = `p_close_quarter < 0.4 AND close_date in current fiscal quarter`.
  - "competitive" = `competitive_risk > 0.5 OR size(competitors) > 0`.
- 10 sample questions and 3 trusted SQL examples.
- The space ID is written to `src/genie/space_id.txt` (committed; not secret).
- `benchmark.py` runs 10 questions via the Genie Conversation API → `evidence/08_genie.md` (question, generated SQL, first 5 result rows, latency).

Required benchmark questions (include verbatim):
1. "What is my open pipeline by stage this quarter?"
2. "Which of my deals mention a competitor and close this quarter?"
3. "Show my top 5 deals by ACV times close probability."
4. "Which accounts have usage down more than 15% in the last 30 days and an open opportunity?"
5. "What are the open next steps from my last calls?"

- [ ] **Step 1:** Load skill `databricks-genie-agents`. Write `space.json` and `create_space.py` (idempotent by title). Run.
- [ ] **Step 2:** Run `benchmark.py`. Pass criteria: ≥8/10 questions return SQL + non-empty results, and Q2 results ⊆ Jordan's opps. If it fails, tune the instructions/examples and re-run (keep both runs in evidence).
- [ ] **Step 3:** Commit.

### Task 10: Databricks App — Fleetwise Seller Hub (AppKit)

**Files:** Create `app/fleetwise-seller-hub/` (scaffolded) and an app resource in `databricks.yml`.

**Interfaces:**
- Consumes the Postgres `serving.*` tables (Task 8), Genie space ID (Task 9), serving endpoint `databricks-claude-sonnet-5-5`, and `demo_identity_map` (Task 4).
- Scaffold: `databricks apps manifest`, then `databricks apps init --name fleetwise-seller-hub --features lakebase,genie,serving …` (derive the `--set` keys from the manifest). `user_api_scopes` include `dashboards.genie`, `sql`, and `serving.serving-endpoints`.
- Server routes (Express in `server/server.ts`, Lakebase via the AppKit lakebase plugin). Persona is resolved per request: OBO user email → `demo_identity_map`, cached 30s.

| Route | Returns / effect |
|---|---|
| `GET /api/me` | `{email, persona_user_id, persona_name, role}` |
| `PUT /api/persona {persona:'seller'\|'manager'}` | updates `demo_identity_map` via the SQL warehouse (Statement Execution, OBO) |
| `GET /api/home` | `{kpis, priority_deals[≤15], actions[open, ≤20], freshness_ts}`, scoped to the persona's visible owner_ids (`user_hierarchy`) |
| `GET /api/deals/:id` | opp + account_360 + insights[] + score probs + contacts (masked) + actions + notes |
| `POST /api/actions/:action_id {decision, reason?}` | inserts into `app.seller_actions`; the response includes the updated action list |
| `POST /api/deals/:id/notes {body}` | inserts a note |
| `POST /api/deals/:id/email-draft` | calls the serving endpoint with the latest insights → `{subject, body}`, stored in `app.email_drafts` |
| `GET /api/team` | manager view: per-rep pipeline, at-risk ACV, NBA acceptance (cut #1) |
| `GET /api/health/db` | `SELECT 1` latency |

- Open actions hide anything with a `seller_actions` decision (join in Postgres), so a decision is reflected instantly.
- `freshness_ts` = max `LastModifiedDate` in the served data.
- Genie: AppKit `genie()` plugin, OBO, with the space from `src/genie/space_id.txt`.
- UI (load `databricks-app-design` first):
  - **My Week:** KPI strip; Priority deals table with a probability bar + reason chips; NBA queue with Accept/Done/Dismiss; freshness badge.
  - **Deal 360:** header + stage timeline; score distribution bars; call insights cards; usage sparkline + product adoption/whitespace; tickets; contacts; notes; Draft email modal.
  - **Ask Genie:** full page + a slide-over on My Week and Deal 360.
  - **Team:** manager view.
  - A persona switcher in the header.
  - Explicit empty, loading, and error states on every panel.
  - Visual direction: fleet/ops palette, dense but calm, not template-looking.

- [ ] **Step 1:** Scaffold the app, then **deploy first** (so the SP owns schema `app`). At startup the server runs `src/lakebase/app_schema.sql` (copied into the app) idempotently. Grant the SP `USAGE`/`SELECT` on schema `serving` (Lakebase skill snippet). Grant the SP `SELECT`/`MODIFY` on `demo_identity_map` and `CAN_RUN` on the Genie space.
- [ ] **Step 2:** Write `tests/smoke.spec.ts` (Playwright):
  - My Week shows the "Priority deals" heading and ≥1 deal row for Jordan.
  - Clicking Accept on the first action removes it from the queue.
  - Deal 360 shows a "Next steps" section.
  - Ask Genie returns an answer to "What is my open pipeline by stage this quarter?"
  - With persona `empty-demo`, My Week shows the empty-state text "No open deals".
- [ ] **Step 3:** Implement the routes and UI until `databricks apps validate -p fevm-serverless-stable-s1omq8` passes, including the smoke test.
- [ ] **Step 4:** Deploy (`databricks bundle deploy` + `databricks bundle run fleetwise-seller-hub`). Verify `app_status.state == RUNNING`.
- [ ] **Step 5:** Run `tests/integration/test_lakebase.py -m after_app`. Expected: PASS.
- [ ] **Step 6:** Write `evidence/09_app.md`:
  - deploy output, app status JSON
  - captured JSON responses from `/api/me`, `/api/home`, `/api/deals/<jordan top deal>`, and `POST /api/actions/...` (call with a user token via `curl -H "Authorization: Bearer $(databricks auth token …)"`)
  - an email draft output
  - `/api/health/db` before and after scale-to-zero (wait ≥6 min idle)
  - the smoke test output
- [ ] **Step 7:** Commit.

### Task 11: End-to-end job, incremental run, freshness proof

**Files:** Modify `databricks.yml` (complete job). Create `jobs/collect_evidence.py` and `tests/integration/test_e2e.py`.

**Interfaces:** The job `seller_superapp_daily` task graph, exactly:
`generate_data` → `pipeline_refresh` → `apply_governance` → `ai_call_insights` → `ai_scoring` → `next_best_actions` → `lakebase_sync` → `writeback_merge` → `evaluate_scores` (condition `run_eval == "true"`) → `collect_evidence`.

Job params: `mode` (init|increment), `batch` (int), `run_eval` (bool).

- `collect_evidence.py` writes to `/Volumes/.../evidence/run_<run_id>/` (then copied into `evidence/runs/` locally):
  - row counts for every table
  - `system.access.table_lineage` rows for the schema (a source→target edge list)
  - run timing per task
- Freshness measurement:
  1. Record `t0` when the increment files land (generator writes `_manifest.json` with a timestamp).
  2. Record `t1` when `GET /api/home` returns the incremented `freshness_ts`.
  3. Report `t1 − t0` and the per-task durations.

- [ ] **Step 1:** Write failing `test_e2e.py`:
  - `test_lineage_connects_volume_to_synced_tables`: a path exists in the lineage edges from a `bronze_opportunity` source through `gold_opportunity_pipeline` → `gold_deal_scores` → the synced `opportunity_pipeline`
  - `test_increment_changed_app_data`: after batch 1, ≥1 Jordan opp stage in Postgres equals the stage in the batch 1 raw files
  - `test_rerun_no_duplicates`: re-running batch 1 → identical row counts
- [ ] **Step 2:** Complete the job. Run `mode=init run_eval=true`, then `mode=increment batch=1`, then batch 1 again. Run the tests. Expected: PASS.
- [ ] **Step 3:** Write `evidence/10_e2e.md`: job run IDs and statuses (JSON), task durations, lineage edge list, freshness `t1 − t0` with breakdown, rerun parity.
- [ ] **Step 4:** Copy the measured freshness number into `docs/DECK_POINTS.md`. Commit.

### Task 12: Executed notebooks, README, value model, final push

**Files:** Create:
- `notebooks/01_walkthrough.ipynb`: a guided run of the whole journey, querying each layer for Jordan's top deal (raw file → bronze → silver → gold → insights → score → NBA → Postgres row → Genie answer)
- `notebooks/02_score_evaluation.ipynb`
- `README.md`, `docs/VALUE_MODEL.md`, `docs/AI_FORCE_MULTIPLIER.md`

**Notebook requirements:** Executed on serverless; exported with outputs (`databricks workspace export --format JUPYTER`); committed with outputs visible. Every cell's output is text (tables printed via `display` → also `print(df.toPandas().to_markdown())`).

**README order (exact):**
1. Business problem & quantified value (from VALUE_MODEL)
2. What the seller sees (walkthrough of the 4 screens, with text descriptions and links to evidence/09)
3. The integrated data journey (diagram as Mermaid + "follow one deal through every layer" table, with evidence links)
4. Decisions & trade-offs (spec §5 + what actually happened: write-back path, ai_decide vs OpenJev, templated transcripts)
5. AI as force multiplier (`docs/AI_FORCE_MULTIPLIER.md`: Claude Code session, skills used, prompts, what AI did vs. what I decided)
6. How to run
7. Evidence index (every `evidence/*.md` with a one-line claim it proves)

**VALUE_MODEL.md:** labeled assumptions (public list-price ranges for CRMA/C360 add-on seats per user per month; seller hours saved on pre-call prep per week; loaded seller cost per hour) × 600 sellers. Plus Databricks run cost estimated from the actual job duration × DBU and the Lakebase CU-hours. Plus measured AI metrics (AUC/lift → illustrative win-rate uplift on scored pipeline, labeled as an assumption). Show the formula and the inputs for every number.

- [ ] **Step 1:** Build and run the notebooks on the workspace, export them, and commit.
- [ ] **Step 2:** Write VALUE_MODEL, AI_FORCE_MULTIPLIER, and README.
- [ ] **Step 3:** Scrub check: `git grep -i -n "<real customer name>"` returns nothing; no tokens/PATs (`git grep -n -E "dapi[0-9a-f]{32}|gho_"` empty).
- [ ] **Step 4:** Run the full test suite `pytest -v`. Expected: all PASS. Paste the summary into `evidence/11_tests.md`.
- [ ] **Step 5:** Commit and push. Update `docs/BACKLOG.md` with anything left open (e.g. the AI Decide preview, the repo readability check).
