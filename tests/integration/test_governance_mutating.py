"""Task 4: governance checks that switch the caller's persona in demo_identity_map.

GUARDED: these tests rewrite the current user's demo_identity_map row (restored on teardown),
which would change what a live app/Genie session for the same login sees. They are skipped
unless selected explicitly:

    pytest tests/integration -m governance_mutating
    # or
    FLEETWISE_GOVERNANCE_MUTATING=1 pytest tests/integration/test_governance_mutating.py

Expected owner sets are derived with SQL from gold_user_hierarchy (ruling R14).
"""

import os

import pytest
from _governance_helpers import GOVERNED_VIEWS, fq, owners, team_ids, user_id

pytestmark = [pytest.mark.integration, pytest.mark.governance_mutating]


@pytest.fixture(autouse=True)
def _guard(request):
    selected = "governance_mutating" in (request.config.getoption("markexpr") or "")
    if not (selected or os.environ.get("FLEETWISE_GOVERNANCE_MUTATING") == "1"):
        pytest.skip("mutates demo_identity_map; run with -m governance_mutating "
                    "or FLEETWISE_GOVERNANCE_MUTATING=1")


@pytest.fixture
def persona(sql, names):
    """Return set_persona(user_id, role); restores the caller's original map rows on teardown."""
    tbl = fq(names, "demo_identity_map")
    original = sql(f"SELECT * FROM {tbl} WHERE workspace_email = current_user()")

    def set_persona(uid, role, updated_at=None, replace=True):
        if replace:
            sql(f"DELETE FROM {tbl} WHERE workspace_email = current_user()")
        if role is not None:
            sql(
                f"INSERT INTO {tbl} (workspace_email, persona_user_id, persona_role, updated_at) "
                "VALUES (current_user(), :u, :r, coalesce(CAST(:t AS TIMESTAMP), current_timestamp()))",
                {"u": uid, "r": role, "t": updated_at},
            )

    yield set_persona

    sql(f"DELETE FROM {tbl} WHERE workspace_email = current_user()")
    for row in original:
        sql(
            f"INSERT INTO {tbl} (workspace_email, persona_user_id, persona_role, updated_at) "
            "VALUES (:e, :u, :r, CAST(:t AS TIMESTAMP))",
            {"e": row["workspace_email"], "u": row["persona_user_id"], "r": row["persona_role"],
             "t": row["updated_at"]},
        )


def _expected(sql, names, base, team):
    return owners(sql, names, base) & team


def test_row_filter_scopes_to_persona(sql, names, persona):
    jordan = user_id(sql, names, "Jordan Rivera")
    persona(jordan, "seller")
    for v in ["v_opportunity_pipeline", "v_seller_kpis"]:
        rows = sql(f"SELECT count(DISTINCT owner_id) AS n FROM {fq(names, v)}")
        assert int(rows[0]["n"]) == 1, f"{v}: seller persona sees {rows[0]['n']} owners"
        assert owners(sql, names, v) == {jordan}


def test_manager_persona_sees_team(sql, names, persona):
    morgan = user_id(sql, names, "Morgan Lee")
    team = team_ids(sql, names, morgan)
    reports = sql(
        f"SELECT count(*) AS n FROM {fq(names, 'gold_user_hierarchy')} WHERE manager_id = :u",
        {"u": morgan},
    )
    assert len(team) == int(reports[0]["n"]) + 1, "a manager's team is the manager plus direct reports"
    persona(morgan, "manager")
    for v in ["v_opportunity_pipeline", "v_seller_kpis"]:
        expected = _expected(sql, names, GOVERNED_VIEWS[v], team)
        assert len(expected) > 1, f"{v}: Morgan's team should own rows for several sellers"
        assert owners(sql, names, v) == expected, f"{v}: manager persona sees the wrong owners"


def test_account_360_scoped(sql, names, persona):
    """v_account_360 is filtered on the account owner: Jordan = own accounts, Morgan = team's."""
    base = fq(names, "gold_account_360")
    for who, role in [("Jordan Rivera", "seller"), ("Morgan Lee", "manager")]:
        uid = user_id(sql, names, who)
        team = team_ids(sql, names, uid)
        expected = {
            r["account_id"]
            for r in sql(f"SELECT account_id, owner_id FROM {base}")
            if r["owner_id"] in team
        }
        assert expected, f"{who} should own at least one account"
        persona(uid, role)
        got = {r["account_id"] for r in sql(f"SELECT account_id FROM {fq(names, 'v_account_360')}")}
        assert got == expected, who
        assert owners(sql, names, "v_account_360") <= team, who


def test_empty_persona_sees_no_open_opps(sql, names, persona):
    taylor = user_id(sql, names, "Taylor Empty")
    persona(taylor, "seller")
    rows = sql(f"SELECT count(*) AS n FROM {fq(names, 'v_opportunity_pipeline')} WHERE NOT is_closed")
    assert int(rows[0]["n"]) == 0
    assert owners(sql, names, "v_opportunity_pipeline") <= {taylor}


def test_admin_persona_sees_all(sql, names, persona):
    persona(None, "admin")
    for v, base in GOVERNED_VIEWS.items():
        assert owners(sql, names, v) == owners(sql, names, base), v


def test_unmapped_caller(sql, names, persona):
    """No map row: account admins see everything, everyone else sees nothing."""
    persona(None, None)
    is_admin = sql("SELECT is_account_group_member('admins') AS a")[0]["a"] == "true"
    for v, base in GOVERNED_VIEWS.items():
        expected = owners(sql, names, base) if is_admin else set()
        assert owners(sql, names, v) == expected, v


def test_duplicate_rows_resolve_to_latest(sql, names, persona):
    """If a login ever has two rows, exactly one persona (latest updated_at) applies."""
    jordan = user_id(sql, names, "Jordan Rivera")
    morgan = user_id(sql, names, "Morgan Lee")
    persona(jordan, "seller", updated_at="2026-01-01T00:00:00Z")
    persona(morgan, "manager", updated_at="2026-01-02T00:00:00Z", replace=False)
    got = sql(f"SELECT {fq(names, 'fn_current_persona')}().persona_user_id AS u")[0]["u"]
    assert got == morgan
    expected = _expected(sql, names, "gold_opportunity_pipeline", team_ids(sql, names, morgan))
    assert owners(sql, names, "v_opportunity_pipeline") == expected


def test_identity_map_rejects_bad_role(sql, names, persona):
    with pytest.raises(RuntimeError, match="(?i)check|constraint"):
        persona(None, "superuser")
