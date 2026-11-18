-- Consumer grant PLAN (ruling R16). NOT run by the job and NOT applied to anyone yet:
-- Task 10 applies it to the app service principal (and Genie users if needed), then adds a
-- second-principal test (base tables PERMISSION_DENIED, views scoped).
--
-- Placeholders, substituted textually by whoever applies the plan:
--   ${catalog}   e.g. serverless_stable_s1omq8_catalog
--   ${schema}    e.g. seller_superapp
--   ${principal} the app SP application id or a narrowly scoped group, backquoted
-- Do not apply to broad workspace groups (e.g. `users`): that is a sharing change.
--
-- Boundary:
--   * consumers read ONLY the dynamic views v_* (owner-rights, filtered on current_user())
--     and the pre-masked gold_contacts_masked (plus the AI gold tables when they exist);
--   * NOTHING on bronze_* / silver_* (producer-only, raw or masked PII) or on the unfiltered
--     gold_* base tables; Lakebase synced tables are read through Postgres roles, not UC;
--   * only the owner/admins hold MODIFY on demo_identity_map; the app writes it through its
--     validated persona endpoint, so no MODIFY grant appears here.

GRANT USE CATALOG ON CATALOG `${catalog}` TO ${principal};
GRANT USE SCHEMA ON SCHEMA `${catalog}`.`${schema}` TO ${principal};

-- Governed (row-filtered) views
GRANT SELECT ON TABLE `${catalog}`.`${schema}`.v_opportunity_pipeline TO ${principal};
GRANT SELECT ON TABLE `${catalog}`.`${schema}`.v_seller_kpis TO ${principal};
GRANT SELECT ON TABLE `${catalog}`.`${schema}`.v_account_360 TO ${principal};

-- Pre-masked contacts (masks inline; safe to serve)
GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_contacts_masked TO ${principal};

-- AI gold tables (Tasks 5-7). Uncomment when they exist; if they are seller-owned and served
-- to sellers, prefer a v_* dynamic view over a direct grant.
-- gold_call_insights exists (Task 5). It has no PII but is not row-filtered: every call of
-- every seller is visible. The app reads it through Lakebase (synced, app-side scoping), so
-- grant it directly only to the app SP; for Genie/seller users, wrap it in a v_* view first.
-- GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_call_insights TO ${principal};
-- gold_deal_scores and gold_lead_scores exist (Task 6). No PII (scored from allow-listed,
-- non-PII fields), but not row-filtered: same rule as gold_call_insights (app SP only, or a
-- v_* view for Genie/seller users).
-- GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_deal_scores TO ${principal};
-- GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_lead_scores TO ${principal};
-- GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_next_best_actions TO ${principal};
-- GRANT SELECT ON TABLE `${catalog}`.`${schema}`.gold_opportunity_app TO ${principal};

-- Functions: the views run with the view owner's rights, so a reader should NOT need
-- EXECUTE on fn_can_see_owner / fn_current_persona / fn_can_see_owner_for / fn_mask_pii.
-- TASK 10 CHECK: query a view as the second principal; only if it fails with a missing
-- EXECUTE privilege, uncomment the lines below.
-- GRANT EXECUTE ON FUNCTION `${catalog}`.`${schema}`.fn_can_see_owner TO ${principal};
-- GRANT EXECUTE ON FUNCTION `${catalog}`.`${schema}`.fn_current_persona TO ${principal};
-- GRANT EXECUTE ON FUNCTION `${catalog}`.`${schema}`.fn_can_see_owner_for TO ${principal};
