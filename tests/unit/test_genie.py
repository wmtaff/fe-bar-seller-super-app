"""Task 9: offline checks for the Genie space definition and the benchmark helpers."""

import json
import re
from types import SimpleNamespace

import pytest

from genie import benchmark as bm
from genie import create_space as cs
from genie.common import SPACE_TEMPLATE, bundle_var

R22_TABLES = {
    "v_opportunity_pipeline", "v_seller_kpis", "v_account_360", "v_next_best_actions",
    "v_call_insights", "v_deal_scores", "gold_user_hierarchy", "gold_lead_scores", "gold_nba_feedback",
}
REQUIRED = [
    "What is my open pipeline by stage this quarter?",
    "Which of my deals mention a competitor and close this quarter?",
    "Show my top 5 deals by ACV times close probability.",
    "Which accounts have usage down more than 15% in the last 30 days and an open opportunity?",
    "What are the open next steps from my last calls?",
]


@pytest.fixture(scope="module")
def space():
    return cs.render_space(SPACE_TEMPLATE.read_text(), "cat", "sch")


# --------------------------------------------------------------------------- space.json


def test_space_tables_are_exactly_r22(space):
    names = {t["identifier"].removeprefix("cat.sch.") for t in space["data_sources"]["tables"]}
    assert names == R22_TABLES


def test_space_has_samples_examples_and_instructions(space):
    assert len(space["config"]["sample_questions"]) == 10
    ins = space["instructions"]
    assert len(ins["example_question_sqls"]) == 3
    text = " ".join(ins["text_instructions"][0]["content"])
    for phrase in ["Feb 1", "acv", "demo_identity_map", "NEVER add a filter", "p_close_quarter < 0.4",
                   "competitive_risk > 0.5", "size(v_call_insights.competitors) > 0"]:
        assert phrase in text, phrase


def test_example_sql_reads_only_space_tables(space):
    allowed = {f"cat.sch.{t}" for t in R22_TABLES}
    for ex in space["instructions"]["example_question_sqls"]:
        sql = "".join(ex["sql"])
        refs = set(re.findall(r"cat\.sch\.\w+", sql))
        assert refs and refs <= allowed, refs
        assert not re.search(r"\b(owner_name|owner_id|name)\s*(=|IN|LIKE)", sql, re.I), \
            "examples must not filter by person (the views are already scoped)"


def test_sample_questions_match_benchmark():
    qs = [q["question"] for q in bm.load_questions()]
    assert len(qs) == 10 and qs[:5] == REQUIRED
    tmpl = json.loads(SPACE_TEMPLATE.read_text())
    assert [s["question"][0] for s in tmpl["config"]["sample_questions"]] == qs


def test_render_space_substitutes_and_validates():
    tmpl = json.dumps({"version": 2, "data_sources": {"tables": [{"identifier": "${catalog}.${schema}.v_x"}]}})
    assert cs.render_space(tmpl, "c", "s")["data_sources"]["tables"][0]["identifier"] == "c.s.v_x"
    with pytest.raises(ValueError, match="placeholder"):
        cs.render_space(tmpl.replace("${schema}", "${nope}"), "c", "s")


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["data_sources"]["tables"].insert(0, {"identifier": "cat.sch.gold_opportunity_pipeline"}), "R22"),
    (lambda s: s["data_sources"]["tables"].reverse(), "sorted by identifier"),
    (lambda s: s["config"]["sample_questions"].reverse(), "sorted by id"),
    (lambda s: s["config"]["sample_questions"][0].update(id="XYZ"), "32 lowercase hex"),
    (lambda s: s["instructions"]["text_instructions"].append({"id": "f" * 32, "content": ["x"]}), "at most one"),
])
def test_validate_space_rejects(space, mutate, match):
    bad = json.loads(json.dumps(space))
    mutate(bad)
    with pytest.raises(ValueError, match=match):
        cs.validate_space(bad, "cat.sch.")


def test_find_space_id_is_idempotent_by_title():
    spaces = [SimpleNamespace(space_id="1", title="Other"), SimpleNamespace(space_id="2", title=cs.TITLE)]
    assert cs.find_space_id(spaces, cs.TITLE) == "2"
    assert cs.find_space_id(spaces[:1], cs.TITLE) is None
    with pytest.raises(RuntimeError, match="2 Genie spaces"):
        cs.find_space_id(spaces + [SimpleNamespace(space_id="3", title=cs.TITLE)], cs.TITLE)


def test_names_come_from_bundle_vars():
    assert bundle_var("catalog") and bundle_var("schema") and bundle_var("warehouse_id")
    for f in ["create_space.py", "benchmark.py", "common.py"]:
        src = (SPACE_TEMPLATE.parent / f).read_text()
        assert bundle_var("warehouse_id") not in src and bundle_var("catalog") not in src, f


# --------------------------------------------------------------------------- benchmark helpers

MSG = {
    "status": "COMPLETED",
    "attachments": [
        {"attachment_id": "a1", "text": {"content": "Here is your pipeline."}},
        {"attachment_id": "a2", "query": {"query": "SELECT 1", "description": "d"}},
    ],
}
RESULT = {"statement_response": {
    "manifest": {"schema": {"columns": [{"name": "opportunity_id"}, {"name": "acv"}]}},
    "result": {"data_array": [["o1", "10"], ["o2", "20"]]},
}}
OPPS = {"o1": "Acme - Telematics", "o2": "Beta - Cams"}


def test_extract_answer_and_rows():
    a = bm.extract_answer(MSG)
    assert (a["sql"], a["attachment_id"], a["text"]) == ("SELECT 1", "a2", "Here is your pipeline.")
    assert bm.extract_answer({"attachments": None})["sql"] is None
    assert bm.result_rows(RESULT) == (["opportunity_id", "acv"], [["o1", "10"], ["o2", "20"]])
    assert bm.result_rows({}) == ([], [])


def test_grade():
    q, q2 = {"id": "q1"}, {"id": "q2", "subset_of_persona_opps": True}
    a = bm.extract_answer(MSG)
    cols, rows = bm.result_rows(RESULT)
    assert bm.grade(q, a, cols, rows, "COMPLETED", OPPS)[0]
    assert bm.grade(q, a, cols, [], "COMPLETED", OPPS) == (False, "SQL returned no rows")
    assert not bm.grade(q, {"sql": None, "text": "Which quarter?"}, [], [], "COMPLETED", OPPS)[0]
    assert bm.grade(q, a, cols, rows, "FAILED", OPPS) == (False, "message FAILED")
    assert bm.grade(q2, a, cols, rows, "COMPLETED", OPPS)[0]
    assert not bm.grade(q2, a, cols, rows + [["o9", "1"]], "COMPLETED", OPPS)[0]


def test_check_subset_by_name_or_missing_column():
    assert bm.check_subset(["opportunity_name"], [["Acme - Telematics"]], OPPS)[0]
    assert not bm.check_subset(["opportunity_name"], [["Zeta - Cams"]], OPPS)[0]
    ok, why = bm.check_subset(["account_name"], [["Acme"]], OPPS)
    assert not ok and "no opportunity_id" in why


def test_render_markdown_keeps_all_runs():
    res = {"id": "q1", "question": "Q?", "passed": True, "reason": "2 row(s)", "status": "COMPLETED",
           "latency_s": 12.0, "sql": "SELECT 1", "text": None, "columns": ["a|b"], "rows": [["x" * 100]],
           "row_count": 1}
    runs = [{"label": f"run {i}", "space_id": "s", "caller": "me", "persona": "Jordan Rivera",
             "started_at": "t", "passed": 1, "results": [res]} for i in (1, 2)]
    md = bm.render_markdown(runs)
    assert "## run 1: 1/1 passed" in md and "## run 2: 1/1 passed" in md
    assert "a\\|b" in md and "x" * 100 not in md and "SELECT 1" in md
