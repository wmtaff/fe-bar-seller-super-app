# 09 - Databricks App: Fleetwise Seller Hub (Task 10)

Measured 2026-11-18/19 (UTC) on `fevm-serverless-stable-s1omq8`. All API calls below were made with the
developer's user OAuth token (`Authorization: Bearer $(databricks auth token -p fevm-serverless-stable-s1omq8 | jq -r .access_token)`),
so the Apps proxy forwards a real user identity (OBO) exactly as for a browser session.

## App status

```json
{
  "name": "fleetwise-seller-hub",
  "url": "https://fleetwise-seller-hub-7474646802937769.aws.databricksapps.com",
  "app_status": {
    "message": "App has status: App is running",
    "state": "RUNNING"
  },
  "compute_status": {
    "message": "App compute is running.",
    "state": "ACTIVE"
  },
  "service_principal_client_id": "e51bc893-d86b-4fd5-9834-d1276fe878c8",
  "user_api_scopes": [
    "sql",
    "dashboards.genie"
  ],
  "active_deployment": {
    "deployment_id": "01f1e3c09f111f3db517180b991c5879",
    "status": {
      "message": "App started successfully",
      "state": "SUCCEEDED"
    },
    "source_code_path": "/Workspace/Users/will.taff@databricks.com/apps/fleetwise-seller-hub",
    "create_time": "2026-11-19T02:26:26Z"
  },
  "resources": [
    {
      "name": "sql-warehouse",
      "sql_warehouse": {
        "id": "9a6db1d12e2ee6d3",
        "permission": "CAN_USE"
      }
    },
    {
      "genie_space": {
        "name": "Fleetwise Revenue Copilot",
        "permission": "CAN_RUN",
        "space_id": "01f1e3a1962912c08de057636d1912d8"
      },
      "name": "genie-space"
    },
    {
      "name": "postgres",
      "postgres": {
        "branch": "projects/seller-superapp/branches/production",
        "database": "projects/seller-superapp/branches/production/databases/databricks-postgres",
        "permission": "CAN_CONNECT_AND_CREATE"
      }
    }
  ]
}
```

## Deploy notes

1. **App created** with `databricks apps create` (resources and OBO scopes as in the bundle resource
   `resources/fleetwise_seller_hub.app.yml`); source uploaded with `databricks sync` (gitignore-aware: no
   `.env`, no `node_modules`) to `/Workspace/Users/will.taff@databricks.com/apps/fleetwise-seller-hub`,
   deployed with `databricks apps deploy fleetwise-seller-hub --source-code-path <that path>` (run by the
   controller after user approval).
2. **First deploy FAILED:** the Apps build's npm mirror returned 404 for `playwright-core@1.56.1` (pulled
   in by the `@playwright/test` devDependency). Fix (commit `1c75acc`): drop Playwright from the app's
   dependencies; exclude `tests/` from `tsconfig.server.json`. Later (`2c6eb59`) the smoke suite got its
   own `tests/package.json`, so `npm run test:smoke` installs Playwright locally only and the Apps build
   never sees it. Redeploy: **RUNNING**, deployment `01f1e3c09f111f3db517180b991c5879`.
3. Deploy-first held: the SP ran `server/sql/app_schema.sql` at startup and owns Postgres schema `app`
   (checked by `jobs/app_post_deploy.py` before granting).
4. **Not yet live:** commit `39f67e6` (render structured call-insight next steps as "action (owner) due
   date" instead of raw JSON) is committed and synced to the source path but the redeploy was denied
   by the permission system for this agent; it needs one more `databricks apps deploy` by the user.

## Grants applied (app SP `e51bc893-d86b-4fd5-9834-d1276fe878c8` only; nothing to groups)

`jobs/app_post_deploy.py` (run by the controller; `d786ee8` commits the required grants before the
optional default-privileges step).

Postgres (Lakebase, as project owner):
```sql
GRANT USAGE ON SCHEMA serving TO "e51bc893-d86b-4fd5-9834-d1276fe878c8";
GRANT SELECT ON ALL TABLES IN SCHEMA serving TO "e51bc893-d86b-4fd5-9834-d1276fe878c8";
-- optional, FAILED with a warning (owner is not a member of databricks_writer_16407):
-- ALTER DEFAULT PRIVILEGES FOR ROLE "databricks_writer_16407" IN SCHEMA serving GRANT SELECT ON TABLES TO ...
-- => re-run app_post_deploy.py after any synced table is re-created.
```

Unity Catalog (`src/governance/grants.sql` rendered with principal = the SP):
```sql
GRANT USE CATALOG ON CATALOG `serverless_stable_s1omq8_catalog` TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT USE SCHEMA ON SCHEMA `serverless_stable_s1omq8_catalog`.`seller_superapp` TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_opportunity_pipeline TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_seller_kpis TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_account_360 TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_next_best_actions TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_call_insights TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.v_deal_scores TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.gold_user_hierarchy TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.gold_lead_scores TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.gold_nba_feedback TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
GRANT SELECT ON TABLE `serverless_stable_s1omq8_catalog`.`seller_superapp`.gold_contacts_masked TO `e51bc893-d86b-4fd5-9834-d1276fe878c8`;
```

Verified with `SHOW GRANTS`: the SP holds `USE SCHEMA` on `seller_superapp` and `SELECT` on
`v_opportunity_pipeline`, and **no grant at all** on `gold_opportunity_app` or `demo_identity_map`.
No MODIFY on the identity map is needed: the persona switcher MERGEs the caller's own row **OBO**
(user scope `sql`) through the warehouse.

## Second-principal check (R16), automated

`GET /api/health/governance` runs **as the app service principal** on the warehouse
(`appkit.analytics.query` outside a user scope):

```json
{
  "principal": "app service principal",
  "base_table": {
    "table": "gold_opportunity_app",
    "ok": false,
    "error": "INSUFFICIENT_PERMISSIONS"
  },
  "view": {
    "table": "v_opportunity_pipeline",
    "ok": true,
    "rows": 0
  },
  "pass": true
}
```

The base gold table is denied (`INSUFFICIENT_PERMISSIONS`); the row-filtered view is readable and
returns 0 rows for the SP (it has no persona in `demo_identity_map`, so `fn_can_see_owner` shows it
nothing). Asserted by `tests/integration/test_app.py::test_sp_second_principal_governance`.

## API captures

### `GET /api/me`
```json
{
  "email": "will.taff@databricks.com",
  "persona_user_id": "0050g000000003OAAQ",
  "persona_name": "Jordan Rivera",
  "role": "seller",
  "persona_key": "seller",
  "mapped": true,
  "visible_owner_count": 1
}
```

### `PUT /api/persona` (manager, then back to seller; admin rejected)
```json
{
  "email": "will.taff@databricks.com",
  "persona_user_id": "0050g000000000MAAQ",
  "persona_name": "Morgan Lee",
  "role": "manager",
  "persona_key": "manager"
}
```
`GET /api/home` as the manager (team scope: 8 reps, deals from 8 owners):
```json
{
  "persona": {
    "persona_user_id": "0050g000000000MAAQ",
    "persona_name": "Morgan Lee",
    "role": "manager"
  },
  "kpis": {
    "fiscal_quarter": "FY27Q4",
    "reps": 8,
    "quota": 2077500,
    "closed_won_acv": 176700,
    "attainment_pct": 0.08505415162454874,
    "open_pipeline_acv": 6224400,
    "commit_acv": 748500,
    "best_case_acv": 3589400,
    "open_opportunities": 46,
    "won_opportunities": 1,
    "coverage_ratio": 3.274621212121212
  },
  "n_deals": 15,
  "owners": [
    "John Smith",
    "Jordan Rivera",
    "Rachel Lopez",
    "Robyn Simmons",
    "Tammy Clements",
    "Timothy Ibarra",
    "Tracy Salazar",
    "William Andrade"
  ]
}
```
```json
{
  "email": "will.taff@databricks.com",
  "persona_user_id": "0050g000000003OAAQ",
  "persona_name": "Jordan Rivera",
  "role": "seller",
  "persona_key": "seller"
}
```
`PUT /api/persona {"persona":"admin"}`:
```
{"error":"persona must be one of seller | manager | empty"}
HTTP 400
```

### `GET /api/home` (Jordan Rivera, FY27Q4; excerpt)
```json
{
  "persona": {
    "persona_user_id": "0050g000000003OAAQ",
    "persona_name": "Jordan Rivera",
    "role": "seller"
  },
  "fiscal_quarter": "FY27Q4",
  "kpis": {
    "fiscal_quarter": "FY27Q4",
    "reps": 1,
    "quota": 500000,
    "closed_won_acv": 176700,
    "attainment_pct": 0.3534,
    "open_pipeline_acv": 1131600,
    "commit_acv": 401100,
    "best_case_acv": 565700,
    "open_opportunities": 18,
    "won_opportunities": 1,
    "coverage_ratio": 3.5001546551190845
  },
  "freshness_ts": "2026-11-16T13:00:00.000Z",
  "priority_deals (15; first 2)": [
    {
      "opportunity_id": "0060g000000037YAAQ",
      "opportunity_name": "Solis Construction - Vehicle Telematics + 1 New Business",
      "account_name": "Solis Construction",
      "owner_name": "Jordan Rivera",
      "stage": "Negotiation",
      "acv": 173100,
      "close_date": "2026-12-30",
      "fiscal_quarter": "FY27Q4",
      "p_close_quarter": 0.8576199144570852,
      "close_label": "Likely",
      "next_action": "address_risk",
      "competitive_risk": 0.8354835207180245,
      "churn_risk": 0.03732688948593843,
      "days_since_last_activity": 7,
      "competitor": "RoadLynx",
      "expected_acv": 148454.00719252144
    },
    {
      "opportunity_id": "0060g000000037hAAA",
      "opportunity_name": "Reid General Contractors - Vehicle Telematics + 1 New Business",
      "account_name": "Reid General Contractors",
      "owner_name": "Jordan Rivera",
      "stage": "Proposal",
      "acv": 105800,
      "close_date": "2027-01-20",
      "fiscal_quarter": "FY27Q4",
      "p_close_quarter": 0.9043950926508699,
      "close_label": "Very likely",
      "next_action": "address_risk",
      "competitive_risk": 0.13296425394084313,
      "churn_risk": 0.03308598029553404,
      "days_since_last_activity": 0,
      "competitor": null,
      "expected_acv": 95685.00080246203
    }
  ],
  "actions (20; first 1)": [
    {
      "action_id": "75b600d4c10a01a17b0aae65f45ba13dfabe99952e6177fb5fe041ce36ee36d6",
      "opportunity_id": "0060g000000037YAAQ",
      "account_id": "0010g0000000000AAA",
      "action_type": "call_next_step",
      "title": "Set up time with the Solis leadership team to review the proposal",
      "why": "Agreed on the 2026-10-29 call (owner: Frances Gonzalez (customer, VP Operations)), due 2026-11-05.",
      "source": "call",
      "due_date": "2026-11-05",
      "priority_score": 222681.01078878215,
      "opportunity_name": "Solis Construction - Vehicle Telematics + 1 New Business",
      "account_name": "Solis Construction"
    }
  ]
}
```

### `GET /api/deals/0060g000000037YAAQ` (Jordan's top deal; excerpt)
```json
{
  "opportunity": {
    "opportunity_id": "0060g000000037YAAQ",
    "opportunity_name": "Solis Construction - Vehicle Telematics + 1 New Business",
    "account_name": "Solis Construction",
    "stage": "Negotiation",
    "acv": 173100,
    "close_date": "2026-12-30T00:00:00.000Z",
    "owner_name": "Jordan Rivera",
    "competitor": "RoadLynx"
  },
  "scores": {
    "p_close_quarter": 0.8576199144570852,
    "close_label": "Likely",
    "close_confidence": 0.5632435426691864,
    "competitive_risk": 0.8354835207180245,
    "churn_risk": 0.03732688948593843,
    "next_action": "address_risk",
    "next_action_conf": 0.9654887824962339,
    "scored_at": "2026-11-18T20:19:33.805Z"
  },
  "account": {
    "account_name": "Solis Construction",
    "industry": "Construction",
    "fleet_size": 673,
    "arr": 0,
    "products_owned": [],
    "whitespace_products": [
      "Vehicle Telematics",
      "AI Dash Cams",
      "Driver Safety",
      "Fuel & Maintenance",
      "Compliance/ELD",
      "Equipment Monitoring"
    ]
  },
  "insights (2; latest)": {
    "started_at": "2026-10-29T22:30:00.000Z",
    "sentiment": "positive",
    "next_steps": [
      {
        "due": "2026-11-04",
        "owner": "Jordan Rivera (Fleetwise AE)",
        "action": "Send a side-by-side comparison against the RoadLynx quote, including coaching and insurance savings"
      },
      {
        "due": "2026-11-05",
        "owner": "Frances Gonzalez (customer, VP Operations)",
        "action": "Set up time with the Solis leadership team to review the proposal"
      },
      {
        "due": "2026-11-12",
        "owner": "Jordan Rivera (Fleetwise AE)",
        "action": "Schedule a call between Albert Harris and the Solis IT team"
      },
      {
        "owner": "Albert Harris (Fleetwise Sales Engineer)",
        "action": "Set up the integration with the customer's maintenance system during onboarding"
      }
    ],
    "open_items": [
      "Whether the insurance savings are real and how to prove them",
      "Leadership team approval and decision",
      "Implementation timeline for a rollout before 2026-12-04",
      "Monthly executive reporting format for leadership",
      "IT review of the maintenance system integration"
    ],
    "competitors": [
      "RoadLynx"
    ]
  },
  "contacts (first 2, masked)": [
    {
      "contact_id": "0030g0000000001AAA",
      "name": "Dana Campbell",
      "title": "Chief Financial Officer",
      "buyer_role": "CFO",
      "email": "d***@solisconstruction.com",
      "phone": "***-***-0137",
      "mailing_state": "ID"
    },
    {
      "contact_id": "0030g0000000002AAA",
      "name": "Samantha Bryant",
      "title": "Director of Fleet",
      "buyer_role": "Fleet Manager",
      "email": "s***@solisconstruction.com",
      "phone": "***-***-0199",
      "mailing_state": "ID"
    }
  ],
  "actions": 6,
  "notes": 0
}
```
Contacts arrive already masked (synced from `gold_contacts_masked`).

### `POST /api/actions/<action_id>` `{"decision":"done","reason":"evidence capture"}` -> HTTP 201
```json
{
  "decision": {
    "id": "2",
    "action_id": "e006ae9c0bca38e87ef2907254ee6cc747cdcca77ca87e3ad139c7f0db69c36a",
    "opportunity_id": "0060g000000037aAAA",
    "persona_user_id": "0050g000000003OAAQ",
    "decision": "done",
    "reason": "evidence capture",
    "created_at": "2026-11-19T02:34:57.668Z"
  },
  "actions (open queue)": "20 items; decided action_id present: False"
}
```
The decided action is gone from the returned queue (the open-actions query anti-joins
`app.seller_actions`), and the queue refills to 20. `POST /api/deals/<id>/notes` likewise returned 201:
```json
{
  "note": {
    "id": "1",
    "body": "Evidence capture: confirm leadership review date.",
    "persona_user_id": "0050g000000003OAAQ",
    "created_at": "2026-11-19T02:34:58.212Z"
  },
  "n_notes": 1
}
```

### Ask Genie: `POST /api/genie/default/messages` (SSE, OBO) "What is my open pipeline by stage this quarter?"
```json
{
  "statuses": [
    "FETCHING_METADATA",
    "ASKING_AI",
    "ASKING_AI",
    "ASKING_AI",
    "ASKING_AI",
    "COMPLETED"
  ],
  "question": "What is my open pipeline by stage this quarter?",
  "message_status": "COMPLETED",
  "generated_sql": "SELECT\n  `stage`,\n  SUM(`acv`) AS `open_pipeline_acv`\nFROM `serverless_stable_s1omq8_catalog`.`seller_superapp`.`v_opportunity_pipeline`\nWHERE `is_closed` = false\n  AND `is_current_quarter` = true\n  AND `stage` IS NOT NULL\nGROUP BY `stage`\nORDER BY `open_pipeline_acv` DESC, `stage` ASC",
  "description": "You want to see the total value of your open sales opportunities for this quarter, broken down by each sales stage.",
  "columns": [
    "stage",
    "open_pipeline_acv"
  ],
  "rows": [
    [
      "Proposal",
      "432000.0"
    ],
    [
      "Negotiation",
      "401100.0"
    ],
    [
      "Discovery",
      "145900.0"
    ],
    [
      "Demo",
      "133700.0"
    ],
    [
      "Qualification",
      "18900.0"
    ]
  ]
}
```
Genie read the row-filtered view `v_opportunity_pipeline` as the user (persona Jordan). The stage
totals sum to **1,131,600**, exactly Jordan's `open_pipeline_acv` in `/api/home` (1,131,600):
the Lakebase path (app-side scoping) and the Genie path (UC row filter) agree.

### `GET /api/health/db`
```json
{
  "ok": true,
  "latency_ms": 4.2,
  "at": "2026-11-19T02:34:58.590Z"
}
```
In-region `SELECT 1` through the AppKit pool: 4.2 ms (vs ~71 ms from the laptop in evidence/07).

### `GET /api/health/db` after scale-to-zero (review focus 5)
No app or Lakebase traffic from 2026-11-19T02:43:07Z for 7 min (scale-to-zero is 300 s). The endpoint
was then `IDLE` (`databricks postgres list-endpoints`):
```json
[{"name":"projects/seller-superapp/branches/production/endpoints/primary","state":"IDLE"}]
```
First call (cold start, endpoint resumes; the pooled connection was recycled transparently):
```json
{"ok":true,"latency_ms":765.9,"at":"2026-11-19T02:50:09.597Z"}
```
Next call (warm):
```json
{"ok":true,"latency_ms":5.2,"at":"2026-11-19T02:50:11.014Z"}
```
The app recovered on the first request with no error.

## Tests

### `tests/integration/test_app.py` (deployed app, user token)
```
============================= test session starts ==============================
platform darwin -- Python 3.11.14, pytest-9.2.0, pluggy-1.7.0 -- /Users/will.taff/claude_scratch/fe-bar/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/will.taff/claude_scratch/fe-bar
configfile: pyproject.toml
plugins: Faker-40.54.0, anyio-4.16.0
collecting ... collected 5 items

tests/integration/test_app.py::test_sp_second_principal_governance PASSED [ 20%]
tests/integration/test_app.py::test_persona_rejects_admin_and_unknown PASSED [ 40%]
tests/integration/test_app.py::test_persona_scopes_home PASSED           [ 60%]
tests/integration/test_app.py::test_deal_outside_scope_is_404 PASSED     [ 80%]
tests/integration/test_app.py::test_health_db PASSED                     [100%]

============================== 5 passed in 27.28s ==============================
```
Covers: the SP second-principal probe, the persona contract (admin / `empty-demo` / extra fields -> 400),
seller vs manager vs empty scoping of `/api/home`, a team deal returning 404 for the empty persona,
and `/api/health/db`.

### Playwright smoke (`npm run test:smoke`) against the **deployed** app
Bearer token via `extraHTTPHeaders` (`tests/playwright.config.ts`), `APP_URL` = the app URL:
```
> fleetwise-seller-hub@1.0.0 test:smoke
> npm --prefix tests install --no-audit --no-fund && cd tests && npx playwright test -c playwright.config.ts
added 1 package in 197ms
Running 6 tests using 1 worker
  ✓  1 smoke.spec.ts:17:3 › Fleetwise Seller Hub smoke › My Week shows Priority deals with at least one deal row for Jordan (6.3s)
  ✓  2 smoke.spec.ts:25:3 › Fleetwise Seller Hub smoke › Accept on the first action removes it from the queue (5.1s)
  ✓  3 smoke.spec.ts:40:3 › Fleetwise Seller Hub smoke › Deal 360 shows a Next steps section (4.7s)
  ✓  4 smoke.spec.ts:48:3 › Fleetwise Seller Hub smoke › Ask Genie answers an open-pipeline question (23.5s)
  ✓  5 smoke.spec.ts:61:3 › Fleetwise Seller Hub smoke › Empty persona shows the No open deals empty state (5.5s)
Internal error: step id not found: fixture@94
  ✓  6 smoke.spec.ts:68:3 › Fleetwise Seller Hub smoke › Persona switcher rejects admin (154ms)
  6 passed (49.2s)
```
(The "Internal error: step id not found" line is a Playwright reporter glitch in `afterAll`, which
reset the persona to seller; all 6 tests passed.)

### Local
`databricks apps validate`: typegen, ast-grep lint, typecheck, build, vitest (9/9) all pass; eslint clean.

### Write-back round trip (`tests/integration/test_lakebase.py -m after_app`, run by the controller)
PASSED via Lakehouse Sync config `app_writeback`: CDC 16.2 s, round trip 59.1 s
(`evidence/07_lakebase_metrics.json`).
