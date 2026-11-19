-- Tags (job task `governance_comments_tags`, runs AFTER apply_governance).
-- Table/column comments for the pipeline tables live in src/pipeline/*.sql (ruling R2);
-- this file covers what the pipeline can't: tags on pipeline tables.
-- Parameters: :catalog, :schema.
--
-- PII tag: this shared workspace has an account-level governed tag `pii` whose allowed
-- values are only [ssn, address], so `pii = true` is rejected
-- (UC_TAG_POLICY_VALUE_NOT_ALLOWED). We use the governed boolean tag `contains_pii = true`
-- plus the system data-classification tags class.email_address / class.phone_number.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

SET TAG ON COLUMN silver_contacts.email contains_pii = true;
SET TAG ON COLUMN silver_contacts.phone contains_pii = true;
SET TAG ON COLUMN silver_contacts.mobile_phone contains_pii = true;
SET TAG ON COLUMN silver_contacts.email `class.email_address`;
SET TAG ON COLUMN silver_contacts.phone `class.phone_number`;
SET TAG ON COLUMN silver_contacts.mobile_phone `class.phone_number`;

SET TAG ON COLUMN silver_leads.email contains_pii = true;
SET TAG ON COLUMN silver_leads.phone contains_pii = true;
SET TAG ON COLUMN silver_leads.email `class.email_address`;
SET TAG ON COLUMN silver_leads.phone `class.phone_number`;

-- Raw PII upstream: bronze keeps the raw CRM values (no mask; producer-only, no consumer
-- grants), and transcript attendees are raw emails.
SET TAG ON COLUMN bronze_contact.Email contains_pii = true;
SET TAG ON COLUMN bronze_contact.Phone contains_pii = true;
SET TAG ON COLUMN bronze_contact.MobilePhone contains_pii = true;
SET TAG ON COLUMN bronze_lead.Email contains_pii = true;
SET TAG ON COLUMN bronze_lead.Phone contains_pii = true;
SET TAG ON COLUMN silver_transcripts.attendees contains_pii = true;

-- Column comments on the governed views: none needed here. `CREATE VIEW ... AS
-- SELECT * FROM gold_...` (row_filters.sql) inherits every gold column comment, and the
-- view-level COMMENT is set in that DDL (verified by test_governed_objects_commented).
