# FE Bar submission form answers

## Customer name
Fleetwise (anonymized fleet-telematics SaaS company; all data is synthetic)

## Industry / vertical
Technology / B2B SaaS: IoT fleet telematics (Revenue Operations / sales productivity)

## What is the business challenge you are solving?
Fleetwise has about 600 sellers who run their day out of Salesforce Customer 360 plus a per-seat revenue-intelligence
add-on (CRMA). That setup has three problems:
- **Expensive seats:** every seller needs an add-on seat, about $1.08M a year at list price. Forecasting, revenue views
  and email drafting each need yet another tool.
- **Stale, slow analytics:** dashboards refresh on roughly 2-hour batch schedules, and heavy aggregations take about 90
  seconds.
- **Signal outside the CRM:** what customers say on Google Meet sales calls (competitors, objections, next steps) isn't
  in the CRM. Neither are product usage and support tickets. Sellers stitch these together by hand before every call,
  and managers forecast on incomplete data.

The goal is to consolidate the seller experience onto Databricks as the single data foundation. That retires the add-on
seats, gives sellers fresh, governed, AI-prioritized data, and returns time to selling.

## How does your Databricks solution address this challenge?
**Fleetwise Seller Hub** is a Databricks App that gives each seller one governed, AI-prioritized view of their book. It
runs on a single connected data journey. The same deal entities flow through every layer (account → opportunity →
call transcript → AI insight → score → next-best action → seller decision):

1. **Lakeflow (ingest and transform).**
   - A deterministic generator lands SFDC-shaped exports in a UC Volume: User, Account, Contact, Opportunity, history,
     Lead, Task and Event. Alongside them go Google Meet transcripts, product usage telemetry and support tickets.
   - A Lakeflow Spark Declarative Pipeline builds bronze → silver → gold:
     - Auto Loader streaming ingest
     - AUTO CDC for latest-by-Id opportunities
     - expectations on keys, amounts and dates
     - gold materialized views for account 360, opportunity pipeline, seller KPIs, user hierarchy and masked contacts
   - One Lakeflow Job orchestrates the whole thing incrementally: generate → governance → pipeline → AI → NBA →
     Lakebase sync → write-back → evidence.
2. **Unity Catalog (govern).**
   - Dynamic views give row-level security per seller, manager and RVP. They're driven by the user hierarchy and a
     persona identity map.
   - Column masks cover contact and lead email and phone.
   - PII is tagged (`contains_pii` plus system classification tags), and every gold table has comments for Genie.
   - CDF is on for sync, and lineage runs end to end.
   - Grants go only to the app's service principal: views only, verified with a second-principal test.
3. **ML / GenAI (make it intelligent).**
   - `ai_query` with Claude Sonnet extracts structured insights from every call: summary, next steps (owner and due
     date), open items, product interests, competitors, objections, sentiment and stakeholders. It runs incrementally:
     only new or changed transcripts are processed.
   - **OpenJev (Qwen 3.5 4B)** via the System One API scores every open deal: close-this-quarter probability, best next
     action, and competitive and churn risk. It also scores every open lead for fit and routing. Answers are calibrated
     probabilities with 0 output tokens.
   - These feed ranked **next-best actions**, prioritized by ACV × P(close) × urgency, with stable IDs. A feedback
     multiplier learns from seller accept/dismiss decisions.
   - The scores were evaluated honestly on 400 held-out closed deals, rebuilt as of a pre-close snapshot, and logged to
     MLflow.
4. **Lakebase (operational serving).**
   - A Lakebase Autoscaling Postgres 17 project gets 8 gold/AI tables as UC → Postgres synced tables, for
     millisecond app reads (6.3 ms over the network baseline).
   - Seller decisions and notes are written to Postgres and flow back to Delta through **Lakehouse Sync** (CDC). From
     there they feed `gold_nba_feedback` and re-rank the next run. Measured round trip: 59 s.
5. **Genie Agent.** "Fleetwise Revenue Copilot" sits over the row-scoped views only, with instructions, joins and
   trusted SQL. It's used standalone and embedded in the app with on-behalf-of-user auth, so "my pipeline" means the
   caller's book. Benchmark: 9 of 10 questions answered correctly.
6. **Databricks App (AppKit).** "Fleetwise Seller Hub" has three screens:
   - **My Week:** KPIs, priority deals with probability bars, and a next-best-action queue with Accept/Done/Dismiss
     write-back.
   - **Deal 360:** the score distribution, call insights, account usage and whitespace, masked contacts and notes.
   - **Ask Genie.**

   A persona switcher moves between seller and manager. Everything deploys via Asset Bundles and scripts, on
   serverless.

## What AI tools did you use, and what was your workflow? What decisions and trade-offs did you have to make for your build?
**Tools and workflow:**
- **Tools:** Claude Code (Opus) with Databricks skills (pipelines, jobs, Lakebase, apps, Genie, UC, AI functions) and
  Google Workspace skills.
- **Workflow:**
  1. Brainstorm the use case from a real engagement, anonymized.
  2. Write a design spec, reviewed by a "builder check" subagent.
  3. Write a 12-task implementation plan.
  4. Execute it subagent by subagent. Each task got a fresh implementer agent, with test-first development and small
     commits, plus an independent reviewer agent against the spec.
  5. Run a final whole-branch review at the end.
- **My role:** I owned the decisions. These included the customer problem, keeping Lakehouse RT out of scope, a private
  repo, mask-only PII, "simple but best practices", and switching to speed mode late in the build. The AI implemented,
  tested and deployed against the live workspace.
- **What the AI reviewers caught that I would have shipped:**
  - an evaluation leak through a CRM field back-filled at loss time, which inflated AUC
  - row-level-security bypass gaps: no grants, raw PII upstream, an unfiltered account table
  - a circular quota calibration
  - increments wiping CRM next steps
  - lead-outcome leakage into the truth set
  - a view DDL that silently dropped the app's grants on every job run

**Key decisions and trade-offs:**
- **Simulated Salesforce exports + Auto Loader** instead of a live Lakeflow Connect connector: there's no Salesforce org
  for the demo. Lakeflow Connect is the production path.
- **A generative model for language, a classifier for decisions:** `ai_query` (Claude) extracts call insights, and
  OpenJev produces calibrated, zero-output-token scores. `ai_decide` was blocked by a disabled preview, so the System
  One API is called directly.
- **The JSON schema goes in the prompt and is validated in SQL,** because the endpoint rejects `responseFormat`. Failed
  rows are captured, not dropped.
- **Row filters on dynamic views, not base tables,** so gold can sync to Lakebase. Synced tables don't carry UC
  row-level security, so the app scopes every query by persona, and Genie sees only the views.
- **Lakebase synced tables plus Lakehouse Sync** instead of the app querying a warehouse: millisecond reads and OLTP
  writes with governed lineage back to Delta. Materialized views sync as SNAPSHOT because TRIGGERED isn't supported on
  them.
- **Incremental, rebuild-safe processing everywhere:** MERGE on stable keys, change detection, and orphan deletes, so
  AI only runs on changed data.
- **Templated, deterministic transcripts with planted ground truth,** so extraction and scoring can be measured. The
  trade-off is less natural conversation and an AUC measured against synthetic truth.
- **Scope cut in speed mode:** the Manager team view and email drafting moved to the roadmap.

## What are the business outcomes and impact?
- **$1.08M a year in hard savings** from retiring ~600 revenue-intelligence/C360 add-on seats (conservative $0.54M,
  high $1.58M at list price). Payback is about 4 months on seats alone, or about 9 months in the conservative case,
  against ~$150K build/pilot and ~$200K a year run cost.
- **About 55,000 seller hours a year returned (about 27 FTE)** at 2 hours/week saved on pre-call prep and tool-hopping:
  insights, scores and next steps arrive pre-assembled per deal.
- **About $6M ACV a year of upside** from +1 point of win rate on ~$600M of worked pipeline. This is not banked; the
  pilot proves it. It's supported by the deal score's ranking power: the top-scored decile of held-out deals won 80%
  vs a 39% base rate (2.06× lift, AUC 0.695).
- **Fresher data for forecasting:** raw data to the seller's screen in 9 minutes, measured end to end, vs ~2-hour batch
  today. Seller decisions are back in the lakehouse in about a minute.
- **One governed platform instead of tool sprawl:** row-level security matching seller/manager scope, masked PII,
  lineage from raw file to app, and no CRM API rate limits.
- **Run cost measured at about $1.15 per incremental pipeline run** (~1.65 DBU) on serverless, plus Lakebase
  scale-to-zero.

All value-lever inputs are labeled assumptions in `docs/VALUE_MODEL.md`. Measured numbers are in `evidence/`.

## GitHub repo link
https://github.com/wmtaff/fe-bar-seller-super-app
