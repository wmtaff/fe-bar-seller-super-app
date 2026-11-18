-- Governance setup (job task `governance_setup`, runs BEFORE pipeline_refresh).
-- Creates the persona identity map used by the row-filter functions. Idempotent:
-- the table is created once and never truncated, so the app's persona switcher
-- (which upserts the viewer's row) survives daily job runs.
-- Parameters: :catalog, :schema (sql_task parameters from the bundle variables).
--
-- The map is DEMO PERSONA IMPERSONATION, not an entitlement: it lets one presenter act as
-- a seller or a manager. Only the owner/admins hold MODIFY on it; the app writes it only
-- through its validated persona endpoint (seller|manager|empty, never admin) - Task 10.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE TABLE IF NOT EXISTS demo_identity_map (
  workspace_email STRING NOT NULL COMMENT 'Workspace login (current_user()) of the viewer, e.g. the demo presenter or the app''s on-behalf-of user. One row per login (primary key).',
  persona_user_id STRING COMMENT 'gold_user_hierarchy.user_id of the demo persona this viewer acts as; it alone decides the scope (own rows plus rows of users whose manager_id/rvp_id it is). Null for persona_role = admin.',
  persona_role STRING NOT NULL COMMENT 'seller | manager | admin. Only admin changes the row filter (sees all rows); seller vs manager is a label, the scope comes from persona_user_id.',
  updated_at TIMESTAMP COMMENT 'When the row was last written. If a login has several rows, fn_current_persona() uses the latest one.',
  CONSTRAINT demo_identity_map_pk PRIMARY KEY (workspace_email)
)
COMMENT 'Governance: maps workspace users to Fleetwise demo personas (demo impersonation, not an entitlement). fn_can_see_owner reads it to scope v_opportunity_pipeline, v_seller_kpis and v_account_360. The app persona switcher upserts the viewer''s row.'
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

-- Re-assert column comments (CREATE IF NOT EXISTS does not update an existing table).
COMMENT ON COLUMN demo_identity_map.persona_user_id IS 'gold_user_hierarchy.user_id of the demo persona this viewer acts as; it alone decides the scope (own rows plus rows of users whose manager_id/rvp_id it is). Null for persona_role = admin.';
COMMENT ON COLUMN demo_identity_map.persona_role IS 'seller | manager | admin. Only admin changes the row filter (sees all rows); seller vs manager is a label, the scope comes from persona_user_id.';

ALTER TABLE demo_identity_map ALTER COLUMN updated_at SET DEFAULT current_timestamp();
ALTER TABLE demo_identity_map DROP CONSTRAINT IF EXISTS valid_persona_role;
ALTER TABLE demo_identity_map ADD CONSTRAINT valid_persona_role CHECK (persona_role IN ('seller', 'manager', 'admin'));
