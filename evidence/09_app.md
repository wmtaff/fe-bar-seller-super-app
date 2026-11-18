# 09 - Databricks App: Fleetwise Seller Hub (Task 10) - PARTIAL

Status on 2026-11-18: **built, validated and created in the workspace, but NOT deployed.** The
permission system denied the deploy (`databricks bundle deploy`, then `databricks apps deploy`)
and the UC grant to the app service principal. Everything after deploy has not run yet, so this
file records only what did run. The commands for the remaining steps are listed at the end.

## What exists

| Item | Value |
|---|---|
| App | `fleetwise-seller-hub`, created with `databricks apps create` (resources and OBO scopes below) |
| URL | https://fleetwise-seller-hub-7474646802937769.aws.databricksapps.com |
| Service principal (application id) | `e51bc893-d86b-4fd5-9834-d1276fe878c8` |
| Compute / app status | `ACTIVE` / `UNAVAILABLE` ("App has not been deployed yet") |
| Source | `app/fleetwise-seller-hub` (AppKit 0.84.0), uploaded to `/Workspace/Users/<deployer>/apps/fleetwise-seller-hub` with `databricks sync` (gitignore-aware: no `.env`, no `node_modules`) |
| Bundle resource | `resources/fleetwise_seller_hub.app.yml` (same resources; bind before the first `bundle deploy`, see below) |

App resources (auto-granted to the SP on deploy): `sql-warehouse` 9a6db1d12e2ee6d3 `CAN_USE`;
`genie-space` 01f1e3a1962912c08de057636d1912d8 `CAN_RUN`; `postgres`
`projects/seller-superapp/branches/production` / `.../databases/databricks-postgres`
`CAN_CONNECT_AND_CREATE`. `user_api_scopes`: `sql`, `dashboards.genie`.

`databricks apps create` response (trimmed):

```json
{
  "name": "fleetwise-seller-hub",
  "url": "https://fleetwise-seller-hub-7474646802937769.aws.databricksapps.com",
  "service_principal_client_id": "e51bc893-d86b-4fd5-9834-d1276fe878c8",
  "compute_status": {"message": "App compute is running.", "state": "ACTIVE"},
  "app_status": {"message": "App has status: App has not been deployed yet. Run your app by deploying source code", "state": "UNAVAILABLE"}
}
```

## Local validation (ran)

`databricks apps validate -p fevm-serverless-stable-s1omq8`:

```
✅ Generating types (0.8s)
✅ Running AST-grep lint (0.4s)
✅ Type checking (2.5s)
✅ Building (4.8s)
✅ Running tests (0.5s)
✅ All validation checks passed (9.1s)
```

`npm test` (vitest, 9 passed): the persona switcher contract (`seller|manager|empty` only;
`admin`, `empty-demo` and extra fields such as a client-supplied email rejected; no option maps to
role admin), the action/note body validation, UC identifier quoting, the 30 s persona TTL cache,
the KPI roll-up (empty scope gives null), and a check that `server/sql/app_schema.sql` is a verbatim
copy of `src/lakebase/app_schema.sql`. `eslint` is clean.

`npx playwright test` without a deployment: 6 smoke tests collected, all skipped
(`APP_URL`/`DATABRICKS_TOKEN` unset).

## Not yet run (blocked on deploy approval)

- deploy output and app status RUNNING
- schema `app` created by the SP
- grants (UC grants.sql to the SP; Postgres `serving` read)
- Lakehouse Sync config `app_writeback`
- `test_writeback_roundtrip` and its round-trip seconds
- API captures (`/api/me`, `/api/home`, `/api/deals/<id>`, `POST /api/actions/...`, `/api/health/db`)
- smoke test run
- the second-principal check (`/api/health/governance`, `tests/integration/test_app.py`)

## Remaining steps, in order (as the project owner)

```bash
P=fevm-serverless-stable-s1omq8
# 1. Deploy (the SP creates and owns schema app at startup). Either:
databricks apps deploy fleetwise-seller-hub \
  --source-code-path /Workspace/Users/will.taff@databricks.com/apps/fleetwise-seller-hub -p $P
#    or, through the bundle (bind the API-created app first):
#    databricks bundle deployment bind fleetwise_seller_hub fleetwise-seller-hub -p $P
#    databricks bundle deploy -p $P && databricks bundle run fleetwise_seller_hub -p $P
databricks apps get fleetwise-seller-hub -p $P -o json | jq .app_status   # expect RUNNING

# 2. Grants to the app SP only: Postgres serving read + UC grants.sql
.venv/bin/python jobs/app_post_deploy.py --profile $P

# 3. Lakehouse Sync config BEFORE any write through the app
.venv/bin/python src/lakebase/setup_lakebase.py --catalog serverless_stable_s1omq8_catalog \
  --schema seller_superapp --action setup --with-cdf --profile $P

# 4. Tests
.venv/bin/python -m pytest tests/integration/test_lakebase.py tests/integration/test_app.py -m after_app -v
cd app/fleetwise-seller-hub && npx playwright install chromium && \
  APP_URL=$(databricks apps get fleetwise-seller-hub -p $P -o json | jq -r .url) \
  DATABRICKS_TOKEN=$(databricks auth token -p $P | jq -r .access_token) npm run test:smoke
```
