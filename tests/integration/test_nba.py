"""Task 7: gold_next_best_actions, gold_opportunity_app and gold_score_eval on the live workspace.

Ruling R14: no hard-coded counts or ids; expectations are derived with SQL from the inputs.
Jordan is looked up by name.
"""

import pytest

pytestmark = pytest.mark.integration

JORDAN = {"name": "Jordan Rivera"}
MIN_JORDAN_OPEN_ACTIONS = 10


@pytest.fixture(scope="module")
def fq(names):
    return f"`{names['catalog']}`.`{names['schema']}`"


def _one(sql, q, params=None):
    return sql(q, params)[0]


def test_nba_ids_unique(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS n, count(DISTINCT action_id) AS d,
               count_if(action_id <> sha2(concat_ws('|', opportunity_id, action_type, source_key), 256)) AS bad_id
        FROM {fq}.gold_next_best_actions""")
    assert int(r["n"]) > 0 and r["n"] == r["d"] and int(r["bad_id"]) == 0, r


def test_nba_only_for_open_opps_with_valid_values(sql, fq):
    r = _one(sql, f"""
        SELECT count_if(o.opportunity_id IS NULL OR o.is_closed) AS not_open,
               count_if(n.source NOT IN ('call', 'model', 'rule')) AS bad_source,
               count_if(n.priority_score IS NULL OR n.priority_score < 0) AS bad_priority,
               count_if(coalesce(n.title, '') = '' OR coalesce(n.why, '') = '') AS no_text,
               count_if(n.owner_id IS DISTINCT FROM o.owner_id OR n.account_id IS DISTINCT FROM o.account_id) AS bad_keys
        FROM {fq}.gold_next_best_actions n
        LEFT JOIN {fq}.gold_opportunity_pipeline o ON o.opportunity_id = n.opportunity_id""")
    assert {k: int(v) for k, v in r.items()} == dict.fromkeys(r, 0)


def test_model_actions_match_confident_scores(sql, fq):
    # every open opp whose model next_action is confident (>= 0.5) has exactly that model action
    r = _one(sql, f"""
        WITH expected AS (
          SELECT s.opportunity_id, s.next_action FROM {fq}.gold_deal_scores s
          JOIN {fq}.gold_opportunity_pipeline o USING (opportunity_id)
          WHERE NOT o.is_closed AND s.next_action_conf >= 0.5),
        actual AS (SELECT opportunity_id, action_type AS next_action
                   FROM {fq}.gold_next_best_actions WHERE source = 'model')
        SELECT (SELECT count(*) FROM expected) AS expected,
               (SELECT count(*) FROM (SELECT * FROM expected EXCEPT SELECT * FROM actual)) AS missing,
               (SELECT count(*) FROM (SELECT * FROM actual EXCEPT SELECT * FROM expected)) AS extra""")
    assert int(r["expected"]) > 0 and int(r["missing"]) == 0 and int(r["extra"]) == 0, r


def test_call_actions_cover_latest_call_next_steps(sql, fq):
    r = _one(sql, f"""
        WITH latest AS (
          SELECT i.* FROM {fq}.gold_call_insights i
          JOIN {fq}.gold_opportunity_pipeline o USING (opportunity_id)
          WHERE NOT o.is_closed AND i.extract_error IS NULL
          QUALIFY row_number() OVER (PARTITION BY i.opportunity_id ORDER BY i.started_at DESC, i.meeting_id) = 1)
        SELECT (SELECT coalesce(sum(size(next_steps)), 0) FROM latest) AS expected,
               (SELECT count(*) FROM {fq}.gold_next_best_actions WHERE source = 'call') AS actual""")
    assert int(r["expected"]) > 0 and r["expected"] == r["actual"], r


def test_jordan_has_actions(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS n FROM {fq}.gold_next_best_actions n
        JOIN {fq}.gold_user_hierarchy u ON u.user_id = n.owner_id
        WHERE u.name = :name AND n.status = 'open'""", JORDAN)
    assert int(r["n"]) >= MIN_JORDAN_OPEN_ACTIONS, r


def test_rule_competitor_expiring_present(sql, fq):
    r = _one(sql, f"""
        WITH jordan_opps AS (
          SELECT o.opportunity_id FROM {fq}.gold_opportunity_pipeline o
          JOIN {fq}.gold_user_hierarchy u ON u.user_id = o.owner_id
          WHERE u.name = :name AND NOT o.is_closed AND o.is_current_quarter
            AND (coalesce(o.competitor, '') <> '' OR EXISTS (
                 SELECT 1 FROM {fq}.gold_call_insights i
                 WHERE i.opportunity_id = o.opportunity_id AND size(i.competitors) > 0)))
        SELECT (SELECT count(*) FROM jordan_opps) AS expected,
               (SELECT count(*) FROM {fq}.gold_next_best_actions n JOIN jordan_opps USING (opportunity_id)
                WHERE n.source = 'rule' AND n.action_type = 'competitor_expiring'
                  AND lower(n.why) LIKE '%competitor%') AS actual""", JORDAN)
    assert int(r["expected"]) >= 1 and r["expected"] == r["actual"], r


def test_priority_score_formula(sql, fq):
    # with no feedback yet, priority = acv * p_close_quarter * urgency (urgency in {1.0, 1.2, 1.5})
    r = _one(sql, f"""
        SELECT count_if(abs(n.priority_score / nullif(o.acv * coalesce(s.p_close_quarter, o.probability / 100.0), 0)
                            - u) > 1e-6) AS bad, count(*) AS n
        FROM {fq}.gold_next_best_actions n
        JOIN {fq}.gold_opportunity_pipeline o USING (opportunity_id)
        LEFT JOIN {fq}.gold_deal_scores s USING (opportunity_id)
        LATERAL VIEW explode(array(CASE
          WHEN n.action_type = 'competitor_expiring' THEN 1.5
          WHEN datediff(n.due_date, (SELECT to_date(max(last_modified_date)) FROM {fq}.gold_opportunity_pipeline)) <= 7 THEN 1.5
          WHEN datediff(n.due_date, (SELECT to_date(max(last_modified_date)) FROM {fq}.gold_opportunity_pipeline)) <= 14 THEN 1.2
          ELSE 1.0 END)) AS u
        WHERE o.acv > 0""")
    assert int(r["n"]) > 0 and int(r["bad"]) == 0, r


def test_opportunity_app_joins_pipeline_and_scores(sql, fq):
    r = _one(sql, f"""
        SELECT (SELECT count(*) FROM {fq}.gold_opportunity_pipeline) AS pipeline,
               (SELECT count(*) FROM {fq}.gold_opportunity_app) AS app,
               (SELECT count(*) FROM {fq}.gold_opportunity_app a
                FULL JOIN {fq}.gold_opportunity_pipeline o USING (opportunity_id)
                LEFT JOIN {fq}.gold_deal_scores s USING (opportunity_id)
                WHERE a.opportunity_id IS NULL OR o.opportunity_id IS NULL
                   OR a.stage IS DISTINCT FROM o.stage OR a.acv IS DISTINCT FROM o.acv
                   OR a.p_close_quarter IS DISTINCT FROM s.p_close_quarter
                   OR a.next_action IS DISTINCT FROM s.next_action) AS mismatched""")
    assert int(r["pipeline"]) > 0 and r["pipeline"] == r["app"] and int(r["mismatched"]) == 0, r


@pytest.mark.parametrize("table", ["gold_next_best_actions", "gold_opportunity_app", "gold_score_eval"])
def test_tables_have_cdf_pk_and_comments(sql, fq, table):
    props = {r["key"]: r["value"] for r in sql(f"SHOW TBLPROPERTIES {fq}.{table}")}
    assert props.get("delta.enableChangeDataFeed") == "true"
    cat, sch = (p.strip("`") for p in fq.split("."))
    missing = sql(f"""
        SELECT column_name FROM `{cat}`.information_schema.columns
        WHERE table_schema = :s AND table_name = :t AND coalesce(comment, '') = ''""", {"s": sch, "t": table})
    assert missing == []
    t = _one(sql, f"""SELECT comment FROM `{cat}`.information_schema.tables
                      WHERE table_schema = :s AND table_name = :t""", {"s": sch, "t": table})
    assert t["comment"]
    pk = _one(sql, f"""SELECT count(*) AS n FROM `{cat}`.information_schema.table_constraints
                       WHERE table_schema = :s AND table_name = :t AND constraint_type = 'PRIMARY KEY'""",
              {"s": sch, "t": table})
    assert int(pk["n"]) == 1


def test_eval_auc_logged(sql, fq):
    r = _one(sql, f"""
        SELECT count_if(metric = 'auc' AND segment = 'all' AND value BETWEEN 0 AND 1) AS auc_rows,
               count_if(metric = 'lift') AS lift_rows,
               count_if(metric LIKE 'competitor_%') AS extraction_rows
        FROM {fq}.gold_score_eval""")
    assert int(r["auc_rows"]) >= 1 and int(r["lift_rows"]) >= 10 and int(r["extraction_rows"]) >= 2, r
