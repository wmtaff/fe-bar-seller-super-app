# Task 2 evidence: synthetic data generator (`generate_data`), dataset v3

Date: 2026-11-17/18. Profile `fevm-serverless-stable-s1omq8`, target `dev`, job `seller_superapp_daily`
(job id 94481485733041), serverless compute, environment client 4 + `faker==40.54.0`. Seed 42, as-of 2026-11-16.

**Output root: `/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v3/`.** The job parameter
`dataset_version` now defaults to `v3` (ruling R12: Jordan's annual quota is 2,000,000, 7 of his 25 open opps close in
FY28Q1, and seller quotas are calibrated to each territory's current-quarter position). The v1 files at the volume root and
the v2 files under `raw/v2/` stay in place and are not read (the permission system blocks deleting them).

## Run 1: `mode=init` (default params)
Run: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/359066797170196?o=7474646802937769

Task `generate_data` SUCCESS. The run as a whole FAILED because the downstream task `pipeline_refresh` failed.
Its pipeline still had Auto Loader checkpoints from `raw/v2`, and inferring the `batch=` partition on the new
path failed with `CF_PARTITON_INFERENCE_ERROR`. Fixed by setting `partitionColumns => 'batch'` in bronze and running
a full refresh; see evidence/02_pipeline.md. The batch 0 manifest that the generator wrote:
```
{
  "batch": 0,
  "counts": {
    "Account": 5000,
    "Contact": 20000,
    "Event": 18289,
    "Lead": 4000,
    "Opportunity": 15000,
    "OpportunityHistory": 66646,
    "Task": 41689,
    "User": 668,
    "UserRole": 24,
    "meet_transcripts": 600,
    "product_usage": 261630,
    "support_tickets": 8000,
    "truth": 19600
  },
  "data_timestamp": "2026-11-16T12:00:00.000Z",
  "landed_at": "2026-11-17T23:04:52Z",
  "mode": "init",
  "seed": 42
}
```

## Run 2: `mode=increment batch=1`
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/130616094417601?o=7474646802937769

2026-11-18 07:57:53 "seller_superapp_daily" RUNNING
2026-11-18 08:00:52 "seller_superapp_daily" TERMINATED SUCCESS
{
  "mode": "increment",
  "batch": 1,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v3",
  "files": 49,
  "generate_seconds": 6.3,
  "total_seconds": 11.5,
  "counts": {
    "User": 0,
    "UserRole": 0,
    "Account": 0,
    "Contact": 0,
    "Opportunity": 150,
    "OpportunityHistory": 150,
    "Lead": 50,
    "Task": 687,
    "Event": 313,
    "meet_transcripts": 40,
    "product_usage": 2907,
    "support_tickets": 100,
    "truth": 110
  }
}
```

## Run 3: `mode=increment batch=1` again (idempotent skip)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/391083867063867?o=7474646802937769

2026-11-18 08:01:07 "seller_superapp_daily" RUNNING
2026-11-18 08:04:38 "seller_superapp_daily" TERMINATED SUCCESS
batch 0001 already present at /Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v3; skipping
{
  "batch": 1,
  "counts": {
    "Account": 0,
    "Contact": 0,
    "Event": 313,
    "Lead": 50,
    "Opportunity": 150,
    "OpportunityHistory": 150,
    "Task": 687,
    "User": 0,
    "UserRole": 0,
    "meet_transcripts": 40,
    "product_usage": 2907,
    "support_tickets": 100,
    "truth": 110
  },
  "data_timestamp": "2026-11-16T13:00:00.000Z",
  "landed_at": "2026-11-18T16:58:24Z",
  "mode": "increment",
  "seed": 42
}
```
(Both increment runs ended TERMINATED SUCCESS, including `pipeline_refresh`.)

## Byte-identical: volume `v3/` vs local run
Local: `generate('init', /tmp/t3/g3, 42, 0)`, then `generate('increment', /tmp/t3/g3, 42, 1)`. Each volume file was
downloaded with the SDK and its sha256 compared with the local file. `_manifest/` files hold the wall-clock
`landed_at`, so they are excluded.
```
data files in volume v3: 660; local: 660; sha256 identical: 660; different/missing: 0
   6,432,219  32f3c816fd9677be  =  _eval/truth/batch=0000/part-0.json
      44,228  d5cbab2eae3a2b5f  =  _eval/truth/batch=0001/part-0.json
         457  a8b0a4bdeb201874  (manifest, wall-clock)  _manifest/batch=0000.json
         436  1d0ec086cc2b49d8  (manifest, wall-clock)  _manifest/batch=0001.json
  19,262,075  40c56aeb4e824c3a  =  product_usage/batch=0000/part-0.csv
     214,934  e7f42740987f9386  =  product_usage/batch=0001/part-0.csv
   2,906,753  8ffcc159186325f1  =  salesforce/Account/batch=0000/part-0.json
   8,732,500  973a05ef69602fe3  =  salesforce/Contact/batch=0000/part-0.json
   8,518,457  b0dba0d821d7d10c  =  salesforce/Event/batch=0000/part-0.json
     146,314  8a78ddf42680cbd8  =  salesforce/Event/batch=0001/part-0.json
   2,743,421  dc6a842909dabb43  =  salesforce/Lead/batch=0000/part-0.json
      34,417  6691eea1cf9e7a8d  =  salesforce/Lead/batch=0001/part-0.json
   9,179,816  e193f0feff2d2188  =  salesforce/Opportunity/batch=0000/part-0.json
      92,109  514691e1a65feacc  =  salesforce/Opportunity/batch=0001/part-0.json
  16,830,362  b5cc644a4c291fce  =  salesforce/OpportunityHistory/batch=0000/part-0.json
      37,732  8c0c0e3643c08b8e  =  salesforce/OpportunityHistory/batch=0001/part-0.json
  19,446,662  3fd8ead8bdc10d86  =  salesforce/Task/batch=0000/part-0.json
     320,098  48082240c7bbfe17  =  salesforce/Task/batch=0001/part-0.json
     319,968  10fde59f4a94655d  =  salesforce/User/batch=0000/part-0.json
       4,253  d5851c00cd84bd28  =  salesforce/UserRole/batch=0000/part-0.json
   3,095,080  55dee1c6775936c2  =  support_tickets/batch=0000/part-0.json
      37,206  6272dd0a7c55b433  =  support_tickets/batch=0001/part-0.json
   2,663,607                    =  meet_transcripts/batch=0000/*.json  (600 files, all identical)
     179,033                    =  meet_transcripts/batch=0001/*.json  (40 files, all identical)
total files: 662; total bytes: 101,242,137
```

## Unit tests
`.venv/bin/pytest tests/unit -q`: 27 passed. New in R12: `test_jordan_kpis_plausible` computes the FY27Q4 KPIs
from the raw files (init + increment 1). It checks Jordan's quota (2,000,000 annual), coverage in [3, 4],
attainment in [25%, 40%], 6-8 of his open opps closing in FY28Q1, and that at least 80% of sellers with
current-quarter pipeline have coverage in [1.5, 5]. Measured values: Jordan coverage 3.50, attainment 29.3%,
7 opps in FY28Q1; org 533/570 = 93.5% in band. All Task 2 persona tests still pass (≥25 open opps, ≥70% in the
current quarter (18/25), ≥8 transcribed, ≥2 quote opps expiring this quarter, Morgan + 8, Taylor 0 open).
