-- Row-scoped dynamic views over the AI gold tables (ruling R22; job task `governance_ai_views`,
-- runs AFTER next_best_actions because the views read the AI tables, which only exist once
-- Tasks 5-7 have run). Same model as row_filters.sql: owner-rights views filtering on
-- fn_can_see_owner, so Genie and seller-facing consumers never read an unfiltered AI table.
-- gold_call_insights and gold_deal_scores carry no owner, so they are filtered on the owner of
-- their opportunity in gold_opportunity_pipeline (opportunity_id is its primary key, so the
-- inner join cannot fan out; calls without an opportunity are not seller-visible).
-- Column comments are inherited from the source columns.
-- Parameters: :catalog, :schema.

-- Views: CREATE VIEW IF NOT EXISTS + ALTER VIEW ... AS, not CREATE OR REPLACE VIEW, because
-- CREATE OR REPLACE VIEW drops the privileges granted on the view (it removed the app SP's
-- SELECT from grants.sql on every job run; found in Task 11). ALTER keeps the object and its grants.
USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE VIEW IF NOT EXISTS v_next_best_actions
COMMENT 'Governed dynamic view of gold_next_best_actions: one row per recommended seller action, row-filtered by fn_can_see_owner(owner_id) (seller = own action queue, manager/RVP = team). Use this (not the gold table) for Genie.'
AS SELECT * FROM gold_next_best_actions WHERE fn_can_see_owner(owner_id);
ALTER VIEW v_next_best_actions AS SELECT * FROM gold_next_best_actions WHERE fn_can_see_owner(owner_id);

CREATE VIEW IF NOT EXISTS v_call_insights
COMMENT 'Governed dynamic view of gold_call_insights: one row per sales call with AI-extracted summary, next steps, open items, competitors, objections, sentiment and stakeholders, plus the opportunity owner_id. Row-filtered by fn_can_see_owner on the owner of the call''s opportunity. Use this (not the gold table) for Genie.'
AS SELECT c.*, p.owner_id
FROM gold_call_insights c
JOIN gold_opportunity_pipeline p ON p.opportunity_id = c.opportunity_id
WHERE fn_can_see_owner(p.owner_id);
ALTER VIEW v_call_insights AS SELECT c.*, p.owner_id
FROM gold_call_insights c
JOIN gold_opportunity_pipeline p ON p.opportunity_id = c.opportunity_id
WHERE fn_can_see_owner(p.owner_id);

CREATE VIEW IF NOT EXISTS v_deal_scores
COMMENT 'Governed dynamic view of gold_deal_scores: one row per open opportunity with the OpenJev P(close this quarter), next action, competitive and churn risk, plus the opportunity owner_id. Row-filtered by fn_can_see_owner on the opportunity owner. Use this (not the gold table) for Genie.'
AS SELECT s.*, p.owner_id
FROM gold_deal_scores s
JOIN gold_opportunity_pipeline p ON p.opportunity_id = s.opportunity_id
WHERE fn_can_see_owner(p.owner_id);
ALTER VIEW v_deal_scores AS SELECT s.*, p.owner_id
FROM gold_deal_scores s
JOIN gold_opportunity_pipeline p ON p.opportunity_id = s.opportunity_id
WHERE fn_can_see_owner(p.owner_id);
