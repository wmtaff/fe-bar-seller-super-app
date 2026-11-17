# Task 1 evidence: bundle skeleton, UC schema & volume

Date: 2026-11-17. Profile `fevm-serverless-stable-s1omq8`, target `dev`.

## `databricks bundle validate --strict -t dev`
```
Name: fe-bar-seller-super-app
Target: dev
Workspace:
  User: will.taff@databricks.com
  Path: /Workspace/Users/will.taff@databricks.com/.bundle/fe-bar-seller-super-app/dev

Validation OK!
```

## `databricks bundle deploy -t dev`
```
Created schemas.seller_superapp
Created volumes.raw
Resources: 2 created, 0 changed, 0 deleted, 0 unchanged
```

## Unity Catalog objects
| object | full name | type |
|---|---|---|
| schema | serverless_stable_s1omq8_catalog.seller_superapp | - |
| volume | serverless_stable_s1omq8_catalog.seller_superapp.raw | MANAGED |

## `pytest tests/integration/test_setup.py -v` (Statement Execution on warehouse 9a6db1d12e2ee6d3)
```
tests/integration/test_setup.py::test_schema_and_volume_exist PASSED     [100%]
============================== 1 passed in 5.02s ===============================
```
Before deploy the same test failed with `assert [] == ['seller_superapp']` (RED).
