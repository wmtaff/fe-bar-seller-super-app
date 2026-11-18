# Backlog

- [x] ~~Verify AI functions on serverless.~~ 2026-11-17, Demo Warehouse `9a6db1d12e2ee6d3`: `ai_query` ✅ works.
- [ ] **Enable "AI Decide" preview** (workspace admin → Previews). `ai_decide` currently fails with
  `PERMISSION_DENIED: AI Decide Preview is not enabled`. Until it's enabled, scoring calls OpenJev
  (`databricks-openjev-qwen35-4b`) directly through the System One API, which is already proven working.
- [ ] **Before submitting:** confirm the FE Bar form can read the private repo (connect GitHub on the form). If it can't, make it public after a scrub.
- Warehouses: use **Demo Warehouse `9a6db1d12e2ee6d3`** for SQL, Genie, and the app. The RT Warehouse is out of scope and rejects AI functions.
  The Serverless Starter Warehouse was failing to launch.
- [ ] **Roleplay docs (Google Docs; links in docs/roleplay/GOOGLE_DOCS.md):** fill the 14 `[[placeholders]]` from evidence once Tasks 6–11 land. Re-check Jordan's KPIs after the R12 quota fix. Frame AUC as "pipeline works against planted truth", not real-world accuracy. Name Postgres RLS as the production path for Lakebase scoping, and call the persona switcher demo-only.
- [ ] **Deck + roleplay sync** (deck: docs/deck/README.md). After Task 3 round 2 (v4 data) and Tasks 6–11:
  - Refresh Jordan's KPIs ($1.24M / 29.3% / 3.5x came from v3) and fill the 7 deck placeholders.
  - In TALK_TRACK/CHEAT_SHEET: replace the "12.38x" note and the KPI placeholders with real values.
  - Fix QA T11 test counts (27 unit / 11 integration and growing), and align QA B4 ("by week 3") with the talk track (weeks 4–6).
  - Create docs/VALUE_MODEL.md (Task 12) using the deck's assumptions, including the conservative column (~9-month payback).
- [ ] **Masked silver is what the pipeline reads (Task 4).** `silver_contacts` and `silver_leads` carry UC column masks, and the pipeline runs as a principal outside any unmasking group, so every downstream pipeline table sees masked email/phone (`f***@domain`, `***-***-1234`). Any future join or dedupe on raw email/phone (e.g. matching transcript attendees to contacts) must read `bronze_contact` / `bronze_lead` instead, inside the pipeline.
