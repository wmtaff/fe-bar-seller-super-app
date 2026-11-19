# Fleetwise Seller Hub – Demo Talk Track (FE Bar)

<!-- toc -->

## How to use this track

- **Run time:** about 20 minutes spoken, which leaves 5–10 minutes of the 20–30 minute slot for questions. Every section has a target clock time. If you run long, use the "compress" note on each segment.
- **Two people are in the room.** The **business persona** is the exec who funds the decision (think CRO or VP RevOps). The **technical persona** is the architect or data platform lead. Name them in the opening and use their names all the way through.
- **Format:** plain text is what you say, in the first person. *[Bracketed italics]* are stage directions. **Bold** is the line to land.
- **Each demo segment has the same shape:** TELL (what you're about to show and why) → SHOW (click path and what to point at) → TELL "so what" (tied to a KPI) → a one-line exec framing → a technical deep-dive option you offer but don't force.
- **Numbers:** every number below is from the committed evidence (`evidence/01`–`11`, `docs/VALUE_MODEL.md`). The full list, with sources, is at the end of this doc. AUC, lift and extraction are measured against the generator's planted truth, not real-world accuracy.
- **Altitude rule:** answer the person who asked, at their altitude, then translate for the other in one sentence. ("For you, Dana, that means…")

## Timing at a glance

| Clock | Section | Minutes | Primary audience |
|---|---|---|---|
| 0:00 | Opening, setup, agenda check | 2.5 | Both |
| 2:30 | Value hypothesis in Fleetwise KPIs | 2.0 | Exec |
| 4:30 | Segment 1: My Week | 2.5 | Exec |
| 7:00 | Segment 2: Deal 360 (AI insights + score) | 3.0 | Both |
| 10:00 | Segment 3: Next-best-action write-back | 1.5 | Architect |
| 11:30 | Segment 4: Ask Genie | 2.0 | Both |
| 13:30 | Segment 5: The manager persona | 1.5 | Exec |
| 15:00 | Segment 6: Under the hood | 2.5 | Architect |
| 17:30 | Close: recap, pilot, asks | 2.5 | Both |
| 20:00 | Open Q&A | 5–10 | Both |

## Pre-flight checklist (do this 15 minutes before)

- App open on **My Week** as **Jordan Rivera**. Know where the **persona switcher** is: in Segment 5 you switch to **Morgan Lee** (manager) live, and back to Jordan afterwards.
- Genie space **Fleetwise Revenue Copilot** open in a third tab, with the sample questions visible.
- Catalog Explorer open on `gold_opportunity_pipeline` → **Lineage** tab, in a fourth tab.
- Run one increment of the daily job about 10 minutes before you start, so "updated N min ago" shows a small number.
- Reset demo state: pick one NBA on Jordan's top deal and leave it **unaccepted** so you can accept it live.
- Warm the app and Lakebase. Click through every screen once so nothing is cold (scale-to-zero) when you're on stage.
- Have the backup ready: the `evidence/` folder and the README walkthrough, in case the app or network fails.

## 0:00 – Opening, setup and agenda check (2.5 min)

*[Camera on you, not the screen yet. Smile, slow down.]*

Thanks for the time, both of you. Let me set this up in about two minutes, then we'll get straight into the product.

Fleetwise sells fleet telematics: vehicle gateways, AI dash cams, driver safety, fuel and maintenance, compliance. You've got about **600 sellers**. Today those sellers live in Salesforce, plus revenue-intelligence and Customer 360 add-on seats, plus a separate forecasting tool and a separate email tool. In discovery you told us three things hurt:

1. **Cost.** You pay per seat, across about 600 sellers, for several overlapping tools.
2. **Speed and freshness.** Dashboards refresh on roughly a **two-hour** batch, and the heavy views take about **90 seconds** to load. Sellers stop trusting them.
3. **Siloed signal.** The best evidence about a deal (what the customer said on the Google Meet call, whether their fleet is actually using the product, whether they have open P1 tickets) lives outside the CRM. Every seller stitches it together by hand before every call.

What I'll show you today is the **Fleetwise Seller Hub**: one app, built on Databricks, that pulls Salesforce, call transcripts, product usage and support tickets into one governed place, adds AI on top, and puts it in front of the seller in milliseconds. Everything you'll see runs on synthetic Fleetwise-shaped data. No real customer data.

Here's the plan. I'll spend two minutes on the value we think this is worth to Fleetwise. Then I'll walk a seller's Monday morning, a deal deep-dive, the AI copilot, and what a manager sees. I'll finish with five minutes under the hood, and a proposal for a pilot.

*[Pause. Look at the exec first.]*

Before I start: **[Exec name]**, what would make this half hour a good use of your time? What do you need to walk away with?

*[Listen. Write down their words. Common answers: "the number," "is this real or a science project," "how fast." Repeat it back.]*

And **[Architect name]**, what about you? What do you need to see to believe this can run in production?

*[Listen. Common answers: security model, Salesforce integration, "who maintains this." Repeat it back.]*

Great. So for you, [Exec], I'll keep coming back to cost and seller productivity. And for you, [Architect], I'll make sure we get to governance and how the data flows. If I skip something you care about, stop me.

*[If either persona names something that isn't in the plan, say: "Good, I'll cover that in [segment]," or "That's a great one for the Q&A. Let me park it here so I don't forget." Write it down where they can see you do it.]*

## 2:30 – The value hypothesis in Fleetwise KPIs (2 min)

*[Still no screen, or one simple slide with three numbers.]*

Before the demo, here's the business case in one breath. These are **assumptions**, not promises. I'll show my arithmetic, and the pilot exists to replace each assumption with a measured number.

**Lever 1: retire overlapping seats.** Revenue-intelligence and analytics add-on seats typically list somewhere around **$75 to $220 per user per month**. Take the middle, about **$150**. That's 600 sellers × $150 × 12 months = **about $1.08 million a year**. The range is about $0.54M at the low end to $1.58M at the high end. To be clear, you keep Salesforce as the system of record. We're retiring the add-ons, not Sales Cloud.

**Lever 2: give sellers time back.** If the Hub saves each seller just **2 hours a week** on pre-call prep and hunting across tools, that's 600 × 2 × 46 working weeks = **about 55,000 hours a year**. That's roughly **27 full-time sellers' worth of selling time** you get without hiring anyone.

**Lever 3: win more of the pipeline you already have.** If AI-ranked priorities and next steps move win rate by **one point** on the pipeline sellers actually work (we'll assume about $600M a year), that's **about $6 million of extra ACV**. I treat that one as upside to prove in the pilot, not something to bank today.

Against that, the platform cost of running this (pipelines, AI enrichment, Lakebase, the app) is an assumption of roughly **$150K to $250K a year** at full scale, and the pilot replaces it with billed cost. At demo scale we measured about **$1.15 per incremental run** (~1.65 DBU, an estimate), roughly $10K a year if it ran hourly, so the assumption is deliberately generous. On seats alone, **payback is about 4 months** (about 9 months in the conservative case), before we count a single hour of seller time.

*[To the exec:]* Does that framing match how you'd pitch it to your CFO, or would you weight it differently?

*[Listen. If they push on the seat number, say: "Fair. In the pilot, we'll pull your actual contract line items and replace my list-price assumption." Then move on.]*

Let me show you what a seller actually gets.

## 4:30 – Segment 1: My Week (2.5 min)

**TELL**

This is Monday morning for **Jordan Rivera**, an enterprise AE. Jordan's question is simple: "Where do I spend my week?" Today, Jordan answers that by opening four tools. Here it's one screen, and it's fresh.

**SHOW**

*[Share screen. App on My Week, logged in as Jordan.]*

1. *[Point at the freshness badge, top-right.]* First, look at this: the data is fresh. We timed one increment from a new CRM file landing to the row this app reads: **9.0 minutes**. Today that's a two-hour batch.
2. *[Point at the KPI strip.]* Jordan's quarter, FY27 Q4: quota attainment at **35.3%**, open pipeline and commit across **18 open deals**. Coverage is **3.5×**. So Jordan has enough pipeline. The problem isn't volume. It's which deals to push.
3. *[Point at Priority deals.]* These are ranked by **ACV times the probability of closing this quarter**. Each one has a probability bar, and these chips say *why*: "competitor mentioned on last call," "usage down 18%," "no activity in 21 days."
4. *[Point at the Next best actions queue.]* And on the right, the actions the Hub thinks Jordan should take this week, each with a one-line reason.
5. *[Hover over a deal row. Let the page respond instantly.]* Notice how fast that is. It's reading from an operational database, not running a report.

**TELL: so what**

So in about ten seconds, Jordan knows the three deals that matter most and exactly what to do on each. **That's the 2 hours a week of prep time from Lever 2, and it's the seat-retirement story from Lever 1, because this replaces the revenue-intelligence dashboard Jordan used to open.**

- **Exec framing:** "Every one of your 600 sellers starts the week with a prioritized, evidence-backed plan instead of a stale dashboard."
- **Technical deep-dive option:** *[To the architect:]* "This page is served from Lakebase, which is Postgres managed by Databricks, through synced tables from Unity Catalog. I'll show the plumbing in a few minutes. Happy to go now if you'd like."

*Compress:* skip the hover and point only at freshness and Priority deals.

## 7:00 – Segment 2: Deal 360, AI insights and score (3 min)

**TELL**

Let's open Jordan's top deal. This is the screen that replaces the "stitch it together by hand" problem: CRM, the call, usage and tickets on one page, with AI that reads the call so Jordan doesn't have to re-listen.

**SHOW**

*[Click the top Priority deal. Deal 360 opens.]*

1. *[Point at the header and stage timeline.]* The basics from Salesforce: stage, ACV, close date, and how long it's sat in this stage.
2. *[Point at the AI score panel.]* Here's the AI's view. Probability of closing this quarter is **0.86** on this deal (Solis Construction), with the full distribution, not just a single number. And here's the suggested next action, with its own probability. The model returns calibrated probabilities, so we can rank by expected value instead of gut feel.
3. *[Point at Latest call insights.]* This came from the Google Meet transcript. The AI pulled out the **next steps** with owners and due dates, the **open items**, the products the customer is **interested** in, and, look here, a **competitor mention**: they brought up **RoadLynx** pricing. That isn't in the CRM competitor field. It was only on the call.
4. *[Point at the usage sparkline and adoption by product.]* This is their fleet's actual product usage. Active vehicles are trending down, and they've never turned on Driver Safety. That's whitespace and a risk signal at the same time.
5. *[Point at the support tickets.]* There's an open high-severity ticket. You do *not* want to send a proposal into an open P1 without knowing about it.
6. *[Point at Contacts.]* Note the emails and phone numbers are **masked**. The app never holds raw PII. I'll come back to that for you, [Architect].

**TELL: so what**

Before this, Jordan finds out about the RoadLynx mention and the P1 ticket in the meeting, from the customer. Now Jordan walks in knowing both. **That's the win-rate lever: better-prepared calls on the deals most likely to move.** And on accuracy, we didn't just eyeball this. We tested the score against deals whose outcome we know. On 400 held-out closed deals it scores an AUC of **0.695**, and the top 10% of deals it ranks close at **2.06×** the average rate (80% vs 39%). That's against the synthetic data's hidden ground truth, so read it as "the pipeline works", and the pilot re-measures it on your closed deals.

- **Exec framing:** "Your sellers get a researched brief on every deal, and a score you can audit, not a black box."
- **Technical deep-dive option:** "Two different AI jobs here. Reading the call is generative, using `ai_query` with Claude and a strict JSON schema, so the output lands as typed columns. The score is a classifier, OpenJev, that returns calibrated probabilities and no generated text, so it's cheap and consistent. I can walk the evaluation if you want."

*Compress:* skip usage and tickets. Land the competitor mention and the score.

## 10:00 – Segment 3: Next-best-action write-back (1.5 min)

**TELL**

An insight is only worth something if the seller acts on it, and if we learn from what they do. Watch what happens when Jordan accepts an action.

**SHOW**

*[Still on Deal 360, or back on My Week. Find the NBA you left unaccepted.]*

1. *[Point at the action.]* The Hub suggests "Bring in an exec sponsor before proposal," because the classifier says single-threaded risk is high and the call confirms only one stakeholder.
2. *[Click **Accept**.]* Accepted. *[Refresh or move to My Week.]* It's moved state instantly. That write went to Lakebase, the operational database.
3. *[Optionally dismiss a different action with a reason.]* If Jordan dismisses one, we capture why.
4. *[To the architect:]* Every accept or dismiss lands in Delta in about a minute (59 s measured), so it's governed and has lineage, like everything else.

**TELL: so what**

That gives you something you've never had: **a measured adoption rate per action type, per rep.** Today you can't tell whether a dashboard changed what anyone did. Here, you'll know, and the ranking gets better as sellers use it.

- **Exec framing:** "You get proof of adoption, not just logins."
- **Technical deep-dive option:** "The app writes to native Postgres tables in Lakebase. Lakehouse Sync streams those writes (CDC) into a Unity Catalog table in about a minute, and the job MERGEs them into `silver_seller_actions`, then a feedback table. One copy of truth, with lineage both ways."

*Compress:* click Accept, say the exec line, move on.

## 11:30 – Segment 4: Ask Genie (2 min)

**TELL**

No screen ever has every question on it. So instead of filing a request with RevOps for a new report, Jordan can just ask. This is the **Fleetwise Revenue Copilot**, a Genie agent, built into the app.

**SHOW**

*[Click **Ask Genie** in the app.]*

1. *[Type, or click the sample question:]* "Which of my Enterprise deals mention a competitor on a call and close this quarter?"
2. *[While it runs:]* It's going to write SQL against the same governed gold tables we just looked at.
3. *[Point at the answer and the table.]* There's the list, with the competitor named on each.
4. *[Click **Show SQL** or the query view.]* And here's the SQL it wrote. Anyone can check its work. Nothing is hidden.
5. *[Follow-up:]* "Which of those have usage trending down?" *[It keeps the context.]*
6. *[Key point. Look at the architect.]* And notice Jordan only sees **Jordan's** deals. Genie runs as the signed-in user, so the Unity Catalog row filters apply. I didn't build a separate security model for the chat.

**TELL: so what**

That's an ad hoc report that today takes a RevOps ticket and a few days, answered in about **18 seconds** (median 18.5 s on our benchmark). **It reduces RevOps report backlog and it's one more tool you don't need a seat for.** On accuracy, we benchmarked it on a fixed set of questions: **9 out of 10 correct**, and the one miss was a correct empty answer on a gap in the synthetic data.

- **Exec framing:** "Every seller and manager gets an analyst who answers in plain English and shows their work."
- **Technical deep-dive option:** "Genie is grounded with table and column comments from Unity Catalog, join definitions, our fiscal-calendar rules, and trusted example SQL. The app calls it through the Genie Conversation API with on-behalf-of-user auth."

*Compress:* one question, show the SQL, make the row-filter point.

## 13:30 – Segment 5: The manager persona (1.5 min)

**TELL**

Now let's switch hats. [Exec], this is what you and your managers care about. **Morgan Lee** manages Jordan's team, and Morgan uses the same app.

**SHOW**

*[Use the persona switcher: Jordan Rivera → Morgan Lee (manager). My Week reloads.]*

1. *[Point at the KPI strip.]* Same screen, now scoped to Morgan's team: 8 reps, 46 open deals, attainment and coverage across the team, from the same data the sellers see.
2. *[Point at Priority deals.]* The team's deals, from every rep, ranked the same way, with the same "why" chips: competitor, usage drop, stale activity.
3. *[Open one of another rep's deals.]* Morgan can open any deal on the team in Deal 360 and walk into the forecast call with the evidence.
4. *[Point at the scope.]* Morgan sees the whole team. Jordan, as we saw, sees only Jordan's book. Same app, same data, scoped by role.

*[Switch the persona back to Jordan.]*

**TELL: so what**

Your Monday forecast call goes from "tell me about your deals" to "here are the deals at risk, what's the plan for each." **That's forecast accuracy and manager time, from the same numbers your sellers see.** A dedicated team roll-up screen (adoption by rep, forecast roll-up) is on the roadmap; the write-back data for it is already flowing.

- **Exec framing:** "Your managers coach from evidence, and you get a forecast built on the same numbers your sellers see."
- **Technical deep-dive option:** "Scoping follows the hierarchy: seller → manager → RVP, from `gold_user_hierarchy`. On the lakehouse side, it's a UC row filter. In the app's Postgres reads, it's the same hierarchy applied in the query. The persona switcher is demo impersonation for one developer identity, not an entitlement."

*Compress:* switch persona, show the team's deals, make the scoping point, switch back.

## 15:00 – Segment 6: Under the hood (2.5 min)

*[Turn to the architect.]* [Architect], this part is mostly for you. [Exec], I'll keep it short, and I'll tell you why each piece matters to the business.

**TELL**

There are six layers, and the key point is that it's **one connected journey on the same entities**: account, opportunity, transcript, score, action. Nothing is copied into a side database that drifts.

**SHOW**

*[Switch to Catalog Explorer on `gold_opportunity_pipeline` → **Lineage**.]*

1. **Ingest: Lakeflow.** *[Point at the upstream nodes.]* Salesforce-shaped exports, Meet transcripts, usage and tickets land in a Unity Catalog volume. A Lakeflow Spark Declarative Pipeline picks up only new files with Auto Loader and builds bronze, silver and gold. Data-quality expectations drop bad keys and dates. In our runs, about 456,000 silver rows went through and **zero failed an expectation** (that's in the evidence). In production, the Salesforce side switches to the **Lakeflow Connect Salesforce connector** instead of file drops.
2. **Govern: Unity Catalog.** *[Point at the columns tab, then the tags.]* Every table and column has a comment, which also teaches Genie. Contact email and phone are tagged PII with a column mask. Row filters scope sellers to their book and managers to their hierarchy.
3. **Intelligence.** *[Point at downstream nodes `gold_call_insights` and `gold_deal_scores`.]* The AI tables are part of the same lineage graph. You can trace a score back to the transcript and the opportunity it came from.
4. **Serve: Lakebase.** *[Point at the synced tables.]* Gold tables sync into Lakebase Postgres, so the app does millisecond point reads (Lakebase adds **6.3 ms** over the network baseline; the query itself runs in 0.07 ms) instead of 90-second dashboard queries. App writes go to Postgres and land back in Delta in about a minute.
5. **Orchestrate and deploy.** One Lakeflow job runs the whole chain (generate, refresh, AI, score, sync, write-back merge, evaluate), and the whole thing is defined in a **Databricks Asset Bundle**. It deploys to dev or prod from Git with one command.

**TELL: so what**

For you, [Architect]: one governance model, one lineage graph, serverless everywhere, everything in Git. For you, [Exec]: **this is why it's not a homegrown science project.** It's managed platform services wired together, and it's reproducible from one bundle deploy and one job run.

- **Exec framing:** "Your data team owns one platform, not five integrations."
- **Technical deep-dive options** (offer one, let them pick): the row filter function and masked vs unmasked query evidence; the synced-table modes and refresh cadence; the score evaluation notebook; the job DAG and run history.

*Compress:* show lineage only, name the five layers in one sentence each.

## 17:30 – Close: recap, pilot and asks (2.5 min)

*[Stop sharing, or go to a single summary slide. Look at the exec.]*

Let me bring it back to what you each told me you needed.

[Exec], you wanted *[repeat their words from the opening]*. Here's the recap:

- **Cost:** about **$1.08 million a year** in add-on seats you can retire, on a platform that costs a fraction of that to run.
- **Productivity:** about **55,000 seller hours a year**, roughly 27 sellers' worth of capacity, if we save each seller 2 hours a week.
- **Revenue:** a credible path to **one point of win rate** on worked pipeline, about **$6 million of ACV**, which we'll prove rather than promise.

[Architect], you wanted *[repeat their words]*. You saw one governed lineage from raw files to the app, row-level scoping that Genie inherits automatically, masked PII, and the whole thing deployable from Git.

**Here's what I propose: a six-week pilot.**

| Week | What happens |
|---|---|
| 1 | Connect Salesforce through Lakeflow Connect (read-only connected app); connect Meet transcripts, usage and tickets; security review kickoff |
| 2–3 | Stand up the Hub on your data, map Salesforce role hierarchy and sharing to UC row filters, calibrate the score on your own closed deals |
| 4–6 | ~40 sellers and 4 managers across two regions use it daily; we measure every week |
| 6 | Readout and go / no-go decision with the numbers below |

**Success criteria we'd agree on up front:**

| Criterion | Target |
|---|---|
| Weekly active pilot sellers | ≥ 70% |
| Self-reported and measured pre-call prep time | down ≥ 30% vs baseline survey |
| NBA acceptance rate | ≥ 30% of surfaced actions accepted |
| Data freshness (Salesforce change → visible in app) | ≤ 15 minutes |
| App page read latency | p95 under 300 ms |
| Deal score on your own closed history | AUC ≥ 0.75 and well calibrated |
| Genie benchmark on your 25 hardest questions | ≥ 90% correct, SQL visible |
| Security | zero scoping violations in a red-team test; PII never stored unmasked in the app |
| Seat-retirement plan | signed-off list of add-on seats retirable at renewal |

**My asks:**

1. [Exec]: an **executive sponsor** (you) and a named **RevOps owner** for the pilot.
2. [Architect]: a **read-only Salesforce connected app** and access to the transcript and usage sources, plus a security reviewer in week 1.
3. Together: pick the **40 pilot sellers**, and put the **week-6 decision meeting** on the calendar today, ideally ahead of your add-on seat renewal date.

*[Pause. Stop talking. Let them respond.]*

What would stop us from starting the week after next?

*[Listen. Whatever they say is your first objection. Handle it, then ask: "If we solve that, are we good to go?"]*

## If something breaks live

| Failure | What you say | What you do |
|---|---|---|
| App slow on first click | "It's waking up. Lakebase scales to zero when nobody's using it, which is why the idle cost is low." | Click again; you warmed it up, so this should be rare |
| App errors or won't load | "Let me show you the same data the app reads." | Switch to Catalog Explorer or Genie on the same gold tables |
| Genie gives a wrong or odd answer | "Good. This is why we show the SQL. Let's look at what it did." | Open the SQL, point out the misread, say how a trusted example would fix it; never hide it |
| Genie is slow | "While that runs, notice it's querying governed tables, not a copy." | Talk through grounding; fall back to the standalone Genie tab |
| Network drops | "Let me walk you through it from the run evidence." | Open README walkthrough and `evidence/` text |

## Measured numbers in this track

| Number | Source |
|---|---|
| Freshness **9.0 min** (540.6 s), file landed → the Lakebase row the app reads | `evidence/10_e2e.md` |
| Jordan FY27Q4: attainment **35.3%**, coverage **3.5×**, 18 open deals | `evidence/09_app.md` (`GET /api/home`) |
| Morgan Lee (manager): 8 reps, 46 open deals | `evidence/09_app.md` |
| Top deal P(close this quarter) **0.86** (Solis Construction) | `evidence/09_app.md` |
| AUC **0.695**; top-decile lift **2.06×** (80% vs 38.75% base, 400 held-out closed deals) | `evidence/06_nba_and_eval.md` |
| Competitor extraction P/R **1.00 / 1.00** (287 planted mentions) | `evidence/06_nba_and_eval.md` |
| Write-back **59.1 s**, app write → Delta (CDC 16.2 s) | `evidence/07_lakebase.md` |
| Lakebase **6.3 ms** added over network baseline (0.07 ms server-side) | `evidence/07_lakebase.md` |
| Genie **9/10**, median **18.5 s** | `evidence/08_genie.md` |
| Run cost **~1.65 DBU ≈ $1.15** per incremental run (≈ $10K/yr if hourly; estimate) | `docs/VALUE_MODEL.md` |
| Tests: **184 passed, 1 failed, 1 skipped** (the failure found a real view-grant bug, fixed in code) | `evidence/11_tests.md` |

## Value arithmetic (assumptions, for reference)

| Lever | Assumption | Arithmetic | Result |
|---|---|---|---|
| Seat retirement | 600 sellers; add-on list price $75–$220/user/month, midpoint $150 | 600 × $150 × 12 | **$1.08M/yr** (range $0.54M–$1.58M) |
| Seller time | 2 hrs/week saved; 46 working weeks; 2,000 hrs per FTE-year | 600 × 2 × 46 = 55,200 hrs; ÷ 2,000 | **~55K hrs/yr ≈ 27 FTE** of selling time |
| Win rate (upside) | $600M/yr worked pipeline; +1 pt win rate | $600M × 0.01 | **~$6M ACV/yr** |
| Platform run cost | Serverless pipeline + AI enrichment + Lakebase + app + Genie at full scale | assumption at full scale; measured at demo scale ~$1.15 per incremental run (≈ $10K/yr hourly; estimate) | **~$150K–$250K/yr** |
| Payback | Build and pilot effort assumption: 2 engineers × 12 weeks ≈ $150K | ($150K build + $200K run) vs $1.08M seat savings | **≈ 4 months on seats alone** (conservative ≈ 9 months) |
