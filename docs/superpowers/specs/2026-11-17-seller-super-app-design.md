# Seller Super App — Design

**Status:** draft for approval · **Date:** 2026-11-17 · **Owner:** Will Taff
**Purpose:** FE Bar build submission (see `docs/FE_BAR_REQUIREMENTS.md`). Deck points are logged in `docs/DECK_POINTS.md`.

## 1. Intent and the why

**Customer (fictional, anonymized):** *Fleetwise*, a fleet-telematics SaaS company (vehicle gateways, AI dash cams,
driver safety, fuel/maintenance, compliance) with **~600 sellers**. It mirrors a real FE engagement. The repo contains
no real customer names, data, or identifying content. All data is synthetic.

**Problem:** Sellers work out of Salesforce Customer 360 + revenue intelligence (CRMA):
- **Per-seat licenses** across ~600 sellers, plus separate tools for forecasting, revenue tabs, and email drafting.
- **Stale, slow analytics:** batch refreshes (~2 h), heavy aggregations ~90 s.
- **Siloed signal:** call transcripts (Google Meet), product usage, and support tickets live outside the CRM. Sellers
  stitch them together by hand before every call.

**Solution:** one Databricks-native **Seller Super App**. Salesforce data and transcripts are ingested by Lakeflow,
governed in Unity Catalog, and enriched with GenAI (next steps, open items, interests) plus an AI classifier
(deal and lead scores with probabilities). They're served at millisecond latency from Lakebase and are queryable in
plain English through a Genie Agent. Seller actions in the app write back to Lakebase and flow back into the
lakehouse, closing the loop.

**Success for the FE Bar:** an evaluator reading only text sees one *connected* data journey on the **same
entities** (account → opportunity → transcript → score → action) through all six layers. It has execution evidence
committed as text, a quantified value story, and documented trade-offs.

## 2. Goals, non-goals, anti-goals

**Goals**
1. End-to-end, integrated: Lakeflow → UC → AI → Lakebase → Genie → App, with UC lineage proving the connections.
2. A demo-worthy app a seller would want to open on Monday morning.
3. AI that is measurable: scores evaluated against held-out synthetic ground truth (AUC / lift), not only "looks plausible."
4. Text-readable execution evidence for every layer, committed in the repo.
5. Reproducible: one bundle deploy plus one job run rebuilds everything.

**Non-goals**
- Lakehouse RT (explicitly out of scope; it also rejects AI functions).
- A real Salesforce org or Lakeflow Connect connector run (we simulate Salesforce exports; see trade-offs).
- Production SSO-to-Salesforce-owner identity mapping, performance benchmarking, or a trained forecasting model.
- The deck (built later from `DECK_POINTS.md`).

**Anti-goals (failure even if it "works")**
- Layers present but disconnected (different datasets per layer, or an app reading CSVs).
- Any real customer data or names in the repo.
- A generic, templated-looking app or a feature tour with no business framing.
- Execution claimed but only provable by screenshots.

## 3. Constraints and environment

| Item | Value |
|---|---|
| Workspace / CLI profile | `fevm-serverless-stable-s1omq8` (https://fevm-serverless-stable-s1omq8.cloud.databricks.com) |
| Catalog / schema | `serverless_stable_s1omq8_catalog` / `seller_superapp` (new) |
| Raw landing | UC Volume `serverless_stable_s1omq8_catalog.seller_superapp.raw` |
| SQL warehouse | **Demo Warehouse `9a6db1d12e2ee6d3`** (`ai_query` verified working). Do not use the RT Warehouse or the Starter Warehouse. |
| Compute | Serverless only (pipelines, jobs, notebooks) |
| GenAI model | `databricks-claude-sonnet-5-5` via `ai_query` (use `databricks-claude-haiku-5-5` for bulk transcript generation if cost/latency matters) (extraction, email draft) |
| Classifier | `databricks-openjev-qwen35-4b` via System One API (`POST /ai-gateway/typesafe/v1/systemone`, model `system.ai.openjev-qwen35-4b`). Verified working. `ai_decide` blocked until the "AI Decide" preview is enabled (see `docs/BACKLOG.md`). |
| Repo | **Private** GitHub repo under `will-taff_data` (e.g. `fe-bar-seller-super-app`) |
| Time box | ~4–8 h build |

## 4. Architecture (decided)

```
 synthetic generator ──► UC Volume /raw (SFDC-export CSV/JSON, Meet transcripts JSON, usage, tickets)
        │
        ▼  Lakeflow Spark Declarative Pipeline (Auto Loader, expectations)
   bronze_* ──► silver_* ──► gold_* ──────────────────────────────┐
        │                         │                               │
        │                         ▼ Lakeflow Job tasks (serverless)│
        │            ai_query → gold_call_insights                │
        │            OpenJev  → gold_deal_scores, gold_lead_scores│
        │            gold_next_best_actions                       │
        │                         │                               │
        ▼                         ▼                               ▼
  Unity Catalog: tags, comments, row filters, column masks, lineage   Genie Agent (gold tables)
                                  │                                          │
                    Lakebase synced tables (UC → Postgres)                   │
                                  │                                          │
                     Databricks App (reads Lakebase, writes app.* tables) ◄──┘ (Genie Conversation API)
                                  │
          app.* writes ─► UC (Lakebase catalog) ─► job MERGE ─► silver_seller_actions ─► gold (feedback metrics)
```

### 4.1 Synthetic data (raw)
The generator is a Python script committed in the repo, run as the first job task or locally with outputs uploaded.
It uses a fixed seed. Shapes follow Salesforce API names (`Id` 18-char, `OwnerId`, `StageName`, `Amount`, `CloseDate`,
`IsClosed`, `IsWon`, …) so the ingest looks like a real SFDC export.

| Dataset | Approx. size | Notes |
|---|---|---|
| `User` + role hierarchy | ~600 sellers + ~60 managers + ~8 RVPs | Segments: SMB / Mid-Market / Enterprise; regions |
| `Account` | ~5,000 | Industry verticals (construction, logistics, field services, public sector, food & bev), fleet size |
| `Contact` | ~20,000 | Email/phone → PII-tagged and masked |
| `Opportunity` + `OpportunityHistory` | ~15,000 (≈3,000 open) | ACV, products (Vehicle Telematics, AI Dash Cams, Driver Safety, Fuel & Maintenance, Compliance/ELD, Equipment Monitoring), competitor field |
| `Lead` | ~4,000 | Inbound leads with source, title, fleet size, notes (for lead scoring) |
| `Task` / `Event` (activities) | ~60,000 | Calls, emails, meetings |
| Meet transcripts (JSON) | ~600 calls on open + recent closed opps | Speaker turns, attendee emails, opp/account IDs. Generated with an LLM from templates seeded by each opp's hidden truth (buying signals, objections, competitor mentions). |
| Product usage telemetry | daily × 90 days per customer account | Active vehicles, feature adoption per product, logins |
| Support tickets | ~8,000 | Severity, product, status, CSAT |

**Hidden ground truth:** every opp and lead gets a latent "true intent" the generator uses to decide its outcome and
to color its transcripts and usage. Closed opps are labeled. This lets us measure scoring quality honestly.
The truth columns are written to a separate `_truth` file that is *not* fed to the AI (`raw/_eval/`).

### 4.2 Lakeflow (ingest + transform)
- **Lakeflow Spark Declarative Pipeline** (SQL or Python, builder's choice). Auto Loader streaming tables read the
  Volume into `bronze_*`, then `silver_*` (typed, deduped, conformed IDs, expectations with `expect_or_drop` on keys
  and dates), then gold materialized views:
  - `gold_user_hierarchy` (seller → manager → RVP)
  - `gold_account_360` (firmographics, ARR, products owned, whitespace, usage trend, open tickets, last touch)
  - `gold_opportunity_pipeline` (open/closed opps with stage age, days-to-close, activity recency)
  - `gold_seller_kpis` (quota, attainment, pipeline coverage, commit, by seller and quarter)
- **Lakeflow Job** `seller_superapp_daily` (serverless) orchestrates:
  `generate_data` → `pipeline_refresh` → `ai_call_insights` → `ai_scoring` → `next_best_actions` →
  `lakebase_sync` (synced-table refresh) → `writeback_merge` → `evaluate_scores` → `collect_evidence`.

### 4.3 Unity Catalog (govern)
- Table and column **comments** everywhere (these also power Genie), plus a **tag** `pii` on contact email/phone.
- **Column masks** on contact email and phone: visible only to group `superapp_revops`. Everyone else sees `j***@domain.com`.
- **Row filter** on gold opportunity/account tables. A seller sees rows they own. A manager or RVP sees their
  hierarchy (via `gold_user_hierarchy` + a `demo_identity_map` that maps workspace users to demo personas).
  Admins see all.
- Lineage: Volume → bronze → silver → gold → AI tables → synced tables is visible in Catalog Explorer, and it is
  exported as text evidence from `system.access.table_lineage`.

### 4.4 Intelligence (ML / GenAI)
1. **Call insights (GenAI):** `ai_query` with a structured `responseFormat` JSON schema over each transcript →
   `gold_call_insights`: summary, next_steps[] (owner, due), open_items[], customer interests (product list),
   competitors mentioned, objections, sentiment, stakeholders + roles.
2. **Deal scoring (classifier):** OpenJev System One over each open opp. The state is opp fields + account usage
   trend + ticket health + latest call insights. Questions:
   - `close_this_quarter` (score, 5 levels)
   - `next_action` (choice: send_proposal / multithread / schedule_demo / exec_sponsor / address_risk / nurture)
   - `competitive_risk`, `churn_risk` (noul)

   Stores the score, confidence, and full probabilities → `gold_deal_scores`.
3. **Lead scoring:** OpenJev over `Lead`. `conversion_fit` (score) + `route_to` (choice: segment) → `gold_lead_scores`.
   If the AI Decide preview gets enabled, swap in `ai_decide` in SQL (same question JSON).
4. **Next best actions:** `gold_next_best_actions` merges transcript next steps, the classifier's next_action, and
   rules (stale opp, expiring competitor quote, usage drop). Each action is ranked by `ACV × P(close) × urgency`,
   with a one-line "why."
5. **Follow-up email draft (on demand in app):** `ai_query`/serving call grounded on the account's latest insights.
   This replaces a separate email tool.
6. **Evaluation:** on closed opps/leads (scored as of their pre-close snapshot), compute AUC, lift by decile, and
   calibration vs ground truth. Results are logged to an MLflow run and written to `gold_score_eval` and
   `evidence/score_eval.md`. Extraction quality: spot-check ~20 transcripts against the generator's planted
   signals (precision/recall of planted competitors and next steps).

### 4.5 Lakebase (operational serving + write-back)
- One **Lakebase Postgres** instance/project `seller-superapp` (autoscaling preferred, provisioned acceptable).
- **Synced tables** (UC → Postgres, triggered after each job run): `account_360`, `opportunity_pipeline` (joined
  with scores), `next_best_actions`, `call_insights`, `seller_kpis`, `user_hierarchy`.
- **App-owned tables** (native Postgres, schema `app`): `seller_actions` (NBA accepted/dismissed/done + reason),
  `notes`, `tasks`, `email_drafts`.
- **Write-back:** the Lakebase database is registered as a UC catalog. The `writeback_merge` job task MERGEs `app.*`
  into `silver_seller_actions` / `silver_seller_notes` → `gold_nba_feedback` (acceptance rate by action type, which
  feeds the next run's ranking). If a managed Lakebase→Delta sync feature is available, prefer it and document it.

### 4.6 Genie Agent
- A Genie space "Fleetwise Revenue Copilot" over the gold + AI tables, with:
  - join definitions and text instructions (fiscal calendar, ACV definition, "my pipeline" = owner hierarchy)
  - ~10 sample questions and a few trusted SQL examples
- It's used **standalone** and **embedded in the app** through the Genie Conversation API.
- Evidence: a scripted run of ~10 benchmark questions with generated SQL + results committed as text.

### 4.7 Databricks App — "Fleetwise Seller Hub"
The app reads from **Lakebase** (fast paths) and **Genie** (questions). It writes to Lakebase `app.*`.
Demo persona switcher: **Seller** (AE "Jordan Rivera") and **Manager**.

Screens:
1. **My Week (home):** greeting + data freshness ("updated 4 min ago"); a KPI strip (quota attainment, open
   pipeline, commit, at-risk ACV); **Priority deals** ranked by `ACV × P(close)` with probability bars and reason
   chips; a **Next best actions** queue with Accept / Done / Dismiss (writes to Lakebase, so the next screen
   refresh reflects it immediately).
2. **Deal / Account 360:**
   - header and stage timeline
   - AI score with the probability distribution and "why"
   - latest-call insights: next steps, open items, interests, competitors
   - usage sparkline + adoption by product (whitespace)
   - support tickets
   - contacts (masked unless RevOps)
   - notes
   - **Draft follow-up email** button
3. **Ask Genie:** a chat panel (also docked on screens 1–2) for questions like "Which of my Enterprise deals
   mention a competitor and close this quarter?"
4. **Manager view:** team roll-up, at-risk deals across reps, NBA adoption by rep (from write-back feedback).

Visual direction: polished, not template-looking. Fleet/ops-flavored palette, dense but calm data UI.

### 4.8 Deployment and evidence
- **Databricks Asset Bundle** for the pipeline, job, and app. Scripts (Python SDK/CLI) for anything the bundle can't
  express (Lakebase synced tables, Genie space, UC grants/filters/masks, if needed).
- **Evidence (text, committed):**
  - notebooks committed *with outputs* (`.ipynb` exported after run)
  - `evidence/` containing pipeline update event log summary, job run JSON + task outputs, row counts per table,
    sample rows of each gold/AI table, lineage export, row-filter/mask demonstration queries, score eval metrics,
    Genie Q&A transcripts, app deploy logs + API responses (curl of app endpoints), Lakebase read/write round-trip log
- **README** order: business problem & quantified value → demo walkthrough → architecture/data flow →
  decisions & trade-offs → AI-as-force-multiplier (how Claude Code was used, prompts/patterns) → how to run → evidence index.

## 5. Decisions & trade-offs (decided so far)
| Decision | Why | Alternative |
|---|---|---|
| Simulate Salesforce with SFDC-shaped exports + Auto Loader | No Salesforce org; keeps the ingest real (streaming, schema evolution, expectations) | Lakeflow Connect Salesforce connector: production path, called out in README |
| Generative model for extraction, OpenJev classifier for scoring | Language needs generation; decisions need calibrated probabilities. OpenJev returns 0 output tokens → cheap/fast | One LLM for both: costlier, uncalibrated |
| Lakebase for app reads/writes | Millisecond point lookups + OLTP writes for seller actions; synced tables avoid custom ETL | App querying a warehouse directly: slower, no OLTP writes |
| Write-back via Lakebase UC catalog + MERGE | Closes the loop with governed lineage | App writing to Delta via SQL: chattier, not operational |
| Row filters in UC; app scoping in Postgres queries | Synced tables don't carry UC row filters, so the app enforces owner scoping in its queries | Per-user Postgres RLS (future) |
| Anonymized fictional customer | FE Bar forbids customer-identifying content | Name the real customer |

## 6. Calls made after design review (builder's calls; Will can override)
1. **Identity & persona.** The app uses **on-behalf-of-user auth** for Genie and SQL, so UC row filters see the real
   viewer (`current_user()`). `demo_identity_map` maps the viewer's workspace email to a persona (`Jordan Rivera`
   seller, or `Morgan Lee` manager). The app's persona switcher updates the viewer's row in that map (app SP has
   MODIFY on that one table). Lakebase reads are scoped in the app's queries using the same persona → owner IDs, so
   app pages and embedded Genie always agree. **Masking:** contacts in Lakebase are synced from a pre-masked view
   (`gold_contacts_masked`), so the app never holds raw PII. The UC column mask on `silver_contacts` is
   demonstrated with evidence queries as both a masked and an unmasked principal. There's no RevOps persona in the app.
2. **Must-haves vs cut order.** Must-have: one connected journey through all six layers on the same entities, with
   evidence. That covers ingest → gold → call insights + deal scores → NBA → Lakebase sync → Seller home + Deal 360
   with NBA write-back → Genie (standalone + embedded) → score eval. If time runs short, cut in this order:
   (1) Manager view, (2) feedback loop into ranking (keep write-back + MERGE, drop re-ranking), (3) lead scoring,
   (4) extraction spot-check, (5) Genie docked on every screen (keep one Ask Genie page).
3. **Incremental, not rebuild.** The generator has two modes: `--init` (full history, fixed seed) and `--increment`
   (a new batch of changes with stable IDs: stage changes, new activities, new calls, a new day of usage) written
   as *new* files, so Auto Loader picks up only new data. The job runs init once, then increments. Freshness is
   **measured** by timing one increment end to end (file landed → visible in the app via Lakebase), recorded in
   `evidence/freshness.md`. The pipeline runs triggered, not continuous, to save cost; continuous is a config flip,
   noted in trade-offs.
4. **Repo.** Private under `will-taff_data` (Will's decision). The submission form supports connecting GitHub for
   private EMU repos, so that check is a backlog item before submitting. No workspace IDs or URLs go in code; they go
   in bundle variables / `.env.example`.
5. **Value numbers.** Only *stated assumptions* using public list-price ranges, plus metrics measured from the build
   (score AUC/lift, freshness, latency). No engagement figures. The value model lives in `docs/VALUE_MODEL.md` with
   every assumption labeled.

## 7. Left to the builder
App framework (AppKit vs FastAPI+React; pick whichever has cleaner Lakebase + Genie support), pipeline language,
exact table columns, transcript-generation prompt and model, NBA ranking formula details, chart library, and Lakebase
autoscaling vs provisioned (based on what works in this workspace).
