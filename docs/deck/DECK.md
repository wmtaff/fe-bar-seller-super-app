# Fleetwise Seller Hub – Business Case (FE Bar)

Text-readable version of the business-audience deck: full slide text plus speaker notes. PDF: `docs/deck/Fleetwise_Seller_Hub_Business_Case.pdf`. Google Slides: see `docs/deck/README.md`.

Fleetwise is a fictional fleet-telematics SaaS company (~600 sellers). All data is synthetic. Competitors named in the data (RoadLynx, FleetCore, Trackwell) are fictional. Values in `[[double brackets]]` are not measured yet; they are listed on slide 15.

Narrative, assumptions and arithmetic match `docs/roleplay/TALK_TRACK.md`, `QA_PREP.md` and `CHEAT_SHEET.md`.

---

## Slide 1. Fleetwise Seller Hub

The business case: ~$1.08M a year in seats out, ~55K seller hours back  
FE Bar · For the CRO / VP RevOps and the Sales Systems lead · November 2026

**Speaker notes:**

> Talk track: 0:00 Opening, setup and agenda check.  
> Thank both personas, set up Fleetwise (fleet telematics, ~600 sellers). Then ask each persona what they need from the half hour and write their words down; repeat them back at the close.  
> Say once: everything shown runs on synthetic, Fleetwise-shaped data. No real customer data.  

---

## Slide 2. The outcome, in Fleetwise's KPIs

Retire overlapping add-on seats, give sellers time back, and win more of the pipeline you already have.

- **$1.08M/yr**: Add-on seats retired (hard savings). Arithmetic: 600 sellers × $150/user/mo × 12; range $0.54M–$1.58M.
- **~55K hrs/yr**: ≈ 27 sellers of selling time (capacity). Arithmetic: 600 sellers × 2 hrs/week × 46 weeks; ÷ 2,000 hrs per FTE.
- **~$6M ACV/yr**: From +1 pt win rate (upside · prove in pilot). Arithmetic: +1 pt × ~$600M worked pipeline; not banked today.

**Run cost ~$150K–$250K/yr (assumption)  ·  Payback ≈ 4 months on seats alone  ·  Time and win rate not in the payback**

**Speaker notes:**

> Talk track: 2:30 The value hypothesis in Fleetwise KPIs.  
> Lead with: these are assumptions, not promises; I show my arithmetic and the pilot replaces each one with a measured number.  
> Lever 1 seats: 600 × $150 × 12 = $1.08M (range $0.54M–$1.58M). We retire the add-ons, not Sales Cloud.  
> Lever 2 time: 600 × 2 × 46 = 55,200 hrs ≈ 27 FTE. Lever 3 win rate: +1 pt on ~$600M ≈ $6M ACV, upside to prove.  
> Payback: ($150K build + $200K run) vs $1.08M ≈ 4 months. Ask the exec: does that match how you'd pitch it to your CFO?  

---

## Slide 3. Today: paying per seat for signal that is stale and scattered

- **Seat costs: ~600**. sellers on per-seat revenue-intelligence, Customer 360, forecasting and email add-ons.
- **Stale, slow analytics: ~2 hrs**. batch refresh; heavy views take ~90 s to load; a live-API patch covers only 10–25 opportunity fields.
- **Tool sprawl: 4 tools**. opened before every call, each with its own seat licence and API rate limits.
- **Signal outside the CRM: 3 silos**. Meet calls, fleet product usage and P1 tickets, stitched together by hand.

*In their words (discovery, paraphrased):*

> “Where do I spend my week? Today I open four tools to find out, and the dashboard is two hours old.” (The seller)

> “Every new question becomes a report ticket, and I can't tell whether any dashboard changed what a rep did.” (RevOps / Sales Systems)


**Speaker notes:**

> Talk track: 0:00 Opening, the three things discovery said hurt.  
> 1 Cost: per-seat, across ~600 sellers, for overlapping tools. 2 Speed and freshness: ~2-hour batch, ~90-second heavy views, sellers stop trusting them. 3 Siloed signal: what the customer said on the Meet call, whether the fleet uses the product, open P1s all live outside the CRM.  
> Land the human cost: every seller stitches this together by hand before every call.  

---

## Slide 4. Monday for Jordan: one screen, a plan, and the evidence

**Jordan Rivera, Enterprise AE  ·  FY27 Q4  ·  29.3% attainment  ·  3.5x coverage  ·  $1.24M open this quarter  (measured in the build)**

Jordan has enough pipeline. The problem is which deals to push.

- **My Week.** KPI strip, Priority deals ranked by ACV × P(close) with “why” chips (competitor on last call, usage down 18%, no activity in 21 days) and a next-best-action queue. *Replaces the revenue-intelligence dashboard.*
- **Deal 360.** Salesforce, the Meet call, fleet usage and tickets on one page. AI flags a RoadLynx pricing mention that is not in the CRM, falling active vehicles and an open P1. *Replaces hand-stitching before every call.*
- **Ask Genie.** “Which of my Enterprise deals mention a competitor and close this quarter?” A plain-English answer, the SQL behind it, scoped to Jordan's book. *Replaces a RevOps report ticket.*

Before: Jordan hears about RoadLynx and the P1 from the customer, in the meeting.   After: Jordan walks in knowing both, and accepts the next step in one click.

**Speaker notes:**

> Talk track: 4:30 Segment 1 My Week, 7:00 Segment 2 Deal 360, 10:00 Segment 3 NBA write-back, 11:30 Segment 4 Ask Genie.  
> Jordan's numbers are live from gold_seller_kpis (FY27Q4): quota $500K, closed-won $146.4K = 29.3%, coverage 3.5x.  
> So what: ~10 seconds to know the three deals that matter (Lever 2 time) and it replaces the dashboard Jordan used to open (Lever 1 seats). The RoadLynx mention and P1 are the win-rate lever: better-prepared calls on the deals most likely to move.  

---

## Slide 5. For the CRO: cost out, capacity up, a forecast you trust

- **Cost.** ~$1.08M / yr of add-on seats retired at renewal. Salesforce stays the system of record: we retire the add-ons, not Sales Cloud.
- **Capacity.** ~55K seller hours a year ≈ 27 sellers of selling time, without hiring anyone.
- **Revenue.** A credible path to +1 pt win rate on worked pipeline ≈ $6M ACV. Proved in the pilot, not banked.
- **Forecast.** Managers run the Monday call from at-risk deals with evidence: one number, one source, the same data sellers see.
- **Adoption.** Proof sellers act on it: accept / dismiss rate per rep and per action type, not just logins.
- **Risk.** Capped: 6 weeks, 40 sellers, read-only Salesforce, decision before the add-on seat renewal.

**Speaker notes:**

> Talk track: 13:30 Segment 5 Manager view (Morgan Lee) and 17:30 Close.  
> Exec framing lines: 'Your managers coach from evidence, and you get a forecast built on the same numbers your sellers see.' 'You get proof of adoption, not just logins.'  
> Objections ready: QA B1 (why pay on top of Salesforce: instead of the add-ons, not on top), B2 (payback ≈ 4 months on seats alone), B13 (risk is capped).  

---

## Slide 6. For RevOps & Sales Systems: one governed app, not a tool stack

- **Fewer tools.** Revenue intelligence, forecasting roll-ups and email drafting in one app: fewer seats, vendors and admin consoles to run.
- **Fresh data.** One managed Lakeflow Connect path for every field, in minutes, not hours ([[freshness: evidence/freshness.md]]). No 2-hour batch, no live-API patch, no rate-limit fights.
- **Less backlog.** Ad-hoc questions go to Genie, which answers in plain English and shows its SQL, instead of becoming report tickets.
- **Same visibility.** Seller → manager → RVP scoping enforced in the data layer; contact PII masked before it reaches the app. Parity with Salesforce sharing tested in the pilot.
- **Measurable.** Every accept and dismiss flows back into the lakehouse: NBA adoption per rep and action type; score accuracy re-measured every cycle.
- **Ownership.** RevOps owns screens, actions and pilot metrics; the data platform team owns pipelines and security; everything ships from one bundle in Git.

**Speaker notes:**

> Talk track: 11:30 Segment 4 Ask Genie (report backlog), 10:00 Segment 3 write-back (adoption), 15:00 Segment 6 (governance).  
> Objections ready: QA B7 (RevOps owns product, platform team owns pipelines), B3 (homegrown-app risk), T3 (Lakeflow Connect, read-only, same silver/gold), T4 (row-level parity with Salesforce sharing), T16 (freshness).  
> Freshness number is a placeholder until evidence/freshness.md lands; if asked, say we time one increment end to end and it's a pilot criterion (≤ 15 min).  

---

## Slide 7. The value model: every assumption labeled, every number shown

| Lever | Assumption | Arithmetic | Conservative | Expected |
|---|---|---|---|---|
| Seat retirement (hard) | 600 sellers; add-on list price $75–$220 / user / month, midpoint $150 | 600 × $150 × 12 | $0.54M / yr (at $75) | $1.08M/yr |
| Seller time | 2 hrs / week saved; 46 working weeks; 2,000 hrs per FTE-year | 600 × 2 × 46 = 55,200 hrs; ÷ 2,000 | ~27.6K hrs ≈ 14 FTE (at 1 hr / week) | ~55K hrs ≈ 27 FTE |
| Win rate (upside) | ~$600M / yr worked pipeline; +1 pt win rate | $600M × 0.01 | $0 (not banked) | ~$6M ACV/yr |
| Platform run cost | Serverless pipeline, AI enrichment, Lakebase, app and Genie at full scale | Assumption; replace with measured [[job cost per run: evidence/job_cost.md]] × runs / yr | $250K / yr | ~$200K / yr (range $150K–$250K) |
| Payback (seats only) | Build + pilot ≈ 2 engineers × 12 weeks ≈ $150K | ($150K + run) ÷ seat savings | ($150K + $250K) ÷ $0.54M ≈ 9 months | ($150K + $200K) ÷ $1.08M ≈ 4 months |

Sensitivity: even in the conservative case, seat savings alone repay build plus first-year run inside year one; at the $220 list-price high end seats are $1.58M / yr. The pilot replaces each assumption: contract line items (seats), before / after survey plus app telemetry (time), NBA acceptance and win rate on scored deals (revenue).

**Speaker notes:**

> Talk track: 'Value arithmetic (assumptions, for reference)' table and 2:30 value hypothesis. Expected column = talk track exactly.  
> Conservative column is the deck's sensitivity line: low list price ($75), high run cost ($250K), 1 hr/week saved, no win-rate credit. Use it if the exec pushes on the seat number.  
> QA B2 (ROI and payback) and B14 ('your numbers are all assumptions': labeled on purpose; give me six weeks and I'll swap every assumption for your number).  

---

## Slide 8. How it works: one connected data journey on the same entities

Same entities through every layer: account  →  opportunity  →  transcript  →  score  →  action

```
  [INGEST: Lakeflow]  →  [GOVERN: Unity Catalog]  →  [INTELLIGENCE: AI Functions + classifier]
  →  [SERVE: Lakebase]  →  [ASK: Genie]  →  [ACT: Databricks App]
  ↺ seller actions: App → Lakebase → MERGE into Delta → next run's ranking
```

- **Ingest (Lakeflow):** Salesforce, Meet calls, usage and tickets land once; bad records are caught at the door.
- **Govern (Unity Catalog):** One security model: row scoping, PII masks, lineage and audit.
- **Intelligence (AI Functions + classifier):** AI reads every call; a classifier scores every deal with calibrated probabilities.
- **Serve (Lakebase):** Millisecond pages for 600 sellers; seller actions saved instantly.
- **Ask (Genie):** Plain-English answers that show their SQL.
- **Act (Databricks App):** Fleetwise Seller Hub: My Week, Deal 360, Manager view.

Closed loop: every Accept / Dismiss is written to Lakebase, merged back into the lakehouse with lineage, and improves the next run's ranking.

**Measured today: 15,000 opportunities and ~446K silver rows through the pipeline  ·  0 rows failed a data-quality check  ·  Lakebase reads [[Lakebase p95 read ms: evidence/lakebase.md]] p95 vs ~90 s dashboards**

**Speaker notes:**

> Talk track: 15:00 Segment 6 Under the hood. Show Catalog Explorer lineage on gold_opportunity_pipeline.  
> Key line: one connected journey on the same entities; nothing copied into a side database that drifts. Production Salesforce ingest switches to the Lakeflow Connect connector.  
> Measured: 15,150 bronze → 15,000 unique silver opportunities; 445,769 silver rows; zero expectation failures (evidence/02_pipeline.md).  
> Exec framing: 'Your data team owns one platform, not five integrations. This is why it's not a homegrown science project.'  

---

## Slide 9. Trust: governed, secure, and AI measured before it is trusted

**Governance**

- Every table and column documented in Unity Catalog; the same comments ground Genie
- Lineage from raw file to app table, so any number traces back to its opportunity
- Every access in the audit log; data never leaves Fleetwise's account

**Security**

- Sellers see their own book, managers their team, RVPs their region
- Genie and SQL run as the signed-in user, so row filters always apply
- Contact PII masked before it reaches the app; Postgres row-level security is the production hardening step

**AI accuracy**

- Deal score tested on held-out closed deals against hidden ground truth never fed to the model: AUC [[AUC: evidence/score_eval.md]], top-decile lift [[top-decile lift: evidence/score_eval.md]]
- Call extraction spot-checked against planted signals: [[extraction precision/recall: evidence/call_insights.md]]
- Genie benchmark [[Genie benchmark x/N: evidence/genie.md]]; every output shows its why or its SQL


**Speaker notes:**

> Talk track: 7:00 Segment 2 (score accuracy), 11:30 Segment 4 (Genie runs as the signed-in user), 15:00 Segment 6 (governance).  
> Objections ready: QA B9 (AI accuracy), B10 (data safety), T5 (synced tables don't carry UC row filters: pre-masked PII, app-scoped queries, Postgres RLS as hardening), T7 (evaluation and drift), T15 (Genie accuracy and guardrails).  
> AUC, lift, extraction and Genie numbers are placeholders; if not filled, say 'we're measuring that, and it's a pilot success criterion'.  

---

## Slide 10. Decisions & trade-offs

| Decision | Why | Alternative considered |
|---|---|---|
| Lakebase serves the app's reads and writes | Millisecond point lookups for 600 sellers plus transactional writes for seller actions; synced tables avoid custom ETL | App querying a warehouse directly: slower, no transactional writes |
| Generative AI reads calls; a classifier scores deals | Language needs generation; decisions need calibrated probabilities. The classifier returns zero output tokens, so it is cheap and consistent | One LLM for both: costlier and uncalibrated |
| Salesforce-shaped exports in the demo; Lakeflow Connect in production | No real Salesforce org; same API schema, so silver and gold do not change | Custom API extraction: more code to own |
| Write-back via Lakebase + MERGE into Delta | Closes the loop with governed lineage; idempotent on action ID | App writing to Delta via SQL: chattier, not operational |
| App-scoped Postgres queries + pre-masked PII | Synced tables don't carry UC row filters, so the app scopes by the same hierarchy | Postgres row-level security (production hardening) |
| Triggered pipeline, not continuous | Lower run cost at the freshness sellers need | Continuous mode: a config flip for specific tables |

**Speaker notes:**

> Source: design spec section 5 trade-offs; QA T1, T2, T3, T5, T6, T8.  
> Keep this brief with the exec; offer the architect a deep-dive on any row. Cross-fire line for the exec: 'That's why the page loads instantly and why your team isn't maintaining another integration.'  

---

## Slide 11. Risks & mitigations

| Risk | Mitigation | How the pilot proves it |
|---|---|---|
| Run cost grows | Serverless and incremental; scoring with a zero-output-token classifier; cost per run tracked in system billing tables | Measured [[job cost per run: evidence/job_cost.md]] scaled to 600 sellers |
| Sellers don't adopt | Built around the question sellers already ask (“where do I spend my week?”); one-click actions; adoption visible per rep | ≥ 70% weekly active; ≥ 30% of actions accepted |
| Homegrown-app risk | Thin app on managed services; one bundle in Git with tests in CI; RevOps owns product, platform team owns pipelines | Handover to the Fleetwise team inside the pilot |
| Salesforce coexistence | Salesforce stays the system of record; read-only connected app; retire the add-ons, not Sales Cloud | Sharing-parity test; zero scoping violations in a red-team test |
| AI is wrong or not trusted | Measured on held-out deals; shows its why and its SQL; re-evaluated every cycle with drift alerts | AUC ≥ 0.75 on Fleetwise's closed deals; Genie ≥ 90% correct |
| Monday 8 a.m. load | Heavy work precomputed in batch; indexed point reads; stateless app scales out | Load test at 600 concurrent users; p95 < 300 ms |

**Speaker notes:**

> Source: QA B3, B5, B8, B13, T13, T14. Handling pattern: acknowledge, answer at their altitude, show proof, bridge to value, check.  
> Bridge line: 'The bigger risk is renewing the add-ons for another three years without testing the alternative.'  

---

## Slide 12. Proposed pilot: six weeks to a go / no-go decision

| Week | What happens |
|---|---|
| 1 | Connect Salesforce through Lakeflow Connect (read-only connected app); connect Meet transcripts, usage and tickets; security review kickoff |
| 2–3 | Stand up the Hub on Fleetwise data; map Salesforce role hierarchy and sharing to UC row filters; calibrate the score on Fleetwise's closed deals |
| 4–6 | ~40 sellers and 4 managers across two regions use it daily; we measure every week |
| 6 | Readout and go / no-go decision against the agreed success criteria |

**Scope:** ~40 sellers + 4 managers, two regions; Read-only Salesforce connection; Nothing in today's tools changes.
**Team:** Fleetwise: exec sponsor, RevOps owner, Salesforce admin, data platform engineer, security reviewer; Databricks: field engineer, plus Lakebase and GenAI specialists on request.

**Speaker notes:**

> Talk track: 17:30 Close, the six-week pilot table. QA B4 (time to value) and B13 (risk if it fails).  
> Time it so the week-6 decision lands before the add-on seat renewal date.  

---

## Slide 13. Pilot success criteria, agreed up front

| Criterion | Target |
|---|---|
| Weekly active pilot sellers | ≥ 70% |
| Self-reported and measured pre-call prep time | Down ≥ 30% vs baseline survey |
| Next-best-action acceptance rate | ≥ 30% of surfaced actions accepted |
| Data freshness (Salesforce change → visible in app) | ≤ 15 minutes |
| App page read latency | p95 under 300 ms |
| Deal score on Fleetwise's own closed history | AUC ≥ 0.75 and well calibrated |
| Genie benchmark on Fleetwise's 25 hardest questions | ≥ 90% correct, SQL visible |
| Security | Zero scoping violations in a red-team test; PII never stored unmasked in the app |
| Seat-retirement plan | Signed-off list of add-on seats retirable at renewal |

**Speaker notes:**

> Talk track: 17:30 Close, success criteria table (verbatim).  
> Each criterion maps to an assumption or a placeholder: prep time → Lever 2; NBA acceptance and score AUC → Lever 3; seat list → Lever 1; freshness, latency, Genie → the technical placeholders.  

---

## Slide 14. The ask: start the pilot the week after next

1. **Executive sponsor:** Name the sponsor (CRO / VP RevOps) and a RevOps owner for the pilot.
2. **Sales Systems & platform:** A read-only Salesforce connected app, access to transcripts, usage and tickets, and a security reviewer in week 1.
3. **Together, today:** Pick the 40 pilot sellers and book the week-6 decision meeting ahead of the add-on seat renewal.

**What would stop us from starting the week after next?**

**Speaker notes:**

> Talk track: 17:30 Close, recap and asks. Repeat each persona's words from the opening first.  
> Recap: ~$1.08M seats, ~55K hours ≈ 27 sellers, a path to +1 pt win rate ≈ $6M ACV. For the architect: one governed lineage, row scoping Genie inherits, masked PII, deployable from Git.  
> Ask the closing question, then stop talking. Whatever they say is the first objection; handle it, then: 'If we solve that, are we good to go?'  

---

## Slide 15. Appendix A: open measurements and sources

| Placeholder (not yet measured) | Source when measured | Used on slide |
|---|---|---|
| [[freshness]] minutes | evidence/freshness.md (one increment, file landed → visible in app) | 6 |
| [[Lakebase p95 read ms]] | evidence/lakebase.md (timed app endpoint reads) | 8 |
| [[job cost per run]] | evidence/job_cost.md (system.billing.usage for the daily job) | 7, 11 |
| [[AUC]] and [[top-decile lift]] | evidence/score_eval.md (held-out closed deals, MLflow run) | 9 |
| [[extraction precision/recall]] | evidence/call_insights.md (~20-transcript spot-check) | 9 |
| [[Genie benchmark x/N]] | evidence/genie.md (~10 scripted benchmark questions) | 9 |

Measured today: Jordan Rivera FY27 Q4 29.3% attainment, 3.5x coverage, $1.24M open (gold_seller_kpis, evidence/02_pipeline.md); 15,000 opportunities, 445,769 silver rows, 0 expectation failures (evidence/02_pipeline.md). Value assumptions: public list-price ranges and the talk-track value arithmetic; no engagement figures. All data synthetic; Fleetwise and competitors (RoadLynx, FleetCore, Trackwell) are fictional.

**Speaker notes:**

> Use if the evaluator or architect asks 'what is measured vs assumed?' (QA Part 4: separate measured from assumed).  
> Swap each placeholder for its number as the evidence files land; otherwise say 'we're measuring that in the pilot'.  

---

## Slide 16. Appendix B: architecture detail for the platform team

- **Ingest:** Lakeflow Spark Declarative Pipeline. Auto Loader reads Salesforce-shaped exports, Meet JSON, usage and tickets from a UC volume → bronze → silver (AUTO CDC SCD1 on LastModifiedDate; expectations drop bad keys and dates) → gold. Production: the Lakeflow Connect Salesforce connector, same schemas.
- **Measured:** 15,150 bronze → 15,000 unique silver opportunities; 0 expectation failures; 11 integration and 27 unit tests passing.
- **Govern:** Comments on every table and column; pii tag and column masks on contact email and phone; row filter on the seller → manager → RVP hierarchy; lineage from volume to app tables.
- **Intelligence:** ai_query (Claude, strict JSON schema) → gold_call_insights. OpenJev classifier (calibrated probabilities, zero output tokens) → gold_deal_scores. gold_next_best_actions ranked by ACV × P(close) × urgency. Evaluation logged to MLflow.
- **Serve:** Lakebase Postgres synced tables from UC (change data feed): account_360, opportunity_pipeline, next_best_actions, call_insights, seller_kpis. Contacts sync from a pre-masked view. The app writes only to native app.* tables.
- **Write-back:** The Lakebase database is registered in UC; a writeback_merge job task MERGEs app.* into silver_seller_actions → gold_nba_feedback, idempotent on action ID.
- **Ask:** Genie space “Fleetwise Revenue Copilot” on the gold tables, embedded via the Conversation API with on-behalf-of-user auth.
- **Orchestrate & deploy:** One serverless Lakeflow job: generate → pipeline_refresh → ai_call_insights → ai_scoring → next_best_actions → lakebase_sync → writeback_merge → evaluate_scores. Everything in one bundle in Git with dev and prod targets.

**Speaker notes:**

> For the technical persona. Talk track 15:00 Segment 6 deep-dive options: row filter and masked vs unmasked evidence, synced-table modes and refresh cadence, score evaluation notebook, job DAG and run history.  
> QA T1–T17 cover the likely questions (Lakebase vs warehouse, synced tables, Salesforce ingest, RLS parity, write-back conflicts, auth, CI/CD, observability, scale, failure modes).
