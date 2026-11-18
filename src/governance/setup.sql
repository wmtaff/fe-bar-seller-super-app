-- Governance setup (job task `governance_setup`, runs BEFORE pipeline_refresh).
-- Creates the persona identity map used by the row-filter functions. Idempotent:
-- the table is created once and never truncated, so the app's persona switcher
-- (which updates the viewer's row) survives daily job runs.
-- Parameters: :catalog, :schema (sql_task parameters from the bundle variables).

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE TABLE IF NOT EXISTS demo_identity_map (
  workspace_email STRING NOT NULL COMMENT 'Workspace login (current_user()) of the viewer, e.g. the demo presenter or the app''s on-behalf-of user.',
  persona_user_id STRING COMMENT 'gold_user_hierarchy.user_id of the demo persona this viewer acts as (null for persona_role = admin).',
  persona_role STRING NOT NULL COMMENT 'seller | manager | admin. seller/manager are scoped to persona_user_id''s book or team; admin sees all rows.'
)
COMMENT 'Governance: maps workspace users to Fleetwise demo personas. fn_can_see_owner reads it to scope v_opportunity_pipeline and v_seller_kpis. The app persona switcher updates the viewer''s row.';
