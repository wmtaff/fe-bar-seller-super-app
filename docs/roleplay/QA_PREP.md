# Fleetwise Seller Hub – Roleplay Q&A Prep (FE Bar)

<!-- toc -->

## How to use this prep

- **Format for every item:** the likely question, a 2–5 sentence answer you can say out loud, the **artifact** to point at, and a **bridge** back to value.
- **The handling pattern (use it every time):** acknowledge → answer at the asker's altitude → show proof → bridge to value → check ("Does that answer it?").
- **Never argue.** If the objection is fair, say "That's fair" and turn it into a pilot success criterion.
- **Translate across.** After a technical answer, give the exec one sentence. After a business answer, give the architect one sentence. The cross-fire section has scripts.
- **Numbers** are from the committed evidence (`evidence/01`–`11`, `docs/VALUE_MODEL.md`). The full list, with sources, is at the end. AUC, lift and extraction are measured against the generator's planted truth, not real-world accuracy.
- Competitor names used in the demo data are fictional: **RoadLynx, FleetCore, Trackwell**. Don't name real vendors; say "a point revenue-intelligence vendor" or "a conversation-intelligence tool."

## Part 1: Business persona (CRO / VP RevOps)

### B1. "We already pay for Salesforce. Why would I pay Databricks on top?"

**Answer:** You keep Salesforce as the system of record for opportunities and accounts. What this replaces are the add-on layers on top of it: the revenue-intelligence and analytics seats and the separate forecasting tool (the email tool follows once email drafting, on the roadmap, lands). At list prices of roughly $75–$220 per user per month, that's about $1.08M a year across 600 sellers at the midpoint. The Databricks run cost is an assumption of $150K–$250K a year at full scale; at demo scale we measured about $1.15 per incremental run (an estimate), and the pilot replaces the assumption with billed cost.

**Artifact:** Value arithmetic table in the talk track; measured run cost (~1.65 DBU ≈ $1.15 per incremental run, ≈ $10K/yr if hourly; estimate) in `docs/VALUE_MODEL.md`.

**Bridge:** "So it's not 'on top.' It's instead of the add-ons, at a fraction of their cost."

### B2. "What's the ROI and payback, really?"

**Answer:** On seat retirement alone, using my midpoint assumption: about $1.08M a year saved, against roughly $150K of build and pilot effort and about $200K a year to run. That's payback in about four months (about nine months in the conservative case). I deliberately don't put the seller-time or win-rate numbers in the payback math, because those need to be proven. The pilot measures prep time and NBA adoption so we can add them with evidence.

**Artifact:** Value arithmetic table; pilot success criteria.

**Bridge:** "The hard savings justify it. The productivity and win-rate upside is what makes it strategic."

### B3. "Isn't this a homegrown app? Who maintains it when the person who built it leaves?"

**Answer:** It's fair to worry about that. It's a thin app on top of managed platform services: Lakeflow for ingest, Unity Catalog for security, Lakebase for the database, Genie for questions. The custom code is mostly screens and queries, and everything (pipelines, jobs, app) is defined in a bundle in Git and redeploys with one command. Your data team already maintains pipelines on this platform. The pilot includes a handover so your team owns it.

**Artifact:** `databricks.yml` and `resources/*.yml` (the bundle); the job DAG.

**Bridge:** "You own the IP and the roadmap, instead of waiting on a vendor's."

### B4. "How long until my sellers actually get value?"

**Answer:** Six weeks to a decision with real Fleetwise data. Week 1 we connect Salesforce read-only and the other sources. Weeks 2–3 we stand up the Hub on your data and calibrate the score on your closed deals. Weeks 4–6, about 40 sellers and 4 managers use it daily and we measure every week. Week 6 is the go / no-go. The reason it's fast is that we're not building infrastructure. We're configuring managed services and pointing the app at your data.

**Artifact:** Pilot timeline table in the talk track.

**Bridge:** "And we can time it so the decision lands before your add-on seat renewal."

### B5. "Sellers hate new tools. How do I know they'll use it?"

**Answer:** Two things. First, it's designed around one question sellers already ask every Monday, "where do I spend my week," and it answers faster than what they have now. Second, we don't have to guess. Every accept and dismiss writes back, so you'll see adoption per rep and per action type, not just logins. In the pilot, the bar is 70% weekly active and at least 30% of actions accepted.

**Artifact:** NBA write-back demo; `gold_nba_feedback` (adoption per rep and action type; a team roll-up screen is on the roadmap).

**Bridge:** "For the first time, you'll know whether your sales tooling changes behavior."

### B6. "Can I trust the forecast numbers in here?"

**Answer:** The numbers come straight from your Salesforce data, through one governed pipeline, with data-quality checks. In our runs, zero rows failed them. Managers see the same numbers sellers see, so there's no "my spreadsheet vs your dashboard." The AI score is an input to the forecast, not a replacement, and we measure it against deals whose outcome we know: AUC of 0.695 on 400 held-out closed deals, with top-decile lift of 2.06×.

**Artifact:** `evidence/02_pipeline.md` expectations table; `evidence/06_nba_and_eval.md`.

**Bridge:** "One number, one source, and you can trace any number back to the opportunity it came from."

### B7. "Who owns this internally, Sales Ops or IT?"

**Answer:** My recommendation: RevOps owns the product (what's on the screens, which actions to recommend, the pilot metrics), and the data platform team owns the pipelines and security. That's the same split you probably have today between Sales Ops and Salesforce admins. We'd name both in week 1.

**Artifact:** Pilot "asks" slide.

**Bridge:** "Clear ownership is a pilot deliverable, not something we figure out later."

### B8. "So are we moving off Salesforce?"

**Answer:** No. Salesforce stays the system of record. Sellers still update opportunities there, and that's where your process and integrations live. What changes is where sellers *work*: they get one screen with everything, and the analytics layer sits on Databricks. If you ever want to change your CRM strategy, your data and intelligence are already in an open platform, which keeps your options open.

**Artifact:** Architecture diagram (spec section 4).

**Bridge:** "We're consolidating tools, not ripping out your CRM."

### B9. "AI makes things up. How accurate is it?"

**Answer:** We separate the two AI jobs. For reading calls, the AI fills a strict schema (next steps, competitors, open items) and we check it against signals we planted in the calls: competitor precision and recall of 1.00 / 1.00 across 287 planted mentions. For scoring, we use a classifier that returns probabilities rather than generated text, and we measure it on held-out deals. In the app, every AI output shows its "why," and Genie shows its SQL. Nothing is a black box.

**Artifact:** `evidence/06_nba_and_eval.md`; Deal 360 "why" chips; Genie "Show SQL."

**Bridge:** "We measure accuracy before we ask anyone to trust it, and the pilot re-measures it on your data."

### B10. "Is our customer data safe? What about the call recordings?"

**Answer:** Everything stays inside your Databricks account, governed by Unity Catalog. Sellers only see their own book and managers see their team, and that's enforced in the data layer, not just the screens. Contact emails and phones are masked, and the app never stores raw PII. The AI models run as Databricks-hosted endpoints, and every access is in the audit log.

**Artifact:** Row-filter and mask evidence queries (masked vs unmasked principal); `gold_contacts_masked` sample (`f***@solisconstruction.com`).

**Bridge:** "Tighter than today, where transcripts and usage live in separate tools with separate access."

### B11. "Doesn't this just swap Salesforce lock-in for Databricks lock-in?"

**Answer:** The data is stored in open formats (Delta tables, standard Postgres in Lakebase) and the app is standard code you own. The AI calls go through a model-agnostic interface, so if a better model comes along, you swap it. Compare that to per-seat SaaS, where your logic and history live in the vendor's format.

**Artifact:** Bundle in Git; table formats in Catalog Explorer.

**Bridge:** "You're investing in your own data asset, not renting a view of it."

### B12. "Why not just buy a revenue-intelligence or conversation-intelligence product?"

**Answer:** You could, and some are good. But each one is another seat license, another copy of your data, and another silo, and none of them combine your product usage and support tickets with the call and the CRM. Here it's one place, and the same data powers forecasting, coaching, the app and plain-English questions. And the platform keeps paying off for your next use case, like churn prediction for customer success.

**Artifact:** Deal 360 (CRM + call + usage + tickets on one page).

**Bridge:** "Buying adds a tool. This removes three."

### B13. "What's the risk if the pilot fails?"

**Answer:** It's capped: six weeks, 40 sellers, a read-only Salesforce connection, and nothing in your current tools changes. If it misses the success criteria we agreed on up front, you've learned that before any renewal decision, and your data platform is better connected than it was. That's a cheap way to de-risk a seven-figure seat decision.

**Artifact:** Success criteria table.

**Bridge:** "The bigger risk is renewing the add-ons for another three years without testing the alternative."

### B14. "Your numbers are all assumptions."

**Answer:** That's right, and I've labeled them that way on purpose. Every assumption has a measurement attached in the pilot: your actual contract line items for seats, a before-and-after survey plus app telemetry for time, and NBA acceptance and win rate on scored deals. What *is* measured today is the technical side: freshness, latency and score accuracy on test data.

**Artifact:** Measured-numbers list mapped to evidence files (end of this doc).

**Bridge:** "Give me six weeks and I'll swap every assumption for your number."

## Part 2: Technical persona (architect / data platform lead)

### T1. "Why Lakebase? Why not just point the app at a SQL warehouse?"

**Answer:** Two reasons: access pattern and writes. The app does lots of small, per-user point lookups ("Jordan's deals," "this account") and needs millisecond responses for 600 concurrent users. That's an OLTP pattern, which Postgres handles well and an analytic warehouse doesn't. And the app writes (accepts, dismisses, notes), which needs a transactional database. The warehouse is still used where it fits: Genie and the analytics run there.

**Artifact:** Lakebase adds 6.3 ms over the network baseline for a deal lookup (0.07 ms server-side; `evidence/07_lakebase.md`) vs the 90-second CRMA views; spec section 5 trade-offs table.

**Bridge (exec):** "That's the difference between a 90-second dashboard and a page that loads before the seller blinks."

### T2. "Why synced tables instead of writing my own ETL into Postgres?"

**Answer:** Synced tables are managed: you declare a UC table as the source and Databricks keeps a Postgres copy up to date, using the Delta change data feed for triggered or continuous modes. Our gold tables have change data feed enabled. Custom ETL means owning the code, the retries, the schema changes and the monitoring yourself. This is one less pipeline to maintain, and lineage stays in Unity Catalog.

**Artifact:** `tests/integration/test_pipeline.py::test_gold_tables_have_cdf_and_comments` (passing); synced tables in Catalog Explorer.

**Bridge (exec):** "Less custom code means less to maintain and less risk."

### T3. "In production, how do you get data out of Salesforce? File drops?"

**Answer:** No. In the demo we simulate Salesforce with exports shaped exactly like the Salesforce API objects (18-character IDs, `OwnerId`, `StageName` and so on), loaded with Auto Loader, because there's no real org. In production, we'd use the **Lakeflow Connect Salesforce connector**: managed, incremental ingestion through a read-only connected app, straight into Unity Catalog. Because the schemas match, the silver and gold layers don't change. For the handful of fields where you need fresher data, we'd tune the connector schedule rather than build a live-API patch.

**Artifact:** `evidence/01_generate_data.md` (SFDC-shaped objects); spec section 5 trade-off.

**Bridge (exec):** "Production ingestion is a managed connector, not something your team builds."

### T4. "How does row-level security compare to Salesforce sharing rules?"

**Answer:** Today we model the most common case, ownership plus role hierarchy: a seller sees what they own, a manager sees their team, an RVP sees their region. That's a UC row filter function that looks up the viewer in a hierarchy table. Salesforce sharing can also include account teams, territories and manual shares. In the pilot, we'd export those sharing grants as a table and add them to the same filter function. Then we prove parity by testing "who can see what" in both systems for a sample of users.

**Artifact:** Row-filter function and its evidence queries; `gold_user_hierarchy` (Jordan → Morgan Lee → Kelly Castaneda).

**Bridge (exec):** "Sellers see exactly what they see in Salesforce today, and we'll prove it in a test before go-live."

### T5. "Synced tables in Lakebase don't carry UC row filters or masks. So how does the app stop Jordan from seeing Morgan's other reps?"

**Answer:** You're right, and that's a deliberate design decision, not an oversight. Three controls. First, PII never reaches Postgres: contacts sync from a pre-masked view, `gold_contacts_masked`, so there's nothing sensitive to leak. Second, the app scopes every Lakebase query by the viewer's identity mapped to owner IDs through the same hierarchy the UC row filter uses, so app pages and Genie always agree. Third, the app's database role has read access only to the synced tables it needs. The hardening step for production is Postgres row-level security policies keyed on the same hierarchy, so the database enforces it even if app code has a bug.

**Artifact:** `evidence/02_pipeline.md` masked contacts sample; spec section 5 ("Row filters in UC; app scoping in Postgres queries"); `test_contacts_masked_has_no_raw_email`.

**Bridge (exec):** "Sensitive data is masked before it ever reaches the app, and we'll add a second lock in the database before production."

### T6. "Write-back: what happens if the app writes while a sync is running? How do you avoid conflicts?"

**Answer:** The app never writes to synced tables. It writes only to its own native Postgres tables (`app.seller_actions`, `app.notes`), so there's no conflict with the sync. Reads in the app combine the two, so a seller sees their accept instantly. Lakehouse Sync streams those rows (Postgres CDC) into a Unity Catalog history table, so an app write lands in Delta in about a minute (59 s measured), and the job's `writeback_merge` task MERGEs them into `silver_seller_actions`, keyed on action ID, so it's idempotent and safe to re-run.

**Artifact:** `writeback_merge` task in the job; `silver_seller_actions`, `gold_nba_feedback`; 59.1 s app-write → Delta round trip (CDC 16.2 s; `evidence/07_lakebase.md`).

**Bridge (exec):** "Sellers see their action instantly, and it's in the lakehouse about a minute later."

### T7. "How do you evaluate the AI, and how do you catch drift?"

**Answer:** The synthetic data has a hidden ground truth for every deal and lead, stored separately and never fed to the AI. We score closed deals as of their pre-close snapshot and compute AUC, lift by decile and calibration, logged to MLflow: AUC 0.695 and top-decile lift 2.06× on 400 held-out closed deals. For extraction, we check against signals we planted: competitor precision / recall 1.00 / 1.00 (287 mentions). In production, the same evaluation runs on your real closed-won and closed-lost deals every cycle, and we'd put data-quality monitoring on the score table to alert on drift in score distribution or calibration.

**Artifact:** `evidence/06_nba_and_eval.md`; `gold_score_eval`; `test_no_ground_truth_ingested` (passing).

**Bridge (exec):** "We measure the AI every time it runs, so you know if it gets worse before your sellers do."

### T8. "ai_query on every transcript sounds expensive. And why a classifier for scoring instead of just asking the LLM?"

**Answer:** Transcripts are processed incrementally, only new calls, in batch on serverless, so the cost scales with call volume, not with users. We didn't meter it per transcript; the upper bound is ~291 model-serving DBU for the initial 640-call extraction on a shared endpoint, and each increment only extracts new calls (40 in our batch 2). For scoring, a generative LLM is the wrong tool. It's costlier, and its "confidence" isn't a calibrated probability. OpenJev returns a calibrated probability for each answer with **zero output tokens**. In our spike, one scoring call used 287 input tokens and returned "send_proposal" at p = 0.89. You can rank by expected value on that, and it's cheap enough to re-score the whole open pipeline every run.

**Artifact:** `docs/DECK_POINTS.md` OpenJev spike; spec section 5 trade-off; `evidence/05_scoring.md` (~1,424 input tokens per deal, 0 output tokens).

**Bridge (exec):** "Use the expensive AI only where you need language. Use the cheap, precise one for the decisions."

### T9. "Call transcripts are full of PII. How do you handle that?"

**Answer:** The transcripts land in a governed UC volume and silver table with restricted access, not in the app. The AI extracts structured fields (next steps, competitors, interests), and that's what the app shows. The full transcript text and attendee emails don't go to Postgres. The model endpoints are Databricks-hosted, so data doesn't leave your account boundary. For production, we'd add `ai_mask` on transcript text before extraction for any fields policy says must never be processed.

**Artifact:** `silver_transcripts` permissions; `gold_call_insights` columns.

**Bridge (exec):** "Sellers get the insight from the call without the raw recording spreading across tools."

### T10. "How does auth work? Does the app run as a service principal with god-mode access?"

**Answer:** The app uses **on-behalf-of-user** authorization for Genie and SQL, so queries run as the signed-in user and UC row filters see the real viewer through `current_user()`. That's why Genie only shows Jordan's deals without any extra code. The app's service principal has narrow rights: read on the synced tables it needs, write on the `app` schema, and modify on one identity-mapping table used for the demo persona switch. The persona switch is demo-only and would be removed in production, where identity comes from SSO.

**Artifact:** App resource config in the bundle; spec section 6.1.

**Bridge (exec):** "The app can't show anyone more than they're already allowed to see."

### T11. "What about CI/CD? Can my team promote this through dev, staging and prod?"

**Answer:** Yes. Everything is a **Databricks Asset Bundle**: the schema, volume, pipeline, job and app. `bundle validate` and `bundle deploy -t dev` are already in the evidence. Targets for staging and prod are just more blocks in the same file, with environment variables for workspace and catalog, and no workspace IDs in code. Unit tests on the generator and integration tests on the pipeline run in CI before deploy.

**Artifact:** `evidence/task1_setup.md` (`Validation OK!`, deploy output); `evidence/11_tests.md` (full suite: 184 passed, 1 failed, 1 skipped; the failure found a real view-grant bug, fixed in code).

**Bridge (exec):** "Changes go through review and testing like any other production software."

### T12. "How do you observe this? How do I know it's healthy?"

**Answer:** Each layer reports into system tables and event logs you already have. The pipeline event log records every update and every expectation pass or fail. Job runs report task status and duration, with alerts on failure. `system.billing.usage` gives cost per job run. `system.access.audit` and lineage tables show who read what. The app shows data freshness on screen, so a stale sync is visible to users immediately, and we'd alert on freshness over a threshold.

**Artifact:** `evidence/02_pipeline.md` expectations from the event log; the "updated N min ago" badge.

**Bridge (exec):** "If something's late, you'll know before a seller does."

### T13. "Will it scale to 600 sellers hitting it Monday at 8 a.m.?"

**Answer:** The heavy work happens in batch, not on page load: enrichment, scoring and ranking are precomputed by the job. Page loads are indexed point reads in Lakebase, which is the pattern Postgres scales best on, with autoscaling compute and connection pooling. The app tier is stateless, so it scales horizontally. In the pilot we'd load-test a Monday-morning spike at 600 concurrent users and set a p95 target. What I'll be honest about: we haven't load-tested yet; the demo numbers are single-user: Lakebase adds 6.3 ms over the network baseline (77.6 ms client p95 from a laptop).

**Artifact:** `evidence/07_lakebase.md`; pilot latency criterion.

**Bridge (exec):** "We'll prove Monday-morning performance before your whole team depends on it."

### T14. "What are the failure modes? Token expiry, scale-to-zero, a sync that falls behind?"

**Answer:**
- **Token expiry:** Lakebase uses short-lived OAuth credentials (about an hour), so the app refreshes them before expiry in its connection pool instead of using a static password.
- **Scale-to-zero:** after idle time, the first request has a cold start of a few seconds; for business hours we'd set a minimum compute size so Monday mornings are warm.
- **Sync lag:** the freshness badge makes it visible, and we alert on it.
- **Upstream failure:** if a job task fails, the app keeps serving the last good data rather than going blank.
- **AI endpoint errors:** failed rows are retried on the next run and never block the pipeline.

**Artifact:** Job DAG with task dependencies; freshness badge.

**Bridge (exec):** "Failures degrade to slightly stale data, not an outage."

### T15. "How accurate is Genie, and what stops it from returning wrong numbers or data someone shouldn't see?"

**Answer:** Accuracy: Genie is grounded with UC table and column comments, join definitions, fiscal-calendar rules (FY27 Q4, ACV definitions, what "my pipeline" means) and trusted example SQL. We benchmark it on a fixed question set: 9/10 correct, median 18.5 s; the one miss was a correct empty answer on a gap in the synthetic data. Guardrails: it only queries the curated gold tables in its space, it runs as the signed-in user so row filters and masks apply, it's read-only, and it always shows its SQL. When it's wrong, we add a trusted example and re-run the benchmark.

**Artifact:** Genie space instructions and sample questions; "Show SQL" in the app; `evidence/08_genie.md`.

**Bridge (exec):** "It's an analyst who shows their work and can't see anything you can't."

### T16. "How fresh is the data, end to end?"

**Answer:** We measure it, rather than guess: one increment from file landed in the volume to visible to the app (the Lakebase row it reads): 9.0 minutes (540.6 s). The pipeline runs triggered to save cost; continuous mode is a config change if you need lower latency on specific tables. Compared to the roughly two-hour batch and a live-API patch for 10–25 fields today, it's one path for all fields.

**Artifact:** `evidence/10_e2e.md`; the freshness badge.

**Bridge (exec):** "Sellers see changes in minutes, not hours, without paying for a live patch."

### T17. "How do you handle Salesforce schema changes and data quality issues?"

**Answer:** Auto Loader handles schema evolution and keeps unexpected fields in a rescued-data column instead of failing. In our runs that column was null on every opportunity row. Silver uses CDC with SCD1 on the newest `LastModifiedDate`, so re-sent records don't double-count: 15,150 bronze opportunity rows became exactly 15,000 unique silver opportunities. Expectations drop rows with bad keys or close dates and record every pass or fail in the event log.

**Artifact:** `evidence/02_pipeline.md` row counts, notes and expectations table; `test_silver_opps_unique_ids`.

**Bridge (exec):** "Bad data gets caught at the door, so the numbers in front of your sellers stay trustworthy."

### T18. "Why build your own deal score instead of using what's in the CRM?"

**Answer:** Because the CRM only sees CRM fields. Our score uses the opportunity, plus product usage trend, ticket health and what was said on the latest call. That's signal the CRM never sees. And we can evaluate it openly on your own history, tune it, and own it.

**Artifact:** Deal 360 "why" chips; `gold_deal_scores` probabilities.

**Bridge (exec):** "A score built on everything you know about the customer, not just what got typed into the CRM."

## Part 3: Cross-fire moments (re-pitch one persona's answer for the other)

| Moment | The asker's answer | Re-pitch for the other persona |
|---|---|---|
| Architect asks about synced tables vs warehouse (T1/T2) | Point reads + OLTP writes → Lakebase; managed sync, no custom ETL | *[To exec:]* "In plain terms, that's why the page loads instantly and why your team isn't maintaining another integration." |
| Exec asks about cost (B1) | Seats retired ≈ $1.08M/yr vs ~$200K run | *[To architect:]* "And the run cost stays low because it's all serverless and scoring uses a zero-output-token classifier, so you're not paying for idle clusters or chatty LLM calls." |
| Architect pushes on RLS in Lakebase (T5) | Pre-masked PII, app-scoped queries, Postgres RLS as hardening | *[To exec:]* "Bottom line: nobody sees a deal or a phone number they can't see in Salesforce today, and we'll prove that in a red-team test in the pilot." |
| Exec asks "can I trust the AI?" (B9) | Measured on held-out deals; shows its why and its SQL | *[To architect:]* "Under the hood, that's an MLflow-logged evaluation on ground truth that's never fed to the model, and in production it re-runs on your closed deals every cycle." |
| Architect asks about Lakeflow Connect (T3) | Managed connector, read-only, same silver/gold | *[To exec:]* "That also kills the live-API patch you pay for today and the API rate limits your tools fight over." |
| Exec asks "who maintains it?" (B3) | Bundle in Git, managed services, RevOps owns product | *[To architect:]* "Concretely: one bundle, tests in CI, targets for dev and prod. Your team would review and deploy it like any other service." |
| Architect asks about scale (T13) | Precompute in batch; point reads; load test in pilot | *[To exec:]* "Monday at 8 a.m. with every seller logging in is exactly what we'll test before rollout." |
| Exec asks about lock-in (B11) | Open formats, code you own | *[To architect:]* "Delta and standard Postgres, the app is ordinary code, and the model is swappable behind `ai_query`." |

**When they talk to each other:** if the exec turns to the architect and asks "is that true?", stay quiet and let the architect answer. Then add one sentence of proof ("and that's in the evidence here") and one sentence of value.

**When altitude clashes:** if the architect goes deep while the exec looks bored, say: "Let me give you the short answer now, and I'd love to do a 30-minute deep-dive with you on this next week." Then summarize for the exec.

## Part 4: Handling what you don't know

1. **Don't bluff.** Say: "I don't want to guess on that. Let me confirm and come back to you by [specific day]." Write it down where they can see you do it. Then actually follow up.
2. **Separate measured from assumed.** "That number is measured in our build," vs "That's an assumption we'll measure in the pilot." Being precise about which is which earns trust with both personas.
3. **Turn the unknown into a pilot criterion.** "I don't have your load profile yet. Let's make 'p95 under 300 ms at 600 concurrent users' a success criterion, and test it in week 4."
4. **Offer the right expert.** "That's a great question for our Lakebase specialist. I'll bring them to the deep-dive." Use this for detailed roadmap, pricing commitments or contract questions.
5. **Answer the part you do know.** "I can't commit to the exact discount, but I can tell you how the cost is structured and how we'd measure it."
6. **Never invent product features or dates.** If asked about a roadmap item, say "I'll check what's committed and get back to you." Don't speculate.
7. **Bridge back.** After any "I'll get back to you," return to value: "What I can say today is that the seat savings alone carry the business case."

## Measured numbers in this prep

| Number | Source |
|---|---|
| AUC **0.695**; top-decile lift **2.06×** (80% vs 38.75% base, 400 held-out closed deals) | `evidence/06_nba_and_eval.md` |
| Competitor extraction P/R **1.00 / 1.00** (287 planted mentions) | `evidence/06_nba_and_eval.md` |
| Freshness **9.0 min** (540.6 s), file landed → the Lakebase row the app reads | `evidence/10_e2e.md` |
| Lakebase **6.3 ms** added over network baseline (0.07 ms server-side; 77.6 ms client p95 from a laptop) | `evidence/07_lakebase.md` |
| Write-back **59.1 s**, app write → Delta (CDC 16.2 s) | `evidence/07_lakebase.md` |
| Run cost **~1.65 DBU ≈ $1.15** per incremental run (≈ $10K/yr if hourly; estimate) | `docs/VALUE_MODEL.md` |
| `ai_query`: upper bound ~291 model-serving DBU for the initial 640-call extraction (shared endpoint) | `docs/VALUE_MODEL.md` |
| OpenJev: ~1,424 input tokens per deal, 0 output tokens | `evidence/05_scoring.md` |
| Genie **9/10**, median **18.5 s** | `evidence/08_genie.md` |
| Payback **≈ 4 months** on seats (conservative ≈ 9 months) | `docs/VALUE_MODEL.md` |
| Tests: **184 passed, 1 failed, 1 skipped** | `evidence/11_tests.md` |
