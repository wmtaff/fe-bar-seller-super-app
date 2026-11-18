# Fleetwise Seller Hub – Demo Cheat Sheet (FE Bar)

## The 3 value numbers (assumptions, arithmetic shown)

| Lever | Number | Arithmetic |
|---|---|---|
| Retire add-on seats (hard) | **~$1.08M/yr** (range $0.54M–$1.58M) | 600 sellers × $150/user/month (list range $75–$220) × 12 |
| Seller time back | **~55K hrs/yr ≈ 27 sellers of capacity** | 600 × 2 hrs/week × 46 weeks; ÷ 2,000 hrs/FTE |
| Win more pipeline (upside) | **~$6M ACV/yr** | +1 pt win rate × ~$600M worked pipeline |

Run cost assumption: ~$150K–$250K/yr → **payback under 6 months on seats alone.**

## 30-second pitch

"Fleetwise pays per seat for overlapping revenue-intelligence, forecasting and email tools across 600 sellers, and the dashboards are two hours stale and take 90 seconds to load. The Seller Hub puts Salesforce, Meet call insights, product usage and tickets on one governed Databricks platform, adds AI that reads every call and scores every deal with calibrated probabilities, and serves it to sellers in milliseconds from Lakebase, with a Genie copilot for any question. That's about $1M a year in seats, about 2 hours a week back per seller, and a path to a point of win rate. Let's prove it in a six-week, 40-seller pilot."

## 5-step click path

1. **My Week (Jordan Rivera):** freshness badge → KPI strip (≈`[[29%]]` attainment, ≈`[[3.5x]]` coverage) → Priority deals with "why" chips.
2. **Deal 360 (top deal):** AI score + distribution → call insights (**RoadLynx** mention not in CRM) → usage drop → open P1 → masked contacts.
3. **Accept an NBA:** click Accept → instant state change (Lakebase write) → "MERGEs back to Delta on the next run."
4. **Ask Genie:** "Which of my Enterprise deals mention a competitor and close this quarter?" → Show SQL → "only Jordan's deals: row filters via on-behalf-of-user auth."
5. **Manager view (Morgan Lee) → Lineage:** at-risk deals + NBA adoption by rep → Catalog Explorer lineage from volume to app tables.

Opening must-do: ask **each** persona what they need. Closing must-do: repeat their words back, propose the pilot, ask for the decision date.

## Top 5 objections, one-liners

| Objection | One-liner |
|---|---|
| "Why pay Databricks on top of Salesforce?" | "It's instead of the add-ons, not on top: about $1.08M of seats out, about $200K of platform in, and Salesforce stays the system of record." |
| "Homegrown app risk / who maintains it?" | "It's a thin app on managed services, all in one bundle in Git. RevOps owns the product, your platform team owns the pipelines." |
| "Can I trust the AI?" | "We measure it on held-out deals (AUC `[[AUC]]`), every output shows its why, and Genie shows its SQL." |
| "Synced tables don't carry UC row filters." | "Right, by design: PII is masked before it reaches Postgres, the app scopes queries by the same hierarchy, and Postgres RLS is the production hardening step." |
| "How do you get Salesforce data in production?" | "Lakeflow Connect's Salesforce connector, read-only and incremental. Our exports match the API schema, so silver and gold don't change." |

## Placeholders to fill before the roleplay

| # | Placeholder | Source |
|---|---|---|
| 1 | `[[AUC]]` | `evidence/score_eval.md` |
| 2 | `[[top-decile lift]]` | `evidence/score_eval.md` |
| 3 | `[[extraction precision/recall]]` | `evidence/call_insights.md` |
| 4 | `[[freshness]]` minutes | `evidence/freshness.md` |
| 5 | `[[Lakebase p95 read ms]]` | `evidence/lakebase.md` |
| 6 | `[[write round-trip ms]]` | `evidence/lakebase.md` |
| 7 | `[[job cost per run]]` | `evidence/job_cost.md` (`system.billing.usage`) |
| 8 | `[[ai_query cost per transcript]]` | `evidence/job_cost.md` |
| 9 | `[[OpenJev cost per scored opp]]` | `evidence/job_cost.md` |
| 10 | `[[Genie benchmark x/N]]` | `evidence/genie.md` |
| 11 | `[[Genie answer seconds]]` | `evidence/genie.md` |
| 12 | `[[Jordan attainment ≈29%]]` | `gold_seller_kpis` after the R12 re-run |
| 13 | `[[Jordan coverage ≈3.5x]]` | Same re-run (committed evidence still says 12.38x) |
| 14 | `[[example deal P(close)]]` | `gold_deal_scores` / `evidence/app.md` |
