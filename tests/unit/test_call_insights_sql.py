"""Task 5: offline checks of src/ai/call_insights.sql and its job wiring (ruling R17)."""

import json
import re
from pathlib import Path

import yaml

from ai.parse import PRODUCTS, SENTIMENTS, STANCES, load_schema

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "src" / "ai" / "call_insights.sql").read_text()
JOB = ROOT / "resources" / "seller_superapp_daily.job.yml"


def _tasks():
    job = yaml.safe_load(JOB.read_text())["resources"]["jobs"]["seller_superapp_daily"]
    return {t["task_key"]: t for t in job["tasks"]}


def test_job_runs_call_insights_after_governance():
    t = _tasks()["ai_call_insights"]
    assert {d["task_key"] for d in t["depends_on"]} == {"governance_comments_tags"}
    sql_task = t["sql_task"]
    assert sql_task["warehouse_id"] == "${var.warehouse_id}"
    assert sql_task["file"]["path"] == "../src/ai/call_insights.sql"
    assert sql_task["parameters"] == {"catalog": "${var.catalog}", "schema": "${var.schema}"}


def test_prompt_embeds_the_schema_file_verbatim():
    # responseFormat is rejected by the Claude endpoint, so the JSON schema rides in the prompt.
    compact = json.dumps(load_schema(), separators=(",", ":"))
    assert "'" not in compact
    assert compact in SQL


def test_sql_enums_match_schema():
    for value in PRODUCTS + SENTIMENTS + STANCES:
        assert f"'{value}'" in SQL, value


def test_ai_query_is_batch_safe():
    assert "ai_query(" in SQL and "'databricks-claude-sonnet-5-5'" in SQL
    assert re.search(r"failOnError\s*=>\s*false", SQL)
    assert ".errorMessage" in SQL and ".result" in SQL


def test_rebuild_safe_merge_and_orphan_delete():
    assert "MERGE INTO gold_call_insights" in SQL
    # only new / changed / previously failed transcripts are sent to the model
    assert "transcript_sha256" in SQL and "prompt_version" in SQL
    assert re.search(r"DELETE FROM gold_call_insights\s+WHERE meeting_id NOT IN", SQL)
    assert "delta.enableChangeDataFeed' = 'true'" in SQL


def test_no_attendee_emails_in_gold():
    ddl = SQL.split("CREATE TABLE IF NOT EXISTS gold_call_insights", 1)[1].split(";", 1)[0]
    assert "attendees" not in ddl.lower()
    assert "attendees" not in SQL.split("MERGE INTO", 1)[1].lower()


def test_target_columns_have_comments():
    ddl = SQL.split("CREATE TABLE IF NOT EXISTS gold_call_insights", 1)[1].split(";", 1)[0]
    cols = re.findall(r"^\s+(\w+) [A-Z<]", ddl, flags=re.M)
    expected = ["meeting_id", "opportunity_id", "account_id", "started_at", "summary", "next_steps",
                "open_items", "interests", "competitors", "objections", "sentiment", "stakeholders",
                "model", "extracted_at", "extract_error"]
    assert all(c in cols for c in expected), cols
    for line in ddl.splitlines():
        if re.match(r"^\s+\w+ [A-Z<]", line):
            assert "COMMENT '" in line, line
    assert re.search(r"\)\s*COMMENT '", ddl)
