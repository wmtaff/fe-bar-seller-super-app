# Evidence 03: Unity Catalog governance (Task 4)

Collected 2026-11-18 on the Demo Warehouse, catalog `serverless_stable_s1omq8_catalog`, schema `seller_superapp`, dataset v4. Last refreshed for fix round 1 (ruling R16).

## What is governed and how (rulings R2, R16)

| Control | Where | Mechanism |
|---|---|---|
| Row-level security per seller / manager / RVP | dynamic views (owner-rights, filtering on `current_user()`): `v_opportunity_pipeline`, `v_seller_kpis`, `v_account_360` | `WHERE fn_can_see_owner(owner_id)`; base gold tables stay unfiltered so Lakebase can sync every row |
| PII masks | `silver_contacts.email/.phone/.mobile_phone`, `silver_leads.email/.phone` | UC column `MASK fn_mask_pii`, declared **in the pipeline DDL** (`src/pipeline/silver.sql`; SDP supports `MASK` on materialized views). No `v_contacts` fallback was needed |
| Tags | the masked columns above, plus raw upstream PII: `bronze_contact.Email/Phone/MobilePhone`, `bronze_lead.Email/Phone`, `silver_transcripts.attendees` | `contains_pii = true` everywhere; system classes `class.email_address` / `class.phone_number` on the silver columns. Applied by `SET TAG` after the pipeline (accepted on pipeline-managed tables) |
| Comments | every gold table/column (pipeline `COMMENT`s), views, `demo_identity_map` | the views inherit the gold column comments from `SELECT *` |
| Lineage | `system.access.table_lineage` | section 6 |

**Persona model.** `demo_identity_map(workspace_email PK, persona_user_id, persona_role CHECK IN (seller, manager, admin), updated_at)` maps a workspace login to a persona in `gold_user_hierarchy`.
- `fn_current_persona()` returns exactly one persona per caller: the latest `updated_at` wins if a login ever has several rows. The PK is informational; Delta doesn't enforce it.
- `fn_can_see_owner_for(persona_user_id, owner_id)` is the testable core. The persona sees their own rows plus rows of anyone whose `manager_id` or `rvp_id` is the persona. So a seller sees their own book, a manager their team, and an RVP the region.
- `fn_can_see_owner(owner_id)` applies it to the caller. Scope comes from `persona_user_id`; `persona_role` only matters for `admin`.

**Admin bypass (design choice).** If the caller has a persona, it decides: `admin` sees everything, anything else is scoped. If the caller has no row, account-group admins (`is_account_group_member('admins')`) see everything and everyone else sees nothing. So a presenter who is an admin can still demonstrate scoping, and an unmapped user is denied by default. (The executing user is a workspace admin, `is_member('admins')`, but not in the account group `admins`; see section 1.)

**Masking design.** Everyone sees masked contacts and leads (`f***@domain`, `***-***-1234`). In production, a RevOps account group (`superapp_revops`, referenced by `fn_mask_pii`) can be granted unmasked access. The unmasked branch is proven through `fn_mask_pii_for(v, true)`, which `fn_mask_pii` uses the same logic as (inlined; section 4).

**PII tag key.** This shared workspace has an account-level governed tag `pii` whose allowed values are only `ssn` and `address`, so `pii = true` fails with `UC_TAG_POLICY_VALUE_NOT_ALLOWED`. The columns carry the governed boolean tag `contains_pii = true` instead, plus Databricks' system data-classification tags.

## Governance boundary

- **bronze_\* and silver_\* are producer-only.** They are read by the pipeline and its owner only, and no consumer is ever granted access. Bronze keeps raw CRM PII (tagged `contains_pii`). Silver PII columns are masked.
- **Consumer grant plan:** `src/governance/grants.sql`, parameterized by `${catalog}`, `${schema}` and `${principal}`. It grants:
  - `USE CATALOG` / `USE SCHEMA`;
  - `SELECT` only on `v_opportunity_pipeline`, `v_seller_kpis`, `v_account_360` and the pre-masked `gold_contacts_masked`;
  - the AI gold tables of Tasks 5–7, as commented placeholders.

  Nothing goes on bronze/silver or on the unfiltered gold base tables. `EXECUTE` on the `fn_*` functions should not be needed, because the views run with owner rights; Task 10 checks this with a second principal. The plan is **not applied to any principal yet**: Task 10 applies it to the app service principal. It must not go to broad workspace groups.
- **demo_identity_map is demo persona impersonation, not an entitlement.** It lets one presenter act as Jordan (seller) or Morgan (manager). Only the owner/admins hold `MODIFY` on it: no grant exists, and the plan adds none. The app writes it only through its validated persona endpoint (`seller|manager|empty`, never `admin`; ruling R4, Task 10). Real entitlements would come from identity groups or Postgres RLS in production.
- The pipeline itself reads masked silver values, so any future join on raw email/phone must read bronze inside the pipeline (docs/BACKLOG.md).

## Job wiring

`seller_superapp_daily`: `generate_data -> governance_setup (setup.sql) -> governance_masks (masks.sql) -> pipeline_refresh -> apply_governance (row_filters.sql) -> governance_comments_tags (comments_tags.sql)`.
- Each governance task is a `sql_task` file on `${var.warehouse_id}` with `catalog`/`schema` parameters.
- The masks run before the pipeline because silver references `fn_mask_pii`.
- The row filters run after it because they read `gold_user_hierarchy`.
- `grants.sql` is not in the job.

Runs:
- 156266414422811: `pipeline_refresh` failed with `UNRESOLVED_ROUTINE fn_mask_pii`, because the pipeline resolves routines on `<catalog>.default`. I cancelled it and fixed it by qualifying the mask as `${uc_schema}.fn_mask_pii` (new pipeline config `uc_schema`).
- 405409722236842: all six tasks SUCCESS (initial build).
- 936054891955460: fix round. `pipeline_refresh` failed on the incremental refresh of `gold_contacts_masked`: `INTERNAL_ERROR Cannot generate code for expression fn_mask_pii_for`, because the mask called a nested SQL UDF. I fixed it by inlining the mask body (`test_mask_matches_core` keeps it in sync with the core).
- 830941596946381: all six tasks SUCCESS. A further incremental pipeline update, 45615d69, also COMPLETED.

## Tests

The map-mutating persona tests are opt-in (`-m governance_mutating` or `FLEETWISE_GOVERNANCE_MUTATING=1`), so a default run never rewrites a live demo login's persona.

```
$ FLEETWISE_GOVERNANCE_MUTATING=1 pytest tests/integration/test_governance.py tests/integration/test_governance_mutating.py tests/unit/test_governance_job.py -q
24 passed in 111.07s
$ pytest tests -q          # default: mutating tests skipped
57 passed, 8 skipped in 94.86s
```


## 1. Who is running these queries

```sql
SELECT current_user() AS caller, is_account_group_member('admins') AS account_admin, is_member('admins') AS workspace_admin, is_account_group_member('superapp_revops') AS in_superapp_revops
```

| caller | account_admin | workspace_admin | in_superapp_revops |
|---|---|---|---|
| will.taff@databricks.com | false | true | false |

## 2. Objects and definitions

```sql
SELECT routine_name, routine_definition FROM information_schema.routines WHERE routine_schema = current_schema() AND routine_name LIKE 'fn\_%' ORDER BY 1
```

| routine_name | routine_definition |
|---|---|
| fn_can_see_owner | CASE   WHEN fn_current_persona() IS NULL THEN is_account_group_member('admins')   WHEN fn_current_persona().persona_role = 'admin' THEN TRUE   ELSE coalesce(fn_can_see_owner_for(fn_current_persona().persona_user_id, fn_can_see_owner.owner_id), FALSE) END |
| fn_can_see_owner_for | fn_can_see_owner_for.persona_user_id IS NOT NULL AND (   fn_can_see_owner_for.owner_id = fn_can_see_owner_for.persona_user_id   OR EXISTS (     SELECT 1 FROM gold_user_hierarchy h     WHERE h.user_id = fn_can_see_owner_for.owner_id       AND (h.manager_id = fn_can_see_owner_for.persona_user_id            OR h.rvp_id = fn_can_see_owner_for.persona_user_id)   ) ) |
| fn_current_persona | ((   SELECT max_by(            named_struct('persona_role', persona_role, 'persona_user_id', persona_user_id),            named_struct('t', coalesce(updated_at, TIMESTAMP '1970-01-01'),                         'r', persona_role, 'u', coalesce(persona_user_id, '')))   FROM demo_identity_map   WHERE workspace_email = current_user() )) |
| fn_mask_pii | CASE   WHEN v IS NULL THEN NULL   WHEN is_account_group_member('superapp_revops') THEN v   WHEN v LIKE '%_@_%' THEN concat(left(v, 1), '***@', substring_index(v, '@', -1))   WHEN v RLIKE '[0-9]' THEN concat('***-***-', right(regexp_replace(v, '[^0-9]', ''), 4))   ELSE '***' END |
| fn_mask_pii_for | CASE   WHEN v IS NULL THEN NULL   WHEN privileged THEN v   WHEN v LIKE '%_@_%' THEN concat(left(v, 1), '***@', substring_index(v, '@', -1))   WHEN v RLIKE '[0-9]' THEN concat('***-***-', right(regexp_replace(v, '[^0-9]', ''), 4))   ELSE '***' END |

```sql
SELECT table_name, view_definition FROM information_schema.views WHERE table_schema = current_schema() AND table_name LIKE 'v\_%' ORDER BY 1
```

| table_name | view_definition |
|---|---|
| v_account_360 | SELECT * FROM gold_account_360 WHERE fn_can_see_owner(owner_id) |
| v_opportunity_pipeline | SELECT * FROM gold_opportunity_pipeline WHERE fn_can_see_owner(owner_id) |
| v_seller_kpis | SELECT * FROM gold_seller_kpis WHERE fn_can_see_owner(owner_id) |

```sql
SELECT table_name, column_name, mask_name, using_columns FROM information_schema.column_masks WHERE table_schema = current_schema() ORDER BY 1, 2
```

| table_name | column_name | mask_name | using_columns |
|---|---|---|---|
| silver_contacts | email | serverless_stable_s1omq8_catalog.seller_superapp.fn_mask_pii |  |
| silver_contacts | mobile_phone | serverless_stable_s1omq8_catalog.seller_superapp.fn_mask_pii |  |
| silver_contacts | phone | serverless_stable_s1omq8_catalog.seller_superapp.fn_mask_pii |  |
| silver_leads | email | serverless_stable_s1omq8_catalog.seller_superapp.fn_mask_pii |  |
| silver_leads | phone | serverless_stable_s1omq8_catalog.seller_superapp.fn_mask_pii |  |

```sql
SELECT table_name, filter_name FROM information_schema.row_filters WHERE table_schema = current_schema()
```

| table_name | filter_name |
|---|---|

Base gold tables carry no row filter (ruling R2), so Lakebase can sync every row; the filter is applied in the views.

```
DESCRIBE TABLE EXTENDED silver_contacts  -- PII columns and mask rows
email | string | Work email. PII: UC column mask fn_mask_pii, raw only for superapp_revops (others see j***@domain.com).
phone | string | Office phone. PII: UC column mask fn_mask_pii, raw only for superapp_revops (others see ***-***-1234).
mobile_phone | string | Mobile phone. PII: UC column mask fn_mask_pii, raw only for superapp_revops.
Comment | Silver: customer contacts, latest row per Id. email and phone are PII with UC column masks (fn_mask_pii); app consumers use gold_contacts_masked. | 
# Column Masks |  | 
email | `serverless_stable_s1omq8_catalog`.`seller_superapp`.`fn_mask_pii` | 
phone | `serverless_stable_s1omq8_catalog`.`seller_superapp`.`fn_mask_pii` | 
mobile_phone | `serverless_stable_s1omq8_catalog`.`seller_superapp`.`fn_mask_pii` | 
```

## 3. Row-level security per persona (v_opportunity_pipeline / v_seller_kpis / v_account_360)

Before: the base table as the same caller, unfiltered.

```sql
SELECT 'gold_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps FROM gold_opportunity_pipeline UNION ALL SELECT 'gold_seller_kpis', count(DISTINCT owner_id), count(*), NULL FROM gold_seller_kpis UNION ALL SELECT 'gold_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL FROM gold_account_360
```

| object | owners | row_count | open_opps |
|---|---|---|---|
| gold_opportunity_pipeline | 599 | 15000 | 2979 |
| gold_seller_kpis | 600 | 6600 |  |
| gold_account_360 (accounts) | 599 | 5000 |  |

After, persona = **Jordan Rivera (seller)**:

```sql
SELECT 'v_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps, round(sum(CASE WHEN NOT is_closed THEN acv END)) AS open_acv FROM v_opportunity_pipeline UNION ALL SELECT 'v_seller_kpis', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_seller_kpis UNION ALL SELECT 'v_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_account_360
```

| object | owners | row_count | open_opps | open_acv |
|---|---|---|---|---|
| v_opportunity_pipeline | 1 | 44 | 25 | 1957700.0 |
| v_seller_kpis | 1 | 11 |  |  |
| v_account_360 (accounts) | 1 | 20 |  |  |

After, persona = **Morgan Lee (manager)**:

```sql
SELECT 'v_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps, round(sum(CASE WHEN NOT is_closed THEN acv END)) AS open_acv FROM v_opportunity_pipeline UNION ALL SELECT 'v_seller_kpis', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_seller_kpis UNION ALL SELECT 'v_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_account_360
```

| object | owners | row_count | open_opps | open_acv |
|---|---|---|---|---|
| v_opportunity_pipeline | 8 | 212 | 60 | 8285100.0 |
| v_seller_kpis | 8 | 88 |  |  |
| v_account_360 (accounts) | 8 | 79 |  |  |

```sql
SELECT h.name, h.role, count(o.opportunity_id) AS visible_opps FROM v_opportunity_pipeline o JOIN gold_user_hierarchy h ON h.user_id = o.owner_id GROUP BY 1, 2 ORDER BY 1
```

| name | role | visible_opps |
|---|---|---|
| John Smith | Seller | 24 |
| Jordan Rivera | Seller | 44 |
| Rachel Lopez | Seller | 24 |
| Robyn Simmons | Seller | 24 |
| Tammy Clements | Seller | 24 |
| Timothy Ibarra | Seller | 24 |
| Tracy Salazar | Seller | 24 |
| William Andrade | Seller | 24 |

```sql
SELECT count(*) AS morgan_direct_reports FROM gold_user_hierarchy WHERE manager_id = (SELECT user_id FROM gold_user_hierarchy WHERE name = 'Morgan Lee')
```

| morgan_direct_reports |
|---|
| 8 |

After, persona = **Taylor Empty (seller, 0 open opps)**:

```sql
SELECT 'v_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps, round(sum(CASE WHEN NOT is_closed THEN acv END)) AS open_acv FROM v_opportunity_pipeline UNION ALL SELECT 'v_seller_kpis', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_seller_kpis UNION ALL SELECT 'v_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_account_360
```

| object | owners | row_count | open_opps | open_acv |
|---|---|---|---|---|
| v_opportunity_pipeline | 0 | 0 |  |  |
| v_seller_kpis | 1 | 11 |  |  |
| v_account_360 (accounts) | 0 | 0 |  |  |

After, persona = **admin persona**:

```sql
SELECT 'v_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps, round(sum(CASE WHEN NOT is_closed THEN acv END)) AS open_acv FROM v_opportunity_pipeline UNION ALL SELECT 'v_seller_kpis', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_seller_kpis UNION ALL SELECT 'v_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_account_360
```

| object | owners | row_count | open_opps | open_acv |
|---|---|---|---|---|
| v_opportunity_pipeline | 599 | 15000 | 2979 | 5.696595E8 |
| v_seller_kpis | 600 | 6600 |  |  |
| v_account_360 (accounts) | 599 | 5000 |  |  |

After, persona = **no map row**:

```sql
SELECT 'v_opportunity_pipeline' AS object, count(DISTINCT owner_id) AS owners, count(*) AS row_count, sum(CASE WHEN NOT is_closed THEN 1 ELSE 0 END) AS open_opps, round(sum(CASE WHEN NOT is_closed THEN acv END)) AS open_acv FROM v_opportunity_pipeline UNION ALL SELECT 'v_seller_kpis', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_seller_kpis UNION ALL SELECT 'v_account_360 (accounts)', count(DISTINCT owner_id), count(*), NULL, NULL FROM v_account_360
```

| object | owners | row_count | open_opps | open_acv |
|---|---|---|---|---|
| v_opportunity_pipeline | 0 | 0 |  |  |
| v_seller_kpis | 0 | 0 |  |  |
| v_account_360 (accounts) | 0 | 0 |  |  |

Map restored after the run:

```sql
SELECT * FROM demo_identity_map
```

| workspace_email | persona_user_id | persona_role | updated_at |
|---|---|---|---|
| will.taff@databricks.com | 0050g000000003OAAQ | seller | 2026-11-18T18:55:23.730Z |

Explicit-persona variant (testable without changing the map): visible users per persona, including Jordan's RVP (whole region).

```sql
WITH p AS (SELECT name AS persona, user_id FROM gold_user_hierarchy WHERE name IN ('Jordan Rivera', 'Morgan Lee', 'Taylor Empty') UNION ALL SELECT concat(r.name, ' (RVP of Jordan)'), r.user_id FROM gold_user_hierarchy j JOIN gold_user_hierarchy r ON r.user_id = j.rvp_id WHERE j.name = 'Jordan Rivera') SELECT p.persona, count(*) AS visible_users FROM p CROSS JOIN gold_user_hierarchy o WHERE fn_can_see_owner_for(p.user_id, o.user_id) GROUP BY 1 ORDER BY 2
```

| persona | visible_users |
|---|---|
| Taylor Empty | 1 |
| Jordan Rivera | 1 |
| Morgan Lee | 9 |
| Kelly Castaneda (RVP of Jordan) | 87 |

## 4. PII masks

Masked path, as the caller above (not in superapp_revops):

```sql
SELECT contact_id, name, email, phone, mobile_phone FROM silver_contacts ORDER BY contact_id LIMIT 5
```

| contact_id | name | email | phone | mobile_phone |
|---|---|---|---|---|
| 0030g0000000000AAA | Frances Gonzalez | f***@solisconstruction.com | ***-***-0163 | ***-***-0111 |
| 0030g0000000001AAA | Dana Campbell | d***@solisconstruction.com | ***-***-0137 | ***-***-0165 |
| 0030g0000000002AAA | Samantha Bryant | s***@solisconstruction.com | ***-***-0199 | ***-***-0184 |
| 0030g0000000003AAA | Stephen Smith | s***@solisconstruction.com | ***-***-0122 | ***-***-0165 |
| 0030g0000000004AAA | Christopher Phillips | c***@blueherondistribution.com | ***-***-0138 | ***-***-0104 |

```sql
SELECT lead_id, name, email, phone FROM silver_leads ORDER BY lead_id LIMIT 3
```

| lead_id | name | email | phone |
|---|---|---|---|
| 00Q0g0000000000EAA | Matthew Gould | m***@willowbenddairy.com | ***-***-0178 |
| 00Q0g0000000001EAA | Matthew Padilla | m***@gonzalezfireprotection.com | ***-***-0154 |
| 00Q0g0000000002EAA | Ashley Hanson | a***@lowerpineridge.com | ***-***-0165 |

```sql
SELECT count(*) AS contacts, sum(CASE WHEN email RLIKE '^.[*]{3}@[^@]+$' THEN 1 ELSE 0 END) AS emails_masked, sum(CASE WHEN phone RLIKE '^[*]{3}-[*]{3}-[0-9]{0,4}$' THEN 1 ELSE 0 END) AS phones_masked FROM silver_contacts
```

| contacts | emails_masked | phones_masked |
|---|---|---|
| 20000 | 20000 | 20000 |

Unmasked path: by design everyone sees masked contacts; in production a RevOps account group (`superapp_revops`) can be granted unmasked access. The unmasked branch is proven through the mask core `fn_mask_pii_for(v, true)` that `fn_mask_pii` uses the same logic as (inlined):

```sql
SELECT fn_mask_pii_for('jane.doe@acme.example', true) AS revops_sees, fn_mask_pii_for('jane.doe@acme.example', false) AS others_see, fn_mask_pii_for('(415) 555-0123', true) AS revops_phone, fn_mask_pii_for('(415) 555-0123', false) AS others_phone
```

| revops_sees | others_see | revops_phone | others_phone |
|---|---|---|---|
| jane.doe@acme.example | j***@acme.example | (415) 555-0123 | ***-***-0123 |

## 5. Tags and comments

```sql
SELECT table_name, column_name, tag_name, tag_value FROM information_schema.column_tags WHERE schema_name = current_schema() ORDER BY 1, 2, 3
```

| table_name | column_name | tag_name | tag_value |
|---|---|---|---|
| bronze_contact | Email | contains_pii | true |
| bronze_contact | MobilePhone | contains_pii | true |
| bronze_contact | Phone | contains_pii | true |
| bronze_lead | Email | contains_pii | true |
| bronze_lead | Phone | contains_pii | true |
| silver_contacts | email | class.email_address |  |
| silver_contacts | email | contains_pii | true |
| silver_contacts | mobile_phone | class.phone_number |  |
| silver_contacts | mobile_phone | contains_pii | true |
| silver_contacts | phone | class.phone_number |  |
| silver_contacts | phone | contains_pii | true |
| silver_leads | email | class.email_address |  |
| silver_leads | email | contains_pii | true |
| silver_leads | phone | class.phone_number |  |
| silver_leads | phone | contains_pii | true |
| silver_transcripts | attendees | contains_pii | true |

```sql
SELECT table_name, table_type, comment FROM information_schema.tables WHERE table_schema = current_schema() AND (table_name LIKE 'gold%' OR table_name LIKE 'v\_%' OR table_name = 'demo_identity_map') ORDER BY 1
```

| table_name | table_type | comment |
|---|---|---|
| demo_identity_map | MANAGED | Governance: maps workspace users to Fleetwise demo personas (demo impersonation, not an entitlement). fn_can_see_owner reads it to scope v_opportunity_pipeline, |
| gold_account_360 | MATERIALIZED_VIEW | Gold: account 360 - firmographics, ARR, products owned and whitespace, 30-day usage trend, support load, open pipeline and last touch. One row per account. |
| gold_contacts_masked | MATERIALIZED_VIEW | Gold: customer contacts with email and phone masked inline, safe to serve to the app via Lakebase. One row per contact. |
| gold_opportunity_pipeline | MATERIALIZED_VIEW | Gold: one row per opportunity (open and closed) with stage age, days to close, activity recency and fiscal quarter. Not row-filtered; use v_opportunity_pipeline |
| gold_seller_kpis | MATERIALIZED_VIEW | Gold: seller KPIs by fiscal quarter - quota, attainment, open pipeline, commit and pipeline coverage. One row per seller per fiscal quarter (sellers with no dea |
| gold_user_hierarchy | MATERIALIZED_VIEW | Gold: Fleetwise sales org hierarchy, seller -> manager -> RVP. One row per user. Used for row-level security and team roll-ups. |
| v_account_360 | VIEW | Governed dynamic view of gold_account_360: one row per customer/prospect account, row-filtered by fn_can_see_owner(owner_id) on the account owner (seller = own  |
| v_opportunity_pipeline | VIEW | Governed dynamic view of gold_opportunity_pipeline: one row per opportunity, row-filtered by fn_can_see_owner(owner_id) so a seller sees their own deals and a m |
| v_seller_kpis | VIEW | Governed dynamic view of gold_seller_kpis: one row per seller and fiscal quarter, row-filtered by fn_can_see_owner(owner_id) (seller = own KPIs, manager/RVP = t |

```sql
SELECT table_name, count(*) AS columns, count(NULLIF(comment, '')) AS commented FROM information_schema.columns WHERE table_schema = current_schema() AND (table_name LIKE 'gold%' OR table_name LIKE 'v\_%' OR table_name IN ('demo_identity_map', 'silver_contacts')) GROUP BY 1 ORDER BY 1
```

| table_name | columns | commented |
|---|---|---|
| demo_identity_map | 4 | 4 |
| gold_account_360 | 30 | 30 |
| gold_contacts_masked | 13 | 13 |
| gold_opportunity_pipeline | 34 | 34 |
| gold_seller_kpis | 17 | 17 |
| gold_user_hierarchy | 15 | 15 |
| silver_contacts | 15 | 15 |
| v_account_360 | 30 | 30 |
| v_opportunity_pipeline | 34 | 34 |
| v_seller_kpis | 17 | 17 |

## 6. Lineage (system.access.table_lineage)

```sql
SELECT source_table_full_name, target_table_full_name, max(event_time) AS last_seen FROM system.access.table_lineage WHERE event_date >= current_date() - 7 AND (target_table_full_name LIKE 'serverless_stable_s1omq8_catalog.seller_superapp.%' OR source_table_full_name LIKE 'serverless_stable_s1omq8_catalog.seller_superapp.%') AND target_table_full_name IS NOT NULL AND source_table_full_name IS NOT NULL AND (target_table_full_name RLIKE '\\.(gold|silver)_' OR target_table_full_name RLIKE '\\.v_') AND source_table_full_name NOT LIKE '%__materialization%' AND target_table_full_name NOT LIKE '%__materialization%' GROUP BY 1, 2 ORDER BY 2, 1
```

| source_table_full_name | target_table_full_name | last_seen |
|---|---|---|
| serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_accounts | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_activities | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunities | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_tickets | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_usage_daily | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_users | serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | 2026-11-18T19:16:11.859Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_accounts | serverless_stable_s1omq8_catalog.seller_superapp.gold_contacts_masked | 2026-11-18T18:41:23.285Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_contacts | serverless_stable_s1omq8_catalog.seller_superapp.gold_contacts_masked | 2026-11-18T19:16:18.419Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_user_hierarchy | serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | 2026-11-18T19:16:06.342Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_accounts | serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | 2026-11-18T19:16:06.342Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_activities | serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | 2026-11-18T19:16:06.342Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunities | serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | 2026-11-18T19:16:06.342Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunity_history | serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | 2026-11-18T19:16:06.342Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | serverless_stable_s1omq8_catalog.seller_superapp.gold_seller_kpis | 2026-11-18T19:16:11.731Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_user_hierarchy | serverless_stable_s1omq8_catalog.seller_superapp.gold_seller_kpis | 2026-11-18T19:16:11.731Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunities | serverless_stable_s1omq8_catalog.seller_superapp.gold_seller_kpis | 2026-11-18T19:16:11.731Z |
| serverless_stable_s1omq8_catalog.seller_superapp.silver_users | serverless_stable_s1omq8_catalog.seller_superapp.gold_user_hierarchy | 2026-11-18T19:16:02.233Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_account | serverless_stable_s1omq8_catalog.seller_superapp.silver_accounts | 2026-11-18T19:15:55.484Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_event | serverless_stable_s1omq8_catalog.seller_superapp.silver_activities | 2026-11-18T19:15:55.381Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_task | serverless_stable_s1omq8_catalog.seller_superapp.silver_activities | 2026-11-18T19:15:55.381Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_contact | serverless_stable_s1omq8_catalog.seller_superapp.silver_contacts | 2026-11-18T19:15:55.362Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_lead | serverless_stable_s1omq8_catalog.seller_superapp.silver_leads | 2026-11-18T19:15:56.699Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_opportunity | serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunities | 2026-11-18T19:15:53.730Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_opportunity_history | serverless_stable_s1omq8_catalog.seller_superapp.silver_opportunity_history | 2026-11-18T19:15:55.578Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_support_tickets | serverless_stable_s1omq8_catalog.seller_superapp.silver_tickets | 2026-11-18T19:15:55.410Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_meet_transcripts | serverless_stable_s1omq8_catalog.seller_superapp.silver_transcripts | 2026-11-18T19:15:55.613Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_product_usage | serverless_stable_s1omq8_catalog.seller_superapp.silver_usage_daily | 2026-11-18T19:15:56.660Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_user | serverless_stable_s1omq8_catalog.seller_superapp.silver_users | 2026-11-18T19:15:58.810Z |
| serverless_stable_s1omq8_catalog.seller_superapp.bronze_user_role | serverless_stable_s1omq8_catalog.seller_superapp.silver_users | 2026-11-18T19:15:58.810Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_account_360 | serverless_stable_s1omq8_catalog.seller_superapp.v_account_360 | 2026-11-18T18:55:34.069Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_opportunity_pipeline | serverless_stable_s1omq8_catalog.seller_superapp.v_opportunity_pipeline | 2026-11-18T18:55:39.696Z |
| serverless_stable_s1omq8_catalog.seller_superapp.gold_seller_kpis | serverless_stable_s1omq8_catalog.seller_superapp.v_seller_kpis | 2026-11-18T18:55:22.043Z |
