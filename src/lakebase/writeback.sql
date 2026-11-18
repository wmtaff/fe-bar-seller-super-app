-- Task 8: write-back from the Seller Hub (Lakebase Postgres schema `app`) into Delta.
-- Job task `writeback_merge` (after ai_scoring, before next_best_actions, so the same run's NBA
-- ranking uses fresh feedback). Parameters: :catalog, :schema, :lakebase_catalog.
--
-- Source of seller decisions, picked at run time (first that exists):
--   1. Lakehouse Sync (primary): {catalog}.{schema}.lb_seller_actions_history, the CDC history of
--      Postgres app.seller_actions; latest change per id by _pg_lsn (a delete removes the row).
--   2. Federated read (fallback): {lakebase_catalog}.app.seller_actions through the Lakebase UC
--      catalog (a full snapshot of the live table).
--   3. Neither (before Task 10 creates schema app): a no-op; the targets are still created empty,
--      so the daily job never fails on a missing app table.
--
-- Outputs (MERGE on keys, rows rewritten only when they change, so re-runs are idempotent and
-- the CDF stays quiet):
--   silver_seller_actions  one row per app.seller_actions row (current state), plus action_type.
--   gold_nba_feedback      per action_type: shown/accepted/done/dismissed + acceptance_rate in 0..1
--                          = (accepted + done) / decided (NULL when nothing decided). Contract read
--                          by src/ai/next_best_actions.sql: (action_type STRING, acceptance_rate DOUBLE).
--   gold_next_best_actions.status  set to the latest decision per action (open when none).

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE TABLE IF NOT EXISTS silver_seller_actions (
  id BIGINT NOT NULL COMMENT 'Postgres app.seller_actions.id (bigserial). Primary key.',
  action_id STRING COMMENT 'Next best action the decision is about (gold_next_best_actions.action_id).',
  opportunity_id STRING COMMENT 'Salesforce Opportunity Id (18-char) of the action.',
  persona_user_id STRING COMMENT 'User Id of the demo persona who made the decision in the app.',
  decision STRING COMMENT 'Seller decision: accepted, done or dismissed.',
  reason STRING COMMENT 'Optional free-text reason the seller gave.',
  created_at TIMESTAMP COMMENT 'When the decision was recorded in the app.',
  action_type STRING COMMENT 'Action type of the action (from gold_next_best_actions when merged; kept if the action later disappears).',
  source_lsn BIGINT COMMENT 'Postgres LSN of the change (Lakehouse Sync path); NULL on the federated fallback.',
  merged_at TIMESTAMP COMMENT 'When this row was last written by writeback_merge.',
  CONSTRAINT silver_seller_actions_pk PRIMARY KEY (id)
)
COMMENT 'Silver: seller decisions on next best actions written by the Fleetwise Seller Hub into Lakebase (app.seller_actions), current state per row. Built by job task writeback_merge from the Lakehouse Sync history (lb_seller_actions_history).'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE TABLE IF NOT EXISTS gold_nba_feedback (
  action_type STRING NOT NULL COMMENT 'Next best action type (see gold_next_best_actions.action_type). Primary key.',
  shown BIGINT COMMENT 'Distinct actions of this type shown to sellers (in the current queue or decided on).',
  accepted BIGINT COMMENT 'Actions whose latest decision is accepted.',
  done BIGINT COMMENT 'Actions whose latest decision is done.',
  dismissed BIGINT COMMENT 'Actions whose latest decision is dismissed.',
  acceptance_rate DOUBLE COMMENT '(accepted + done) / (accepted + done + dismissed), 0..1; NULL when no decision yet. Feeds the NBA priority factor clamp(0.5 + rate, 0.5, 1.5).',
  updated_at TIMESTAMP COMMENT 'When the counts last changed.',
  CONSTRAINT gold_nba_feedback_pk PRIMARY KEY (action_type)
)
COMMENT 'Gold: seller feedback on next best actions by action type (acceptance rate), closing the loop from the Seller Hub back into the NBA ranking (job task next_best_actions runs right after). Built by job task writeback_merge.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- --------------------------------------------------------------------------- pick the source
-- (A SQL file task runs statement by statement, so the existence checks use session variables
-- and EXECUTE IMMEDIATE, as in next_best_actions.sql.)
DECLARE OR REPLACE VARIABLE wb_source_sql STRING;

SET VAR wb_source_sql = (
  SELECT CASE
    WHEN count_if(table_catalog = :catalog AND table_schema = :schema
                  AND table_name = 'lb_seller_actions_history') > 0 THEN
      'CREATE OR REPLACE TEMPORARY VIEW wb_source AS
       SELECT id, action_id, opportunity_id, persona_user_id, decision, reason,
              CAST(created_at AS TIMESTAMP) AS created_at, _pg_lsn AS source_lsn,
              _pg_change_type = \'delete\' AS is_deleted
       FROM lb_seller_actions_history
       WHERE _pg_change_type IN (\'insert\', \'update_postimage\', \'delete\')
       QUALIFY row_number() OVER (PARTITION BY id ORDER BY _pg_lsn DESC) = 1'
    WHEN count_if(table_catalog = :lakebase_catalog AND table_schema = 'app'
                  AND table_name = 'seller_actions') > 0 THEN
      'CREATE OR REPLACE TEMPORARY VIEW wb_source AS
       SELECT id, action_id, opportunity_id, persona_user_id, decision, reason,
              CAST(created_at AS TIMESTAMP) AS created_at, CAST(NULL AS BIGINT) AS source_lsn,
              false AS is_deleted
       FROM `' || :lakebase_catalog || '`.app.seller_actions'
    ELSE
      'CREATE OR REPLACE TEMPORARY VIEW wb_source AS
       SELECT id, action_id, opportunity_id, persona_user_id, decision, reason, created_at,
              source_lsn, false AS is_deleted
       FROM silver_seller_actions'
    END
  FROM system.information_schema.tables
  WHERE table_catalog IN (:catalog, :lakebase_catalog)
    AND table_name IN ('lb_seller_actions_history', 'seller_actions'));

EXECUTE IMMEDIATE wb_source_sql;

-- action types of the current NBA queue (empty on a first-ever run, before next_best_actions)
DECLARE OR REPLACE VARIABLE wb_nba_exists BOOLEAN;

SET VAR wb_nba_exists = (
  SELECT count(*) > 0 FROM information_schema.tables
  WHERE table_catalog = current_catalog() AND table_schema = current_schema()
    AND table_name = 'gold_next_best_actions');

DECLARE OR REPLACE VARIABLE wb_nba_sql STRING;

SET VAR wb_nba_sql = CASE WHEN wb_nba_exists
  THEN 'CREATE OR REPLACE TEMPORARY VIEW wb_nba AS SELECT action_id, action_type FROM gold_next_best_actions'
  ELSE 'CREATE OR REPLACE TEMPORARY VIEW wb_nba AS
        SELECT CAST(NULL AS STRING) AS action_id, CAST(NULL AS STRING) AS action_type WHERE false'
  END;

EXECUTE IMMEDIATE wb_nba_sql;

-- --------------------------------------------------------------------------- silver_seller_actions
MERGE INTO silver_seller_actions t
USING (
  SELECT s.*, n.action_type FROM wb_source s LEFT JOIN wb_nba n ON n.action_id = s.action_id
) s
ON t.id = s.id
WHEN MATCHED AND s.is_deleted THEN DELETE
WHEN MATCHED AND (t.decision IS DISTINCT FROM s.decision OR t.reason IS DISTINCT FROM s.reason
                  OR t.action_id IS DISTINCT FROM s.action_id
                  OR t.opportunity_id IS DISTINCT FROM s.opportunity_id
                  OR t.persona_user_id IS DISTINCT FROM s.persona_user_id
                  OR t.created_at IS DISTINCT FROM s.created_at
                  OR (t.action_type IS NULL AND s.action_type IS NOT NULL)) THEN UPDATE SET
  t.action_id = s.action_id, t.opportunity_id = s.opportunity_id, t.persona_user_id = s.persona_user_id,
  t.decision = s.decision, t.reason = s.reason, t.created_at = s.created_at,
  t.action_type = coalesce(s.action_type, t.action_type),
  t.source_lsn = coalesce(s.source_lsn, t.source_lsn), t.merged_at = current_timestamp()
WHEN NOT MATCHED AND NOT s.is_deleted THEN INSERT
  (id, action_id, opportunity_id, persona_user_id, decision, reason, created_at, action_type, source_lsn,
   merged_at)
  VALUES (s.id, s.action_id, s.opportunity_id, s.persona_user_id, s.decision, s.reason, s.created_at,
          s.action_type, s.source_lsn, current_timestamp())
-- the source always covers every live row (full history / live snapshot / silver itself), so a
-- row it no longer has was deleted upstream
WHEN NOT MATCHED BY SOURCE THEN DELETE;

-- --------------------------------------------------------------------------- gold_nba_feedback
CREATE OR REPLACE TEMPORARY VIEW wb_latest_decision AS
SELECT action_id, action_type, decision
FROM silver_seller_actions
QUALIFY row_number() OVER (PARTITION BY action_id ORDER BY created_at DESC, id DESC) = 1;

MERGE INTO gold_nba_feedback t
USING (
  WITH shown AS (
    SELECT action_type, count(DISTINCT action_id) AS shown
    FROM (SELECT action_id, action_type FROM wb_nba
          UNION SELECT action_id, action_type FROM wb_latest_decision)
    WHERE action_type IS NOT NULL
    GROUP BY action_type
  ),
  decided AS (
    SELECT action_type, count_if(decision = 'accepted') AS accepted, count_if(decision = 'done') AS done,
           count_if(decision = 'dismissed') AS dismissed
    FROM wb_latest_decision WHERE action_type IS NOT NULL
    GROUP BY action_type
  )
  SELECT s.action_type, s.shown, coalesce(d.accepted, 0) AS accepted, coalesce(d.done, 0) AS done,
         coalesce(d.dismissed, 0) AS dismissed,
         CASE WHEN coalesce(d.accepted + d.done + d.dismissed, 0) > 0
              THEN CAST(d.accepted + d.done AS DOUBLE) / (d.accepted + d.done + d.dismissed) END
           AS acceptance_rate
  FROM shown s LEFT JOIN decided d USING (action_type)
) s
ON t.action_type = s.action_type
WHEN MATCHED AND (t.shown IS DISTINCT FROM s.shown OR t.accepted IS DISTINCT FROM s.accepted
                  OR t.done IS DISTINCT FROM s.done OR t.dismissed IS DISTINCT FROM s.dismissed
                  OR t.acceptance_rate IS DISTINCT FROM s.acceptance_rate) THEN UPDATE SET
  t.shown = s.shown, t.accepted = s.accepted, t.done = s.done, t.dismissed = s.dismissed,
  t.acceptance_rate = s.acceptance_rate, t.updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (action_type, shown, accepted, done, dismissed, acceptance_rate, updated_at)
  VALUES (s.action_type, s.shown, s.accepted, s.done, s.dismissed, s.acceptance_rate, current_timestamp())
WHEN NOT MATCHED BY SOURCE THEN DELETE;

-- --------------------------------------------------------------------------- NBA status
-- The app-owned status column of gold_next_best_actions mirrors the latest decision (open when
-- none, e.g. after a decision row is deleted). Only rows whose status changes are rewritten.
DECLARE OR REPLACE VARIABLE wb_status_sql STRING;

SET VAR wb_status_sql = CASE WHEN wb_nba_exists
  THEN 'MERGE INTO gold_next_best_actions t
        USING (SELECT n.action_id, coalesce(d.decision, \'open\') AS status
               FROM gold_next_best_actions n LEFT JOIN wb_latest_decision d USING (action_id)) s
        ON t.action_id = s.action_id
        WHEN MATCHED AND t.status IS DISTINCT FROM s.status THEN UPDATE SET t.status = s.status'
  ELSE 'SELECT 1'
  END;

EXECUTE IMMEDIATE wb_status_sql;
