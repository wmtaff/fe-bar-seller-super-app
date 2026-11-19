"""Build notebooks/01_walkthrough.ipynb (cells below), then execute it with:
  .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/01_walkthrough.ipynb
The notebook runs as a client of the live workspace: SQL on the serverless SQL warehouse, files from
the UC volume, Postgres on Lakebase, the Genie Conversation API and the deployed app's REST API.
"""
from pathlib import Path

import nbformat as nbf

MD, CODE = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
MD("""# Fleetwise Seller Hub: follow one deal through every layer

This notebook follows **Jordan Rivera's top open deal** (`0060g000000037YAAQ`) from the raw Salesforce
export file in the UC volume through bronze, silver and gold (Lakeflow Declarative Pipeline), the
GenAI call insights (`ai_query`), the OpenJev deal score, the next-best-action queue, the Lakebase
Postgres row the app reads, a Genie answer, and finally the app's own REST API.

Every output is printed as text so it can be read without running anything.

**How it ran:** executed with `jupyter nbconvert --execute` on a laptop acting as a *client* of the
live workspace: all SQL runs on the workspace's serverless SQL warehouse, files come from the UC volume,
Postgres is the Lakebase Autoscaling endpoint, Genie and the app are called over their REST APIs. Auth is
the developer's own OAuth (CLI profile); no tokens are stored. Data is synthetic (no real customer)."""),
CODE("""import json, logging, sys, time
from pathlib import Path
import pandas as pd, requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format, StatementParameterListItem

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests" / "integration")]
from _lakebase_helpers import connect
from lakebase import setup_lakebase as lb

PROFILE, WAREHOUSE = "fevm-serverless-stable-s1omq8", "9a6db1d12e2ee6d3"
CATALOG, SCHEMA = "serverless_stable_s1omq8_catalog", "seller_superapp"
DEAL = "0060g000000037YAAQ"
w = WorkspaceClient(profile=PROFILE)
logging.getLogger("databricks.sdk").setLevel(logging.ERROR)  # quiet SDK endpoint-probe warnings
pd.set_option("display.width", 200, "display.max_colwidth", 120)

def q(sql, **params):
    r = w.statement_execution.execute_statement(
        statement=sql, warehouse_id=WAREHOUSE, catalog=CATALOG, schema=SCHEMA, wait_timeout="50s",
        disposition=Disposition.INLINE, format=Format.JSON_ARRAY,
        parameters=[StatementParameterListItem(name=k, value=str(v)) for k, v in params.items()] or None)
    while r.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2); r = w.statement_execution.get_statement(r.statement_id)
    assert r.status.state.value == "SUCCEEDED", r.status.error
    cols = [c.name for c in r.manifest.schema.columns]
    return pd.DataFrame(r.result.data_array or [], columns=cols)

def show(df, transpose=False):
    print((df.T if transpose else df).to_markdown())

print("workspace user:", w.current_user.me().user_name)
print(q("SELECT current_user() AS sql_user, current_catalog() AS catalog, current_schema() AS schema").to_markdown(index=False))"""),
MD("## 1. Raw file (UC volume, Salesforce-API-shaped JSON export)\nThe bronze row records which file it came from (`_metadata.file_path`)."),
CODE("""src = q("SELECT _source_file FROM bronze_opportunity WHERE Id = :id ORDER BY batch DESC LIMIT 1", id=DEAL)._source_file[0]
print("source file:", src)
lines = w.files.download(src).contents.read().decode().splitlines()
raw = next(json.loads(l) for l in lines if DEAL in l)
print(f"{len(lines)} records in the file; the one for {DEAL}:")
print(json.dumps(raw, indent=2))"""),
MD("## 2. Bronze (streaming table, Auto Loader, append-only)"),
CODE("""show(q("SELECT Id, Name, StageName, Amount, CloseDate, OwnerId, NextStep, batch, _ingested_at, _source_file FROM bronze_opportunity WHERE Id = :id ORDER BY batch", id=DEAL), transpose=True)"""),
MD("## 3. Silver (typed, deduplicated: one row per opportunity, latest `LastModifiedDate` wins)"),
CODE("""show(q("SELECT opportunity_id, opportunity_name, stage_name, amount, close_date, owner_id, competitor, next_step, last_modified_date FROM silver_opportunities WHERE opportunity_id = :id", id=DEAL), transpose=True)"""),
MD("## 4. Gold: `gold_opportunity_pipeline` (joined with account, owner hierarchy, activity)\nAnd the governed view the seller-facing tools read: `v_opportunity_pipeline` is row-filtered by `fn_can_see_owner`."),
CODE("""show(q("SELECT opportunity_id, account_name, owner_name, segment, stage, acv, fiscal_quarter, is_current_quarter, stage_age_days, days_since_last_activity, activities_30d FROM gold_opportunity_pipeline WHERE opportunity_id = :id", id=DEAL), transpose=True)
print()
print(q("SELECT count(*) AS rows_visible_to_me_in_v_opportunity_pipeline, count(DISTINCT owner_id) AS owners_visible FROM v_opportunity_pipeline").to_markdown(index=False))"""),
MD("## 5. GenAI call insights (`ai_query` over the Meet transcripts, `gold_call_insights`)"),
CODE("""ci = q("SELECT meeting_id, started_at, sentiment, competitors, objections, next_steps, summary, model, prompt_version FROM gold_call_insights WHERE opportunity_id = :id ORDER BY started_at DESC", id=DEAL)
print(f"{len(ci)} call(s) for this deal; most recent first")
for _, r in ci.head(3).iterrows():
    print("---"); print(r.to_markdown())"""),
MD("## 6. Deal score (OpenJev, `gold_deal_scores`): calibrated probabilities, not free text"),
CODE("""show(q("SELECT opportunity_id, p_close_quarter, close_label, close_confidence, close_probs, next_action, next_action_conf, competitive_risk, churn_risk, model, latency_ms, input_tokens, scored_at FROM gold_deal_scores WHERE opportunity_id = :id", id=DEAL), transpose=True)"""),
MD("## 7. Next best actions (`gold_next_best_actions`, ranked, stable `action_id`)"),
CODE("""show(q("SELECT action_id, action_type, source, title, why, priority_score, status, due_date FROM gold_next_best_actions WHERE opportunity_id = :id ORDER BY priority_score DESC", id=DEAL))"""),
MD("## 8. Lakebase Postgres row the app reads (`serving.opportunity_pipeline`, a synced table from `gold_opportunity_app`)"),
CODE("""pg = connect(w, lb.Config(catalog=CATALOG, schema=SCHEMA).branch_path)
with pg.cursor() as c:
    c.execute("SELECT opportunity_id, opportunity_name, owner_name, stage, acv, close_date, p_close_quarter, close_label, next_action, competitive_risk, last_modified_date, scored_at FROM serving.opportunity_pipeline WHERE opportunity_id = %s", (DEAL,))
    print(pd.DataFrame(c.fetchall(), columns=[d.name for d in c.description]).T.to_markdown())
    t = time.perf_counter(); c.execute("SELECT stage FROM serving.opportunity_pipeline WHERE opportunity_id = %s", (DEAL,)); c.fetchone()
    print(f"\\npoint lookup round trip from this client: {(time.perf_counter()-t)*1000:.1f} ms (includes laptop->AWS network)")
    c.execute("SELECT count(*) FROM serving.opportunity_pipeline"); pg_n = c.fetchone()[0]
uc_n = int(q("SELECT count(*) AS n FROM gold_opportunity_app").n[0])
print(f"row parity: UC gold_opportunity_app={uc_n}  Postgres serving.opportunity_pipeline={pg_n}  equal={uc_n == pg_n}")"""),
MD("## 9. Genie answer (\"Fleetwise Revenue Copilot\", on-behalf-of the caller, row-scoped views only)"),
CODE("""from genie.benchmark import ask
space = (ROOT / "src/genie/space_id.txt").read_text().strip()
a = ask(w, space, "Show my top 5 deals by ACV times close probability.")
print("status:", a["status"], f"latency {a['latency_s']:.1f} s")
print("generated SQL:\\n" + (a["sql"] or ""))
print(pd.DataFrame(a["all_rows"], columns=a["columns"]).to_markdown(index=False))
print("\\nour deal in Genie's answer:", any(DEAL in map(str, r) for r in a["all_rows"]))"""),
MD("## 10. The app's REST API (deployed Databricks App, user OAuth, persona = Jordan Rivera)"),
CODE("""app = w.apps.get("fleetwise-seller-hub")
print("app:", app.name, app.app_status.state.value, app.url)
s = requests.Session(); s.headers["Authorization"] = f"Bearer {w.config.oauth_token().access_token}"
me = s.get(app.url + "/api/me", timeout=120).json()
print(json.dumps({k: me[k] for k in ("persona_name", "role", "visible_owner_count") if k in me}, indent=2))
home = s.get(app.url + "/api/home", timeout=120).json()
print("freshness_ts:", home["freshness_ts"], "| fiscal_quarter:", home["fiscal_quarter"])
print("KPIs:", json.dumps(home["kpis"]))
print(pd.DataFrame(home["priority_deals"])[["opportunity_id", "opportunity_name", "stage", "acv", "p_close_quarter"]].head(5).to_markdown(index=False))
deal = s.get(app.url + f"/api/deals/{DEAL}", timeout=120).json()
print("\\nGET /api/deals/" + DEAL + " (excerpt):")
print(json.dumps({"opportunity": {k: deal["opportunity"][k] for k in ("opportunity_name", "stage", "acv", "owner_name")},
                  "scores": deal["scores"], "insights": len(deal["insights"]), "actions": [x.get("title") for x in deal["actions"]][:5],
                  "contacts_sample": deal["contacts"][:2]}, indent=2, default=str))"""),
MD("""## Summary
The same `opportunity_id` appears in the raw file, bronze, silver, gold, the AI tables, the next-best-action
queue, the Lakebase row, Genie's answer and the app API, so every layer is connected by one key and one
governed lineage graph (see `evidence/10_e2e.md` for the `system.access.table_lineage` edges).
Score quality is in `evidence/06_nba_and_eval.md` (AUC 0.695, top-decile lift 2.06x)."""),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
nbf.write(nb, Path(__file__).with_name("01_walkthrough.ipynb"))
