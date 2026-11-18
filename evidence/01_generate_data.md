# Task 2 evidence: synthetic data generator (`generate_data`), dataset v4

Date: 2026-11-18. Profile `fevm-serverless-stable-s1omq8`, target `dev`, job `seller_superapp_daily`
(job id 94481485733041), serverless compute, environment client 4 + `faker==40.54.0`. Seed 42, as-of 2026-11-16.

**Output root: `/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v4/`.** The job parameter
`dataset_version` now defaults to `v4` (ruling R13). In v4, seller quotas come from trailing closed-won history,
clamped per segment, and the deal economics per segment were rebalanced (see the Task 3 report). The v1 files at
the volume root and the v2 and v3 files stay in place and are not read (the permission system blocks deleting them).

## Run 1: `mode=init` (default params)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/328392860805018?o=7474646802937769

2026-11-18 08:36:33 "seller_superapp_daily" RUNNING
2026-11-18 08:48:02 "seller_superapp_daily" TERMINATED CANCELED Run cancelled by user
```
Task `generate_data` TERMINATED SUCCESS. Its output (task logs):
```
{
  "mode": "init",
  "batch": 0,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v4",
  "files": 613,
  "generate_seconds": 15.9,
  "total_seconds": 70.0,
  "counts": {
    "User": 668,
    "UserRole": 24,
    "Account": 5000,
    "Contact": 20000,
    "Opportunity": 15000,
    "OpportunityHistory": 66406,
    "Lead": 4000,
    "Task": 41636,
    "Event": 18313,
    "meet_transcripts": 600,
    "product_usage": 272160,
    "support_tickets": 8000,
    "truth": 19600
  }
}
```
I cancelled the job run while `pipeline_refresh` was retrying. The first incremental refresh after a
`dataset_version` switch fails on the old Auto Loader checkpoints (`LOCATION_OVERLAP`), so the pipeline was
fully refreshed instead (update `89cf7ed9`); see evidence/02_pipeline.md.

## Run 2: `mode=increment batch=1`
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/360677024866427?o=7474646802937769

2026-11-18 08:50:30 "seller_superapp_daily" RUNNING
2026-11-18 08:53:08 "seller_superapp_daily" TERMINATED SUCCESS
{
  "mode": "increment",
  "batch": 1,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v4",
  "files": 49,
  "generate_seconds": 8.1,
  "total_seconds": 13.6,
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
    "product_usage": 3024,
    "support_tickets": 100,
    "truth": 111
  }
}
```

## Run 3: `mode=increment batch=1` again (idempotent skip)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/645394654606111?o=7474646802937769

2026-11-18 08:53:24 "seller_superapp_daily" RUNNING
2026-11-18 08:55:18 "seller_superapp_daily" TERMINATED SUCCESS
batch 0001 already present at /Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v4; skipping
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
    "product_usage": 3024,
    "support_tickets": 100,
    "truth": 111
  },
  "data_timestamp": "2026-11-16T13:00:00.000Z",
  "landed_at": "2026-11-18T17:50:58Z",
  "mode": "increment",
  "seed": 42
}
```

## Byte-identical: volume `v4/` vs local run
Local: `generate('init', /tmp/t3/g4, 42, 0)`, then `generate('increment', /tmp/t3/g4, 42, 1)`. Each volume file was
downloaded with the SDK and its sha256 compared with the local file. `_manifest/` files hold the wall-clock
`landed_at`, so they are excluded.
```
data files in volume v4: 660; local: 660; sha256 identical: 660; different/missing: 0
   6,438,155  b2d4a3f6ec290b79  =  _eval/truth/batch=0000/part-0.json
      44,602  c5fa2001835f5aa3  =  _eval/truth/batch=0001/part-0.json
         457  4ce9d01f1d132076  (manifest, wall-clock)  _manifest/batch=0000.json
         436  84dc358f6ab56ad3  (manifest, wall-clock)  _manifest/batch=0001.json
  19,942,324  0f9f983d055b06f3  =  product_usage/batch=0000/part-0.csv
     222,590  44713ad2ac2ea7d5  =  product_usage/batch=0001/part-0.csv
   2,878,689  9fe58b2cae09aa9e  =  salesforce/Account/batch=0000/part-0.json
   8,732,500  973a05ef69602fe3  =  salesforce/Contact/batch=0000/part-0.json
   8,532,811  3621cccf70b9cef4  =  salesforce/Event/batch=0000/part-0.json
     146,328  9e75bf61fdb568bb  =  salesforce/Event/batch=0001/part-0.json
   2,743,421  dc6a842909dabb43  =  salesforce/Lead/batch=0000/part-0.json
      34,417  6691eea1cf9e7a8d  =  salesforce/Lead/batch=0001/part-0.json
   9,027,708  a16ef69f07083eb7  =  salesforce/Opportunity/batch=0000/part-0.json
      90,443  62506d68cfacf688  =  salesforce/Opportunity/batch=0001/part-0.json
  16,794,655  fc08594ca69cec26  =  salesforce/OpportunityHistory/batch=0000/part-0.json
      37,742  5c208a8c426eb5d7  =  salesforce/OpportunityHistory/batch=0001/part-0.json
  19,422,901  8523ee079cb981ad  =  salesforce/Task/batch=0000/part-0.json
     320,098  b972d9d32b022a4a  =  salesforce/Task/batch=0001/part-0.json
     320,220  c4410964cda46c97  =  salesforce/User/batch=0000/part-0.json
       4,253  d5851c00cd84bd28  =  salesforce/UserRole/batch=0000/part-0.json
   3,097,164  961e8b5f3457b2b8  =  support_tickets/batch=0000/part-0.json
      37,125  eac0a378e7e43ba2  =  support_tickets/batch=0001/part-0.json
   2,642,761                    =  meet_transcripts/batch=0000/*.json  (600 files, all identical)
     176,334                    =  meet_transcripts/batch=0001/*.json  (40 files, all identical)
total files: 662; total bytes: 101,688,134
```

## Unit tests
`.venv/bin/pytest tests/unit -q`: 28 passed. These include:
- `test_jordan_kpis_plausible`: Jordan coverage 3.50, attainment 35.3%, 7 opps in FY28Q1.
- `test_quota_sanity` (computed from raw):
  - every non-persona quota is within the segment clamp;
  - past-quarter attainment p90 = 1.34x and max = 3.79x;
  - Morgan's team quota max/min = 2.53;
  - org coverage in-band share is **0.524** (311/593 sellers with FY27Q4 pipeline at 1.5-5x).

All Task 2 persona tests still pass:
- Jordan has 25 open opps, 18 of them in the current quarter.
- All 10 transcribed opps and all 3 quote opps are in FY27Q4.
- Morgan manages Jordan + 7 others.
- Taylor has 0 open opps.
