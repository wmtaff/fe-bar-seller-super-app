# Task 3 evidence: Lakeflow Spark Declarative Pipeline (bronze -> silver -> gold)

Date: 2026-11-17. Profile `fevm-serverless-stable-s1omq8`, target `dev`. Pipeline `seller_superapp_pipeline`
(id `256cf7ee-6a09-4ae7-ae80-f7492987f221`), serverless, SQL (`src/pipeline/{bronze,silver,gold}.sql`),
catalog `serverless_stable_s1omq8_catalog`, schema `seller_superapp`. Source: `raw/v2/` only (init batch 0 +
increment batch 1); `_eval/` and `_manifest/` are never read. Data as-of = max opportunity LastModifiedDate =
2026-11-16T13:00Z (ruling R7), current fiscal quarter FY27Q4.

## Updates
| update_id | finished | state | how |
|---|---|---|---|
| `d9e1b51b-30c9-4c43-a348-bf0c203ea723` | 2026-11-17T22:44:27.920Z | COMPLETED | `databricks bundle run seller_superapp_pipeline` (first run, initial load) |
| `fbc044b3-5af2-498f-b13b-9ff028cd2222` | 2026-11-17T22:47:55.565Z | COMPLETED | `databricks bundle run seller_superapp_pipeline` (after the coverage_ratio past-quarter tweak) |
| `2bb8ce1a-6f04-4cb9-ba74-17ccd484041d` | 2026-11-17T22:49:50.332Z | COMPLETED | job `seller_superapp_daily` run 595528639153615: `generate_data` (batch 0 present, skipped) -> `pipeline_refresh` |

Update URL (first run): https://fevm-serverless-stable-s1omq8.cloud.databricks.com/#joblist/pipelines/256cf7ee-6a09-4ae7-ae80-f7492987f221/updates/d9e1b51b-30c9-4c43-a348-bf0c203ea723

Job run URL (pipeline_refresh as a job task): https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/595528639153615?o=7474646802937769 (TERMINATED SUCCESS)

## Row counts (after the latest update)
| table | rows |
|---|---|
| `bronze_account` | 5,000 |
| `bronze_contact` | 20,000 |
| `bronze_event` | 18,602 |
| `bronze_lead` | 4,050 |
| `bronze_meet_transcripts` | 640 |
| `bronze_opportunity` | 15,150 |
| `bronze_opportunity_history` | 66,796 |
| `bronze_product_usage` | 264,537 |
| `bronze_support_tickets` | 8,100 |
| `bronze_task` | 42,376 |
| `bronze_user` | 668 |
| `bronze_user_role` | 24 |
| `silver_accounts` | 5,000 |
| `silver_activities` | 60,978 |
| `silver_contacts` | 20,000 |
| `silver_leads` | 4,050 |
| `silver_opportunities` | 15,000 |
| `silver_opportunity_history` | 66,796 |
| `silver_tickets` | 8,100 |
| `silver_transcripts` | 640 |
| `silver_usage_daily` | 264,537 |
| `silver_users` | 668 |
| `gold_account_360` | 5,000 |
| `gold_contacts_masked` | 20,000 |
| `gold_opportunity_pipeline` | 15,000 |
| `gold_seller_kpis` | 7,200 |
| `gold_user_hierarchy` | 668 |

Notes: `bronze_opportunity` has 15,150 rows (15,000 init + 150 re-emitted in batch 1); `silver_opportunities`
has 15,000 unique Ids (AUTO CDC SCD1 keeps the newest LastModifiedDate). 150 Ids have 2 bronze versions.
Bronze `_rescued_data` is null on every opportunity row.

## Expectations (from the event log, `flow_progress.data_quality.expectations`)
| update | dataset | expectation | passed | failed |
|---|---|---|---|---|
| `2bb8ce1a` | `silver_accounts` | `valid_id` | 5,000 | 0 |
| `2bb8ce1a` | `silver_activities` | `valid_id` | 60,978 | 0 |
| `2bb8ce1a` | `silver_contacts` | `valid_id` | 20,000 | 0 |
| `2bb8ce1a` | `silver_leads` | `valid_id` | 4,050 | 0 |
| `2bb8ce1a` | `silver_opportunity_history` | `valid_id` | 66,796 | 0 |
| `2bb8ce1a` | `silver_tickets` | `valid_id` | 8,100 | 0 |
| `2bb8ce1a` | `silver_transcripts` | `valid_id` | 640 | 0 |
| `2bb8ce1a` | `silver_usage_daily` | `valid_id` | 264,537 | 0 |
| `2bb8ce1a` | `silver_users` | `valid_id` | 668 | 0 |
| `d9e1b51b` | `silver_accounts` | `valid_id` | 5,000 | 0 |
| `d9e1b51b` | `silver_activities` | `valid_id` | 60,978 | 0 |
| `d9e1b51b` | `silver_contacts` | `valid_id` | 20,000 | 0 |
| `d9e1b51b` | `silver_leads` | `valid_id` | 4,050 | 0 |
| `d9e1b51b` | `silver_opportunities_cdc` | `non_negative_amount` | 15,000 | 0 |
| `d9e1b51b` | `silver_opportunities_cdc` | `valid_close_date` | 15,000 | 0 |
| `d9e1b51b` | `silver_opportunities_cdc` | `valid_id` | 15,000 | 0 |
| `d9e1b51b` | `silver_opportunity_history` | `valid_id` | 66,796 | 0 |
| `d9e1b51b` | `silver_tickets` | `valid_id` | 8,100 | 0 |
| `d9e1b51b` | `silver_transcripts` | `valid_id` | 640 | 0 |
| `d9e1b51b` | `silver_usage_daily` | `valid_id` | 264,537 | 0 |
| `d9e1b51b` | `silver_users` | `valid_id` | 668 | 0 |
| `fbc044b3` | `silver_accounts` | `valid_id` | 5,000 | 0 |
| `fbc044b3` | `silver_activities` | `valid_id` | 60,978 | 0 |
| `fbc044b3` | `silver_contacts` | `valid_id` | 20,000 | 0 |
| `fbc044b3` | `silver_leads` | `valid_id` | 4,050 | 0 |
| `fbc044b3` | `silver_opportunity_history` | `valid_id` | 66,796 | 0 |
| `fbc044b3` | `silver_tickets` | `valid_id` | 8,100 | 0 |
| `fbc044b3` | `silver_transcripts` | `valid_id` | 640 | 0 |
| `fbc044b3` | `silver_usage_daily` | `valid_id` | 264,537 | 0 |
| `fbc044b3` | `silver_users` | `valid_id` | 668 | 0 |

`valid_id` and `valid_close_date` are `ON VIOLATION DROP ROW`; `non_negative_amount` is warn-only (`EXPECT`).
No row failed any expectation. The streaming CDC flow reports metrics only in the update that processed new
bronze rows; MV metrics appear on each recompute.

## Spot checks
Personas (from `gold_user_hierarchy`, looked up by name, not hard-coded Ids):
```
{"name": "Jordan Rivera", "role": "Seller", "manager_name": "Morgan Lee", "rvp_name": "Kelly Castaneda"}
{"name": "Morgan Lee", "role": "Manager", "manager_name": "Kelly Castaneda", "rvp_name": "Kelly Castaneda"}
{"name": "Taylor Empty", "role": "Seller", "manager_name": "Kristen Crawford", "rvp_name": "Kelly Castaneda"}
```
Jordan Rivera open pipeline by stage (`gold_opportunity_pipeline`, 25 open):
```
{"stage": "Demo", "n": "8", "acv": "790700.0"}
{"stage": "Discovery", "n": "4", "acv": "105500.0"}
{"stage": "Negotiation", "n": "4", "acv": "715900.0"}
{"stage": "Proposal", "n": "7", "acv": "362600.0"}
{"stage": "Qualification", "n": "2", "acv": "211600.0"}
```
Current-quarter KPIs (`gold_seller_kpis`, quota = annual Quota__c / 4):
```
{"owner_name": "Jordan Rivera", "fiscal_quarter": "FY27Q4", "quota": "300000.0", "closed_won_acv": "146400.0", "attainment_pct": "48.8", "open_pipeline_acv": "1901000.0", "commit_acv": "715900.0", "coverage_ratio": "12.38"}
{"owner_name": "Taylor Empty", "fiscal_quarter": "FY27Q4", "quota": "225000.0", "closed_won_acv": "0.0", "attainment_pct": "0.0", "open_pipeline_acv": "0.0", "commit_acv": "0.0", "coverage_ratio": "0.0"}
```
Masked contacts (`gold_contacts_masked`):
```
{"email": "f***@solisconstruction.com", "phone": "***-***-0163"}
{"email": "d***@solisconstruction.com", "phone": "***-***-0137"}
{"email": "s***@solisconstruction.com", "phone": "***-***-0199"}
```

## Tests
`.venv/bin/pytest tests/integration/test_pipeline.py -m integration -v`
```
tests/integration/test_pipeline.py::test_gold_tables_exist PASSED        [ 11%]
tests/integration/test_pipeline.py::test_gold_tables_have_cdf_and_comments PASSED [ 22%]
tests/integration/test_pipeline.py::test_silver_opps_unique_ids PASSED   [ 33%]
tests/integration/test_pipeline.py::test_jordan_open_pipeline PASSED     [ 44%]
tests/integration/test_pipeline.py::test_taylor_empty_has_no_open_pipeline PASSED [ 55%]
tests/integration/test_pipeline.py::test_fiscal_quarter_and_hierarchy PASSED [ 66%]
tests/integration/test_pipeline.py::test_contacts_masked_has_no_raw_email PASSED [ 77%]
tests/integration/test_pipeline.py::test_no_ground_truth_ingested PASSED [ 88%]
tests/integration/test_pipeline.py::test_expectations_recorded PASSED    [100%]
============================== 9 passed in 22.14s ==============================
```
