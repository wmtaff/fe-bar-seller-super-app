-- Gold: business-ready materialized views consumed by AI, Lakebase, Genie and the app.
-- All day-based measures are relative to the data as-of date (latest opportunity
-- LastModifiedDate; 2026-11-16 per ruling R7), never current_date(), so the demo is stable.
-- Fiscal year starts Feb 1: fiscal_quarter = FYyyQn, e.g. 2026-11-16 -> FY27Q4.
-- No row filters here (ruling R2): Task 4 adds secure views and masks. CDF is on for
-- every gold table (Lakebase synced tables need it).

-- --------------------------------------------------------------------------- helpers
CREATE TEMPORARY VIEW data_as_of AS
SELECT max(last_modified_date) AS as_of_ts, to_date(max(last_modified_date)) AS as_of_date
FROM silver_opportunities;

-- --------------------------------------------------------------------------- user hierarchy
CREATE OR REFRESH MATERIALIZED VIEW gold_user_hierarchy (
  user_id STRING NOT NULL COMMENT 'Salesforce User Id (18-char). Primary key.',
  name STRING COMMENT 'Full name of the Fleetwise employee.',
  email STRING COMMENT 'Work email (fleetwise.example).',
  role STRING COMMENT 'Level in the sales hierarchy: Seller, Manager or RVP.',
  role_name STRING COMMENT 'Salesforce UserRole name, e.g. "Account Executive - Mid-Market West".',
  title STRING COMMENT 'Job title, e.g. Account Executive, Senior Account Executive, Sales Manager, Regional Vice President.',
  segment STRING COMMENT 'Sales segment: SMB, Mid-Market or Enterprise.',
  region STRING COMMENT 'Sales region: West, Central or East.',
  manager_id STRING COMMENT 'User Id of the direct manager (null for RVPs).',
  manager_name STRING COMMENT 'Name of the direct manager.',
  rvp_id STRING COMMENT 'User Id of the Regional Vice President at the top of this user''s chain (the RVP''s own Id for RVPs).',
  rvp_name STRING COMMENT 'Name of the Regional Vice President.',
  annual_quota DOUBLE COMMENT 'Annual bookings quota in USD (team roll-up for managers and RVPs).',
  demo_persona STRING COMMENT 'Demo persona tag: seller (Jordan Rivera), manager (Morgan Lee), empty-demo (Taylor Empty); null otherwise.',
  is_active BOOLEAN COMMENT 'Whether the user is active.'
)
COMMENT 'Gold: Fleetwise sales org hierarchy, seller -> manager -> RVP. One row per user. Used for row-level security and team roll-ups.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
WITH lvl AS (
  SELECT *,
    CASE WHEN title = 'Regional Vice President' THEN 'RVP'
         WHEN title = 'Sales Manager' THEN 'Manager'
         ELSE 'Seller' END AS role
  FROM silver_users
)
SELECT
  u.user_id, u.name, u.email, u.role, u.role_name, u.title, u.segment, u.region,
  u.manager_id,
  m.name AS manager_name,
  CASE WHEN u.role = 'RVP' THEN u.user_id
       WHEN u.role = 'Manager' THEN u.manager_id
       ELSE m.manager_id END AS rvp_id,
  CASE WHEN u.role = 'RVP' THEN u.name
       WHEN u.role = 'Manager' THEN m.name
       ELSE r.name END AS rvp_name,
  u.annual_quota, u.demo_persona, u.is_active
FROM lvl u
LEFT JOIN lvl m ON u.manager_id = m.user_id
LEFT JOIN lvl r ON m.manager_id = r.user_id;

-- --------------------------------------------------------------------------- opportunity pipeline
CREATE OR REFRESH MATERIALIZED VIEW gold_opportunity_pipeline (
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
  last_activity_at TIMESTAMP COMMENT 'Most recent completed call, email or meeting logged on the opportunity (null if none).',
  days_since_last_activity INT COMMENT 'Days from last_activity_at to the data as-of date.',
  activities_30d INT COMMENT 'Number of activities on the opportunity in the 30 days up to the as-of date.',
  competitor STRING COMMENT 'Competitor recorded in the CRM field (RoadLynx, FleetCore, Trackwell), often blank even when one is involved.',
  products ARRAY<STRING> COMMENT 'Fleetwise products on the opportunity.',
  primary_product STRING COMMENT 'First product on the opportunity.',
  fleet_size INT COMMENT 'Number of vehicles in scope.',
  next_step STRING COMMENT 'CRM NextStep field typed by the seller.',
  loss_reason STRING COMMENT 'Reason for Closed Lost (null otherwise).',
  created_date TIMESTAMP COMMENT 'When the opportunity was created.',
  last_modified_date TIMESTAMP COMMENT 'Last CRM modification (the AUTO CDC sequence column).'
)
COMMENT 'Gold: one row per opportunity (open and closed) with stage age, days to close, activity recency and fiscal quarter. Not row-filtered; use v_opportunity_pipeline for governed access.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
WITH stage_entry AS (
  SELECT h.opportunity_id, h.stage_name, max(h.created_date) AS entered_at
  FROM silver_opportunity_history h
  GROUP BY h.opportunity_id, h.stage_name
),
act AS (
  SELECT a.opportunity_id,
         max(a.activity_at) AS last_activity_at,
         count_if(a.activity_at > d.as_of_ts - INTERVAL 30 DAYS) AS activities_30d
  FROM silver_activities a CROSS JOIN data_as_of d
  WHERE a.opportunity_id IS NOT NULL AND a.activity_at <= d.as_of_ts
  GROUP BY a.opportunity_id
),
o AS (
  SELECT o.*,
    concat('FY', lpad(CAST(pmod(year(add_months(o.close_date, 11)), 100) AS STRING), 2, '0'),
           'Q', CAST(floor(pmod(month(o.close_date) - 2, 12) / 3) + 1 AS STRING)) AS fq
  FROM silver_opportunities o
),
cur AS (
  SELECT d.*,
    concat('FY', lpad(CAST(pmod(year(add_months(d.as_of_date, 11)), 100) AS STRING), 2, '0'),
           'Q', CAST(floor(pmod(month(d.as_of_date) - 2, 12) / 3) + 1 AS STRING)) AS current_fq
  FROM data_as_of d
)
SELECT
  o.opportunity_id, o.opportunity_name, o.account_id, a.account_name,
  o.owner_id, u.name AS owner_name, u.manager_id, u.rvp_id,
  a.segment, a.region,
  o.stage_name AS stage, o.amount AS acv, o.close_date,
  o.fq AS fiscal_quarter,
  o.fq = c.current_fq AS is_current_quarter,
  o.is_closed, o.is_won, o.probability, o.forecast_category, o.opportunity_type, o.lead_source,
  CAST(datediff(c.as_of_date, to_date(coalesce(s.entered_at, o.created_date))) AS INT) AS stage_age_days,
  CAST(datediff(o.close_date, c.as_of_date) AS INT) AS days_to_close,
  act.last_activity_at,
  CAST(datediff(c.as_of_date, to_date(act.last_activity_at)) AS INT) AS days_since_last_activity,
  CAST(coalesce(act.activities_30d, 0) AS INT) AS activities_30d,
  o.competitor, o.products, o.primary_product, o.fleet_size, o.next_step, o.loss_reason,
  o.created_date, o.last_modified_date
FROM o
CROSS JOIN cur c
LEFT JOIN stage_entry s ON s.opportunity_id = o.opportunity_id AND s.stage_name = o.stage_name
LEFT JOIN act ON act.opportunity_id = o.opportunity_id
LEFT JOIN silver_accounts a ON a.account_id = o.account_id
LEFT JOIN gold_user_hierarchy u ON u.user_id = o.owner_id;

-- --------------------------------------------------------------------------- account 360
CREATE OR REFRESH MATERIALIZED VIEW gold_account_360 (
  account_id STRING NOT NULL COMMENT 'Salesforce Account Id (18-char). Primary key.',
  account_name STRING COMMENT 'Company name.',
  industry STRING COMMENT 'Industry vertical: Construction, Logistics & Transportation, Field Services, Public Sector, Food & Beverage.',
  account_type STRING COMMENT 'Customer (owns at least one product) or Prospect.',
  segment STRING COMMENT 'Segment: SMB, Mid-Market or Enterprise.',
  region STRING COMMENT 'Region: West, Central or East.',
  billing_state STRING COMMENT 'US state of the billing address.',
  fleet_size INT COMMENT 'Total vehicles in the customer''s fleet.',
  employees INT COMMENT 'Number of employees.',
  annual_revenue DOUBLE COMMENT 'Company annual revenue in USD.',
  owner_id STRING COMMENT 'User Id of the account owner (seller).',
  owner_name STRING COMMENT 'Name of the account owner.',
  customer_since DATE COMMENT 'Date of the first Closed Won deal (null for prospects).',
  arr DOUBLE COMMENT 'Current annual recurring revenue in USD.',
  products_owned ARRAY<STRING> COMMENT 'Fleetwise products the account already owns.',
  whitespace_products ARRAY<STRING> COMMENT 'Fleetwise products the account does not own yet (cross-sell whitespace).',
  active_vehicles_30d DOUBLE COMMENT 'Average daily active vehicles over the last 30 days of usage data (null for prospects).',
  usage_trend_pct_30d DOUBLE COMMENT 'Percent change in average daily active vehicles, last 30 days vs the 30 days before (negative = declining usage).',
  adoption_vehicle_telematics_30d DOUBLE COMMENT 'Average Vehicle Telematics feature adoption (0..1) over the last 30 days.',
  adoption_ai_dash_cams_30d DOUBLE COMMENT 'Average AI Dash Cams feature adoption (0..1) over the last 30 days.',
  adoption_driver_safety_30d DOUBLE COMMENT 'Average Driver Safety feature adoption (0..1) over the last 30 days.',
  adoption_fuel_maintenance_30d DOUBLE COMMENT 'Average Fuel & Maintenance feature adoption (0..1) over the last 30 days.',
  adoption_compliance_eld_30d DOUBLE COMMENT 'Average Compliance/ELD feature adoption (0..1) over the last 30 days.',
  adoption_equipment_monitoring_30d DOUBLE COMMENT 'Average Equipment Monitoring feature adoption (0..1) over the last 30 days.',
  usage_as_of DATE COMMENT 'Latest usage date in the data (the window end for the 30-day usage measures).',
  open_tickets INT COMMENT 'Support tickets currently Open or Pending.',
  p1_tickets_30d INT COMMENT 'P1 (highest severity) support tickets created in the last 30 days.',
  open_opportunities INT COMMENT 'Number of open opportunities on the account.',
  open_pipeline_acv DOUBLE COMMENT 'Sum of ACV of open opportunities on the account (USD).',
  last_activity_at TIMESTAMP COMMENT 'Most recent completed call, email or meeting with the account.'
)
COMMENT 'Gold: account 360 - firmographics, ARR, products owned and whitespace, 30-day usage trend, support load, open pipeline and last touch. One row per account.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
WITH ua AS (
  SELECT max(usage_date) AS usage_as_of FROM silver_usage_daily
),
usage AS (
  SELECT u.account_id,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.active_vehicles END) AS last30,
    avg(CASE WHEN u.usage_date <= date_sub(ua.usage_as_of, 30) AND u.usage_date > date_sub(ua.usage_as_of, 60)
             THEN u.active_vehicles END) AS prior30,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_vehicle_telematics END) AS ad_vt,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_ai_dash_cams END) AS ad_dc,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_driver_safety END) AS ad_ds,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_fuel_maintenance END) AS ad_fm,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_compliance_eld END) AS ad_eld,
    avg(CASE WHEN u.usage_date > date_sub(ua.usage_as_of, 30) THEN u.adoption_equipment_monitoring END) AS ad_em
  FROM silver_usage_daily u CROSS JOIN ua
  GROUP BY u.account_id
),
tix AS (
  SELECT t.account_id,
    count_if(t.status IN ('Open', 'Pending')) AS open_tickets,
    count_if(t.severity = 'P1' AND t.created_at > d.as_of_ts - INTERVAL 30 DAYS) AS p1_30d
  FROM silver_tickets t CROSS JOIN data_as_of d
  GROUP BY t.account_id
),
opps AS (
  SELECT account_id, count(*) AS n_open, sum(acv) AS open_acv
  FROM gold_opportunity_pipeline WHERE NOT is_closed GROUP BY account_id
),
act AS (
  SELECT a.account_id, max(a.activity_at) AS last_activity_at
  FROM silver_activities a CROSS JOIN data_as_of d
  WHERE a.activity_at <= d.as_of_ts
  GROUP BY a.account_id
)
SELECT
  a.account_id, a.account_name, a.industry, a.account_type, a.segment, a.region, a.billing_state,
  a.fleet_size, a.employees, a.annual_revenue, a.owner_id, own.name AS owner_name, a.customer_since,
  a.current_arr AS arr,
  a.products_owned,
  array_except(array('Vehicle Telematics', 'AI Dash Cams', 'Driver Safety', 'Fuel & Maintenance',
                     'Compliance/ELD', 'Equipment Monitoring'), a.products_owned) AS whitespace_products,
  round(usage.last30, 1) AS active_vehicles_30d,
  round((usage.last30 - usage.prior30) / nullif(usage.prior30, 0) * 100, 1) AS usage_trend_pct_30d,
  round(usage.ad_vt, 3) AS adoption_vehicle_telematics_30d,
  round(usage.ad_dc, 3) AS adoption_ai_dash_cams_30d,
  round(usage.ad_ds, 3) AS adoption_driver_safety_30d,
  round(usage.ad_fm, 3) AS adoption_fuel_maintenance_30d,
  round(usage.ad_eld, 3) AS adoption_compliance_eld_30d,
  round(usage.ad_em, 3) AS adoption_equipment_monitoring_30d,
  CASE WHEN usage.account_id IS NOT NULL THEN ua.usage_as_of END AS usage_as_of,
  CAST(coalesce(tix.open_tickets, 0) AS INT) AS open_tickets,
  CAST(coalesce(tix.p1_30d, 0) AS INT) AS p1_tickets_30d,
  CAST(coalesce(opps.n_open, 0) AS INT) AS open_opportunities,
  CAST(coalesce(opps.open_acv, 0) AS DOUBLE) AS open_pipeline_acv,
  act.last_activity_at
FROM silver_accounts a
CROSS JOIN ua
LEFT JOIN silver_users own ON own.user_id = a.owner_id
LEFT JOIN usage ON usage.account_id = a.account_id
LEFT JOIN tix ON tix.account_id = a.account_id
LEFT JOIN opps ON opps.account_id = a.account_id
LEFT JOIN act ON act.account_id = a.account_id;

-- --------------------------------------------------------------------------- seller KPIs
CREATE OR REFRESH MATERIALIZED VIEW gold_seller_kpis (
  owner_id STRING NOT NULL COMMENT 'User Id of the seller. Primary key with fiscal_quarter.',
  fiscal_quarter STRING NOT NULL COMMENT 'Fiscal quarter FYyyQn (fiscal year starts Feb 1; Nov 2026 = FY27Q4). Primary key with owner_id.',
  owner_name STRING COMMENT 'Seller name.',
  manager_id STRING COMMENT 'User Id of the seller''s manager.',
  rvp_id STRING COMMENT 'User Id of the seller''s RVP.',
  segment STRING COMMENT 'Seller segment: SMB, Mid-Market or Enterprise.',
  region STRING COMMENT 'Seller region: West, Central or East.',
  is_current_quarter BOOLEAN COMMENT 'True for the current fiscal quarter (as of the data date).',
  quota DOUBLE COMMENT 'Quarterly quota in USD (annual quota / 4).',
  closed_won_acv DOUBLE COMMENT 'ACV of Closed Won opportunities with close_date in the quarter (USD).',
  attainment_pct DOUBLE COMMENT 'closed_won_acv / quota * 100.',
  open_pipeline_acv DOUBLE COMMENT 'ACV of open opportunities with close_date in the quarter (USD).',
  commit_acv DOUBLE COMMENT 'ACV of open opportunities in forecast category Commit (Negotiation) closing in the quarter (USD).',
  best_case_acv DOUBLE COMMENT 'ACV of open opportunities in forecast category Best Case closing in the quarter (USD).',
  open_opportunities INT COMMENT 'Count of open opportunities closing in the quarter.',
  won_opportunities INT COMMENT 'Count of Closed Won opportunities in the quarter.',
  coverage_ratio DOUBLE COMMENT 'Pipeline coverage: open_pipeline_acv / remaining quota (quota - closed_won_acv); null when quota is already met or the quarter is in the past.'
)
COMMENT 'Gold: seller KPIs by fiscal quarter - quota, attainment, open pipeline, commit and pipeline coverage. One row per seller per fiscal quarter (sellers with no deals get zero rows, not missing rows).'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
WITH sellers AS (
  SELECT * FROM gold_user_hierarchy WHERE role = 'Seller'
),
quarters AS (
  SELECT q.fiscal_quarter, q.is_current_quarter,
    -- FYyyQn labels sort chronologically as strings
    q.fiscal_quarter < c.current_fq AS is_past_quarter
  FROM (SELECT fiscal_quarter, bool_or(is_current_quarter) AS is_current_quarter
        FROM gold_opportunity_pipeline GROUP BY fiscal_quarter) q
  CROSS JOIN (SELECT max(fiscal_quarter) AS current_fq FROM gold_opportunity_pipeline
              WHERE is_current_quarter) c
),
agg AS (
  SELECT owner_id, fiscal_quarter,
    sum(CASE WHEN is_won THEN acv ELSE 0 END) AS won_acv,
    sum(CASE WHEN NOT is_closed THEN acv ELSE 0 END) AS open_acv,
    sum(CASE WHEN NOT is_closed AND forecast_category = 'Commit' THEN acv ELSE 0 END) AS commit_acv,
    sum(CASE WHEN NOT is_closed AND forecast_category = 'Best Case' THEN acv ELSE 0 END) AS best_case_acv,
    count_if(NOT is_closed) AS n_open,
    count_if(is_won) AS n_won
  FROM gold_opportunity_pipeline
  GROUP BY owner_id, fiscal_quarter
),
base AS (
  SELECT s.user_id AS owner_id, q.fiscal_quarter, s.name AS owner_name, s.manager_id, s.rvp_id,
    s.segment, s.region, q.is_current_quarter, q.is_past_quarter,
    s.annual_quota / 4 AS quota,
    CAST(coalesce(g.won_acv, 0) AS DOUBLE) AS closed_won_acv,
    CAST(coalesce(g.open_acv, 0) AS DOUBLE) AS open_pipeline_acv,
    CAST(coalesce(g.commit_acv, 0) AS DOUBLE) AS commit_acv,
    CAST(coalesce(g.best_case_acv, 0) AS DOUBLE) AS best_case_acv,
    CAST(coalesce(g.n_open, 0) AS INT) AS open_opportunities,
    CAST(coalesce(g.n_won, 0) AS INT) AS won_opportunities
  FROM sellers s
  CROSS JOIN quarters q
  LEFT JOIN agg g ON g.owner_id = s.user_id AND g.fiscal_quarter = q.fiscal_quarter
)
SELECT
  owner_id, fiscal_quarter, owner_name, manager_id, rvp_id, segment, region, is_current_quarter,
  quota, closed_won_acv,
  round(closed_won_acv / nullif(quota, 0) * 100, 1) AS attainment_pct,
  open_pipeline_acv, commit_acv, best_case_acv, open_opportunities, won_opportunities,
  CASE WHEN NOT is_past_quarter AND quota - closed_won_acv > 0 THEN round(open_pipeline_acv / (quota - closed_won_acv), 2) END
    AS coverage_ratio
FROM base;

-- --------------------------------------------------------------------------- contacts (masked)
CREATE OR REFRESH MATERIALIZED VIEW gold_contacts_masked (
  contact_id STRING NOT NULL COMMENT 'Salesforce Contact Id (18-char). Primary key.',
  account_id STRING COMMENT 'Account Id the contact belongs to.',
  account_name STRING COMMENT 'Account (company) name.',
  name STRING COMMENT 'Contact full name.',
  title STRING COMMENT 'Contact job title.',
  buyer_role STRING COMMENT 'Buying-committee role: VP Operations, Fleet Manager, Safety Director, CFO, IT.',
  email STRING COMMENT 'Masked email: first letter + *** + @domain, e.g. j***@acme.com. PII - raw value only in silver_contacts.',
  email_domain STRING COMMENT 'Email domain of the contact (not PII).',
  phone STRING COMMENT 'Masked phone: ***-***-<last 4 digits>. PII - raw value only in silver_contacts.',
  mobile_phone STRING COMMENT 'Masked mobile phone: ***-***-<last 4 digits>.',
  mailing_state STRING COMMENT 'US state of the contact.',
  owner_id STRING COMMENT 'User Id of the seller who owns the contact (same as the account owner).',
  last_modified_date TIMESTAMP COMMENT 'Last CRM modification.'
)
COMMENT 'Gold: customer contacts with email and phone masked inline, safe to serve to the app via Lakebase. One row per contact.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS SELECT
  c.contact_id, c.account_id, a.account_name, c.name, c.title, c.buyer_role,
  CASE WHEN c.email IS NULL THEN NULL
       ELSE concat(left(c.email, 1), '***@', substring_index(c.email, '@', -1)) END AS email,
  substring_index(c.email, '@', -1) AS email_domain,
  CASE WHEN c.phone IS NULL THEN NULL
       ELSE concat('***-***-', right(regexp_replace(c.phone, '[^0-9]', ''), 4)) END AS phone,
  CASE WHEN c.mobile_phone IS NULL THEN NULL
       ELSE concat('***-***-', right(regexp_replace(c.mobile_phone, '[^0-9]', ''), 4)) END AS mobile_phone,
  c.mailing_state, c.owner_id, c.last_modified_date
FROM silver_contacts c
LEFT JOIN silver_accounts a ON a.account_id = c.account_id;
