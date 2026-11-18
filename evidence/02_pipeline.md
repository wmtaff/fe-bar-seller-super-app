# Task 3 evidence: Lakeflow Spark Declarative Pipeline (bronze -> silver -> gold), dataset v3

Date: 2026-11-18 (fix round 1, ruling R12). Profile `fevm-serverless-stable-s1omq8`, target `dev`. Pipeline
`seller_superapp_pipeline` (id `256cf7ee-6a09-4ae7-ae80-f7492987f221`), serverless, SQL
(`src/pipeline/{bronze,silver,gold}.sql`), catalog `serverless_stable_s1omq8_catalog`, schema `seller_superapp`.
Source: `raw/v3/` only (`raw_root` pipeline configuration; init batch 0 + increment batch 1). `_eval/` and
`_manifest/` are never read. All 15,150 bronze opportunity rows have `_source_file` under `/raw/v3/`. The data
as-of time is the latest opportunity LastModifiedDate, 2026-11-16T13:00Z (ruling R7). The current fiscal quarter is FY27Q4.

**Final update: `e6a3973f-01b6-4f41-b431-5b4b15432541` (full refresh, COMPLETED).**
https://fevm-serverless-stable-s1omq8.cloud.databricks.com/#joblist/pipelines/256cf7ee-6a09-4ae7-ae80-f7492987f221/updates/e6a3973f-01b6-4f41-b431-5b4b15432541

## Update history (event log)
| update_id | finished | state | what |
|---|---|---|---|
| `d9e1b51b-30c9-4c43-a348-bf0c203ea723` | 2026-11-17T22:44:27.920Z | COMPLETED | v2: first run (Task 3 initial) |
| `fbc044b3-5af2-498f-b13b-9ff028cd2222` | 2026-11-17T22:47:55.565Z | COMPLETED | v2: coverage past-quarter tweak |
| `2bb8ce1a-6f04-4cb9-ba74-17ccd484041d` | 2026-11-17T22:49:50.332Z | COMPLETED | v2: job run 595528639153615 pipeline_refresh |
| `eab2dcac-3a82-4800-8b93-20152ea36177` | 2026-11-17T23:08:13.784Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `8ef7a65a-91bc-4f5b-81e6-6e00e3120d33` | 2026-11-17T23:09:34.355Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `8431fa95-c845-4780-922d-4fec775d1fb6` | 2026-11-17T23:11:12.969Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `b3429640-24b6-47d9-8b98-93420b3d806f` | 2026-11-17T23:13:32.544Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `2b73f66b-3e90-4936-93a7-6e943d509a56` | 2026-11-17T23:17:10.494Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `f30f2135-fbca-4ba2-9f2a-6f4f4204c5cd` | 2026-11-17T23:23:31.602Z | FAILED | v3 switch: `CF_PARTITON_INFERENCE_ERROR` (old v2 checkpoints); fixed with `partitionColumns => 'batch'` + full refresh |
| `4bee1ab3-3d30-482b-90d9-4b6ae5607f5a` | 2026-11-17T23:28:36.787Z | COMPLETED | **v3 full refresh** after partitionColumns fix (v3 init data) |
| `06176a0b-a0dc-4763-9ed7-294846701e5c` | 2026-11-18T17:00:16.343Z | COMPLETED | v3 incremental `pipeline_refresh` (job increment run) |
| `2e04b8a7-12d3-415d-99da-0429ecde57d9` | 2026-11-18T17:04:18.656Z | COMPLETED | v3 incremental `pipeline_refresh` (job increment run) |
| `e6a3973f-01b6-4f41-b431-5b4b15432541` | 2026-11-18T17:07:41.280Z | COMPLETED | **v3 full refresh, final** (init + batch 1) |

The FAILED updates come from the first v3 job run and its retries (the `pipeline_refresh` task ran before the fix).
The v3 job runs for increment batch 1 (130616094417601) and batch 1 again (391083867063867) ended TERMINATED SUCCESS,
with incremental `pipeline_refresh`. Then the final full refresh ran.

## Row counts (after the final full refresh)
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

`bronze_opportunity` has 15,150 rows: 15,000 from init plus 150 re-emitted in batch 1. `silver_opportunities` has 15,000
unique Ids, because AUTO CDC SCD1 keeps the newest LastModifiedDate.

## Expectations (event log, final update `e6a3973f`)
| dataset | expectation | passed | failed |
|---|---|---|---|
| `silver_accounts` | `valid_id` | 5,000 | 0 |
| `silver_activities` | `valid_id` | 60,978 | 0 |
| `silver_contacts` | `valid_id` | 20,000 | 0 |
| `silver_leads` | `valid_id` | 4,050 | 0 |
| `silver_opportunities_cdc` | `non_negative_amount` | 15,000 | 0 |
| `silver_opportunities_cdc` | `valid_close_date` | 15,000 | 0 |
| `silver_opportunities_cdc` | `valid_id` | 15,000 | 0 |
| `silver_opportunity_history` | `valid_id` | 66,796 | 0 |
| `silver_tickets` | `valid_id` | 8,100 | 0 |
| `silver_transcripts` | `valid_id` | 640 | 0 |
| `silver_usage_daily` | `valid_id` | 264,537 | 0 |
| `silver_users` | `valid_id` | 668 | 0 |

`valid_id` and `valid_close_date` drop violating rows (`ON VIOLATION DROP ROW`). `non_negative_amount` only warns (`EXPECT`).
No row failed any expectation.

## KPIs (ruling R12)
Current quarter (`gold_seller_kpis`; quota = annual Quota__c / 4):
```
{"owner_name": "Taylor Empty", "fiscal_quarter": "FY27Q4", "quota": "225000.0", "closed_won_acv": "0.0", "attainment_pct": "0.0", "open_pipeline_acv": "0.0", "commit_acv": "0.0", "coverage_ratio": "0.0"}
{"owner_name": "Jordan Rivera", "fiscal_quarter": "FY27Q4", "quota": "500000.0", "closed_won_acv": "146400.0", "attainment_pct": "29.3", "open_pipeline_acv": "1237100.0", "commit_acv": "494500.0", "coverage_ratio": "3.5"}
```
Org-wide, for sellers with FY27Q4 open pipeline:
```
{"sellers_with_open": "570", "in_band": "533", "share": "0.935", "p": "[\"1.955\",\"2.66\",\"3.37\"]"}
```
Jordan Rivera's open opportunities by fiscal quarter:
```
{"fiscal_quarter": "FY27Q4", "n": "18", "acv": "1237100.0"}
{"fiscal_quarter": "FY28Q1", "n": "7", "acv": "949200.0"}
```
Personas (`gold_user_hierarchy`, looked up by name):
```
{"name": "Jordan Rivera", "role": "Seller", "manager_name": "Morgan Lee", "rvp_name": "Kelly Castaneda", "annual_quota": "2000000.0"}
{"name": "Morgan Lee", "role": "Manager", "manager_name": "Kelly Castaneda", "rvp_name": "Kelly Castaneda", "annual_quota": "6100000.0"}
{"name": "Taylor Empty", "role": "Seller", "manager_name": "Kristen Crawford", "rvp_name": "Kelly Castaneda", "annual_quota": "900000.0"}
```
Masked contacts (`gold_contacts_masked`):
```
{"email": "f***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0163"}
{"email": "d***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0137"}
{"email": "s***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0199"}
```

## Tests
`.venv/bin/pytest tests/integration/test_pipeline.py -m integration -v`
```
tests/integration/test_pipeline.py::test_gold_tables_exist PASSED        [  9%]
tests/integration/test_pipeline.py::test_gold_tables_have_cdf_and_comments PASSED [ 18%]
tests/integration/test_pipeline.py::test_silver_opps_unique_ids PASSED   [ 27%]
tests/integration/test_pipeline.py::test_jordan_open_pipeline PASSED     [ 36%]
tests/integration/test_pipeline.py::test_taylor_empty_has_no_open_pipeline PASSED [ 45%]
tests/integration/test_pipeline.py::test_fiscal_quarter_and_hierarchy PASSED [ 54%]
tests/integration/test_pipeline.py::test_contacts_masked_has_no_raw_email PASSED [ 63%]
tests/integration/test_pipeline.py::test_no_ground_truth_ingested PASSED [ 72%]
tests/integration/test_pipeline.py::test_expectations_recorded PASSED    [ 81%]
tests/integration/test_pipeline.py::test_fiscal_quarter_literal_cases PASSED [ 90%]
tests/integration/test_pipeline.py::test_jordan_kpis_plausible PASSED    [100%]
============================= 11 passed in 45.13s ==============================
```
`.venv/bin/pytest tests/unit -q`: 27 passed.
