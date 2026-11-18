# Task 3 evidence: Lakeflow Spark Declarative Pipeline (bronze -> silver -> gold), dataset v4

Date: 2026-11-18 (fix round 2, ruling R13). Profile `fevm-serverless-stable-s1omq8`, target `dev`. Pipeline
`seller_superapp_pipeline` (id `256cf7ee-6a09-4ae7-ae80-f7492987f221`), serverless, SQL
(`src/pipeline/{bronze,silver,gold}.sql`), catalog `serverless_stable_s1omq8_catalog`, schema `seller_superapp`.
Source: `raw/v4/` only (`raw_root` pipeline configuration; init batch 0 + increment batch 1). `_eval/` and
`_manifest/` are never read. All 15,150 bronze opportunity rows have `_source_file` under `/raw/v4/`. The data as-of
time is the latest opportunity LastModifiedDate, 2026-11-16T13:00Z (ruling R7). The current fiscal quarter is FY27Q4.

**Final update: `3c2f2255-0131-4584-ac3b-f720c4e188ac` (full refresh, COMPLETED).**
https://fevm-serverless-stable-s1omq8.cloud.databricks.com/#joblist/pipelines/256cf7ee-6a09-4ae7-ae80-f7492987f221/updates/3c2f2255-0131-4584-ac3b-f720c4e188ac

## Update history (event log, 2026-11-18)
| update_id | finished | state | what |
|---|---|---|---|
| `06176a0b-a0dc-4763-9ed7-294846701e5c` | 2026-11-18T17:00:16.343Z | COMPLETED | v3 increment (fix round 1) |
| `2e04b8a7-12d3-415d-99da-0429ecde57d9` | 2026-11-18T17:04:18.656Z | COMPLETED | v3 increment again (fix round 1) |
| `e6a3973f-01b6-4f41-b431-5b4b15432541` | 2026-11-18T17:07:41.280Z | COMPLETED | v3 final full refresh (fix round 1) |
| `248108b1-5f85-4635-b25a-0c3dfce7ad70` | 2026-11-18T17:40:25.144Z | FAILED | v4 init job `pipeline_refresh` attempt: `LOCATION_OVERLAP` on the old v3 Auto Loader checkpoints |
| `4aca60a4-7ad0-4f02-81a7-d381188d8444` | 2026-11-18T17:41:40.794Z | FAILED | v4 init job `pipeline_refresh` attempt: `LOCATION_OVERLAP` on the old v3 Auto Loader checkpoints |
| `cbf8a978-1813-42b2-aff9-db916986e439` | 2026-11-18T17:43:13.567Z | FAILED | v4 init job `pipeline_refresh` attempt: `LOCATION_OVERLAP` on the old v3 Auto Loader checkpoints |
| `8fe02812-edfc-4512-9b6d-3336b2df62f4` | 2026-11-18T17:45:27.301Z | FAILED | v4 init job `pipeline_refresh` attempt: `LOCATION_OVERLAP` on the old v3 Auto Loader checkpoints |
| `c6d3f149-a78b-4fae-b0d6-d04b028d365b` | 2026-11-18T17:47:54.929Z | CANCELED | v4 init job run retry, cancelled |
| `89cf7ed9-25db-4337-a379-8588fe02b714` | 2026-11-18T17:50:14.205Z | COMPLETED | **v4 full refresh** (v4 init data) |
| `68dc4c94-2041-4f8e-aa5e-d1692c98407b` | 2026-11-18T17:52:52.116Z | COMPLETED | v4 incremental `pipeline_refresh` (job increment run) |
| `bca06a89-0106-4b24-b881-12c48a6c5735` | 2026-11-18T17:55:02.399Z | COMPLETED | v4 incremental `pipeline_refresh` (job increment run) |
| `3c2f2255-0131-4584-ac3b-f720c4e188ac` | 2026-11-18T17:57:43.178Z | COMPLETED | **v4 full refresh, final** (init + batch 1) |

Switching `raw_root` to a new dataset version needs a full refresh: the first incremental refresh fails on the
streaming checkpoints of the old path. The v4 init job's `pipeline_refresh` retries were cancelled, a full refresh
ran, and the increment jobs (runs 360677024866427 and 645394654606111) then succeeded with incremental refreshes.
The final full refresh came last.

## Row counts (after the final full refresh)
| table | rows |
|---|---|
| `bronze_account` | 5,000 |
| `bronze_contact` | 20,000 |
| `bronze_event` | 18,626 |
| `bronze_lead` | 4,050 |
| `bronze_meet_transcripts` | 640 |
| `bronze_opportunity` | 15,150 |
| `bronze_opportunity_history` | 66,556 |
| `bronze_product_usage` | 275,184 |
| `bronze_support_tickets` | 8,100 |
| `bronze_task` | 42,323 |
| `bronze_user` | 668 |
| `bronze_user_role` | 24 |
| `silver_accounts` | 5,000 |
| `silver_activities` | 60,949 |
| `silver_contacts` | 20,000 |
| `silver_leads` | 4,050 |
| `silver_opportunities` | 15,000 |
| `silver_opportunity_history` | 66,556 |
| `silver_tickets` | 8,100 |
| `silver_transcripts` | 640 |
| `silver_usage_daily` | 275,184 |
| `silver_users` | 668 |
| `gold_account_360` | 5,000 |
| `gold_contacts_masked` | 20,000 |
| `gold_opportunity_pipeline` | 15,000 |
| `gold_seller_kpis` | 6,600 |
| `gold_user_hierarchy` | 668 |

`bronze_opportunity` has 15,150 rows: 15,000 from init plus 150 re-emitted in batch 1. `silver_opportunities` has 15,000
unique Ids.

## Expectations (event log, final update `3c2f2255`)
| dataset | expectation | passed | failed |
|---|---|---|---|
| `silver_accounts` | `valid_id` | 5,000 | 0 |
| `silver_activities` | `valid_id` | 60,949 | 0 |
| `silver_contacts` | `valid_id` | 20,000 | 0 |
| `silver_leads` | `valid_id` | 4,050 | 0 |
| `silver_opportunities_cdc` | `non_negative_amount` | 15,000 | 0 |
| `silver_opportunities_cdc` | `valid_close_date` | 15,000 | 0 |
| `silver_opportunities_cdc` | `valid_id` | 15,000 | 0 |
| `silver_opportunity_history` | `valid_id` | 66,556 | 0 |
| `silver_tickets` | `valid_id` | 8,100 | 0 |
| `silver_transcripts` | `valid_id` | 640 | 0 |
| `silver_usage_daily` | `valid_id` | 275,184 | 0 |
| `silver_users` | `valid_id` | 668 | 0 |

No row failed any expectation (`valid_id` and `valid_close_date` drop violating rows, `non_negative_amount` only warns).

## Seller KPI sanity (ruling R13, from `gold_seller_kpis`)
Annual quota by segment, excluding the pinned personas. The clamp is 0.6-1.8 x SEGMENT_QUOTA
(SMB 600k, Mid-Market 1.1M, Enterprise 2.0M):
```
{"segment": "Enterprise", "sellers": "142", "mn": "1200000.0", "p50": "1945000.0", "mx": "3600000.0"}
{"segment": "Mid-Market", "sellers": "236", "mn": "660000.0", "p50": "1095000.0", "mx": "1980000.0"}
{"segment": "SMB", "sellers": "220", "mn": "360000.0", "p50": "460000.0", "mx": "1080000.0"}
```
Past-quarter attainment % by quarter (overall p90 134.2%, max 379.1%):
```
{"fiscal_quarter": "FY25Q4", "p50": "49.5", "p90": "106.8", "mx": "379.1"}
{"fiscal_quarter": "FY26Q1", "p50": "59.5", "p90": "122.2", "mx": "284.2"}
{"fiscal_quarter": "FY26Q2", "p50": "64.1", "p90": "127.8", "mx": "286.0"}
{"fiscal_quarter": "FY26Q3", "p50": "64.8", "p90": "133.4", "mx": "321.1"}
{"fiscal_quarter": "FY26Q4", "p50": "71.9", "p90": "128.2", "mx": "233.2"}
{"fiscal_quarter": "FY27Q1", "p50": "70.1", "p90": "124.9", "mx": "255.8"}
{"fiscal_quarter": "FY27Q2", "p50": "77.7", "p90": "140.3", "mx": "249.6"}
{"fiscal_quarter": "FY27Q3", "p50": "94.1", "p90": "169.7", "mx": "268.0"}
```
Morgan Lee's team annual quotas (max/min = 2.53):
```
{"owner_name": "Robyn Simmons", "annual_quota": "790000.0"}
{"owner_name": "John Smith", "annual_quota": "820000.0"}
{"owner_name": "Tracy Salazar", "annual_quota": "840000.0"}
{"owner_name": "William Andrade", "annual_quota": "940000.0"}
{"owner_name": "Tammy Clements", "annual_quota": "960000.0"}
{"owner_name": "Timothy Ibarra", "annual_quota": "980000.0"}
{"owner_name": "Rachel Lopez", "annual_quota": "980000.0"}
{"owner_name": "Jordan Rivera", "annual_quota": "2000000.0"}
```
FY27Q4 coverage, for sellers with open pipeline. **The measured in-band share is 0.524** (the requirement is at least 0.5):
```
{"sellers_with_open": "593", "in_band": "311", "share": "0.524", "p": "[\"0.791\",\"2.2199999999999998\",\"5.18\"]"}
```
Personas, current quarter:
```
{"owner_name": "Jordan Rivera", "fiscal_quarter": "FY27Q4", "quota": "500000.0", "closed_won_acv": "176700.0", "attainment_pct": "35.3", "open_pipeline_acv": "1131600.0", "commit_acv": "401100.0", "coverage_ratio": "3.5"}
{"owner_name": "Taylor Empty", "fiscal_quarter": "FY27Q4", "quota": "225000.0", "closed_won_acv": "0.0", "attainment_pct": "0.0", "open_pipeline_acv": "0.0", "commit_acv": "0.0", "coverage_ratio": "0.0"}
{"fiscal_quarter": "FY27Q4", "n": "18", "acv": "1131600.0"}
{"fiscal_quarter": "FY28Q1", "n": "7", "acv": "826100.0"}
```
Hierarchy (`gold_user_hierarchy`):
```
{"name": "Jordan Rivera", "role": "Seller", "manager_name": "Morgan Lee", "rvp_name": "Kelly Castaneda", "annual_quota": "2000000.0"}
{"name": "Morgan Lee", "role": "Manager", "manager_name": "Kelly Castaneda", "rvp_name": "Kelly Castaneda", "annual_quota": "8310000.0"}
{"name": "Taylor Empty", "role": "Seller", "manager_name": "Kristen Crawford", "rvp_name": "Kelly Castaneda", "annual_quota": "900000.0"}
```
Masked contacts (`gold_contacts_masked`):
```
{"email": "f***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0163"}
{"email": "d***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0137"}
{"email": "s***@solisconstruction.com", "email_domain": "solisconstruction.com", "phone": "***-***-0199"}
```

## Tests
`.venv/bin/pytest tests/integration/test_pipeline.py -m integration -v -s`
```
tests/integration/test_pipeline.py::test_gold_tables_exist PASSED
tests/integration/test_pipeline.py::test_gold_tables_have_cdf_and_comments PASSED
tests/integration/test_pipeline.py::test_silver_opps_unique_ids PASSED
tests/integration/test_pipeline.py::test_jordan_open_pipeline PASSED
tests/integration/test_pipeline.py::test_taylor_empty_has_no_open_pipeline PASSED
tests/integration/test_pipeline.py::test_fiscal_quarter_and_hierarchy PASSED
tests/integration/test_pipeline.py::test_contacts_masked_has_no_raw_email PASSED
tests/integration/test_pipeline.py::test_no_ground_truth_ingested PASSED
tests/integration/test_pipeline.py::test_expectations_recorded PASSED
tests/integration/test_pipeline.py::test_fiscal_quarter_literal_cases PASSED
tests/integration/test_pipeline.py::test_jordan_kpis_plausible PASSED
tests/integration/test_pipeline.py::test_seller_kpis_sanity past-quarter attainment p90=134.2% max=379.1%
org coverage in-band share=0.524 (311/593)
PASSED
======================== 12 passed in 87.38s (0:01:27) =========================
```
`.venv/bin/pytest tests/unit -q`: 28 passed.
