-- Task 5: GenAI call insights (job task `ai_call_insights`, runs after governance_comments_tags).
-- One row per Google Meet call in silver_transcripts -> gold_call_insights, extracted with
-- ai_query on databricks-claude-sonnet-5-5. Parameters: :catalog, :schema.
--
-- Rebuild-safe and incremental (ruling R17):
--   * only transcripts that are new, changed (transcript_sha256), extracted with another
--     prompt_version/model, or that failed last time are sent to the model;
--   * insight rows whose meeting_id is gone from silver_transcripts are deleted;
--   * results are staged in tmp_call_insights_batch first, so each transcript is sent to the
--     model exactly once per run, then MERGEd on meeting_id (no duplicates on re-run).
--
-- Structured output: this endpoint rejects `responseFormat` ("Structured output is not
-- supported for this model because its translation requires forced tool use"), and also
-- rejects `temperature`. So the JSON Schema in src/ai/insights_schema.json is embedded
-- verbatim in the prompt and the reply is validated here (try_parse_json + from_json, enum
-- filters). src/ai/parse.py applies the same rules in Python (unit tests, Task 7 spot-check).
-- A bad reply never fails the job: the row is kept with extract_error set
-- (ai_query error text, empty_response, invalid_json or missing_summary) and retried next run.
--
-- PII: the prompt uses the attendee roster's name/role/company only; raw attendee emails are
-- never read, and gold_call_insights carries no email or phone column.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE TABLE IF NOT EXISTS gold_call_insights (
  meeting_id STRING NOT NULL COMMENT 'Google Meet meeting id (silver_transcripts.meeting_id). Primary key: one row per call.',
  opportunity_id STRING COMMENT 'Salesforce Opportunity Id (18-char) the call belongs to (joins gold_opportunity_pipeline.opportunity_id).',
  account_id STRING COMMENT 'Salesforce Account Id (18-char) of the customer or prospect on the call.',
  started_at TIMESTAMP COMMENT 'When the call started (UTC).',
  summary STRING COMMENT 'AI-written 2-3 sentence summary: where the deal stands, the main concern, the agreed next step. Null when extract_error is set.',
  next_steps ARRAY<STRUCT<action: STRING, owner: STRING, due: STRING>> COMMENT 'Follow-ups agreed on the call: action (imperative), owner ("Name (role)", seller or customer), due (YYYY-MM-DD when a date was stated, else null).',
  open_items ARRAY<STRING> COMMENT 'Questions, requests or decisions still unresolved at the end of the call.',
  interests ARRAY<STRING> COMMENT 'Fleetwise products the customer showed interest in. Only Vehicle Telematics, AI Dash Cams, Driver Safety, Fuel & Maintenance, Compliance/ELD, Equipment Monitoring.',
  competitors ARRAY<STRING> COMMENT 'Competing vendors mentioned on the call, as spoken (e.g. RoadLynx, FleetCore, Trackwell). Empty when none.',
  objections ARRAY<STRING> COMMENT 'Customer concerns or pushback (price, timing, contract, cameras, IT review ...), competitor quotes include price and expiry.',
  sentiment STRING COMMENT 'Overall customer sentiment toward buying from Fleetwise on this call: positive, neutral or negative.',
  stakeholders ARRAY<STRUCT<name: STRING, role: STRING, stance: STRING>> COMMENT 'Customer-side people on or named in the call: name, role/title, stance (champion, supportive, neutral, skeptical, blocker). No contact details.',
  model STRING COMMENT 'Serving endpoint used for the extraction (databricks-claude-sonnet-5-5).',
  prompt_version STRING COMMENT 'Version of the extraction prompt. A new version re-extracts every call.',
  transcript_sha256 STRING COMMENT 'SHA-256 of the transcript text that was extracted. A change triggers re-extraction.',
  extracted_at TIMESTAMP COMMENT 'When this row was last extracted.',
  extract_error STRING COMMENT 'Null on success. Otherwise why extraction failed (ai_query error, empty_response, invalid_json, missing_summary). Failed rows are retried on the next run.',
  CONSTRAINT gold_call_insights_pk PRIMARY KEY (meeting_id)
)
COMMENT 'Gold (GenAI): one row per sales call with AI-extracted summary, next steps, open items, product interests, competitors, objections, sentiment and stakeholders. Built by ai_query over silver_transcripts, feeds Deal 360, deal scoring and next-best-actions. Contains no PII.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- Idempotent; keeps CDF on even if the table was created before this property was added.
ALTER TABLE gold_call_insights SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

-- Calls removed upstream (e.g. a pipeline full refresh dropped them) lose their insights too.
DELETE FROM gold_call_insights
WHERE meeting_id NOT IN (SELECT meeting_id FROM silver_transcripts);

CREATE OR REPLACE TABLE tmp_call_insights_batch AS
WITH pending AS (
  SELECT
    s.meeting_id,
    s.opportunity_id,
    s.account_id,
    s.started_at,
    s.transcript_text,
    sha2(s.transcript_text, 256) AS transcript_sha256,
    o.owner_name,
    o.account_name,
    transform(s.attendees, a -> concat_ws(' | ', a.name, a.role, a.company)) AS roster
  FROM silver_transcripts s
  LEFT JOIN gold_opportunity_pipeline o ON o.opportunity_id = s.opportunity_id
  LEFT JOIN gold_call_insights t ON t.meeting_id = s.meeting_id
  WHERE s.transcript_text IS NOT NULL
    AND (t.meeting_id IS NULL
      OR t.extract_error IS NOT NULL
      OR t.transcript_sha256 IS DISTINCT FROM sha2(s.transcript_text, 256)
      OR t.prompt_version IS DISTINCT FROM 'v1'
      OR t.model IS DISTINCT FROM 'databricks-claude-sonnet-5-5')
),
calls AS (
  SELECT
    p.*,
    ai_query(
      'databricks-claude-sonnet-5-5',
      concat(
        'You are a sales operations analyst at Fleetwise, a fleet telematics vendor. ',
        'Read the Google Meet sales call transcript below and extract insights for the Fleetwise seller.\n\n',
        'Context\n',
        '- Meeting date: ', date_format(p.started_at, 'EEEE, yyyy-MM-dd'), '\n',
        '- Fleetwise seller (opportunity owner): ', coalesce(p.owner_name, 'unknown'), '\n',
        '- Customer account: ', coalesce(p.account_name, 'unknown'), '\n',
        '- Attendees (name | role | company): ', coalesce(array_join(p.roster, ' / '), 'unknown'), '\n\n',
        'Return ONLY one JSON object, with no prose and no markdown code fences, that conforms to this JSON Schema:\n',
        '{"type":"object","additionalProperties":false,"required":["summary","next_steps","open_items","interests","competitors","objections","sentiment","stakeholders"],"properties":{"summary":{"type":"string"},"next_steps":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["action","owner","due"],"properties":{"action":{"type":"string"},"owner":{"type":"string"},"due":{"type":["string","null"]}}}},"open_items":{"type":"array","items":{"type":"string"}},"interests":{"type":"array","items":{"type":"string","enum":["Vehicle Telematics","AI Dash Cams","Driver Safety","Fuel & Maintenance","Compliance/ELD","Equipment Monitoring"]}},"competitors":{"type":"array","items":{"type":"string"}},"objections":{"type":"array","items":{"type":"string"}},"sentiment":{"type":"string","enum":["positive","neutral","negative"]},"stakeholders":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["name","role","stance"],"properties":{"name":{"type":"string"},"role":{"type":"string"},"stance":{"type":"string","enum":["champion","supportive","neutral","skeptical","blocker"]}}}}}}',
        '\n\nField rules\n',
        '- summary: exactly 2 or 3 sentences (at most 70 words) of plain prose for a busy seller: where the deal stands, the main customer concern or blocker, and the agreed next step. No lists, no dates beyond the key next step.\n',
        '- next_steps: every concrete follow-up that someone committed to on the call, on either side. ',
        'action: an imperative phrase naming the deliverable, specific enough to act on (for example "Send the revised proposal with 20-vehicle pilot pricing"). ',
        'owner: the person who committed, written as "Full Name (role)" using the attendee roster, for example "Alex Kim (Fleetwise AE)" or "Sam Ortiz (customer, IT Director)". Use the role alone if no name is known. ',
        'due: the date stated for that step as YYYY-MM-DD, resolved against the meeting date (for example "by Monday" means the first Monday after the meeting). Null when no timing was stated. ',
        'Do not invent steps that were not agreed.\n',
        '- open_items: at most 5 questions, requests or decisions still unresolved at the end of the call, most important first, each a short phrase. Do not repeat the next steps.\n',
        '- interests: Fleetwise products the customer asked about or showed interest in, using only these exact names: ',
        'Vehicle Telematics (GPS, live location, trip history), AI Dash Cams (cameras, video, event clips), ',
        'Driver Safety (coaching, scorecards, safe driving), Fuel & Maintenance (fuel spend, idling, fault codes, preventive maintenance), ',
        'Compliance/ELD (ELD, hours of service, roadside inspections, FMCSA), Equipment Monitoring (trailers, generators, unpowered assets). Empty if none.\n',
        '- competitors: competing vendors mentioned on the call, company names only, exactly as spoken. Fleetwise is never a competitor. Empty if none.\n',
        '- objections: at most 5 customer concerns or pushback, each a short phrase (price, timing, contract terms, driver or union pushback on cameras, IT or security review, adoption). ',
        'When a competitor quote is mentioned, include the competitor, price and expiry as YYYY-MM-DD, for example "RoadLynx quoted $28 per vehicle per month, valid through 2026-12-04".\n',
        '- sentiment: the overall customer attitude toward buying from Fleetwise on this call: positive, neutral or negative.\n',
        '- stakeholders: customer-side people (never Fleetwise employees) who spoke or were named, with role = their title or function from the roster or the conversation ("unknown" if not known), ',
        'and stance toward the deal = champion (actively pushing it internally), supportive, neutral, skeptical, or blocker (opposing it). Never include email addresses or phone numbers.\n\n',
        'Transcript\n',
        p.transcript_text
      ),
      modelParameters => named_struct('max_tokens', 8000),
      failOnError => false
    ) AS ai
  FROM pending p
),
parsed AS (
  SELECT
    c.*,
    c.ai.result AS raw_text,
    c.ai.errorMessage AS ai_error,
    -- first "{" to last "}": drops any prose or ``` fences around the object
    regexp_extract(coalesce(c.ai.result, ''), '(?s)\\{.*\\}', 0) AS json_text
  FROM calls c
),
typed AS (
  SELECT
    *,
    CASE WHEN try_parse_json(json_text) IS NOT NULL THEN from_json(json_text,
      'STRUCT<summary: STRING, next_steps: ARRAY<STRUCT<action: STRING, owner: STRING, due: STRING>>, open_items: ARRAY<STRING>, interests: ARRAY<STRING>, competitors: ARRAY<STRING>, objections: ARRAY<STRING>, sentiment: STRING, stakeholders: ARRAY<STRUCT<name: STRING, role: STRING, stance: STRING>>>')
    END AS j
  FROM parsed
),
checked AS (
  SELECT
    *,
    CASE
      WHEN ai_error IS NOT NULL THEN concat('ai_query: ', ai_error)
      WHEN raw_text IS NULL OR trim(raw_text) = '' THEN 'empty_response'
      WHEN j IS NULL THEN 'invalid_json'
      WHEN nullif(trim(j.summary), '') IS NULL THEN 'missing_summary'
    END AS extract_error
  FROM typed
)
SELECT
  meeting_id,
  opportunity_id,
  account_id,
  started_at,
  IF(extract_error IS NULL, trim(j.summary), NULL) AS summary,
  IF(extract_error IS NULL, coalesce(filter(
    transform(j.next_steps, s -> named_struct(
      'action', nullif(trim(s.action), ''),
      'owner', nullif(trim(s.owner), ''),
      'due', CASE WHEN trim(s.due) RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                  THEN CAST(try_to_date(trim(s.due)) AS STRING) END)),
    s -> s.action IS NOT NULL), array()), NULL) AS next_steps,
  IF(extract_error IS NULL, coalesce(array_distinct(filter(transform(j.open_items, v -> trim(v)), v -> v <> '')), array()), NULL) AS open_items,
  IF(extract_error IS NULL, coalesce(array_distinct(filter(transform(j.interests, v -> trim(v)),
    v -> v IN ('Vehicle Telematics', 'AI Dash Cams', 'Driver Safety', 'Fuel & Maintenance', 'Compliance/ELD', 'Equipment Monitoring'))), array()), NULL) AS interests,
  IF(extract_error IS NULL, coalesce(array_distinct(filter(transform(j.competitors, v -> trim(v)), v -> v <> '')), array()), NULL) AS competitors,
  IF(extract_error IS NULL, coalesce(array_distinct(filter(transform(j.objections, v -> trim(v)), v -> v <> '')), array()), NULL) AS objections,
  CASE WHEN extract_error IS NULL AND lower(trim(j.sentiment)) IN ('positive', 'neutral', 'negative')
       THEN lower(trim(j.sentiment)) END AS sentiment,
  IF(extract_error IS NULL, coalesce(filter(
    transform(j.stakeholders, s -> named_struct(
      'name', nullif(trim(s.name), ''),
      'role', nullif(trim(s.role), ''),
      'stance', CASE WHEN lower(trim(s.stance)) IN ('champion', 'supportive', 'neutral', 'skeptical', 'blocker')
                     THEN lower(trim(s.stance)) END)),
    s -> s.name IS NOT NULL), array()), NULL) AS stakeholders,
  'databricks-claude-sonnet-5-5' AS model,
  'v1' AS prompt_version,
  transcript_sha256,
  current_timestamp() AS extracted_at,
  extract_error
FROM checked;

MERGE INTO gold_call_insights t
USING tmp_call_insights_batch s
ON t.meeting_id = s.meeting_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

DROP TABLE IF EXISTS tmp_call_insights_batch;
