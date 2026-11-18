# Backlog

- [x] ~~Verify AI functions on serverless.~~ 2026-11-17, Demo Warehouse `9a6db1d12e2ee6d3`: `ai_query` ✅ works.
- [ ] **Enable "AI Decide" preview** (workspace admin → Previews). `ai_decide` currently fails with
  `PERMISSION_DENIED: AI Decide Preview is not enabled`. Until it's enabled, scoring calls OpenJev
  (`databricks-openjev-qwen35-4b`) directly through the System One API, which is already proven working.
- [ ] **Before submitting:** confirm the FE Bar form can read the private repo (connect GitHub on the form). If it can't, make it public after a scrub.
- Warehouses: use **Demo Warehouse `9a6db1d12e2ee6d3`** for SQL, Genie, and the app. The RT Warehouse is out of scope and rejects AI functions.
  The Serverless Starter Warehouse was failing to launch.
- [ ] **Roleplay docs (Google Docs; links in docs/roleplay/GOOGLE_DOCS.md):** fill the 14 `[[placeholders]]` from evidence once Tasks 6–11 land. Re-check Jordan's KPIs after the R12 quota fix. Frame AUC as "pipeline works against planted truth", not real-world accuracy. Name Postgres RLS as the production path for Lakebase scoping, and call the persona switcher demo-only.
