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
    # R22: the AI views read the AI tables, which exist only after next_best_actions
    assert _deps(t["governance_ai_views"]) == {"next_best_actions"}


def test_governance_tasks_are_sql_files_on_the_warehouse_var():
    t = _tasks()
    for key in ["governance_setup", "governance_masks", "apply_governance", "governance_comments_tags",
                "governance_ai_views"]:
        sql_task = t[key]["sql_task"]
        assert sql_task["warehouse_id"] == "${var.warehouse_id}"
        path = sql_task["file"]["path"]
        assert path.startswith("../src/governance/") and (ROOT / path[3:]).exists(), path
        assert sql_task["parameters"] == {"catalog": "${var.catalog}", "schema": "${var.schema}"}


def _mv_schema(sql_text, name):
    return sql_text.split(f"CREATE OR REFRESH MATERIALIZED VIEW {name}", 1)[1].split(" AS SELECT", 1)[0]


def test_pipeline_declares_masks_on_pii_columns():
    silver = (ROOT / "src" / "pipeline" / "silver.sql").read_text()
    for table, cols in {"silver_contacts": ["email", "phone", "mobile_phone"],
                        "silver_leads": ["email", "phone"]}.items():
        block = _mv_schema(silver, table)
        for col in cols:
            assert re.search(rf"\b{col} STRING MASK \S*fn_mask_pii\b", block), (table, col)


def test_grant_plan_is_views_only_and_not_wired():
    plan = (GOV / "grants.sql").read_text()
    active = [l for l in plan.splitlines() if l.strip().startswith("GRANT")]
    assert active and all("${principal}" in l for l in active)
    granted = " ".join(active)
    for view in ["v_opportunity_pipeline", "v_seller_kpis", "v_account_360", "gold_contacts_masked",
                 "v_next_best_actions", "v_call_insights", "v_deal_scores"]:
        assert f".{view} TO" in granted, view
    assert not re.search(r"\.(bronze|silver)_\w+ TO", granted), "no grants on bronze/silver"
    base_gold = re.findall(r"\.(gold_\w+) TO", granted)
    # only base tables with no seller-owned rows (R22); never pipeline/KPI/account/AI fact tables
    assert set(base_gold) == {"gold_contacts_masked", "gold_user_hierarchy", "gold_lead_scores",
                              "gold_nba_feedback"}, base_gold
    assert "MODIFY" not in granted and "EXECUTE" not in granted
    job = JOB.read_text()
    assert "grants.sql" not in job, "the grant plan is applied by Task 10, not the daily job"


def test_governance_sql_files_exist():
    for f in ["setup.sql", "row_filters.sql", "masks.sql", "comments_tags.sql", "grants.sql",
              "ai_views.sql"]:
        assert (GOV / f).read_text().strip(), f
