"""Task 4: Unity Catalog governance (ruling R2).

Row-level security lives on the secure views v_opportunity_pipeline / v_seller_kpis
(the base gold tables stay unfiltered so Lakebase can sync them). PII masks live on
silver_contacts.email / .phone. Expected values are derived with SQL from
gold_user_hierarchy, never hard-coded (ruling R14 regenerates the data).

The tests switch the executing user's persona in demo_identity_map and restore the
original row afterwards.
"""

import re

import pytest

pytestmark = pytest.mark.integration

GOVERNED_VIEWS = ["v_opportunity_pipeline", "v_seller_kpis"]
FUNCTIONS = ["fn_can_see_owner", "fn_can_see_owner_for", "fn_mask_pii", "fn_mask_pii_for"]
MASKED_EMAIL = re.compile(r"^.\*\*\*@[^@]+$")
MASKED_PHONE = re.compile(r"^\*\*\*-\*\*\*-\d{0,4}$")


def _fq(names, obj):
    return f"`{names['catalog']}`.`{names['schema']}`.`{obj}`"


def _user_id(sql, names, full_name):
    rows = sql(
        f"SELECT user_id FROM {_fq(names, 'gold_user_hierarchy')} WHERE name = :n", {"n": full_name}
    )
    assert len(rows) == 1, f"expected exactly one user named {full_name}, got {rows}"
    return rows[0]["user_id"]


def _team_ids(sql, names, leader_id):
    """Leader plus everyone whose manager or RVP is the leader (independent of the UDFs)."""
    rows = sql(
        f"SELECT user_id FROM {_fq(names, 'gold_user_hierarchy')} "
        "WHERE user_id = :u OR manager_id = :u OR rvp_id = :u",
        {"u": leader_id},
    )
    return {r["user_id"] for r in rows}


def _owners(sql, names, obj, where=""):
    rows = sql(f"SELECT DISTINCT owner_id FROM {_fq(names, obj)} {where}")
    return {r["owner_id"] for r in rows}


def _is_account_admin(sql):
    return sql("SELECT is_account_group_member('admins') AS a")[0]["a"] == "true"


@pytest.fixture
def persona(sql, names):
    """Return set_persona(user_id, role); restores the caller's original map row on teardown."""
    tbl = _fq(names, "demo_identity_map")
    original = sql(f"SELECT * FROM {tbl} WHERE workspace_email = current_user()")

    def set_persona(user_id, role):
        sql(f"DELETE FROM {tbl} WHERE workspace_email = current_user()")
        if role is not None:
            sql(
                f"INSERT INTO {tbl} (workspace_email, persona_user_id, persona_role) "
                "VALUES (current_user(), :u, :r)",
                {"u": user_id, "r": role},
            )

    yield set_persona

    sql(f"DELETE FROM {tbl} WHERE workspace_email = current_user()")
    for row in original:
        sql(
            f"INSERT INTO {tbl} (workspace_email, persona_user_id, persona_role) "
            "VALUES (:e, :u, :r)",
            {"e": row["workspace_email"], "u": row["persona_user_id"], "r": row["persona_role"]},
        )


# --------------------------------------------------------------------------- objects


def test_governance_objects_exist(sql, names):
    rows = sql(
        f"SELECT routine_name FROM `{names['catalog']}`.information_schema.routines "
        "WHERE routine_schema = :s",
        {"s": names["schema"]},
    )
    missing = set(FUNCTIONS) - {r["routine_name"] for r in rows}
    assert not missing, f"missing functions: {missing}"
    rows = sql(
        f"SELECT table_name, table_type FROM `{names['catalog']}`.information_schema.tables "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    types = {r["table_name"]: r["table_type"] for r in rows}
    assert types.get("demo_identity_map") == "MANAGED"
    for v in GOVERNED_VIEWS:
        assert types.get(v) == "VIEW", f"{v} missing or not a view: {types.get(v)}"


def test_identity_map_seeded_for_current_user(sql, names):
    rows = sql(
        f"SELECT m.persona_role, h.name FROM {_fq(names, 'demo_identity_map')} m "
        f"JOIN {_fq(names, 'gold_user_hierarchy')} h ON h.user_id = m.persona_user_id "
        "WHERE m.workspace_email = current_user()"
    )
    assert len(rows) == 1, f"expected one seeded map row for the current user, got {rows}"
    assert rows[0]["persona_role"] in {"seller", "manager", "admin"}


# --------------------------------------------------------------------------- row filter


def test_row_filter_scopes_to_persona(sql, names, persona):
    jordan = _user_id(sql, names, "Jordan Rivera")
    persona(jordan, "seller")
    for v in GOVERNED_VIEWS:
        rows = sql(f"SELECT count(DISTINCT owner_id) AS n FROM {_fq(names, v)}")
        assert int(rows[0]["n"]) == 1, f"{v}: seller persona sees {rows[0]['n']} owners"
        assert _owners(sql, names, v) == {jordan}


def test_manager_persona_sees_team(sql, names, persona):
    morgan = _user_id(sql, names, "Morgan Lee")
    team = _team_ids(sql, names, morgan)
    reports = sql(
        f"SELECT count(*) AS n FROM {_fq(names, 'gold_user_hierarchy')} WHERE manager_id = :u",
        {"u": morgan},
    )
    assert len(team) == int(reports[0]["n"]) + 1, "a manager's team is the manager plus direct reports"
    persona(morgan, "manager")
    for v, base in [("v_opportunity_pipeline", "gold_opportunity_pipeline"),
                    ("v_seller_kpis", "gold_seller_kpis")]:
        expected = _owners(sql, names, base) & team
        assert len(expected) > 1, f"{base}: Morgan's team should own rows for several sellers"
        assert _owners(sql, names, v) == expected, f"{v}: manager persona sees the wrong owners"


def test_empty_persona_sees_no_open_opps(sql, names, persona):
    taylor = _user_id(sql, names, "Taylor Empty")
    persona(taylor, "seller")
    rows = sql(
        f"SELECT count(*) AS n FROM {_fq(names, 'v_opportunity_pipeline')} WHERE NOT is_closed"
    )
    assert int(rows[0]["n"]) == 0
    assert _owners(sql, names, "v_opportunity_pipeline") <= {taylor}


def test_explicit_persona_variant(sql, names):
    """fn_can_see_owner_for(persona, owner) is the testable core (no dependence on the caller)."""
    hier = _fq(names, "gold_user_hierarchy")
    fn = _fq(names, "fn_can_see_owner_for")
    for who in ["Jordan Rivera", "Morgan Lee"]:
        uid = _user_id(sql, names, who)
        rows = sql(f"SELECT user_id FROM {hier} WHERE {fn}(:p, user_id)", {"p": uid})
        assert {r["user_id"] for r in rows} == _team_ids(sql, names, uid), who
    rows = sql(f"SELECT count(*) AS n FROM {hier} WHERE {fn}(NULL, user_id)")
    assert int(rows[0]["n"]) == 0, "a NULL persona sees nothing"


def test_admin_persona_sees_all(sql, names, persona):
    persona(None, "admin")
    for v, base in [("v_opportunity_pipeline", "gold_opportunity_pipeline"),
                    ("v_seller_kpis", "gold_seller_kpis")]:
        assert _owners(sql, names, v) == _owners(sql, names, base), v


def test_unmapped_caller(sql, names, persona):
    """No map row: account admins see everything, everyone else sees nothing."""
    persona(None, None)
    for v, base in [("v_opportunity_pipeline", "gold_opportunity_pipeline"),
                    ("v_seller_kpis", "gold_seller_kpis")]:
        expected = _owners(sql, names, base) if _is_account_admin(sql) else set()
        assert _owners(sql, names, v) == expected, v


def test_base_gold_tables_unfiltered(sql, names, persona):
    """Ruling R2: gold tables carry no row filter, so Lakebase can sync every row."""
    persona(_user_id(sql, names, "Jordan Rivera"), "seller")
    rows = sql(
        f"SELECT table_name FROM `{names['catalog']}`.information_schema.row_filters "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    assert not [r for r in rows if r["table_name"].startswith("gold_")]
    assert len(_owners(sql, names, "gold_opportunity_pipeline")) > 1


# --------------------------------------------------------------------------- masks and tags


def test_masks_attached(sql, names):
    rows = sql(
        f"SELECT column_name, mask_name FROM `{names['catalog']}`.information_schema.column_masks "
        "WHERE table_schema = :s AND table_name = 'silver_contacts'",
        {"s": names["schema"]},
    )
    masks = {r["column_name"]: r["mask_name"] for r in rows}
    assert set(masks) >= {"email", "phone"}, masks
    assert all(m.endswith("fn_mask_pii") for m in masks.values()), masks


def test_email_masked(sql, names):
    if sql("SELECT is_account_group_member('superapp_revops') AS g")[0]["g"] == "true":
        pytest.skip("caller is in superapp_revops, so sees raw values")
    rows = sql(f"SELECT email, phone FROM {_fq(names, 'silver_contacts')} WHERE email IS NOT NULL")
    assert rows
    bad_email = [r["email"] for r in rows if not MASKED_EMAIL.match(r["email"])]
    assert not bad_email, f"unmasked emails: {bad_email[:5]}"
    bad_phone = [r["phone"] for r in rows if r["phone"] and not MASKED_PHONE.match(r["phone"])]
    assert not bad_phone, f"unmasked phones: {bad_phone[:5]}"


def test_mask_function_paths(sql, names):
    """fn_mask_pii_for(v, privileged) shows both paths without needing group membership."""
    fn = _fq(names, "fn_mask_pii_for")
    rows = sql(
        f"SELECT {fn}('jane.doe@acme.example', true) AS e_raw, "
        f"{fn}('jane.doe@acme.example', false) AS e_masked, "
        f"{fn}('(415) 555-0123', false) AS p_masked, {fn}(NULL, false) AS n"
    )[0]
    assert rows["e_raw"] == "jane.doe@acme.example"
    assert rows["e_masked"] == "j***@acme.example"
    assert rows["p_masked"] == "***-***-0123"
    assert rows["n"] is None


def test_pii_tags_present(sql, names):
    rows = sql(
        f"SELECT column_name, tag_value FROM `{names['catalog']}`.information_schema.column_tags "
        "WHERE schema_name = :s AND table_name = 'silver_contacts' AND tag_name = 'pii'",
        {"s": names["schema"]},
    )
    tags = {r["column_name"]: r["tag_value"] for r in rows}
    assert tags.get("email") == "true" and tags.get("phone") == "true", tags


def test_governed_objects_commented(sql, names):
    objs = GOVERNED_VIEWS + ["demo_identity_map"]
    rows = sql(
        f"SELECT table_name, comment FROM `{names['catalog']}`.information_schema.tables "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    comments = {r["table_name"]: r["comment"] for r in rows}
    assert all(comments.get(o) for o in objs), {o: comments.get(o) for o in objs}
    rows = sql(
        f"SELECT table_name, column_name FROM `{names['catalog']}`.information_schema.columns "
        "WHERE table_schema = :s AND (table_name LIKE 'gold%' OR table_name LIKE 'v\\_%' "
        "OR table_name = 'demo_identity_map') "
        "AND (comment IS NULL OR comment = '')",
        {"s": names["schema"]},
    )
    assert not rows, f"uncommented columns: {rows[:10]}"
