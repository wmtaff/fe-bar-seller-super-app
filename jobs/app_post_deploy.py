"""Task 10 post-deploy grants for the Fleetwise Seller Hub service principal (idempotent).

Run once after the app's first deploy (and again after any synced table is re-created), as the
Lakebase project owner / UC object owner:

    .venv/bin/python jobs/app_post_deploy.py --profile fevm-serverless-stable-s1omq8

1. Checks the app is RUNNING and that its SP created and owns Postgres schema `app`
   (deploy-first: the SP runs src/lakebase/app_schema.sql at startup).
2. Applies src/governance/grants.sql in UC with principal = the app SP application id ONLY
   (never a broad group, ruling R16). No MODIFY on demo_identity_map: the app writes it OBO.
3. Grants the SP read access on Postgres schema `serving` (Task 8 handoff step 3), including
   default privileges for the synced-table writer role so re-created tables stay readable.

Next (not done here): Lakehouse Sync config (setup_lakebase.py --with-cdf), then
`pytest tests/integration -m after_app` and the Playwright smoke test.
"""

import argparse
import re
import sys
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))
from _lakebase_helpers import connect  # noqa: E402

APP = "fleetwise-seller-hub"


def uc_grants(w: WorkspaceClient, warehouse_id: str, catalog: str, schema: str, sp: str) -> list[str]:
    plan = (ROOT / "src" / "governance" / "grants.sql").read_text()
    plan = plan.replace("${catalog}", catalog).replace("${schema}", schema).replace("${principal}", f"`{sp}`")
    stmts = [s.strip() for s in re.findall(r"^GRANT [^;]+;", plan, flags=re.M)]
    done = []
    for stmt in stmts:
        r = w.statement_execution.execute_statement(warehouse_id=warehouse_id, statement=stmt, wait_timeout="50s")
        if r.status.error:
            raise RuntimeError(f"{stmt}\n-> {r.status.error.message}")
        done.append(stmt)
        print("UC  ", stmt)
    return done


def pg_grants(w: WorkspaceClient, branch_path: str, sp: str) -> None:
    with connect(w, branch_path) as pg, pg.cursor() as cur:
        cur.execute("SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'app'")
        row = cur.fetchone()
        if not row:
            raise SystemExit("schema app does not exist: deploy the app first (its SP must create it)")
        print("PG   schema app owner:", row[0])
        cur.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'serving'")
        writers = [r[0] for r in cur.fetchall()]
        for s in (f'GRANT USAGE ON SCHEMA serving TO "{sp}"',
                  f'GRANT SELECT ON ALL TABLES IN SCHEMA serving TO "{sp}"'):
            cur.execute(s)
            print("PG  ", s)
        pg.commit()  # the required grants must not be rolled back by the optional step below
        # Optional: future synced tables are owned by the sync writer role. Changing its default
        # privileges needs membership in that role, which the project owner may not have. If it is
        # refused, re-run this script after any synced table is (re)created.
        for wr in writers:
            s = f'ALTER DEFAULT PRIVILEGES FOR ROLE "{wr}" IN SCHEMA serving GRANT SELECT ON TABLES TO "{sp}"'
            try:
                cur.execute(s)
                pg.commit()
                print("PG  ", s)
            except psycopg.errors.InsufficientPrivilege as e:
                pg.rollback()
                print(f"PG   WARN skipped (no membership in {wr}): {e.diag.message_primary}; "
                      "re-run this script after recreating a synced table")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--catalog", default="serverless_stable_s1omq8_catalog")
    ap.add_argument("--schema", default="seller_superapp")
    ap.add_argument("--warehouse-id", default="9a6db1d12e2ee6d3")
    ap.add_argument("--branch", default="projects/seller-superapp/branches/production")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    app = w.apps.get(APP)
    state = app.app_status.state.value if app.app_status and app.app_status.state else None
    if state != "RUNNING":
        raise SystemExit(f"{APP} is {state}: deploy and start it first")
    sp = app.service_principal_client_id
    print(f"app {APP} RUNNING at {app.url}; SP application id {sp}")
    pg_grants(w, a.branch, sp)
    uc_grants(w, a.warehouse_id, a.catalog, a.schema, sp)


if __name__ == "__main__":
    main()
