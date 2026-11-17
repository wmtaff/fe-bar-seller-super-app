# Task 2 evidence: synthetic data generator (`generate_data`)

Date: 2026-11-17. Profile `fevm-serverless-stable-s1omq8`, target `dev`, job `seller_superapp_daily`
(job id 94481485733041), serverless compute, environment client 4 + `faker==40.54.0`.
Output: `/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw/`. Seed 42, as-of 2026-11-16.

## Run 1: `mode=init` (run 302093760007613)
Task attempt 0 (task run 808231075668689) generated and copied every file in **74.1 s**
(14.8 s to generate, the rest copying 613 files into the volume; 99 s task execution incl. startup).
The run was then marked FAILED only because the entrypoint ended with `sys.exit(0)`, which serverless
Python tasks report as `SystemExit: 0`. The automatic retry (attempt 1) found the manifest and skipped.
Fixed by calling `main()` without `sys.exit` (all later runs: SUCCESS). The data and the manifest from
attempt 0 are complete (manifest is written last). Output of attempt 0 (`databricks jobs get-run-output 808231075668689`):
```
{
  "mode": "init",
  "batch": 0,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw",
  "files": 613,
  "generate_seconds": 14.8,
  "total_seconds": 74.1,
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

## Run 2: `mode=init` again (idempotent skip)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/604539357907364?o=7474646802937769

2026-11-17 13:09:08 "seller_superapp_daily" RUNNING
2026-11-17 13:09:40 "seller_superapp_daily" TERMINATED SUCCESS
batch 0000 already present at /Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw; skipping
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
  "landed_at": "2026-11-17T22:05:37Z",
  "mode": "init",
  "seed": 42
}
```

## Run 3: `mode=increment batch=1`
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/290495516154124?o=7474646802937769

2026-11-17 13:09:42 "seller_superapp_daily" RUNNING
2026-11-17 13:10:23 "seller_superapp_daily" TERMINATED SUCCESS
{
  "mode": "increment",
  "batch": 1,
  "out": "/Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw",
  "files": 49,
  "generate_seconds": 5.9,
  "total_seconds": 10.4,
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
    "truth": 90
  }
}
```

## Run 4: `mode=increment batch=1` again (idempotent skip)
```
Run URL: https://fevm-serverless-stable-s1omq8.cloud.databricks.com/jobs/94481485733041/runs/518444495207717?o=7474646802937769

2026-11-17 13:10:36 "seller_superapp_daily" RUNNING
2026-11-17 13:11:08 "seller_superapp_daily" TERMINATED SUCCESS
batch 0001 already present at /Volumes/serverless_stable_s1omq8_catalog/seller_superapp/raw; skipping
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
    "truth": 90
  },
  "data_timestamp": "2026-11-16T13:00:00.000Z",
  "landed_at": "2026-11-17T22:10:09Z",
  "mode": "increment",
  "seed": 42
}
```

## Byte-identical: serverless output vs local `python -m fleetwise_gen.cli --seed 42`
sha256 prefix (volume file vs local file):
```
e55f3354558da049 e55f3354558da049 salesforce/Opportunity/batch=0000/part-0.json
973a05ef69602fe3 973a05ef69602fe3 salesforce/Contact/batch=0000/part-0.json
764b67e0d9955ff8 764b67e0d9955ff8 _eval/truth/batch=0000/part-0.json
40c56aeb4e824c3a 40c56aeb4e824c3a product_usage/batch=0000/part-0.csv
85f0bbc30d3111b7 85f0bbc30d3111b7 meet_transcripts/batch=0000/aap-pntj-afq-00253.json
7a7cdd084fce99c8 7a7cdd084fce99c8 salesforce/Opportunity/batch=0001/part-0.json
48082240c7bbfe17 48082240c7bbfe17 salesforce/Task/batch=0001/part-0.json
aff4ec102197f3b4 aff4ec102197f3b4 _eval/truth/batch=0001/part-0.json
```

## Volume file listing (recursive; transcripts summarised per batch)
`databricks fs ls` in CLI v1.25.0 has no `-r` flag, so the listing walks the volume with the SDK
(`WorkspaceClient.files.list_directory_contents`). Columns: bytes, path relative to the volume.
```
5,733,103  _eval/truth/batch=0000/part-0.json
      32,712  _eval/truth/batch=0001/part-0.json
         457  _manifest/batch=0000.json
         435  _manifest/batch=0001.json
  19,262,075  product_usage/batch=0000/part-0.csv
     214,934  product_usage/batch=0001/part-0.csv
   2,906,753  salesforce/Account/batch=0000/part-0.json
   8,732,500  salesforce/Contact/batch=0000/part-0.json
   8,522,057  salesforce/Event/batch=0000/part-0.json
     146,634  salesforce/Event/batch=0001/part-0.json
   2,732,782  salesforce/Lead/batch=0000/part-0.json
      34,417  salesforce/Lead/batch=0001/part-0.json
   9,179,849  salesforce/Opportunity/batch=0000/part-0.json
      90,371  salesforce/Opportunity/batch=0001/part-0.json
  16,830,362  salesforce/OpportunityHistory/batch=0000/part-0.json
      37,732  salesforce/OpportunityHistory/batch=0001/part-0.json
  19,446,662  salesforce/Task/batch=0000/part-0.json
     320,098  salesforce/Task/batch=0001/part-0.json
     320,299  salesforce/User/batch=0000/part-0.json
       4,253  salesforce/UserRole/batch=0000/part-0.json
   3,095,080  support_tickets/batch=0000/part-0.json
      37,206  support_tickets/batch=0001/part-0.json
   2,605,725  meet_transcripts/batch=0000/*.json  (600 files)
     179,492  meet_transcripts/batch=0001/*.json  (40 files)
total files: 662; total bytes: 100,465,988
```

## Unit tests
`.venv/bin/pytest tests/unit -v`: 19 passed (determinism, 18-char unique IDs, referential integrity,
truth not in raw files, Jordan / Morgan / Taylor personas, stable increment IDs, idempotent increment,
win rate tracks intent, close dates in current/next fiscal quarter, fictional competitors, transcript roles).
