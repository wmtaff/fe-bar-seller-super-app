-- Row-level security (job task `apply_governance`, runs AFTER pipeline_refresh because the
-- functions read gold_user_hierarchy). Ruling R2: the filter is applied in dynamic views
-- (owner-rights, filtering on current_user()) v_opportunity_pipeline / v_seller_kpis /
-- v_account_360; the base gold tables stay unfiltered so Lakebase
-- can sync every row (synced tables don't carry UC row filters anyway). Genie and the
-- evidence queries use the views.
-- Parameters: :catalog, :schema.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- Testable core: can this persona see rows owned by owner_id?
-- A persona sees their own rows, plus rows of anyone whose manager or RVP they are.
CREATE OR REPLACE FUNCTION fn_can_see_owner_for(persona_user_id STRING, owner_id STRING)
RETURNS BOOLEAN
COMMENT 'Row-filter core: TRUE when owner_id is the persona, or the persona is the owner''s manager_id or rvp_id in gold_user_hierarchy. A NULL persona sees nothing.'
RETURN fn_can_see_owner_for.persona_user_id IS NOT NULL AND (
  fn_can_see_owner_for.owner_id = fn_can_see_owner_for.persona_user_id
  OR EXISTS (
    SELECT 1 FROM gold_user_hierarchy h
    WHERE h.user_id = fn_can_see_owner_for.owner_id
      AND (h.manager_id = fn_can_see_owner_for.persona_user_id
           OR h.rvp_id = fn_can_see_owner_for.persona_user_id)
  )
);

-- The caller's persona: exactly one row, chosen deterministically if a login has several
-- (latest updated_at, then persona_role, then persona_user_id). NULL when unmapped.
CREATE OR REPLACE FUNCTION fn_current_persona()
RETURNS STRUCT<persona_role: STRING, persona_user_id: STRING>
COMMENT 'The current_user()''s demo persona from demo_identity_map (latest updated_at wins if a login has several rows); NULL if the caller has no row.'
RETURN (
  SELECT max_by(
           named_struct('persona_role', persona_role, 'persona_user_id', persona_user_id),
           named_struct('t', coalesce(updated_at, TIMESTAMP '1970-01-01'),
                        'r', persona_role, 'u', coalesce(persona_user_id, '')))
  FROM demo_identity_map
  WHERE workspace_email = current_user()
);

-- The caller-aware filter. Admin bypass rule (documented in evidence/03_governance.md):
--   * caller has a persona -> it decides (persona_role = admin sees all; otherwise scoped via
--     fn_can_see_owner_for). This keeps scoping demonstrable even when the presenter is an admin.
--   * caller has no persona -> account-group admins see all, everyone else sees nothing.
CREATE OR REPLACE FUNCTION fn_can_see_owner(owner_id STRING)
RETURNS BOOLEAN
COMMENT 'Row filter for seller-owned rows: the caller''s persona (fn_current_persona) decides - admin = all, otherwise own rows plus the rows of users the persona manages (manager_id/rvp_id). Callers with no persona: account group admins see all, others nothing.'
RETURN CASE
  WHEN fn_current_persona() IS NULL THEN is_account_group_member('admins')
  WHEN fn_current_persona().persona_role = 'admin' THEN TRUE
  ELSE coalesce(fn_can_see_owner_for(fn_current_persona().persona_user_id, fn_can_see_owner.owner_id), FALSE)
END;

CREATE OR REPLACE VIEW v_opportunity_pipeline
COMMENT 'Governed dynamic view of gold_opportunity_pipeline: one row per opportunity, row-filtered by fn_can_see_owner(owner_id) so a seller sees their own deals and a manager/RVP their team''s. Use this (not the gold table) for Genie and ad-hoc analysis.'
AS SELECT * FROM gold_opportunity_pipeline WHERE fn_can_see_owner(owner_id);

CREATE OR REPLACE VIEW v_seller_kpis
COMMENT 'Governed dynamic view of gold_seller_kpis: one row per seller and fiscal quarter, row-filtered by fn_can_see_owner(owner_id) (seller = own KPIs, manager/RVP = team).'
AS SELECT * FROM gold_seller_kpis WHERE fn_can_see_owner(owner_id);

CREATE OR REPLACE VIEW v_account_360
COMMENT 'Governed dynamic view of gold_account_360: one row per customer/prospect account, row-filtered by fn_can_see_owner(owner_id) on the account owner (seller = own accounts, manager/RVP = team''s accounts).'
AS SELECT * FROM gold_account_360 WHERE fn_can_see_owner(owner_id);

-- Seed: the user running the job acts as the seller persona (Jordan Rivera) unless they
-- already have a valid persona (the app's persona switcher owns the row after that). A row
-- whose persona no longer exists in gold_user_hierarchy (e.g. after a data regeneration) is
-- reset. The source is a single aggregated row, so the MERGE can never multi-match.
MERGE INTO demo_identity_map t
USING (
  SELECT current_user() AS workspace_email,
         (SELECT min(user_id) FROM gold_user_hierarchy WHERE name = 'Jordan Rivera') AS persona_user_id,
         'seller' AS persona_role,
         NOT EXISTS (
           SELECT 1 FROM demo_identity_map m
           LEFT JOIN gold_user_hierarchy h ON h.user_id = m.persona_user_id
           WHERE m.workspace_email = current_user()
             AND (m.persona_role = 'admin' OR h.user_id IS NOT NULL)
         ) AS is_stale
) s
ON t.workspace_email = s.workspace_email
WHEN MATCHED AND s.is_stale THEN UPDATE SET
  t.persona_user_id = s.persona_user_id, t.persona_role = s.persona_role, t.updated_at = current_timestamp()
WHEN NOT MATCHED AND s.persona_user_id IS NOT NULL THEN INSERT (workspace_email, persona_user_id, persona_role, updated_at)
  VALUES (s.workspace_email, s.persona_user_id, s.persona_role, current_timestamp());
