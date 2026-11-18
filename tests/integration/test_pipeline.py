"""Task 3: Lakeflow SDP pipeline (bronze -> silver -> gold) on live data in raw/<dataset_version>."""

import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

DATASET_VERSION = os.environ.get("FLEETWISE_DATASET_VERSION", "v3")
GOLD_SQL = Path(__file__).resolve().parents[2] / "src" / "pipeline" / "gold.sql"

GOLD_TABLES = [
    "gold_user_hierarchy",
    "gold_account_360",
    "gold_opportunity_pipeline",
    "gold_seller_kpis",
    "gold_contacts_masked",
]
SILVER_TABLES = [
    "silver_users",
    "silver_accounts",
    "silver_contacts",
    "silver_opportunities",
    "silver_opportunity_history",
    "silver_leads",
    "silver_activities",
    "silver_transcripts",
    "silver_usage_daily",
    "silver_tickets",
]
BRONZE_TABLES = [
    "bronze_user",
    "bronze_user_role",
    "bronze_account",
    "bronze_contact",
    "bronze_opportunity",
    "bronze_opportunity_history",
    "bronze_lead",
    "bronze_task",
    "bronze_event",
    "bronze_meet_transcripts",
    "bronze_product_usage",
    "bronze_support_tickets",
]


def _fq(names, table):
    return f"`{names['catalog']}`.`{names['schema']}`.`{table}`"


def _user_id(sql, names, full_name):
    rows = sql(
        f"SELECT user_id FROM {_fq(names, 'gold_user_hierarchy')} WHERE name = :n", {"n": full_name}
    )
    assert len(rows) == 1, f"expected exactly one user named {full_name}, got {rows}"
    return rows[0]["user_id"]


def test_gold_tables_exist(sql, names):
    rows = sql(
        f"SELECT table_name FROM `{names['catalog']}`.information_schema.tables "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    present = {r["table_name"] for r in rows}
    missing = [t for t in GOLD_TABLES + SILVER_TABLES + BRONZE_TABLES if t not in present]
    assert not missing, f"missing tables: {missing}"
    for t in GOLD_TABLES:
        n = int(sql(f"SELECT count(*) AS n FROM {_fq(names, t)}")[0]["n"])
        assert n > 0, f"{t} is empty"


def test_gold_tables_have_cdf_and_comments(sql, names):
    for t in GOLD_TABLES:
        props = {
            r["key"]: r["value"] for r in sql(f"SHOW TBLPROPERTIES {_fq(names, t)}")
        }
        assert props.get("delta.enableChangeDataFeed") == "true", f"{t}: CDF not enabled"
    rows = sql(
        f"SELECT table_name, comment FROM `{names['catalog']}`.information_schema.tables "
        "WHERE table_schema = :s AND table_name LIKE 'gold%'",
        {"s": names["schema"]},
    )
    for r in rows:
        if r["table_name"] in GOLD_TABLES:
            assert r["comment"], f"{r['table_name']} has no table comment"
    uncommented = sql(
        f"SELECT table_name, column_name FROM `{names['catalog']}`.information_schema.columns "
        "WHERE table_schema = :s AND table_name LIKE 'gold%' AND (comment IS NULL OR comment = '')",
        {"s": names["schema"]},
    )
    uncommented = [r for r in uncommented if r["table_name"] in GOLD_TABLES]
    assert not uncommented, f"gold columns without comments: {uncommented}"


def test_silver_opps_unique_ids(sql, names):
    r = sql(
        f"SELECT count(*) AS n, count(DISTINCT opportunity_id) AS d FROM {_fq(names, 'silver_opportunities')}"
    )[0]
    assert int(r["n"]) >= 15000
    assert r["n"] == r["d"]
    # Re-emitted opps: silver keeps the newest version (AUTO CDC on LastModifiedDate).
    stale = sql(
        f"""
        WITH latest AS (
          SELECT Id, max(to_timestamp(LastModifiedDate)) AS lm
          FROM {_fq(names, 'bronze_opportunity')} GROUP BY Id)
        SELECT count(*) AS n FROM latest l JOIN {_fq(names, 'silver_opportunities')} s
          ON s.opportunity_id = l.Id
        WHERE s.last_modified_date <> l.lm
        """
    )[0]
    assert int(stale["n"]) == 0
    changed = sql(
        f"SELECT count(*) AS n FROM (SELECT Id FROM {_fq(names, 'bronze_opportunity')} "
        "GROUP BY Id HAVING count(*) > 1)"
    )[0]
    assert int(changed["n"]) > 0, "expected increment batches to re-emit some opps"


def test_jordan_open_pipeline(sql, names):
    jordan = _user_id(sql, names, "Jordan Rivera")
    r = sql(
        f"SELECT count(*) AS n FROM {_fq(names, 'gold_opportunity_pipeline')} "
        "WHERE owner_id = :o AND NOT is_closed",
        {"o": jordan},
    )[0]
    assert int(r["n"]) >= 25


def test_taylor_empty_has_no_open_pipeline(sql, names):
    taylor = _user_id(sql, names, "Taylor Empty")
    r = sql(
        f"SELECT count(*) AS n FROM {_fq(names, 'gold_opportunity_pipeline')} "
        "WHERE owner_id = :o AND NOT is_closed",
        {"o": taylor},
    )[0]
    assert int(r["n"]) == 0
    kpi = sql(
        f"SELECT open_pipeline_acv FROM {_fq(names, 'gold_seller_kpis')} "
        "WHERE owner_id = :o AND fiscal_quarter = 'FY27Q4'",
        {"o": taylor},
    )
    assert len(kpi) == 1 and float(kpi[0]["open_pipeline_acv"]) == 0.0


def test_fiscal_quarter_and_hierarchy(sql, names):
    bad = sql(
        f"""
        SELECT count(*) AS n FROM {_fq(names, 'gold_opportunity_pipeline')}
        WHERE fiscal_quarter <> concat('FY',
              lpad(CAST(pmod(year(add_months(close_date, 11)), 100) AS STRING), 2, '0'),
              'Q', CAST(floor((pmod(month(close_date) - 2, 12)) / 3) + 1 AS STRING))
        """
    )[0]
    assert int(bad["n"]) == 0
    q = sql(
        f"SELECT DISTINCT fiscal_quarter FROM {_fq(names, 'gold_opportunity_pipeline')} "
        "WHERE close_date BETWEEN DATE'2026-11-01' AND DATE'2027-01-31'"
    )
    assert [r["fiscal_quarter"] for r in q] == ["FY27Q4"]
    jordan = _user_id(sql, names, "Jordan Rivera")
    morgan = _user_id(sql, names, "Morgan Lee")
    h = sql(
        f"SELECT manager_id, rvp_id FROM {_fq(names, 'gold_user_hierarchy')} WHERE user_id = :u",
        {"u": jordan},
    )[0]
    assert h["manager_id"] == morgan
    m = sql(
        f"SELECT manager_id FROM {_fq(names, 'gold_user_hierarchy')} WHERE user_id = :u",
        {"u": morgan},
    )[0]
    assert h["rvp_id"] == m["manager_id"]


def test_contacts_masked_has_no_raw_email(sql, names):
    r = sql(
        f"""
        SELECT count(*) AS n,
               count_if(email RLIKE '^[^*]+@') AS raw_email,
               count_if(phone RLIKE '[0-9]{{3}}[^0-9]+[0-9]{{4}}$' AND phone NOT LIKE '***-***-%') AS raw_phone
        FROM {_fq(names, 'gold_contacts_masked')}
        """
    )[0]
    assert int(r["n"]) >= 20000
    assert int(r["raw_email"]) == 0
    assert int(r["raw_phone"]) == 0


def test_no_ground_truth_ingested(sql, names):
    rows = sql(
        f"SELECT table_name, column_name FROM `{names['catalog']}`.information_schema.columns "
        "WHERE table_schema = :s AND lower(column_name) IN "
        "('true_intent','will_win','planted_competitors','planted_next_steps')",
        {"s": names["schema"]},
    )
    assert rows == []
    leaked = sql(
        f"SELECT count(*) AS n FROM {_fq(names, 'bronze_opportunity')} "
        "WHERE _source_file LIKE '%/_eval/%' OR _source_file NOT LIKE :root",
        {"root": f"%/raw/{DATASET_VERSION}/%"},
    )[0]
    assert int(leaked["n"]) == 0


def test_expectations_recorded(sql, names):
    rows = sql(
        f"""
        SELECT e.name AS expectation, e.dataset AS dataset,
               sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
        FROM (
          SELECT explode(from_json(details:flow_progress.data_quality.expectations,
                 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
          FROM event_log(TABLE({_fq(names, 'silver_opportunities')}))
          WHERE event_type = 'flow_progress'
            AND details:flow_progress.data_quality.expectations IS NOT NULL)
        GROUP BY e.name, e.dataset
        """
    )
    got = {r["expectation"] for r in rows}
    for name in ("valid_id", "non_negative_amount", "valid_close_date"):
        assert name in got, f"expectation {name} not in event log: {rows}"
    assert sum(int(r["passed"]) for r in rows) > 0


def _fiscal_quarter_exprs() -> list[str]:
    """The fiscal-quarter expressions used in gold.sql, with the date column renamed to `d`."""
    text = GOLD_SQL.read_text()
    exprs = re.findall(r"concat\('FY'.*?\+ 1 AS STRING\)\)", text, re.S)
    return [" ".join(re.sub(r"\b(o\.close_date|as_of_date)\b", "d", e).split()) for e in exprs]


def test_fiscal_quarter_literal_cases(sql):
    exprs = _fiscal_quarter_exprs()
    assert len(exprs) >= 2 and len(set(exprs)) == 1, exprs
    cases = {
        "2026-02-01": "FY27Q1",
        "2027-01-31": "FY27Q4",
        "2026-01-15": "FY26Q4",
        "2026-11-16": "FY27Q4",
        "2026-04-30": "FY27Q1",
        "2026-05-01": "FY27Q2",
        "2026-10-31": "FY27Q3",
        "2027-02-01": "FY28Q1",
    }
    values = ", ".join(f"(DATE'{d}')" for d in cases)
    rows = sql(f"SELECT CAST(d AS STRING) AS d, {exprs[0]} AS fq FROM VALUES {values} AS t(d)")
    assert {r["d"]: r["fq"] for r in rows} == cases


def test_jordan_kpis_plausible(sql, names):
    """Ruling R12: Jordan's FY27Q4 coverage is 3-4x and attainment 25-40%."""
    jordan = _user_id(sql, names, "Jordan Rivera")
    k = sql(
        f"SELECT quota, attainment_pct, coverage_ratio FROM {_fq(names, 'gold_seller_kpis')} "
        "WHERE owner_id = :o AND fiscal_quarter = 'FY27Q4'",
        {"o": jordan},
    )
    assert len(k) == 1
    assert float(k[0]["quota"]) == 500000.0
    assert 3.0 <= float(k[0]["coverage_ratio"]) <= 4.0, k
    assert 0.25 <= float(k[0]["attainment_pct"]) / 100 <= 0.40, k
    org = sql(
        f"SELECT count(*) AS n, count_if(coverage_ratio BETWEEN 1.5 AND 5.0) AS ok "
        f"FROM {_fq(names, 'gold_seller_kpis')} WHERE is_current_quarter AND open_pipeline_acv > 0"
    )[0]
    assert int(org["ok"]) >= 0.8 * int(org["n"]), org
