-- Task 7: next best actions + the app's opportunity table (job task `next_best_actions`,
-- runs after ai_scoring). Parameters: :catalog, :schema.
--
-- 1. gold_opportunity_app (ruling R3): gold_opportunity_pipeline LEFT JOIN gold_deal_scores,
--    open and closed opportunities. A regular Delta table (CDF on) so Lakebase can sync it.
-- 2. gold_next_best_actions: the seller's ranked action queue (spec 4.4 item 4). Sources:
--      call  - every next_steps item of the opportunity's latest successful call insight;
--      model - the deal model's next_action when next_action_conf >= 0.5;
--      rule  - stale_opp (no completed activity for 21+ days), competitor_expiring (competitor in
--              the CRM field or on any call, and the deal closes this quarter), usage_drop
--              (account 30-day usage trend below -15%), p1_ticket (an Open/Pending P1 ticket).
--              Account-level rules attach to the account's largest open opportunity.
--    priority_score = acv * p_close * urgency * feedback, where p_close = p_close_quarter
--    (falls back to the CRM stage probability if the deal has no score), urgency = 1.5 when the
--    action is due within 7 days of the data as-of date (overdue included) or is
--    competitor_expiring, 1.2 within 14 days, else 1.0; feedback = clamp(0.5 + acceptance rate
--    of the action type, 0.5, 1.5) from Task 8's write-back table, 1.0 while it is absent/empty.
--
-- Rebuild-safe (ruling R17): candidates are recomputed deterministically from the inputs every
-- run; action_id = sha2(opportunity_id | action_type | source_key) is stable across runs, so the
-- app's write-backs keyed on action_id survive. One MERGE inserts new actions, updates changed
-- ones (never the app-owned status), and deletes actions whose source disappeared. Rows that did
-- not change are not rewritten (no CDF churn for the Lakebase sync).
-- Day-based logic is relative to the data as-of date (latest opportunity LastModifiedDate, as in
-- gold.sql), never current_date(), so the demo is stable.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- --------------------------------------------------------------------------- gold_opportunity_app
CREATE TABLE IF NOT EXISTS gold_opportunity_app (
  opportunity_id STRING NOT NULL COMMENT 'Salesforce Opportunity Id (18-char). Primary key.',
  opportunity_name STRING COMMENT 'Opportunity name: "<account> - <primary product> <type>".',
  account_id STRING COMMENT 'Salesforce Account Id of the customer or prospect.',
  account_name STRING COMMENT 'Account (company) name.',
  owner_id STRING COMMENT 'User Id of the seller who owns the opportunity.',
  owner_name STRING COMMENT 'Name of the owning seller.',
  manager_id STRING COMMENT 'User Id of the owning seller''s manager.',
  rvp_id STRING COMMENT 'User Id of the owning seller''s RVP.',
  segment STRING COMMENT 'Account segment: SMB, Mid-Market or Enterprise.',
  region STRING COMMENT 'Account region: West, Central or East.',
  stage STRING COMMENT 'Sales stage: Qualification, Discovery, Demo, Proposal, Negotiation, Closed Won, Closed Lost.',
  acv DOUBLE COMMENT 'Annual contract value in USD (Salesforce Amount). "ACV" always means this column.',
  close_date DATE COMMENT 'Expected (open) or actual (closed) close date.',
  fiscal_quarter STRING COMMENT 'Fiscal quarter of close_date, FYyyQn; the fiscal year starts Feb 1 (Nov 2026 = FY27Q4).',
  is_current_quarter BOOLEAN COMMENT 'True when close_date falls in the current fiscal quarter (as of the data date).',
  is_closed BOOLEAN COMMENT 'True for Closed Won / Closed Lost.',
  is_won BOOLEAN COMMENT 'True for Closed Won.',
  probability INT COMMENT 'Stage default win probability in percent (CRM field, not a model score).',
  forecast_category STRING COMMENT 'CRM forecast category: Pipeline, Best Case, Commit, Closed, Omitted.',
  opportunity_type STRING COMMENT 'New Business, Expansion or Renewal.',
  lead_source STRING COMMENT 'Original lead source of the opportunity.',
  stage_age_days INT COMMENT 'Days since the opportunity entered its current stage, relative to the data as-of date.',
  days_to_close INT COMMENT 'close_date minus the data as-of date in days (negative = close date has passed).',
  last_activity_at TIMESTAMP COMMENT 'Most recent completed activity on the opportunity: a Task (call/email) with Status Completed or a meeting that started by the as-of time (null if none).',
  days_since_last_activity INT COMMENT 'Days from last_activity_at to the data as-of date.',
  activities_30d INT COMMENT 'Number of completed activities on the opportunity in the 30 days up to the as-of time.',
  competitor STRING COMMENT 'Competitor recorded in the CRM field (RoadLynx, FleetCore, Trackwell), often blank even when one is involved.',
  products ARRAY<STRING> COMMENT 'Fleetwise products on the opportunity.',
  primary_product STRING COMMENT 'First product on the opportunity.',
  fleet_size INT COMMENT 'Number of vehicles in scope.',
  next_step STRING COMMENT 'CRM NextStep field typed by the seller.',
  loss_reason STRING COMMENT 'Reason for Closed Lost (null otherwise).',
  created_date TIMESTAMP COMMENT 'When the opportunity was created.',
  last_modified_date TIMESTAMP COMMENT 'Last CRM modification (the AUTO CDC sequence column).',
  p_close_quarter DOUBLE COMMENT 'AI: calibrated likelihood (0..1) that the deal closes won this fiscal quarter (gold_deal_scores). Null for closed opps and unscored deals.',
  close_label STRING COMMENT 'AI: most probable close-this-quarter level: Very unlikely, Unlikely, Possible, Likely, Very likely.',
  close_confidence DOUBLE COMMENT 'AI: confidence (0..1) of the close-this-quarter answer.',
  next_action STRING COMMENT 'AI: recommended next seller action: send_proposal, multithread, schedule_demo, exec_sponsor, address_risk or nurture.',
  next_action_conf DOUBLE COMMENT 'AI: confidence (0..1) of next_action.',
  competitive_risk DOUBLE COMMENT 'AI: probability (0..1) that a competitor is actively in the deal with a real chance to win.',
  churn_risk DOUBLE COMMENT 'AI: probability (0..1) that the account is at risk of churning or shrinking.',
  scored_at TIMESTAMP COMMENT 'When the deal was last scored (gold_deal_scores.scored_at).',
  score_error STRING COMMENT 'Null when the last scoring call succeeded; otherwise its error (the previous good score is kept).',
  row_hash STRING COMMENT 'SHA-256 of the row content; the MERGE rewrites a row only when it changes (internal change detection).',
  CONSTRAINT gold_opportunity_app_pk PRIMARY KEY (opportunity_id)
)
COMMENT 'Gold (app): one row per opportunity (open and closed) from gold_opportunity_pipeline with its OpenJev deal scores (gold_deal_scores, null for closed opps). Synced to Lakebase for the Seller Hub app. Not row-filtered; the app scopes rows to the signed-in seller. Rebuilt by MERGE in job task next_best_actions.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

ALTER TABLE gold_opportunity_app SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

MERGE INTO gold_opportunity_app t
USING (
  SELECT o.*,
         s.p_close_quarter, s.close_label, s.close_confidence, s.next_action, s.next_action_conf,
         s.competitive_risk, s.churn_risk, s.scored_at, s.score_error,
         sha2(to_json(struct(o.*, s.p_close_quarter, s.close_label, s.close_confidence, s.next_action,
                             s.next_action_conf, s.competitive_risk, s.churn_risk, s.scored_at,
                             s.score_error)), 256) AS row_hash
  FROM gold_opportunity_pipeline o
  LEFT JOIN gold_deal_scores s ON s.opportunity_id = o.opportunity_id
) s
ON t.opportunity_id = s.opportunity_id
WHEN MATCHED AND t.row_hash IS DISTINCT FROM s.row_hash THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;

-- --------------------------------------------------------------------------- feedback (optional)
-- Task 8's write-back table may not exist yet: reference it only through dynamic SQL after an
-- information_schema check, so this file runs either way. Expected contract (Task 8):
-- one row per action_type with acceptance_rate in 0..1.
-- (A SQL file task runs statement by statement, so this uses a session variable rather than a
-- BEGIN ... END block.)
DECLARE OR REPLACE VARIABLE nba_feedback_sql STRING;

SET VAR nba_feedback_sql = (
  SELECT CASE WHEN count(*) > 0
    THEN 'CREATE OR REPLACE TEMPORARY VIEW nba_feedback AS
          SELECT action_type, least(1.5, greatest(0.5, 0.5 + avg(acceptance_rate))) AS factor
          FROM gold_nba_feedback WHERE acceptance_rate IS NOT NULL GROUP BY action_type'
    ELSE 'CREATE OR REPLACE TEMPORARY VIEW nba_feedback AS
          SELECT CAST(NULL AS STRING) AS action_type, CAST(NULL AS DOUBLE) AS factor WHERE false'
    END
  FROM information_schema.tables
  WHERE table_catalog = current_catalog() AND table_schema = current_schema()
    AND table_name = 'gold_nba_feedback');

EXECUTE IMMEDIATE nba_feedback_sql;

-- --------------------------------------------------------------------------- candidate actions
CREATE OR REPLACE TEMPORARY VIEW nba_candidates AS
WITH as_of AS (
  SELECT to_date(max(last_modified_date)) AS as_of_date FROM gold_opportunity_pipeline
),
open_opps AS (
  SELECT o.opportunity_id, o.account_id, o.owner_id, o.acv, o.close_date, o.is_current_quarter,
         o.competitor, o.created_date, o.last_activity_at, o.days_since_last_activity,
         coalesce(s.p_close_quarter, o.probability / 100.0, 0) AS p_close,
         s.next_action, s.next_action_conf
  FROM gold_opportunity_pipeline o
  LEFT JOIN gold_deal_scores s ON s.opportunity_id = o.opportunity_id
  WHERE NOT o.is_closed
),
calls AS (
  SELECT i.* FROM gold_call_insights i
  WHERE i.extract_error IS NULL AND i.opportunity_id IN (SELECT opportunity_id FROM open_opps)
),
latest_call AS (
  SELECT * FROM calls
  QUALIFY row_number() OVER (PARTITION BY opportunity_id ORDER BY started_at DESC, meeting_id) = 1
),
call_competitors AS (
  -- competitors on any call, and the earliest competitor quote expiry mentioned in an objection
  SELECT c.opportunity_id,
         array_distinct(flatten(collect_list(c.competitors))) AS competitors,
         min(CASE WHEN lower(obj) RLIKE 'quot|valid|expir'
                  THEN try_to_date(regexp_extract(obj, '(\\d{4}-\\d{2}-\\d{2})', 1)) END) AS quote_expires
  FROM calls c
  LEFT JOIN LATERAL (SELECT explode_outer(c.objections) AS obj) o
  GROUP BY c.opportunity_id
),
biggest_open_opp AS (
  SELECT account_id, opportunity_id FROM open_opps
  QUALIFY row_number() OVER (PARTITION BY account_id ORDER BY acv DESC NULLS LAST, opportunity_id) = 1
),
call_actions AS (
  SELECT c.opportunity_id, 'call_next_step' AS action_type,
         concat(c.meeting_id, '#', CAST(ns.pos AS STRING)) AS source_key, 'call' AS source,
         coalesce(nullif(trim(ns.step.action), ''), 'Follow up on the latest call') AS title,
         concat('Agreed on the ', date_format(c.started_at, 'yyyy-MM-dd'), ' call',
                CASE WHEN ns.step.owner IS NOT NULL THEN concat(' (owner: ', ns.step.owner, ')') ELSE '' END,
                CASE WHEN ns.step.due IS NOT NULL THEN concat(', due ', ns.step.due) ELSE '' END, '.') AS why,
         try_to_date(ns.step.due) AS due_date
  FROM latest_call c
  LATERAL VIEW posexplode(c.next_steps) ns AS pos, step
),
model_actions AS (
  SELECT o.opportunity_id, o.next_action AS action_type, 'model' AS source_key, 'model' AS source,
         CASE o.next_action
           WHEN 'send_proposal' THEN 'Send or revise the proposal'
           WHEN 'multithread' THEN 'Bring in more stakeholders (IT, finance, operations)'
           WHEN 'schedule_demo' THEN 'Schedule a demo or pilot'
           WHEN 'exec_sponsor' THEN 'Engage an executive sponsor'
           WHEN 'address_risk' THEN 'Address the open risk directly'
           WHEN 'nurture' THEN 'Keep in touch and nurture'
           ELSE o.next_action END AS title,
         concat('Deal model recommends ', o.next_action, ' (confidence ',
                CAST(round(o.next_action_conf * 100) AS INT), '%; P(close this quarter) ',
                CAST(round(o.p_close * 100) AS INT), '%).') AS why,
         CAST(NULL AS DATE) AS due_date
  FROM open_opps o
  WHERE o.next_action IS NOT NULL AND o.next_action_conf >= 0.5
),
stale_rule AS (
  SELECT o.opportunity_id, 'stale_opp' AS action_type, 'stale' AS source_key, 'rule' AS source,
         concat('Re-engage: no activity in ', d.days, ' days') AS title,
         concat('No completed call, email or meeting for ', d.days, ' days',
                CASE WHEN o.last_activity_at IS NOT NULL
                     THEN concat(' (last activity ', date_format(o.last_activity_at, 'yyyy-MM-dd'), ')')
                     ELSE ' (no activity logged yet)' END, '.') AS why,
         date_add(a.as_of_date, 7) AS due_date
  FROM open_opps o CROSS JOIN as_of a
  CROSS JOIN LATERAL (SELECT coalesce(o.days_since_last_activity,
                                      datediff(a.as_of_date, to_date(o.created_date))) AS days) d
  WHERE d.days >= 21
),
competitor_rule AS (
  SELECT o.opportunity_id, 'competitor_expiring' AS action_type, 'competitor' AS source_key, 'rule' AS source,
         concat('Counter ', array_join(x.comps, ' / '), ' before the quarter closes') AS title,
         concat('Competitor ', array_join(x.comps, ', '), ' is in the deal and it closes ',
                date_format(o.close_date, 'yyyy-MM-dd'), ' (this quarter)',
                CASE WHEN cc.quote_expires IS NOT NULL
                     THEN concat('; a competitor quote expires ', date_format(cc.quote_expires, 'yyyy-MM-dd'))
                     ELSE '' END, '.') AS why,
         least(o.close_date, cc.quote_expires) AS due_date
  FROM open_opps o
  LEFT JOIN call_competitors cc ON cc.opportunity_id = o.opportunity_id
  CROSS JOIN LATERAL (SELECT array_distinct(filter(concat(
                        CASE WHEN coalesce(o.competitor, '') <> '' THEN array(o.competitor) ELSE array() END,
                        coalesce(cc.competitors, array())), c -> coalesce(c, '') <> '')) AS comps) x
  WHERE o.is_current_quarter AND size(x.comps) > 0
),
usage_rule AS (
  SELECT b.opportunity_id, 'usage_drop' AS action_type, 'usage' AS source_key, 'rule' AS source,
         'Check in on falling product usage' AS title,
         concat('Account usage is down ', CAST(round(-acc.usage_trend_pct_30d) AS INT),
                '% over the last 30 days (active vehicles vs the 30 days before).') AS why,
         date_add(a.as_of_date, 14) AS due_date
  FROM gold_account_360 acc
  JOIN biggest_open_opp b ON b.account_id = acc.account_id
  CROSS JOIN as_of a
  WHERE acc.usage_trend_pct_30d < -15
),
p1_rule AS (
  SELECT b.opportunity_id, 'p1_ticket' AS action_type, 'p1' AS source_key, 'rule' AS source,
         'Get the open P1 support ticket resolved' AS title,
         concat(t.n, ' open P1 support ticket', CASE WHEN t.n > 1 THEN 's' ELSE '' END,
                ', oldest opened ', date_format(t.oldest, 'yyyy-MM-dd'), ': "', t.subject, '".') AS why,
         date_add(a.as_of_date, 2) AS due_date
  FROM (SELECT account_id, count(*) AS n, min(created_at) AS oldest,
               min_by(subject, struct(created_at, ticket_id)) AS subject
        FROM silver_tickets
        WHERE severity = 'P1' AND status IN ('Open', 'Pending')
        GROUP BY account_id) t
  JOIN biggest_open_opp b ON b.account_id = t.account_id
  CROSS JOIN as_of a
),
actions AS (
  SELECT * FROM call_actions
  UNION ALL SELECT * FROM model_actions
  UNION ALL SELECT * FROM stale_rule
  UNION ALL SELECT * FROM competitor_rule
  UNION ALL SELECT * FROM usage_rule
  UNION ALL SELECT * FROM p1_rule
),
keyed AS (
  SELECT sha2(concat_ws('|', opportunity_id, action_type, source_key), 256) AS action_id, *
  FROM actions
)
SELECT
  x.action_id, x.opportunity_id, o.account_id, o.owner_id, x.action_type, x.source_key, x.title, x.why, x.source,
  x.due_date,
  coalesce(o.acv, 0) * o.p_close * u.urgency * coalesce(f.factor, 1.0) AS priority_score
FROM keyed x
JOIN open_opps o ON o.opportunity_id = x.opportunity_id
CROSS JOIN as_of a
LEFT JOIN nba_feedback f ON f.action_type = x.action_type
CROSS JOIN LATERAL (SELECT CASE
    WHEN x.action_type = 'competitor_expiring' THEN 1.5
    WHEN datediff(x.due_date, a.as_of_date) <= 7 THEN 1.5
    WHEN datediff(x.due_date, a.as_of_date) <= 14 THEN 1.2
    ELSE 1.0 END AS urgency) u;

-- --------------------------------------------------------------------------- gold_next_best_actions
CREATE TABLE IF NOT EXISTS gold_next_best_actions (
  action_id STRING NOT NULL COMMENT 'Stable action id: sha2(opportunity_id | action_type | source_key, 256). Primary key; the same action keeps its id across runs, so app write-backs keyed on it survive.',
  opportunity_id STRING NOT NULL COMMENT 'Salesforce Opportunity Id (18-char) of the open opportunity the action is for (joins gold_opportunity_app).',
  account_id STRING COMMENT 'Salesforce Account Id of the opportunity.',
  owner_id STRING COMMENT 'User Id of the seller who owns the opportunity (the action queue owner).',
  action_type STRING COMMENT 'call_next_step (from a call), a model next_action (send_proposal, multithread, schedule_demo, exec_sponsor, address_risk, nurture), or a rule: stale_opp, competitor_expiring, usage_drop, p1_ticket.',
  source_key STRING COMMENT 'Identifies the source item within the action type: <meeting_id>#<position> for call next steps, model, or the rule name.',
  title STRING COMMENT 'One-line action shown in the app queue.',
  why STRING COMMENT 'One-line reason the action is recommended (the evidence behind it).',
  source STRING COMMENT 'Where the action comes from: call (call insights), model (OpenJev next_action) or rule.',
  due_date DATE COMMENT 'When the action is due: the call next step due date, the competitor quote expiry or close date, or a rule SLA from the data as-of date. Null when none.',
  priority_score DOUBLE COMMENT 'Ranking score = ACV x P(close this quarter) x urgency (1.5 due within 7 days or competitor_expiring, 1.2 within 14 days, else 1.0) x seller-feedback factor (0.5..1.5, 1.0 until feedback exists).',
  status STRING DEFAULT 'open' COMMENT 'Action status: open on creation; the app write-back (Task 8) sets accepted, dismissed or done. Never overwritten by a re-run.',
  created_at TIMESTAMP COMMENT 'When the action first appeared.',
  updated_at TIMESTAMP COMMENT 'When the action text, due date, owner or priority last changed.',
  CONSTRAINT gold_next_best_actions_pk PRIMARY KEY (action_id)
)
COMMENT 'Gold (AI): the seller''s ranked next best actions for open opportunities - call next steps, the deal model''s next action (confidence >= 0.5) and rules (stale, competitor this quarter, usage drop, open P1 ticket), ranked by ACV x P(close) x urgency. Synced to Lakebase for the Seller Hub queue. Rebuilt deterministically by MERGE in job task next_best_actions; ids are stable.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'delta.feature.allowColumnDefaults' = 'supported');

ALTER TABLE gold_next_best_actions SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

MERGE INTO gold_next_best_actions t
USING nba_candidates s
ON t.action_id = s.action_id
WHEN MATCHED AND (t.title IS DISTINCT FROM s.title OR t.why IS DISTINCT FROM s.why
                  OR t.due_date IS DISTINCT FROM s.due_date OR t.owner_id IS DISTINCT FROM s.owner_id
                  OR t.account_id IS DISTINCT FROM s.account_id
                  OR abs(t.priority_score - s.priority_score) > 1e-9) THEN UPDATE SET
  t.account_id = s.account_id, t.owner_id = s.owner_id, t.title = s.title, t.why = s.why,
  t.due_date = s.due_date, t.priority_score = s.priority_score, t.updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT
  (action_id, opportunity_id, account_id, owner_id, action_type, source_key, title, why, source, due_date,
   priority_score, status, created_at, updated_at)
  VALUES (s.action_id, s.opportunity_id, s.account_id, s.owner_id, s.action_type, s.source_key, s.title, s.why,
          s.source, s.due_date, s.priority_score, 'open', current_timestamp(), current_timestamp())
WHEN NOT MATCHED BY SOURCE THEN DELETE;
