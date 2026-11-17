# FE Bar — Requirements Checklist (working notes)

## Scoring
Four domains, each Below / Meets / Exceeds: **Product, Industry, Build + AI Mindset, Customer Skills**.
Final: Did not pass / Pass / Strongly passed. AI evaluator reads **text only**.

## Part 1 — The Build (4–8 hrs)
Real customer problem in a specific industry (use Industry Outcome Maps). End-to-end, **integrated** data journey from raw synthetic/public data:

| Stage | Requirement |
|---|---|
| Lakeflow | Ingest the raw data |
| Unity Catalog | Govern it |
| Lakebase | Operational serving |
| ML or GenAI | Make it intelligent |
| Genie Agent | Natural-language querying |
| Databricks App | Surface it to the business |

### Submission contents
1. **Build (required)**: code, notebooks, app, dashboards + **execution evidence as text**
   (notebooks committed with outputs, run logs, query results, model output). Screenshots don't count.
   Source alone fails Build. GitHub repo link required and readable (public or connected EMU).
   No real customer data.
2. **Deck (required)**: PDF/.txt/.md. Lead with business outcome, quantify in buyer KPIs,
   value framed for exec sponsor AND domain owner.
3. Conversation ID (optional).

## Part 2 — AI Demo Roleplay (20–30 min, Yoodli)
Two personas at once: business stakeholder (exec/funder) + technical stakeholder (architect/data lead).
Scored on: demo setup, tell-show-tell, value communication (KPIs, exec altitude), reading the room
(altitude switching), professionalism/objection handling.
Prep pushback: cost, risk, time-to-value (biz); architecture, data quality, security, integration (tech).

## Integrity rules
Own work only; not from go/solution-builder; no sharing/reuse. AI tools are encouraged — document them.

## Tips → design implications
- README opens with business problem + quantified value; architecture later.
- Make data flow obvious and connected (lineage visible in UC; same entities flow through every layer).
- "Decisions & trade-offs" section.
- "AI as force multiplier" section: tools, prompts, patterns used.
- Common fails: internal problem, disconnected layers, narrative skips value.
