"""Shared helpers for the governance integration tests (Task 4)."""

GOVERNED_VIEWS = {
    "v_opportunity_pipeline": "gold_opportunity_pipeline",
    "v_seller_kpis": "gold_seller_kpis",
    "v_account_360": "gold_account_360",
}


def fq(names, obj):
    return f"`{names['catalog']}`.`{names['schema']}`.`{obj}`"


def user_id(sql, names, full_name):
    rows = sql(f"SELECT user_id FROM {fq(names, 'gold_user_hierarchy')} WHERE name = :n", {"n": full_name})
    assert len(rows) == 1, f"expected exactly one user named {full_name}, got {rows}"
    return rows[0]["user_id"]


def rvp_of(sql, names, uid):
    rows = sql(f"SELECT rvp_id FROM {fq(names, 'gold_user_hierarchy')} WHERE user_id = :u", {"u": uid})
    return rows[0]["rvp_id"]


def team_ids(sql, names, leader_id):
    """Leader plus everyone whose manager or RVP is the leader (independent of the UDFs)."""
    rows = sql(
        f"SELECT user_id FROM {fq(names, 'gold_user_hierarchy')} "
        "WHERE user_id = :u OR manager_id = :u OR rvp_id = :u",
        {"u": leader_id},
    )
    return {r["user_id"] for r in rows}


def owners(sql, names, obj):
    return {r["owner_id"] for r in sql(f"SELECT DISTINCT owner_id FROM {fq(names, obj)}")}
