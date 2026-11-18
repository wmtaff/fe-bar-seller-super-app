"""Task 8: offline checks for the Lakebase setup script, the app DDL, write-back SQL and job wiring."""

import re
from pathlib import Path

import yaml

from lakebase import setup_lakebase as lb

ROOT = Path(__file__).resolve().parents[2]
LB = ROOT / "src" / "lakebase"
JOB = ROOT / "resources" / "seller_superapp_daily.job.yml"

EXPECTED = {
    "account_360": ("gold_account_360", ["account_id"]),
    "opportunity_pipeline": ("gold_opportunity_app", ["opportunity_id"]),
    "next_best_actions": ("gold_next_best_actions", ["action_id"]),
    "call_insights": ("gold_call_insights", ["meeting_id"]),
    "seller_kpis": ("gold_seller_kpis", ["owner_id", "fiscal_quarter"]),
    "user_hierarchy": ("gold_user_hierarchy", ["user_id"]),
    "contacts": ("gold_contacts_masked", ["contact_id"]),
    "lead_scores": ("gold_lead_scores", ["lead_id"]),
}
APP_TABLES = ["seller_actions", "notes", "email_drafts"]


def _cfg():
    return lb.Config(catalog="cat", schema="sch")


def test_synced_table_list_matches_brief():
    assert {t.pg_table: (t.source, t.primary_key) for t in lb.SYNCED_TABLES} == EXPECTED


def test_synced_table_spec_is_triggered_into_serving():
    cfg = _cfg()
    spec = lb.synced_table_spec(cfg, lb.SYNCED_TABLES[0], existing_pipeline_id=None)
    assert spec.source_table_full_name == "cat.sch.gold_account_360"
    assert spec.scheduling_policy.value == "TRIGGERED"
    assert spec.branch == "projects/seller-superapp/branches/production"
    assert spec.postgres_database == "databricks_postgres"
    assert spec.create_database_objects_if_missing is True
    # pipeline metadata goes to the regular UC catalog, never the Lakebase catalog
    assert (spec.new_pipeline_spec.storage_catalog, spec.new_pipeline_spec.storage_schema) == ("cat", "sch")
    assert cfg.synced_table_name("account_360") == "synced_tables/fleetwise_lakebase.serving.account_360"


def test_later_synced_tables_share_one_pipeline():
    spec = lb.synced_table_spec(_cfg(), lb.SYNCED_TABLES[1], existing_pipeline_id="p-1")
    assert spec.existing_pipeline_id == "p-1" and spec.new_pipeline_spec is None


def test_app_schema_ddl_is_idempotent_with_replica_identity_full():
    ddl = (LB / "app_schema.sql").read_text()
    assert re.search(r"CREATE SCHEMA IF NOT EXISTS app\b", ddl)
    for t in APP_TABLES:
        assert re.search(rf"CREATE TABLE IF NOT EXISTS app\.{t}\s*\(", ddl), t
        assert re.search(rf"ALTER TABLE app\.{t} REPLICA IDENTITY FULL", ddl), t
    assert re.search(r"CHECK \(decision IN \('accepted', 'done', 'dismissed'\)\)", ddl)
    assert "DROP " not in ddl.upper()


def test_writeback_sql_builds_contract_tables():
    sql = (LB / "writeback.sql").read_text()
    assert re.search(r"CREATE TABLE IF NOT EXISTS silver_seller_actions", sql)
    m = re.search(r"CREATE TABLE IF NOT EXISTS gold_nba_feedback \((.*?)\n\)", sql, re.S)
    assert m, "gold_nba_feedback DDL missing"
    body = m.group(1)
    assert re.search(r"\baction_type STRING NOT NULL", body)
    assert re.search(r"\bacceptance_rate DOUBLE", body)
    for c in ["shown", "accepted", "done", "dismissed"]:
        assert re.search(rf"\b{c} BIGINT", body), c
    # tolerant of the app tables / history table not existing yet
    assert "lb_seller_actions_history" in sql and "EXECUTE IMMEDIATE" in sql


def _tasks():
    job = yaml.safe_load(JOB.read_text())["resources"]["jobs"]["seller_superapp_daily"]
    return {t["task_key"]: t for t in job["tasks"]}


def _deps(task):
    return {d["task_key"] for d in task.get("depends_on", [])}


def test_job_wires_writeback_then_nba_then_sync():
    t = _tasks()
    # write-back first so the same run's NBA ranking uses the fresh feedback and statuses,
    # then the sync publishes everything to Lakebase
    assert _deps(t["writeback_merge"]) == {"ai_scoring"}
    assert _deps(t["next_best_actions"]) == {"writeback_merge"}
    assert _deps(t["lakebase_sync"]) == {"next_best_actions"}
    wb = t["writeback_merge"]["sql_task"]
    assert wb["file"]["path"] == "../src/lakebase/writeback.sql"
    assert wb["parameters"]["lakebase_catalog"] == "${var.lakebase_catalog}"
    sync = t["lakebase_sync"]["spark_python_task"]
    assert sync["python_file"] == "../src/lakebase/setup_lakebase.py"
    assert "--action" in sync["parameters"] and "sync" in sync["parameters"]
