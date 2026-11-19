# Fleetwise Seller Hub – Demo Cheat Sheet (FE Bar)

## The 3 value numbers (assumptions, arithmetic shown)

| Lever | Number | Arithmetic |
|---|---|---|
| Retire add-on seats (hard) | **~$1.08M/yr** (range $0.54M–$1.58M) | 600 sellers × $150/user/month (list range $75–$220) × 12 |
| Seller time back | **~55K hrs/yr ≈ 27 sellers of capacity** | 600 × 2 hrs/week × 46 weeks; ÷ 2,000 hrs/FTE |
| Win more pipeline (upside) | **~$6M ACV/yr** | +1 pt win rate × ~$600M worked pipeline |

Run cost assumption: ~$150K–$250K/yr at full scale (measured at demo scale: ~1.65 DBU ≈ $1.15 per incremental run, ≈ $10K/yr if hourly; estimate) → **payback ≈ 4 months on seats alone** (conservative ≈ 9 months).

## 30-second pitch

"Fleetwise pays per seat for overlapping revenue-intelligence, forecasting and email tools across 600 sellers, and the dashboards are two hours stale and take 90 seconds to load. The Seller Hub puts Salesforce, Meet call insights, product usage and tickets on one governed Databricks platform, adds AI that reads every call and scores every deal with calibrated probabilities, and serves it to sellers in milliseconds from Lakebase, with a Genie copilot for any question. That's about $1M a year in seats, about 2 hours a week back per seller, and a path to a point of win rate. Let's prove it in a six-week, 40-seller pilot."

## 5-step click path

1. **My Week (Jordan Rivera):** freshness badge → KPI strip (**35.3%** attainment, **3.5×** coverage, 18 open deals) → Priority deals with "why" chips.
2. **Deal 360 (top deal):** AI score + distribution → call insights (**RoadLynx** mention not in CRM) → usage drop → open P1 → masked contacts.
3. **Accept an NBA:** click Accept → instant state change (Lakebase write) → "lands in Delta in about a minute (59 s measured)."
4. **Ask Genie:** "Which of my Enterprise deals mention a competitor and close this quarter?" → Show SQL → "only Jordan's deals: row filters via on-behalf-of-user auth."
5. **Persona switcher → manager (Morgan Lee) → Lineage:** switch persona; My Week now shows the team's deals (8 reps, 46 open deals) → Catalog Explorer lineage from volume to app tables.

Opening must-do: ask **each** persona what they need. Closing must-do: repeat their words back, propose the pilot, ask for the decision date.

## Top 5 objections, one-liners

| Objection | One-liner |
|---|---|
| "Why pay Databricks on top of Salesforce?" | "It's instead of the add-ons, not on top: about $1.08M of seats out, about $200K of platform in, and Salesforce stays the system of record." |
| "Homegrown app risk / who maintains it?" | "It's a thin app on managed services, all in one bundle in Git. RevOps owns the product, your platform team owns the pipelines." |
| "Can I trust the AI?" | "We measure it on held-out deals (AUC 0.695, top-decile lift 2.06×), every output shows its why, and Genie shows its SQL." |
| "Synced tables don't carry UC row filters." | "Right, by design: PII is masked before it reaches Postgres, the app scopes queries by the same hierarchy, and Postgres RLS is the production hardening step." |
| "How do you get Salesforce data in production?" | "Lakeflow Connect's Salesforce connector, read-only and incremental. Our exports match the API schema, so silver and gold don't change." |

## Measured numbers (from the committed evidence)

| # | Number | Source |
|---|---|---|
| 1 | Deal score AUC **0.695** (400 held-out closed deals) | `evidence/06_nba_and_eval.md` |
| 2 | Top-decile lift **2.06×** (80% vs 38.75% base) | `evidence/06_nba_and_eval.md` |
| 3 | Competitor extraction P/R **1.00 / 1.00** (287 planted mentions) | `evidence/06_nba_and_eval.md` |
| 4 | Freshness **9.0 min** (540.6 s), file landed → Lakebase row the app reads | `evidence/10_e2e.md` |
| 5 | Lakebase lookup **6.3 ms** added over network baseline (0.07 ms server-side; 77.6 ms client p95 from a laptop) | `evidence/07_lakebase.md` |
| 6 | Write-back **59.1 s** app write → Delta (CDC 16.2 s) | `evidence/07_lakebase.md` |
| 7 | Run cost **~1.65 DBU ≈ $1.15** per incremental run (≈ $10K/yr if hourly; estimate) | `docs/VALUE_MODEL.md` |
| 8 | `ai_query` cost: not metered per transcript; upper bound ~291 model-serving DBU for the initial 640-call extraction (shared endpoint); increments only extract new calls | `docs/VALUE_MODEL.md` |
| 9 | OpenJev scoring: ~1,424 input tokens per deal, **0 output tokens** | `evidence/05_scoring.md` |
| 10 | Genie benchmark **9/10** | `evidence/08_genie.md` |
| 11 | Genie median latency **18.5 s** | `evidence/08_genie.md` |
| 12 | Jordan attainment **35.3%** (FY27Q4) | `evidence/09_app.md` |
| 13 | Jordan coverage **3.5×**, 18 open deals | `evidence/09_app.md` |
| 14 | Top deal (Solis Construction) P(close this quarter) **0.86** | `evidence/09_app.md` |
| 15 | Tests: **187 passed, 0 failed, 1 skipped** (the view-grant bug the suite caught was fixed and re-verified) | `evidence/11_tests.md` |
