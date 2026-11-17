-- Bronze: raw files from the generator, ingested incrementally with Auto Loader.
-- Reads ONLY ${raw_root} (= /Volumes/<catalog>/<schema>/<volume>/v2, ruling R10).
-- Never reads v2/_eval (ground truth) or v2/_manifest.
-- Salesforce objects land as strings (like a raw SFDC export); silver casts types.

CREATE OR REFRESH STREAMING TABLE bronze_user
COMMENT 'Bronze: raw Salesforce User (sellers, managers, RVPs), JSON lines from raw/v2/salesforce/User/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/User/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_user_role
COMMENT 'Bronze: raw Salesforce UserRole (role hierarchy), JSON lines from raw/v2/salesforce/UserRole/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/UserRole/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_account
COMMENT 'Bronze: raw Salesforce Account, JSON lines from raw/v2/salesforce/Account/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Account/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_contact
COMMENT 'Bronze: raw Salesforce Contact (raw PII: email/phone), JSON lines from raw/v2/salesforce/Contact/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Contact/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_opportunity
COMMENT 'Bronze: raw Salesforce Opportunity (increments re-emit changed opps with a newer LastModifiedDate), JSON lines from raw/v2/salesforce/Opportunity/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Opportunity/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_opportunity_history
COMMENT 'Bronze: raw Salesforce OpportunityHistory (stage changes), JSON lines from raw/v2/salesforce/OpportunityHistory/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/OpportunityHistory/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_lead
COMMENT 'Bronze: raw Salesforce Lead, JSON lines from raw/v2/salesforce/Lead/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Lead/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_task
COMMENT 'Bronze: raw Salesforce Task (calls, emails), JSON lines from raw/v2/salesforce/Task/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Task/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_event
COMMENT 'Bronze: raw Salesforce Event (meetings), JSON lines from raw/v2/salesforce/Event/batch=NNNN. All fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/salesforce/Event/',
  format => 'json',
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_meet_transcripts
COMMENT 'Bronze: raw Google Meet transcripts, one JSON document per meeting (meeting_id, opportunity_id, account_id, started_at, duration_min, attendees[], turns[]).'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/meet_transcripts/',
  format => 'json',
  multiLine => true,
  schemaHints => 'meeting_id STRING, opportunity_id STRING, account_id STRING, started_at STRING, duration_min INT, attendees ARRAY<STRUCT<name: STRING, email: STRING, role: STRING, company: STRING>>, turns ARRAY<STRUCT<speaker: STRING, ts: STRING, text: STRING>>'
);

CREATE OR REFRESH STREAMING TABLE bronze_product_usage
COMMENT 'Bronze: raw daily product usage telemetry per customer account (CSV), all fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/product_usage/',
  format => 'csv',
  header => true,
  inferColumnTypes => false
);

CREATE OR REFRESH STREAMING TABLE bronze_support_tickets
COMMENT 'Bronze: raw support tickets (JSON lines), all fields as strings.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${raw_root}/support_tickets/',
  format => 'json',
  inferColumnTypes => false
);
