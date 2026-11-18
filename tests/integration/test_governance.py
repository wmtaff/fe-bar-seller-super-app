"""Task 4: Unity Catalog governance (rulings R2, R16) - read-only checks.

Row-level security lives on dynamic views (owner-rights, filtering on current_user()):
v_opportunity_pipeline, v_seller_kpis, v_account_360. The base gold tables stay unfiltered so
Lakebase can sync them. PII masks live on silver_contacts / silver_leads. Expected values are
derived with SQL from gold_user_hierarchy, never hard-coded (ruling R14).

Tests that switch the caller's persona in demo_identity_map are in
test_governance_mutating.py (guarded; see its docstring).
"""

import re

import pytest
from _governance_helpers import AI_VIEWS, GOVERNED_VIEWS, fq, rvp_of, team_ids, user_id

pytestmark = pytest.mark.integration

FUNCTIONS = ["fn_can_see_owner", "fn_can_see_owner_for", "fn_current_persona", "fn_mask_pii", "fn_mask_pii_for"]
MASKED_EMAIL = re.compile(r"^.\*\*\*@[^@]+$")
MASKED_PHONE = re.compile(r"^\*\*\*-\*\*\*-\d{0,4}$")
PII_COLUMNS = {
    "silver_contacts": ["email", "phone", "mobile_phone"],
    "silver_leads": ["email", "phone"],
}


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
    for v in list(GOVERNED_VIEWS) + list(AI_VIEWS):
        assert types.get(v) == "VIEW", f"{v} missing or not a view: {types.get(v)}"


def test_identity_map_seeded_for_current_user(sql, names):
    rows = sql(
        f"SELECT m.persona_role, h.name FROM {fq(names, 'demo_identity_map')} m "
        f"JOIN {fq(names, 'gold_user_hierarchy')} h ON h.user_id = m.persona_user_id "
        "WHERE m.workspace_email = current_user()"
    )
    assert len(rows) == 1, f"expected one seeded map row for the current user, got {rows}"
    assert rows[0]["persona_role"] in {"seller", "manager", "admin"}


def test_identity_map_unique(sql, names):
    rows = sql(
        f"SELECT count(*) AS n, count(DISTINCT workspace_email) AS d FROM {fq(names, 'demo_identity_map')}"
    )
    assert rows[0]["n"] == rows[0]["d"], f"duplicate logins in demo_identity_map: {rows}"


# --------------------------------------------------------------------------- row filter


def test_explicit_persona_variant(sql, names):
    """fn_can_see_owner_for(persona, owner) is the testable core (no dependence on the caller)."""
    hier = fq(names, "gold_user_hierarchy")
    fn = fq(names, "fn_can_see_owner_for")
    jordan = user_id(sql, names, "Jordan Rivera")
    cases = {
        "seller": jordan,
        "manager": user_id(sql, names, "Morgan Lee"),
        "rvp": rvp_of(sql, names, jordan),  # Jordan's RVP sees the whole region
    }
    seen = {}
    for label, uid in cases.items():
        rows = sql(f"SELECT user_id FROM {hier} WHERE {fn}(:p, user_id)", {"p": uid})
        seen[label] = {r["user_id"] for r in rows}
        assert seen[label] == team_ids(sql, names, uid), label
    assert seen["seller"] == {jordan}
    assert seen["seller"] < seen["manager"] < seen["rvp"], "scope must widen seller < manager < RVP"
    rows = sql(f"SELECT count(*) AS n FROM {hier} WHERE {fn}(NULL, user_id)")
    assert int(rows[0]["n"]) == 0, "a NULL persona sees nothing"


def test_base_gold_tables_unfiltered(sql, names):
    """Ruling R2: gold tables carry no row filter, so Lakebase can sync every row."""
    rows = sql(
        f"SELECT table_name FROM `{names['catalog']}`.information_schema.row_filters "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    assert not [r for r in rows if r["table_name"].startswith("gold_")]


# --------------------------------------------------------------------------- masks and tags


def test_masks_attached(sql, names):
    rows = sql(
        f"SELECT table_name, column_name, mask_name FROM `{names['catalog']}`.information_schema.column_masks "
        "WHERE table_schema = :s",
        {"s": names["schema"]},
    )
    masks = {(r["table_name"], r["column_name"]): r["mask_name"] for r in rows}
    for table, cols in PII_COLUMNS.items():
        for col in cols:
            assert (masks.get((table, col)) or "").endswith("fn_mask_pii"), (table, col, masks)


def test_email_masked(sql, names):
    if sql("SELECT is_account_group_member('superapp_revops') AS g")[0]["g"] == "true":
        pytest.skip("caller is in superapp_revops, so sees raw values")
    for table in PII_COLUMNS:
        rows = sql(f"SELECT email, phone FROM {fq(names, table)} WHERE email IS NOT NULL")
        assert rows, table
        bad_email = [r["email"] for r in rows if not MASKED_EMAIL.match(r["email"])]
        assert not bad_email, f"{table}: unmasked emails: {bad_email[:5]}"
        bad_phone = [r["phone"] for r in rows if r["phone"] and not MASKED_PHONE.match(r["phone"])]
        assert not bad_phone, f"{table}: unmasked phones: {bad_phone[:5]}"


def test_mask_function_paths(sql, names):
    """fn_mask_pii_for(v, privileged) shows both paths without needing group membership."""
    fn = fq(names, "fn_mask_pii_for")
    rows = sql(
        f"SELECT {fn}('jane.doe@acme.example', true) AS e_raw, "
        f"{fn}('jane.doe@acme.example', false) AS e_masked, "
        f"{fn}('(415) 555-0123', false) AS p_masked, {fn}(NULL, false) AS n"
    )[0]
    assert rows["e_raw"] == "jane.doe@acme.example"
    assert rows["e_masked"] == "j***@acme.example"
    assert rows["p_masked"] == "***-***-0123"
    assert rows["n"] is None


def test_mask_matches_core(sql, names):
    """fn_mask_pii inlines fn_mask_pii_for (nested UDFs break incremental refresh); keep in sync."""
    if sql("SELECT is_account_group_member('superapp_revops') AS g")[0]["g"] == "true":
        pytest.skip("caller is in superapp_revops")
    m, core = fq(names, "fn_mask_pii"), fq(names, "fn_mask_pii_for")
    rows = sql(
        f"SELECT count(*) AS n FROM (SELECT explode(array('jane.doe@acme.example', '(415) 555-0123', "
        f"'no digits', '', NULL, 'a@b')) AS v) WHERE NOT ({m}(v) <=> {core}(v, false))"
    )
    assert int(rows[0]["n"]) == 0


def test_pii_tags_present(sql, names):
    """`pii` is an account-governed tag here (allowed values ssn/address only), so the PII
    flag is the governed boolean tag contains_pii=true plus the system class.* tags."""
    rows = sql(
        f"SELECT table_name, column_name, tag_name, tag_value "
        f"FROM `{names['catalog']}`.information_schema.column_tags WHERE schema_name = :s",
        {"s": names["schema"]},
    )
    tags = {(r["table_name"], r["column_name"], r["tag_name"]): r["tag_value"] for r in rows}
    expected = dict(PII_COLUMNS)
    expected.update({
        "bronze_contact": ["Email", "Phone", "MobilePhone"],
        "bronze_lead": ["Email", "Phone"],
        "silver_transcripts": ["attendees"],
    })
    for table, cols in expected.items():
        for col in cols:
            assert tags.get((table, col, "contains_pii")) == "true", (table, col)
    for table in PII_COLUMNS:
        assert (table, "email", "class.email_address") in tags, table
        assert (table, "phone", "class.phone_number") in tags, table


def test_governed_objects_commented(sql, names):
    objs = list(GOVERNED_VIEWS) + list(AI_VIEWS) + ["demo_identity_map"]
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
