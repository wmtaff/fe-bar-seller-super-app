# Deck points (running log — build the deck from this later)

## Customer & problem (anonymized: "Fleetwise", fleet-telematics SaaS, ~600 sellers)
Mirrors a real engagement; no real customer data or names in the repo.
- Seller analytics/forecasting/revenue view live in Salesforce revenue intelligence (CRMA) + C360 (per-seat licensed).
- Batch reporting: ~2-hour refresh schedules; heavy aggregation queries ~90 s.
- Freshness: hourly Fivetran plus a live-API patch for ~10–25 opportunity fields (~5–7 min latency today).
- Tool sprawl: forecasting, revenue tabs, and customer email generation are separate tools, each with seat licenses and API rate limits.
- Goal: consolidate onto one Databricks-backed Seller Super App; Databricks becomes the data foundation.

## Value levers to quantify (numbers TBD from synthetic data + assumptions)
- Seat-license retirement: ~600 sellers × CRMA/C360 add-on cost per seat per year.
- Seller time: hours/week spent on pre-call prep, CRM hygiene, and hunting across tools → selling time.
- Win rate / pipeline: prioritizing on AI deal score + next steps → conversion uplift on scored pipeline.
- Freshness: ~2-hour batch → minutes.

## Audiences
- Exec sponsor (CRO / VP RevOps): cost takeout, forecast accuracy, seller productivity.
- Domain owner (RevOps / Sales Systems lead): one app, governed data, no rate limits, fewer tools.
- Technical (data platform lead): UC governance, lineage, Lakebase serving, reverse sync, security.

## Technical proof points collected
- OpenJev (Qwen 3.5 4B, `databricks-openjev-qwen35-4b`, System One API) returns calibrated
  score/choice/yes-no answers with probabilities and **0 output tokens**, so it's cheap and fast for scoring.
  Spike (2026-11-17): close-likelihood score 3.13/4 "Likely" (conf 0.62); next action
  "send_proposal" p=0.89; 287 input tokens.
- Lakehouse RT warehouse rejects AI functions (`ai_query` UNSUPPORTED_FEATURE; `ai_decide` unresolved). So AI enrichment
  runs in the Lakeflow job on serverless compute, not on a warehouse. RT stays out of scope anyway.
- `ai_decide` = the SQL-native wrapper for the same System One question types (model not selectable).

## Objections to prep (collect as we go)
- Biz: cost vs CRMA seats; risk of a homegrown app; time to value.
- Tech: Salesforce data freshness; row-level security parity with SFDC sharing; write-back consistency; AI accuracy.
