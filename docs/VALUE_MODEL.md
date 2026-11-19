# Value model: Fleetwise Seller Hub

Every number below is either **(A) an assumption** (labeled, with its source or rationale) or
**(M) measured** in this build (with the evidence file). The pilot's job is to replace each (A) with the
customer's own number. Figures match `docs/deck/DECK.md` and `docs/roleplay/CHEAT_SHEET.md`.

## Inputs

| # | Input | Value | Type |
|---|---|---|---|
| I1 | Sellers using revenue-intelligence / C360 add-on seats | 600 | (A) org size from discovery |
| I2 | Add-on list price per user per month | $150 midpoint (public list range $75–$220) | (A) public list-price range for revenue-intelligence / C360-style add-ons |
| I3 | Seller hours saved per week (pre-call prep, CRM hygiene, hunting across tools) | 2 h expected, 1 h conservative | (A) |
| I4 | Working weeks per year | 46 | (A) |
| I5 | Hours per FTE-year | 2,000 | (A) |
| I6 | Worked pipeline per year | ~$600M ACV | (A) |
| I7 | Win-rate uplift on scored pipeline | +1 pt expected, 0 conservative | (A) illustrative, to prove in pilot |
| I8 | Build + pilot cost | ~$150K (2 engineers × 12 weeks) | (A) |
| I9 | Platform run cost at full scale | ~$200K/yr (range $150K–$250K) | (A), cross-checked against the measured run cost below |
| M1 | Deal-score AUC on held-out closed deals | 0.695 (top-decile lift 2.06×) | (M) `evidence/06_nba_and_eval.md`, against planted synthetic truth |
| M2 | Data freshness: raw file landed to visible in the app | **9.0 min** (540.6 s) vs ~2-hour batch today | (M) `evidence/10_e2e.md` |

## Levers

| Lever | Formula | Conservative | Expected |
|---|---|---|---|
| 1. Retire add-on seats (hard savings) | I1 × I2 × 12 | 600 × $75 × 12 = **$0.54M/yr** | 600 × $150 × 12 = **$1.08M/yr** (high end at $220: $1.58M) |
| 2. Seller time back (capacity) | I1 × I3 × I4; ÷ I5 | 600 × 1 × 46 = 27,600 h ≈ 14 FTE | 600 × 2 × 46 = **55,200 h ≈ 27 FTE** |
| 3. Win more pipeline (upside, not banked) | I6 × I7 | $0 | $600M × 0.01 = **~$6M ACV/yr** |

Why lever 3 is plausible (still an assumption): the OpenJev deal score ranks deals well enough to
prioritize (M1: the top-scored decile of held-out deals won at 80% vs a 39% base rate). Turning that ranking
into +1 pt of win rate depends on sellers acting on it, which is what the pilot measures (NBA acceptance and
win rate on scored vs. unscored deals). The AUC is measured against **planted synthetic truth**, so it proves
the pipeline works, not real-world accuracy.

## Payback (seats only; time and win rate are not in it)

| Case | Formula | Result |
|---|---|---|
| Expected | (I8 $150K + I9 $200K) ÷ lever 1 $1.08M × 12 months | **≈ 4 months** |
| Conservative | ($150K + $250K) ÷ $0.54M × 12 months | **≈ 9 months** |

Even the conservative case repays build plus first-year run inside year one, on seats alone.

## Measured run cost of this build (estimate)

Labeled **estimate**: DBU quantities come from `system.billing.usage` for this workspace on 2026-11-18
(the build day; billing lags a few hours, so the 2026-11-19 runs aren't in it yet) and from the measured task
durations of the batch-2 run (`evidence/10_e2e.md`). The $/DBU rate is an assumption.

| Component | Basis | DBU per increment run |
|---|---|---|
| Lakeflow pipeline update (serverless) | (M) 6.69 DBU billed over 25 pipeline updates on 2026-11-18 (includes full refreshes, so high) | ~0.27 |
| Python job tasks (generator, OpenJev scoring driver, Lakebase sync driver, evidence) | (M) 0.2–0.9 DBU billed per full job run on 2026-11-18 | ~0.5 |
| SQL tasks on the 2X-Small serverless warehouse (4 DBU/h) | (M) 205 s of SQL tasks inside an 11.4-min run; (A) warehouse billed for the whole run window | ~0.76 |
| Lakebase synced-table pipelines | (M) 0.71 DBU billed over 6 sync updates | ~0.12 |
| **Compute subtotal** | | **~1.65 DBU ≈ $1.15/run** at (A) $0.70/DBU list |
| Lakebase endpoint | (M) 1 CU, scale-to-zero after 300 s; a run keeps it awake ~2 min of sync + 5 min tail ≈ **0.12 CU-hours/run**; app use adds ~1 CU-hour per active hour; billed 0.27 DBU on 2026-11-18 | separate |
| AI model serving (per token) | (M) `ai_query` only extracts **new** calls (40 in batch 2) and OpenJev only re-scores **changed** deals; the day of the initial 640-call extraction billed ~291 model-serving DBU on the Claude endpoint (an upper bound: the endpoint is shared across the workspace) | separate, scales with call volume |

Annualized at an hourly cadence: 8,760 runs × ~$1.15 ≈ **~$10K/yr** of pipeline/job/SQL compute, plus
Lakebase at roughly 3,100 CU-hours/yr (1 CU × 12 h × 260 business days) and AI tokens proportional to new
calls. That is well under the $150K–$250K/yr planning assumption (I9), which stays the number in the
payback math because production adds the full call volume (~600 sellers' calls through `ai_query`), app and
Genie compute, larger Lakebase sizing, and dev/test environments. The pilot replaces I9 with billed
`system.billing.usage` for the pilot cohort.

## What is simulated

Salesforce data is Salesforce-API-shaped export files written by a deterministic generator (production
path: the Lakeflow Connect Salesforce connector); Meet transcripts are templated (no LLM in the
generator); AUC/lift are measured against the generator's planted truth. No real customer data is used.
