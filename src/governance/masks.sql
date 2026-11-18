-- PII column-mask functions (job task `governance_masks`, runs BEFORE pipeline_refresh,
-- because src/pipeline/silver.sql declares `email ... MASK fn_mask_pii` on silver_contacts
-- and the pipeline needs the function to exist when it (re)creates the table).
-- Mask shapes match gold_contacts_masked, so that MV is identical whether the pipeline
-- reads silver_contacts masked or raw.
-- Parameters: :catalog, :schema.

USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- Testable core: the mask with the privilege decision passed in.
CREATE OR REPLACE FUNCTION fn_mask_pii_for(v STRING, privileged BOOLEAN)
RETURNS STRING
COMMENT 'PII mask core. privileged = true returns v unchanged. Otherwise emails become <first letter>***@<domain>, phone numbers ***-***-<last 4 digits>, anything else ***. NULL stays NULL.'
RETURN CASE
  WHEN v IS NULL THEN NULL
  WHEN privileged THEN v
  WHEN v LIKE '%_@_%' THEN concat(left(v, 1), '***@', substring_index(v, '@', -1))
  WHEN v RLIKE '[0-9]' THEN concat('***-***-', right(regexp_replace(v, '[^0-9]', ''), 4))
  ELSE '***'
END;

-- The column mask attached to silver_contacts.email and .phone: raw values only for the
-- account group superapp_revops.
CREATE OR REPLACE FUNCTION fn_mask_pii(v STRING)
RETURNS STRING
COMMENT 'Column mask for contact email/phone: unmasked only for members of account group superapp_revops; everyone else sees j***@domain.com / ***-***-1234.'
RETURN fn_mask_pii_for(v, is_account_group_member('superapp_revops'));
