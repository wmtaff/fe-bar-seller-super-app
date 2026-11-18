"""Task 5: gold_call_insights on the live workspace (after the `ai_call_insights` job task).

Ruling R14: no hard-coded counts or ids. Coverage is measured against silver_transcripts,
and Jordan Rivera is found by name in gold_user_hierarchy.
"""

import pytest

from ai.parse import PRODUCTS, SENTIMENTS, STANCES

pytestmark = pytest.mark.integration

MIN_COVERAGE = 0.95
MIN_JORDAN_CALLS = 8


@pytest.fixture(scope="module")
def fq(names):
    return f"`{names['catalog']}`.`{names['schema']}`"


def _one(sql, q, params=None):
    return sql(q, params)[0]


def test_insights_coverage(sql, fq):
    r = _one(sql, f"""
        SELECT
          (SELECT count(*) FROM {fq}.silver_transcripts) AS transcripts,
          count_if(i.summary IS NOT NULL) AS with_summary
        FROM {fq}.silver_transcripts s
        LEFT JOIN {fq}.gold_call_insights i ON i.meeting_id = s.meeting_id""")
    transcripts, with_summary = int(r["transcripts"]), int(r["with_summary"])
    assert transcripts > 0
    assert with_summary / transcripts >= MIN_COVERAGE, (with_summary, transcripts)


def test_jordan_has_insights_on_his_opps(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS n
        FROM {fq}.gold_call_insights i
        JOIN {fq}.gold_opportunity_pipeline o ON o.opportunity_id = i.opportunity_id
        JOIN {fq}.gold_user_hierarchy u ON u.user_id = o.owner_id
        WHERE u.name = :name AND i.summary IS NOT NULL""", {"name": "Jordan Rivera"})
    assert int(r["n"]) >= MIN_JORDAN_CALLS


def test_one_row_per_meeting_and_no_orphans(sql, fq):
    r = _one(sql, f"""
        SELECT count(*) AS n, count(DISTINCT meeting_id) AS d,
               count_if(meeting_id NOT IN (SELECT meeting_id FROM {fq}.silver_transcripts)) AS orphans
        FROM {fq}.gold_call_insights""")
    assert r["n"] == r["d"] and int(r["orphans"]) == 0


def test_every_row_has_insights_or_an_error(sql, fq):
    r = _one(sql, f"""
        SELECT count_if((summary IS NULL) = (extract_error IS NULL)) AS bad
        FROM {fq}.gold_call_insights""")
    assert int(r["bad"]) == 0


def test_values_respect_schema_enums(sql, fq):
    products = ", ".join(f"'{p}'" for p in PRODUCTS)
    sentiments = ", ".join(f"'{s}'" for s in SENTIMENTS)
    stances = ", ".join(f"'{s}'" for s in STANCES)
    r = _one(sql, f"""
        SELECT
          count_if(exists(interests, x -> x NOT IN ({products}))) AS bad_interests,
          count_if(summary IS NOT NULL AND sentiment IS NOT NULL AND sentiment NOT IN ({sentiments})) AS bad_sentiment,
          count_if(exists(stakeholders, s -> s.stance IS NOT NULL AND s.stance NOT IN ({stances}))) AS bad_stance,
          count_if(exists(next_steps, s -> s.due IS NOT NULL AND try_to_date(s.due) IS NULL)) AS bad_due,
          count_if(summary IS NOT NULL AND sentiment IS NULL) AS no_sentiment
        FROM {fq}.gold_call_insights""")
    assert {k: int(v) for k, v in r.items()} == {
        "bad_interests": 0, "bad_sentiment": 0, "bad_stance": 0, "bad_due": 0, "no_sentiment": 0}


def test_next_steps_are_concrete(sql, fq):
    # most calls end with an agreed next step that has a named owner
    r = _one(sql, f"""
        SELECT count_if(summary IS NOT NULL) AS ok,
               count_if(exists(next_steps, s -> s.owner IS NOT NULL)) AS with_owned_step
        FROM {fq}.gold_call_insights""")
    assert int(r["with_owned_step"]) >= MIN_COVERAGE * int(r["ok"])


def test_no_contact_details_in_insights(sql, fq):
    r = _one(sql, f"""
        SELECT count_if(to_json(struct(summary, next_steps, open_items, objections, stakeholders))
                        RLIKE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]+') AS with_email
        FROM {fq}.gold_call_insights""")
    assert int(r["with_email"]) == 0


def test_cdf_and_comments(sql, fq):
    props = {r["key"]: r["value"] for r in sql(f"SHOW TBLPROPERTIES {fq}.gold_call_insights")}
    assert props.get("delta.enableChangeDataFeed") == "true"
    cols = sql(f"DESCRIBE TABLE {fq}.gold_call_insights")
    real = [c for c in cols if c["col_name"] and not c["col_name"].startswith("#")]
    assert real and all(c["comment"] for c in real), [c["col_name"] for c in real if not c["comment"]]
    detail = _one(sql, f"DESCRIBE DETAIL {fq}.gold_call_insights")
    assert detail["description"]
