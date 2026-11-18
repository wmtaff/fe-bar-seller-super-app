"""Task 6: gold_deal_scores / gold_lead_scores on the live workspace (after job task `ai_scoring`).

Ruling R14: no hard-coded counts or ids; expectations are derived with SQL from the inputs
(open opps in gold_opportunity_pipeline, open leads in silver_leads).
"""

import pytest

from ai.questions import CLOSE_LEVELS, DEAL_QUESTIONS, FIT_LEVELS, LEAD_QUESTIONS

pytestmark = pytest.mark.integration

MIN_COVERAGE = 0.99
MIN_STDDEV = 0.1
OPEN_LEADS = """FROM {fq}.silver_leads
  WHERE NOT coalesce(is_converted, false) AND coalesce(status, '') NOT IN ('Qualified', 'Unqualified')"""


@pytest.fixture(scope="module")
def fq(names):
    return f"`{names['catalog']}`.`{names['schema']}`"


def _one(sql, q, params=None):
    return sql(q, params)[0]


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def test_all_open_opps_scored(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS open_opps, count_if(s.p_close_quarter IS NOT NULL) AS scored
        FROM {fq}.gold_opportunity_pipeline o
        LEFT JOIN {fq}.gold_deal_scores s ON s.opportunity_id = o.opportunity_id
        WHERE NOT o.is_closed""")
    open_opps, scored = int(r["open_opps"]), int(r["scored"])
    assert open_opps > 0
    assert scored / open_opps >= MIN_COVERAGE, (scored, open_opps)


def test_scores_vary(sql, fq):
    r = _one(sql, f"SELECT stddev(p_close_quarter) AS sd FROM {fq}.gold_deal_scores")
    assert float(r["sd"]) > MIN_STDDEV, r


def test_deal_scores_only_open_and_unique(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS n, count(DISTINCT s.opportunity_id) AS d,
               count_if(o.opportunity_id IS NULL OR o.is_closed) AS not_open
        FROM {fq}.gold_deal_scores s
        LEFT JOIN {fq}.gold_opportunity_pipeline o ON o.opportunity_id = s.opportunity_id""")
    assert r["n"] == r["d"] and int(r["not_open"]) == 0


def test_deal_score_values_are_valid(sql, fq):
    actions = _in(DEAL_QUESTIONS["next_action"]["criteria"])
    r = _one(sql, f"""
        SELECT
          count_if(p_close_quarter NOT BETWEEN 0 AND 1) AS bad_p,
          count_if(p_close_quarter IS NOT NULL AND close_label NOT IN ({_in(CLOSE_LEVELS)})) AS bad_label,
          count_if(p_close_quarter IS NOT NULL AND next_action NOT IN ({actions})) AS bad_action,
          count_if(p_close_quarter IS NOT NULL AND abs(aggregate(map_values(close_probs), 0D, (a, x) -> a + x) - 1) > 1e-3) AS bad_probs,
          count_if(competitive_risk NOT BETWEEN 0 AND 1 OR churn_risk NOT BETWEEN 0 AND 1) AS bad_risk,
          count_if(p_close_quarter IS NULL AND score_error IS NULL) AS unexplained_null
        FROM {fq}.gold_deal_scores""")
    assert {k: int(v) for k, v in r.items()} == dict.fromkeys(r, 0)


def test_all_open_leads_scored_and_only_open(sql, fq):
    r = _one(sql, f"""
        WITH open_leads AS (SELECT lead_id {OPEN_LEADS.format(fq=fq)})
        SELECT (SELECT count(*) FROM open_leads) AS open_leads,
               (SELECT count(*) FROM {fq}.gold_lead_scores s JOIN open_leads USING (lead_id)
                WHERE s.fit_score IS NOT NULL) AS scored,
               (SELECT count(*) FROM {fq}.gold_lead_scores s LEFT ANTI JOIN open_leads USING (lead_id)) AS not_open""")
    assert int(r["open_leads"]) > 0
    assert int(r["scored"]) / int(r["open_leads"]) >= MIN_COVERAGE, r
    assert int(r["not_open"]) == 0


def test_lead_score_values_are_valid(sql, fq):
    r = _one(sql, f"""
        SELECT
          count_if(fit_score NOT BETWEEN 0 AND 1) AS bad_fit,
          count_if(fit_score IS NOT NULL AND fit_label NOT IN ({_in(FIT_LEVELS)})) AS bad_label,
          count_if(fit_score IS NOT NULL AND route_to NOT IN ({_in(LEAD_QUESTIONS['route_to']['criteria'])})) AS bad_route,
          count_if(fit_score IS NULL AND score_error IS NULL) AS unexplained_null
        FROM {fq}.gold_lead_scores""")
    assert {k: int(v) for k, v in r.items()} == dict.fromkeys(r, 0)


@pytest.mark.parametrize("table", ["gold_deal_scores", "gold_lead_scores"])
def test_score_tables_have_cdf_pk_and_comments(sql, fq, table):
    props = {r["key"]: r["value"] for r in sql(f"SHOW TBLPROPERTIES {fq}.{table}")}
    assert props.get("delta.enableChangeDataFeed") == "true"
    cat, sch = (p.strip("`") for p in fq.split("."))
    missing = sql(f"""
        SELECT column_name FROM `{cat}`.information_schema.columns
        WHERE table_schema = :s AND table_name = :t AND coalesce(comment, '') = ''""", {"s": sch, "t": table})
    assert missing == []
    t = _one(sql, f"""
        SELECT comment FROM `{cat}`.information_schema.tables
        WHERE table_schema = :s AND table_name = :t""", {"s": sch, "t": table})
    assert t["comment"]
    pk = sql(f"""
        SELECT count(*) AS n FROM `{cat}`.information_schema.table_constraints
        WHERE table_schema = :s AND table_name = :t AND constraint_type = 'PRIMARY KEY'""", {"s": sch, "t": table})
    assert int(pk[0]["n"]) == 1


def test_jordan_has_scored_deals(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS open_opps, count_if(s.p_close_quarter IS NOT NULL) AS scored
        FROM {fq}.gold_opportunity_pipeline o
        JOIN {fq}.gold_user_hierarchy u ON u.user_id = o.owner_id
        LEFT JOIN {fq}.gold_deal_scores s ON s.opportunity_id = o.opportunity_id
        WHERE u.name = :name AND NOT o.is_closed""", {"name": "Jordan Rivera"})
    assert int(r["open_opps"]) > 0 and r["scored"] == r["open_opps"]
