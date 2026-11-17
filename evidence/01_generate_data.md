# Task 2 evidence: synthetic data generator (`generate_data`), dataset v2

Date: 2026-11-17. Profile `fevm-serverless-stable-s1omq8`, target `dev`, job `seller_superapp_daily`
(job id 94481485733041), serverless compute, environment client 4 + `faker==40.54.0`. Seed 42, as-of 2026-11-16.

**Output root: `/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v2/`.** Job parameter
`dataset_version` defaults to `v2` (ruling R10). Files from the first generator version (fix round 0) are
still at the volume root (`raw/salesforce`, `raw/_eval`, ...). They are not used; downstream tasks read `raw/v2/`.

## Run 1: `mode=init` (default params)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/1115755588770367?o=7474646802937769

2026-11-17 13:25:21 "seller_superapp_daily" RUNNING
2026-11-17 13:27:02 "seller_superapp_daily" TERMINATED SUCCESS
{
  "mode": "init",
  "batch": 0,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v2",
  "files": 613,
  "generate_seconds": 13.7,
  "total_seconds": 69.6,
  "counts": {
    "User": 668,
    "UserRole": 24,
    "Account": 5000,
    "Contact": 20000,
    "Opportunity": 15000,
    "OpportunityHistory": 66646,
    "Lead": 4000,
    "Task": 41689,
    "Event": 18289,
    "meet_transcripts": 600,
    "product_usage": 261630,
    "support_tickets": 8000,
    "truth": 19600
  }
}
```

## Run 2: `mode=increment batch=1`
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/919295058839706?o=7474646802937769

2026-11-17 13:27:14 "seller_superapp_daily" RUNNING
2026-11-17 13:27:54 "seller_superapp_daily" TERMINATED SUCCESS
{
  "mode": "increment",
  "batch": 1,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v2",
  "files": 49,
  "generate_seconds": 5.9,
  "total_seconds": 10.2,
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
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/600845920521143?o=7474646802937769

2026-11-17 13:27:56 "seller_superapp_daily" RUNNING
2026-11-17 13:28:28 "seller_superapp_daily" TERMINATED SUCCESS
batch 0001 already present at /Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/v2; skipping
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
  "landed_at": "2026-11-17T22:27:39Z",
  "mode": "increment",
  "seed": 42
}
```

## Byte-identical: volume `v2/` vs local run
Local: `python -m fleetwise_gen.cli --mode init --out /tmp/fwv2 --seed 42`, then `--mode increment --batch 1`.
Each volume file was downloaded with the SDK and its sha256 compared with the local file. `_manifest/`
files hold the wall-clock `landed_at`, so they are excluded.
```
data files in volume v2: 660; local: 660; sha256 identical: 660; missing locally: 0; missing in volume: 0
```

## Volume file listing (recursive)
`databricks fs ls` in CLI v1.25.0 has no `-r` flag, so the listing walks the volume with the SDK
(`files.list_directory_contents`). Columns: bytes, sha256 prefix, `=` when identical to the local file, path under `raw/v2/`.
```
   6,432,219  32f3c816fd9677be  =  _eval/truth/batch=0000/part-0.json
      44,228  d5cbab2eae3a2b5f  =  _eval/truth/batch=0001/part-0.json
         457  f0bda103f042c450  (manifest, wall-clock)  _manifest/batch=0000.json
         436  9e6777e6a01a32f6  (manifest, wall-clock)  _manifest/batch=0001.json
  19,262,075  40c56aeb4e824c3a  =  product_usage/batch=0000/part-0.csv
     214,934  e7f42740987f9386  =  product_usage/batch=0001/part-0.csv
   2,906,753  8ffcc159186325f1  =  salesforce/Account/batch=0000/part-0.json
   8,732,500  973a05ef69602fe3  =  salesforce/Contact/batch=0000/part-0.json
   8,518,457  b0dba0d821d7d10c  =  salesforce/Event/batch=0000/part-0.json
     146,314  8a78ddf42680cbd8  =  salesforce/Event/batch=0001/part-0.json
   2,743,421  dc6a842909dabb43  =  salesforce/Lead/batch=0000/part-0.json
      34,417  6691eea1cf9e7a8d  =  salesforce/Lead/batch=0001/part-0.json
   9,179,816  15d51bb2f3466541  =  salesforce/Opportunity/batch=0000/part-0.json
      92,109  514691e1a65feacc  =  salesforce/Opportunity/batch=0001/part-0.json
  16,830,362  90a3ae96ffde1e43  =  salesforce/OpportunityHistory/batch=0000/part-0.json
      37,732  8c0c0e3643c08b8e  =  salesforce/OpportunityHistory/batch=0001/part-0.json
  19,446,662  3fd8ead8bdc10d86  =  salesforce/Task/batch=0000/part-0.json
     320,098  48082240c7bbfe17  =  salesforce/Task/batch=0001/part-0.json
     320,299  3152c816f8f329e4  =  salesforce/User/batch=0000/part-0.json
       4,253  d5851c00cd84bd28  =  salesforce/UserRole/batch=0000/part-0.json
   3,095,080  55dee1c6775936c2  =  support_tickets/batch=0000/part-0.json
      37,206  6272dd0a7c55b433  =  support_tickets/batch=0001/part-0.json
   2,663,607                    =  meet_transcripts/batch=0000/*.json  (600 files, all identical)
     179,033                    =  meet_transcripts/batch=0001/*.json  (40 files, all identical)
total files: 662; total bytes: 101,242,468
```

## Unit tests
`.venv/bin/pytest tests/unit -v`: 26 passed. Coverage: determinism, 18-char unique IDs, referential integrity,
no truth fields in raw files (init and increment), Jordan / Morgan / Taylor personas, stable increment IDs,
idempotent increment, NextStep preserved in increments, lead truth declaring the masked outcome fields,
truth rows for opps closed in an increment, Meet-code meeting ids, varied transcript phrasing,
win rate tracking intent, close dates in the current/next fiscal quarter, fictional competitors.
