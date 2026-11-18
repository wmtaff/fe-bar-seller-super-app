-- Silver: typed, deduplicated, snake_case, conformed IDs.
-- Salesforce masters are deduplicated to the latest row per Id (LastModifiedDate, then
-- ingest time). Opportunities use AUTO CDC (SCD type 1) sequenced by LastModifiedDate,
-- because increments re-emit full rows for changed opps.
-- silver_contacts.email/phone carry UC column masks (Task 4); gold_contacts_masked masks inline for Lakebase.

-- --------------------------------------------------------------------------- users
CREATE OR REFRESH MATERIALIZED VIEW silver_users (
  CONSTRAINT valid_id EXPECT (user_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: Fleetwise users (sellers, sales managers, RVPs) with their Salesforce role. Latest row per Id.'
AS
WITH u AS (
  SELECT * FROM bronze_user
  QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1
),
r AS (
  SELECT * FROM bronze_user_role
  QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1
)
SELECT
  u.Id AS user_id,
  u.Name AS name,
  u.FirstName AS first_name,
  u.LastName AS last_name,
  u.Email AS email,
  u.Username AS username,
  u.Alias AS alias,
  u.Title AS title,
  u.UserRoleId AS role_id,
  r.Name AS role_name,
  r.ParentRoleId AS parent_role_id,
  u.ManagerId AS manager_id,
  u.Segment__c AS segment,
  u.Region__c AS region,
  CAST(u.Quota__c AS DOUBLE) AS annual_quota,
  CAST(u.IsActive AS BOOLEAN) AS is_active,
  u.Demo_Persona__c AS demo_persona,
  to_timestamp(u.CreatedDate) AS created_date,
  to_timestamp(u.LastModifiedDate) AS last_modified_date
FROM u LEFT JOIN r ON u.UserRoleId = r.Id;

-- --------------------------------------------------------------------------- accounts
CREATE OR REFRESH MATERIALIZED VIEW silver_accounts (
  CONSTRAINT valid_id EXPECT (account_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: customer and prospect accounts (firmographics, owner, ARR, products owned). Latest row per Id.'
AS SELECT
  Id AS account_id,
  Name AS account_name,
  Industry AS industry,
  Type AS account_type,
  Segment__c AS segment,
  Region__c AS region,
  BillingCity AS billing_city,
  BillingState AS billing_state,
  BillingCountry AS billing_country,
  Phone AS phone,
  Website AS website,
  CAST(NumberOfEmployees AS INT) AS employees,
  CAST(Fleet_Size__c AS INT) AS fleet_size,
  CAST(AnnualRevenue AS DOUBLE) AS annual_revenue,
  OwnerId AS owner_id,
  CASE WHEN Products_Owned__c IS NULL OR Products_Owned__c = '' THEN array()
       ELSE split(Products_Owned__c, ';') END AS products_owned,
  CAST(Current_ARR__c AS DOUBLE) AS current_arr,
  to_date(Customer_Since__c) AS customer_since,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date
FROM bronze_account
QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- contacts (PII, UC column masks)
-- email, phone and mobile_phone carry the UC column mask fn_mask_pii (created by the governance_masks job
-- task before pipeline_refresh; src/governance/masks.sql). Only account group superapp_revops
-- sees raw values. The pipeline itself reads the masked values, so gold_contacts_masked
-- (same mask shapes) is unaffected. Tags are applied post-pipeline (comments_tags.sql).
-- The function name must be fully qualified: the pipeline resolves routines on
-- <catalog>.default, not the target schema, so ${uc_schema} = <catalog>.<schema>.
CREATE OR REFRESH MATERIALIZED VIEW silver_contacts (
  contact_id STRING COMMENT 'Salesforce Contact Id (18-char). Primary key.',
  account_id STRING COMMENT 'Account Id the contact belongs to.',
  first_name STRING COMMENT 'Contact first name.',
  last_name STRING COMMENT 'Contact last name.',
  name STRING COMMENT 'Contact full name.',
  title STRING COMMENT 'Contact job title.',
  buyer_role STRING COMMENT 'Buying-committee role: VP Operations, Fleet Manager, Safety Director, CFO, IT.',
  email STRING MASK ${uc_schema}.fn_mask_pii COMMENT 'Work email. PII: UC column mask fn_mask_pii, raw only for superapp_revops (others see j***@domain.com).',
  phone STRING MASK ${uc_schema}.fn_mask_pii COMMENT 'Office phone. PII: UC column mask fn_mask_pii, raw only for superapp_revops (others see ***-***-1234).',
  mobile_phone STRING MASK ${uc_schema}.fn_mask_pii COMMENT 'Mobile phone. PII: UC column mask fn_mask_pii, raw only for superapp_revops.',
  mailing_state STRING COMMENT 'US state of the contact.',
  owner_id STRING COMMENT 'User Id of the seller who owns the contact.',
  lead_source STRING COMMENT 'Original lead source.',
  created_date TIMESTAMP COMMENT 'When the contact was created.',
  last_modified_date TIMESTAMP COMMENT 'Last CRM modification.',
  CONSTRAINT valid_id EXPECT (contact_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: customer contacts, latest row per Id. email and phone are PII with UC column masks (fn_mask_pii); app consumers use gold_contacts_masked.'
AS SELECT
  Id AS contact_id,
  AccountId AS account_id,
  FirstName AS first_name,
  LastName AS last_name,
  Name AS name,
  Title AS title,
  Role__c AS buyer_role,
  Email AS email,
  Phone AS phone,
  MobilePhone AS mobile_phone,
  MailingState AS mailing_state,
  OwnerId AS owner_id,
  LeadSource AS lead_source,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date
FROM bronze_contact
QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- opportunities (AUTO CDC)
CREATE TEMPORARY VIEW opportunity_changes AS
SELECT
  Id AS opportunity_id,
  Name AS opportunity_name,
  AccountId AS account_id,
  OwnerId AS owner_id,
  StageName AS stage_name,
  CAST(Amount AS DOUBLE) AS amount,
  to_date(CloseDate) AS close_date,
  CAST(IsClosed AS BOOLEAN) AS is_closed,
  CAST(IsWon AS BOOLEAN) AS is_won,
  CAST(Probability AS INT) AS probability,
  ForecastCategoryName AS forecast_category,
  Type AS opportunity_type,
  LeadSource AS lead_source,
  CASE WHEN Products__c IS NULL OR Products__c = '' THEN array()
       ELSE split(Products__c, ';') END AS products,
  Primary_Product__c AS primary_product,
  CAST(Fleet_Size__c AS INT) AS fleet_size,
  Competitor__c AS competitor,
  Loss_Reason__c AS loss_reason,
  NextStep AS next_step,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date,
  _source_file,
  _ingested_at
FROM STREAM(bronze_opportunity);

CREATE OR REFRESH STREAMING TABLE silver_opportunities (
  CONSTRAINT valid_id EXPECT (opportunity_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT non_negative_amount EXPECT (amount >= 0),
  CONSTRAINT valid_close_date EXPECT (close_date IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: opportunities, latest version per Id (AUTO CDC SCD1 sequenced by LastModifiedDate).';

CREATE FLOW silver_opportunities_cdc AS AUTO CDC INTO silver_opportunities
FROM STREAM(opportunity_changes)
KEYS (opportunity_id)
SEQUENCE BY STRUCT(last_modified_date, _ingested_at)
STORED AS SCD TYPE 1;

-- --------------------------------------------------------------------------- opportunity history
CREATE OR REFRESH MATERIALIZED VIEW silver_opportunity_history (
  CONSTRAINT valid_id EXPECT (history_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: opportunity stage-change history (one row per stage entry).'
AS SELECT
  Id AS history_id,
  OpportunityId AS opportunity_id,
  StageName AS stage_name,
  CAST(Amount AS DOUBLE) AS amount,
  to_date(CloseDate) AS close_date,
  CAST(Probability AS INT) AS probability,
  ForecastCategory AS forecast_category,
  CreatedById AS created_by_id,
  to_timestamp(CreatedDate) AS created_date
FROM bronze_opportunity_history
QUALIFY row_number() OVER (PARTITION BY Id ORDER BY _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- leads
CREATE OR REFRESH MATERIALIZED VIEW silver_leads (
  CONSTRAINT valid_id EXPECT (lead_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: inbound leads, latest row per Id. Status values include Working, Nurturing, Qualified, Unqualified.'
AS SELECT
  Id AS lead_id,
  FirstName AS first_name,
  LastName AS last_name,
  Name AS name,
  Company AS company,
  Title AS title,
  Email AS email,
  Phone AS phone,
  LeadSource AS lead_source,
  Status AS status,
  Industry AS industry,
  State AS state,
  Country AS country,
  CAST(Fleet_Size__c AS INT) AS fleet_size,
  CASE WHEN Products_Of_Interest__c IS NULL OR Products_Of_Interest__c = '' THEN array()
       ELSE split(Products_Of_Interest__c, ';') END AS products_of_interest,
  Description AS description,
  OwnerId AS owner_id,
  CAST(IsConverted AS BOOLEAN) AS is_converted,
  to_date(ConvertedDate) AS converted_date,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date
FROM bronze_lead
QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- activities (Task + Event)
CREATE OR REFRESH MATERIALIZED VIEW silver_activities (
  CONSTRAINT valid_id EXPECT (activity_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: sales activities - Salesforce Tasks (calls, emails) and Events (meetings) in one table. activity_at is when it happened (or is scheduled).'
AS
WITH t AS (
  SELECT * FROM bronze_task
  QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1
),
e AS (
  SELECT * FROM bronze_event
  QUALIFY row_number() OVER (PARTITION BY Id ORDER BY to_timestamp(LastModifiedDate) DESC, _ingested_at DESC) = 1
)
SELECT
  Id AS activity_id,
  'Task' AS activity_object,
  Type AS activity_type,
  Subject AS subject,
  Status AS status,
  Priority AS priority,
  -- completed tasks are created when they happen; open tasks are scheduled on ActivityDate
  CASE WHEN CAST(IsClosed AS BOOLEAN) THEN to_timestamp(CreatedDate)
       ELSE to_timestamp(ActivityDate) END AS activity_at,
  CAST(CallDurationInSeconds AS INT) / 60.0 AS duration_min,
  WhoId AS contact_id,
  WhatId AS opportunity_id,
  AccountId AS account_id,
  OwnerId AS owner_id,
  CAST(NULL AS STRING) AS location,
  Description AS description,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date
FROM t
UNION ALL
SELECT
  Id AS activity_id,
  'Event' AS activity_object,
  Type AS activity_type,
  Subject AS subject,
  CAST(NULL AS STRING) AS status,
  CAST(NULL AS STRING) AS priority,
  to_timestamp(StartDateTime) AS activity_at,
  CAST(DurationInMinutes AS DOUBLE) AS duration_min,
  WhoId AS contact_id,
  WhatId AS opportunity_id,
  AccountId AS account_id,
  OwnerId AS owner_id,
  Location AS location,
  Description AS description,
  to_timestamp(CreatedDate) AS created_date,
  to_timestamp(LastModifiedDate) AS last_modified_date
FROM e;

-- --------------------------------------------------------------------------- transcripts
CREATE OR REFRESH MATERIALIZED VIEW silver_transcripts (
  CONSTRAINT valid_id EXPECT (meeting_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: one row per Google Meet call with the full transcript in transcript_text ("[hh:mm:ss] Speaker: text" per line).'
AS SELECT
  meeting_id,
  opportunity_id,
  account_id,
  to_timestamp(started_at) AS started_at,
  CAST(duration_min AS INT) AS duration_min,
  attendees,
  size(turns) AS turn_count,
  array_join(transform(turns, t -> concat('[', t.ts, '] ', t.speaker, ': ', t.text)), '\n') AS transcript_text,
  _source_file AS source_file
FROM bronze_meet_transcripts
QUALIFY row_number() OVER (PARTITION BY meeting_id ORDER BY _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- usage
CREATE OR REFRESH MATERIALIZED VIEW silver_usage_daily (
  CONSTRAINT valid_id EXPECT (account_id IS NOT NULL AND usage_date IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: daily product usage per customer account (active vehicles, logins, safety events, adoption 0..1 per product).'
AS SELECT
  account_id,
  to_date(usage_date) AS usage_date,
  CAST(total_vehicles AS INT) AS total_vehicles,
  CAST(active_vehicles AS INT) AS active_vehicles,
  CAST(driver_app_logins AS INT) AS driver_app_logins,
  CAST(admin_logins AS INT) AS admin_logins,
  CAST(safety_events AS INT) AS safety_events,
  CAST(adoption_vehicle_telematics AS DOUBLE) AS adoption_vehicle_telematics,
  CAST(adoption_ai_dash_cams AS DOUBLE) AS adoption_ai_dash_cams,
  CAST(adoption_driver_safety AS DOUBLE) AS adoption_driver_safety,
  CAST(adoption_fuel_maintenance AS DOUBLE) AS adoption_fuel_maintenance,
  CAST(adoption_compliance_eld AS DOUBLE) AS adoption_compliance_eld,
  CAST(adoption_equipment_monitoring AS DOUBLE) AS adoption_equipment_monitoring
FROM bronze_product_usage
QUALIFY row_number() OVER (PARTITION BY account_id, usage_date ORDER BY _ingested_at DESC) = 1;

-- --------------------------------------------------------------------------- tickets
CREATE OR REFRESH MATERIALIZED VIEW silver_tickets (
  CONSTRAINT valid_id EXPECT (ticket_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Silver: customer support tickets, latest row per ticket_id. Severity P1 (highest) to P4; status Open, Pending, Solved, Closed.'
AS SELECT
  ticket_id,
  account_id,
  requester_contact_id,
  product,
  subject,
  severity,
  status,
  channel,
  to_timestamp(created_at) AS created_at,
  to_timestamp(updated_at) AS updated_at,
  to_timestamp(solved_at) AS solved_at,
  CAST(first_response_minutes AS INT) AS first_response_minutes,
  CAST(csat_score AS INT) AS csat_score
FROM bronze_support_tickets
QUALIFY row_number() OVER (PARTITION BY ticket_id ORDER BY to_timestamp(updated_at) DESC, _ingested_at DESC) = 1;
