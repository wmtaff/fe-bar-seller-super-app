-- Row-level security (job task `apply_governance`, runs AFTER pipeline_refresh because the
-- functions read gold_user_hierarchy). Ruling R2: the filter is applied in the secure views
-- v_opportunity_pipeline / v_seller_kpis; the base gold tables stay unfiltered so Lakebase
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

-- The caller-aware filter. Admin bypass rule (documented in evidence/03_governance.md):
--   * caller has a demo_identity_map row  -> the row decides (persona_role = admin sees all;
--     seller/manager are scoped via fn_can_see_owner_for). This keeps scoping demonstrable
--     even when the presenter is an admin.
--   * caller has no row -> account-group admins see all, everyone else sees nothing.
CREATE OR REPLACE FUNCTION fn_can_see_owner(owner_id STRING)
RETURNS BOOLEAN
COMMENT 'Row filter for seller-owned rows: the caller''s demo_identity_map persona decides (admin = all, seller = own book, manager/RVP = team). Callers with no map row: account group admins see all, others nothing.'
RETURN CASE
  WHEN NOT EXISTS (SELECT 1 FROM demo_identity_map m WHERE m.workspace_email = current_user())
    THEN is_account_group_member('admins')
  ELSE EXISTS (
    SELECT 1 FROM demo_identity_map m
    WHERE m.workspace_email = current_user()
      AND (m.persona_role = 'admin'
           OR fn_can_see_owner_for(m.persona_user_id, fn_can_see_owner.owner_id))
  )
END;

CREATE OR REPLACE VIEW v_opportunity_pipeline
COMMENT 'Governed view of gold_opportunity_pipeline: one row per opportunity, row-filtered by fn_can_see_owner(owner_id) so a seller sees their own deals and a manager/RVP their team''s. Use this (not the gold table) for Genie and ad-hoc analysis.'
AS SELECT * FROM gold_opportunity_pipeline WHERE fn_can_see_owner(owner_id);

CREATE OR REPLACE VIEW v_seller_kpis
COMMENT 'Governed view of gold_seller_kpis: one row per seller and fiscal quarter, row-filtered by fn_can_see_owner(owner_id) (seller = own KPIs, manager/RVP = team).'
AS SELECT * FROM gold_seller_kpis WHERE fn_can_see_owner(owner_id);

-- Seed: the user running the job acts as the seller persona (Jordan Rivera) unless they
-- already have a valid row (the app's persona switcher owns it after that). A row whose
-- persona no longer exists in gold_user_hierarchy (e.g. after a data regeneration) is reset.
MERGE INTO demo_identity_map t
USING (
  SELECT current_user() AS workspace_email, j.user_id AS persona_user_id, 'seller' AS persona_role,
         (m.persona_role <> 'admin' AND h.user_id IS NULL) AS is_stale
  FROM gold_user_hierarchy j
  LEFT JOIN demo_identity_map m ON m.workspace_email = current_user()
  LEFT JOIN gold_user_hierarchy h ON h.user_id = m.persona_user_id
  WHERE j.name = 'Jordan Rivera'
) s
ON t.workspace_email = s.workspace_email
WHEN MATCHED AND s.is_stale
  THEN UPDATE SET t.persona_user_id = s.persona_user_id, t.persona_role = s.persona_role
WHEN NOT MATCHED THEN INSERT (workspace_email, persona_user_id, persona_role)
  VALUES (s.workspace_email, s.persona_user_id, s.persona_role);
