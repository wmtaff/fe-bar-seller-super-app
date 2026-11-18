"""Task 4: job wiring for governance (ruling R2), checked offline from the bundle YAML."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "resources" / "seller_superapp_daily.job.yml"
GOV = ROOT / "src" / "governance"


def _tasks():
    job = yaml.safe_load(JOB.read_text())["resources"]["jobs"]["seller_superapp_daily"]
    return {t["task_key"]: t for t in job["tasks"]}


def _deps(task):
    return {d["task_key"] for d in task.get("depends_on", [])}


def test_governance_tasks_ordered_around_pipeline():
    t = _tasks()
    assert _deps(t["governance_setup"]) == {"generate_data"}
    # the pipeline declares MASK fn_mask_pii, so the mask functions must exist first
    assert _deps(t["governance_masks"]) == {"governance_setup"}
    assert "governance_masks" in _deps(t["pipeline_refresh"])
    # row filters read gold_user_hierarchy; tags need the pipeline tables
    assert _deps(t["apply_governance"]) == {"pipeline_refresh"}
    assert _deps(t["governance_comments_tags"]) == {"apply_governance"}


def test_governance_tasks_are_sql_files_on_the_warehouse_var():
    t = _tasks()
    for key in ["governance_setup", "governance_masks", "apply_governance", "governance_comments_tags"]:
        sql_task = t[key]["sql_task"]
        assert sql_task["warehouse_id"] == "${var.warehouse_id}"
        path = sql_task["file"]["path"]
        assert path.startswith("../src/governance/") and (ROOT / path[3:]).exists(), path
        assert sql_task["parameters"] == {"catalog": "${var.catalog}", "schema": "${var.schema}"}


def test_pipeline_declares_masks_on_silver_contacts():
    silver = (ROOT / "src" / "pipeline" / "silver.sql").read_text()
    block = silver.split("CREATE OR REFRESH MATERIALIZED VIEW silver_contacts", 1)[1].split(" AS SELECT", 1)[0]
    assert "email STRING" in block and "phone STRING" in block
    for col in ["email", "phone", "mobile_phone"]:
        assert re.search(rf"\b{col} STRING MASK \S*fn_mask_pii\b", block), col


def test_governance_sql_files_exist():
    for f in ["setup.sql", "row_filters.sql", "masks.sql", "comments_tags.sql"]:
        assert (GOV / f).read_text().strip(), f
