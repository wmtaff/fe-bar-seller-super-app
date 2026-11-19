# AI as a force multiplier

The whole build (synthetic data generator, Lakeflow pipeline, Unity Catalog governance, AI enrichment and
scoring, Lakebase serving and write-back, Genie space, Databricks App, tests and evidence) was produced
in about two working days with **Claude Code**, working in a *subagent-driven* mode. One human (Will)
owned the problem, the decisions and the approvals; the AI did most of the typing, running and checking.

## How it was set up

1. **Spec first.** A design spec (`docs/superpowers/specs/2026-11-17-seller-super-app-design.md`) written with
   the AI in a brainstorming loop: intent, goals and anti-goals, architecture, decisions & trade-offs.
2. **Plan second.** A 12-task build plan (`docs/superpowers/plans/2026-11-17-seller-super-app.md`) with, for
   each task, the files, interfaces, failing tests to write first, and the evidence to produce.
3. **A controller session dispatched one implementer subagent per task**, each with a short brief and a
   shared global context, followed by an **independent reviewer subagent** that read the diff against the
   spec (spec compliance, then code quality). Findings classed Critical / Important / Minor; only Critical
   and Important triggered a fix round. A ledger recorded every dispatch, review and **ruling** (R1–R23), so
   decisions survived context limits and were auditable.
4. **Databricks skills** loaded into the agents gave them current, idiomatic product guidance: Asset Bundles,
   Lakeflow Declarative Pipelines, Unity Catalog (row filters, masks, tags, system tables), AI Functions,
   Lakebase (Autoscaling, synced tables, Lakehouse Sync), Genie agents, Databricks Apps (AppKit), jobs and
   the Python SDK.
5. **Speed mode at the end** (ruling R23): when the user said "just make it work, this is for a demo",
   per-task reviews were dropped for Tasks 9–12 in favor of one final branch review.

## What the AI did vs. what the human decided

| The human decided | The AI did |
|---|---|
| Industry and problem: a fleet-telematics SaaS seller org (~600 sellers) consolidating per-seat revenue-intelligence add-ons into one Databricks-backed app | Turned that into a spec, a 12-task plan, and Salesforce-API-shaped synthetic data with planted, measurable truth |
| Scope: Lakehouse RT out of scope; Team/Manager view and email drafting cut for time | Implemented the remaining demo path end to end; documented the cuts |
| Private GitHub repo, no real customer names anywhere | Anonymized everything ("Fleetwise"); scrub checks in the final task |
| Governance: mask-only for PII (no unmasked group), grants to the app service principal only, never to broad groups | Wrote masks, row filters, dynamic views, tags, the grant plan and a second-principal test |
| "Simple but best practices", then "plumbing over polish" (data realism doesn't gate), then speed mode | Applied those as rulings so reviewers gated on working code, tests, evidence and security, not cosmetics |
| Approvals for anything that deploys, grants or deletes | Asked; when the permission system denied a deploy or grant, stopped and surfaced it instead of working around it |

## Real catches by the reviewer subagents (each fixed before moving on)

- **Evaluation leak via the CRM competitor field (Task 7).** The score evaluation re-scored closed deals "as
  of" a pre-close snapshot, but the snapshot still read `Competitor__c`, which the generator back-fills at
  loss time. That is post-outcome information. Removing it moved AUC from 0.697 to **0.695**; the number we
  report is the clean one.
- **Lead outcome leakage (Task 2, ruling R11).** Raw `Lead.Status` encoded the planted `will_win` intent.
  Fix: keep the realistic CRM fields in raw data, but lead scoring uses only open leads and excludes
  `Status / IsConverted / ConvertedDate`, and the lead eval masks them.
- **`NextStep` wiped on increments (Task 2).** Increment batches wrote `NextStep = null`, so every daily run
  would have erased the seller's next step downstream. Fixed in the generator, with an increment test.
- **Circular quotas (Task 3, ruling R13).** Per-seller quotas were being fitted from the same pipeline they
  were meant to judge (coverage came out 12x). Replaced with quota = clamp(trailing closed-won × 1.2, segment
  bounds) and hard sanity tests.
- **Row-level-security bypass gaps (Task 4, ruling R16).** The first governance pass row-filtered the
  pipeline view but left `gold_account_360` unfiltered, let duplicate identity-map rows break the persona
  lookup, left the map caller-writable, and had no grant model. Fixed with dynamic views for every
  seller-facing object, a deterministic single-row persona lookup, MODIFY only for owners, a parameterized
  grant plan applied only to the app SP, and a test that runs as that second principal.
- Smaller but real: a busy-poll test fixture (Task 1), unpinned `faker` breaking byte-identical output
  (Task 2), a nested-function column mask that broke incremental refresh (Task 4).

## What actually happened when reality disagreed with the plan

- `ai_decide` was blocked (preview not enabled), so scoring calls OpenJev directly over the System One API.
- The model endpoint rejected `responseFormat`, so the JSON schema went into the prompt and every response is
  validated with `from_json` against the declared schema (R19); malformed rows land in `extract_error`.
- Materialized views can't sync as TRIGGERED to Lakebase, so four MV-backed synced tables use SNAPSHOT (R21).
- The write-back path became **Lakehouse Sync** (Postgres CDC into UC), measured at a 59.1 s round trip.
- An Apps build failed on an npm mirror 404 for a dev dependency; the controller fixed the package manifest.
- The final full test run caught the job's `CREATE OR REPLACE VIEW` silently dropping the app service
  principal's view grants on every run; the DDL now uses `ALTER VIEW` (a static test guards it), and the
  re-grant waits for the human's approval because the agent isn't allowed to grant on its own.

## Patterns that made it work

- **Spec → plan → task briefs → TDD**: each brief named the failing test to write first; "done" meant the
  test passed against the live workspace and the evidence file was committed.
- **Independent review** by a fresh subagent that only sees the diff and the spec, so it isn't anchored on the
  implementer's reasoning.
- **A ledger of rulings** with "cost if wrong" for each, so trade-offs are explicit and reversible.
- **Evidence as text**: every task wrote `evidence/NN_*.md` from real runs (run ids, counts, query output), and
  tests write measured numbers into JSON that the evidence quotes, so docs can't drift from measurements.
- **No hard-coded truth in tests** (R14): expected counts and ids are read from the live data.
- **Human-in-the-loop for blast radius**: deploys, grants and deletes go through the permission system;
  denials are reported, never retried around.
