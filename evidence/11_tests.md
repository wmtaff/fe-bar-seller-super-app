# 11 - Full test suite (Task 12)

Run 2026-11-19 ~03:19–03:23 UTC from the developer laptop against the live workspace
(`fevm-serverless-stable-s1omq8`), after the batch-2 job run and its rerun (`evidence/10_e2e.md`):

```
$ .venv/bin/pytest -q -m "not governance_mutating" -rfEs
F..............................................s........................ [ 38%]
........................................................................ [ 77%]
..........................................                               [100%]
=========================== short test summary info ============================
FAILED tests/integration/test_app.py::test_sp_second_principal_governance - A...
SKIPPED [1] tests/integration/test_lakebase.py:211: the real lb_seller_actions_history exists; covered by test_writeback_roundtrip
1 failed, 184 passed, 1 skipped, 9 deselected in 261.18s (0:04:21)
```

The 9 `governance_mutating` tests (they rewrite the caller's `demo_identity_map` row) are opt-in and were
deselected, as in earlier tasks.

| Suite | Tests | Result |
|---|---|---|
| Unit (`tests/unit`, no workspace) | 103 in the full run; **105** after adding `test_view_ddl.py` (re-run: `105 passed in 35.20s`) | all pass |
| Integration: setup, pipeline, governance, insights, scores, NBA | 1 + 12 + 11 + 8 + 9 + 12 | all pass |
| Integration: Lakebase (synced tables, latency, write-back round trip) | 20 | 19 pass, 1 skip (the simulated write-back test skips because the real Lakehouse Sync table exists; the real round-trip test passed) |
| Integration: end to end (`test_e2e.py`, Task 11) | 5 | all pass |
| Integration: deployed app (`test_app.py`) | 5 | **4 pass, 1 fail** (below) |

## The failure, and what it found

`test_sp_second_principal_governance` calls the app's `/api/health/governance`, which reads as the app
service principal. It expects the base table `gold_opportunity_app` to be denied (it was) and the
row-filtered view `v_opportunity_pipeline` to be allowed. The view was **denied**:

```
{'principal': 'app service principal', 'base_table': {'table': 'gold_opportunity_app', 'ok': False, 'error': 'INSUFFICIENT_PERMISSIONS'},
 'view': {'table': 'v_opportunity_pipeline', 'ok': False, 'error': 'INSUFFICIENT_PERMISSIONS'}, 'pass': False}
```

Root cause (a real bug): the job's `apply_governance` and `governance_ai_views` tasks redefined the six `v_*`
views with `CREATE OR REPLACE VIEW`, which drops the privileges granted on them. `SHOW GRANTS` confirmed that
the app SP kept its grants on tables (`gold_user_hierarchy`, `gold_lead_scores`, `gold_nba_feedback`,
`gold_contacts_masked`) but had none left on the views. The test passed in Task 10 because no job run had
happened since the grants were applied; the two batch-2 runs removed them. The app's seller screens are not
affected (they read Lakebase; Genie runs on-behalf-of the user), only the SP's UC view access.

Fix (commit "fix(governance): keep view grants across job runs"): the view DDL is now
`CREATE VIEW IF NOT EXISTS … ; ALTER VIEW … AS …`, which keeps the view object and its grants, and a static
unit test (`tests/unit/test_view_ddl.py`) forbids `CREATE OR REPLACE VIEW` in those files. It was deployed and
run (`only: apply_governance, governance_comments_tags, governance_ai_views`, run `697166856718289`: SUCCESS),
and `test_governance.py` + `test_setup.py` were re-run: `12 passed`.

**Not yet done (needs the user):** re-applying the app SP's view grants. The permission system denied a
re-grant from this agent (a grant to a service principal needs the user's approval), so it was not retried.
To close it: `.venv/bin/python jobs/app_post_deploy.py --profile fevm-serverless-stable-s1omq8`, then
`pytest tests/integration/test_app.py`. Then run the job once more and repeat the test, to confirm that
`ALTER VIEW` keeps the grants (expected, but not yet observed with a second principal).

## Re-measured numbers (not replacing the committed evidence)

The full run re-ran the Lakebase measurements. They were not written over `evidence/07_lakebase_metrics.json`,
because the README and evidence/07 quote the Task 10 numbers. This run: write-back round trip **32.5 s** (CDC
12.6 s; Task 10: 59.1 s / 16.2 s); lookup client p95 78.9 ms; server execution p95 0.06 ms; added over the
network p95 13.0 ms (Task 10: 6.3 ms), within the 50 ms budget.

## Final re-run (2026-11-19, after the user-approved re-grant)

1. `jobs/app_post_deploy.py` re-applied the app SP's grants (16 statements, SP only). Then `tests/integration/test_app.py` gave 5 passed, including the second-principal check (a base table is INSUFFICIENT_PERMISSIONS, `v_opportunity_pipeline` is readable).
2. A full `seller_superapp_daily` run (95252289759977, `mode=increment batch=2`) SUCCEEDED. Afterwards `test_app.py` again gave 5 passed, so the `ALTER VIEW` fix keeps the grants across job runs.
3. That run's `collect_evidence` wrote an empty row-count snapshot but reported SUCCESS. Cause: the SQL `startswith()` filter matched nothing on serverless job compute. Fixed in commit 1a586b7: the filter moved to Python, and an empty result now raises. Re-run 953272368127810 SUCCEEDED with a full snapshot. The rerun-parity test now ignores empty (invalid) snapshots.
4. Full suite: `pytest -q -m "not governance_mutating"` gave **187 passed, 0 failed, 1 skipped, 9 deselected**.
