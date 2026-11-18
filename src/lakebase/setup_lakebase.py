"""Lakebase serving layer (Task 8): project, UC catalog, synced tables, and the sync job task.

Actions (all idempotent, safe to re-run):
  setup  create-if-missing: Autoscaling project (PG 17; auto-creates branch `production`, database
         `databricks_postgres` and the primary endpoint) and the synced tables (UC gold -> Postgres
         schema `serving`; one shared sync pipeline per scheduling policy). Optional: --register-catalog
         (Lakebase database as a UC catalog; needs CREATE CATALOG on the metastore) and --with-cdf
         (Lakehouse Sync config for the app schema; run in Task 10 once that schema exists).
  sync   job task `lakebase_sync`: ensure the synced tables exist, start one update of each sync
         pipeline, wait for it, then check every table is ONLINE. (setup ends with a sync too:
         a table that joins an existing pipeline stays OFFLINE until that pipeline's next update.)

Usage: python setup_lakebase.py --catalog <uc catalog> --schema <uc schema> [--action setup|sync]
       [--serving-schema serving] [--project seller-superapp] [--with-cdf]
       [--register-catalog --lakebase-catalog fleetwise_lakebase] [--profile <cli profile>]

Synced tables are registered in the regular catalog ({catalog}.{serving_schema}.<table>), which
maps to Postgres "{serving_schema}"."<table>". That needs no metastore privilege, unlike
registering the database as its own UC catalog (optional, only for the federated fallback).

Auth: WorkspaceClient default auth (job run-as identity; locally pass --profile). No host,
token or workspace id appears in code. Never modifies synced tables inside Postgres.
Sources are the base gold tables (ruling R2): synced tables do not carry UC row filters/masks,
so the app scopes rows by persona in its own queries; contacts sync from the masked gold table.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

log = logging.getLogger("setup_lakebase")

PIPELINE_WAIT_S = 3600
ONLINE_WAIT_S = 3600
POLL_S = 15


@dataclass(frozen=True)
class SyncedSpec:
    pg_table: str           # table name in Postgres schema `serving` (and in UC {catalog}.serving)
    source: str             # UC source table in {catalog}.{schema}
    primary_key: list[str]
    policy: str = "TRIGGERED"


# TRIGGERED (incremental, reads the source's change data feed) for the Delta tables, which all
# have CDF on. SNAPSHOT (full copy each refresh) for the pipeline materialized views: reading CDF
# from an MV fails with MATERIALIZED_VIEW_CDF_REQUIRES_EXTERNAL_METADATA (verified 2026-11-18), and
# these tables are small (hundreds to a few thousand rows), so a snapshot takes seconds.
SYNCED_TABLES: list[SyncedSpec] = [
    SyncedSpec("account_360", "gold_account_360", ["account_id"], "SNAPSHOT"),
    SyncedSpec("opportunity_pipeline", "gold_opportunity_app", ["opportunity_id"]),
    SyncedSpec("next_best_actions", "gold_next_best_actions", ["action_id"]),
    SyncedSpec("call_insights", "gold_call_insights", ["meeting_id"]),
    SyncedSpec("seller_kpis", "gold_seller_kpis", ["owner_id", "fiscal_quarter"], "SNAPSHOT"),
    SyncedSpec("user_hierarchy", "gold_user_hierarchy", ["user_id"], "SNAPSHOT"),
    SyncedSpec("contacts", "gold_contacts_masked", ["contact_id"], "SNAPSHOT"),
    SyncedSpec("lead_scores", "gold_lead_scores", ["lead_id"]),
]


@dataclass(frozen=True)
class Config:
    catalog: str                                  # regular UC catalog: sources, synced-table entries, pipeline storage
    schema: str                                   # UC schema of the gold sources (and Lakehouse Sync landing)
    project: str = "seller-superapp"
    branch: str = "production"
    postgres_database: str = "databricks_postgres"
    pg_schema: str = "serving"                    # UC schema of the synced tables == their Postgres schema
    lakebase_catalog: str = "fleetwise_lakebase"  # optional UC catalog on the Lakebase database (fallback path)
    app_pg_schema: str = "app"                    # app-owned tables (created by the app SP, Task 10)
    cdf_config_id: str = "app_writeback"          # Lakehouse Sync config id ([a-z][a-z0-9_]*): Postgres `app` -> UC schema

    @property
    def project_path(self) -> str:
        return f"projects/{self.project}"

    @property
    def branch_path(self) -> str:
        return f"{self.project_path}/branches/{self.branch}"

    @property
    def fq(self) -> str:
        return f"`{self.catalog}`.`{self.schema}`"

    def source_full_name(self, spec: SyncedSpec) -> str:
        return f"{self.catalog}.{self.schema}.{spec.source}"

    def synced_table_id(self, pg_table: str) -> str:
        return f"{self.catalog}.{self.pg_schema}.{pg_table}"

    def synced_table_name(self, pg_table: str) -> str:
        return f"synced_tables/{self.synced_table_id(pg_table)}"


def synced_table_spec(cfg: Config, spec: SyncedSpec, existing_pipeline_id: str | None):
    """The first table of a scheduling policy creates the sync pipeline; the rest join it (one
    pipeline per policy: fewer connections and one update per run, as the Lakebase docs recommend)."""
    from databricks.sdk.service.postgres import (
        NewPipelineSpec,
        SyncedTableSyncedTableSpec,
        SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy as Policy,
    )

    return SyncedTableSyncedTableSpec(
        source_table_full_name=cfg.source_full_name(spec),
        primary_key_columns=list(spec.primary_key),
        scheduling_policy=Policy(spec.policy),
        branch=cfg.branch_path,
        postgres_database=cfg.postgres_database,
        create_database_objects_if_missing=True,
        existing_pipeline_id=existing_pipeline_id,
        new_pipeline_spec=None if existing_pipeline_id else NewPipelineSpec(
            storage_catalog=cfg.catalog, storage_schema=cfg.schema),
    )


# --------------------------------------------------------------------------- lookups
def _get(fn, **kw):
    from databricks.sdk.errors import NotFound

    try:
        return fn(**kw)
    except NotFound:
        return None


def database_path(w, cfg: Config) -> str:
    """Database RESOURCE path (projects/../databases/<id>) for the connect name databricks_postgres."""
    for db in w.postgres.list_databases(parent=cfg.branch_path):
        if db.status and db.status.postgres_database == cfg.postgres_database:
            return db.name
    raise RuntimeError(f"database {cfg.postgres_database} not found on {cfg.branch_path}")


# --------------------------------------------------------------------------- setup
def ensure_project(w, cfg: Config) -> None:
    from databricks.sdk.common.lro import LroOptions
    from databricks.sdk.service.postgres import Project, ProjectSpec

    if _get(w.postgres.get_project, name=cfg.project_path):
        log.info("project %s exists", cfg.project_path)
        return
    log.info("creating project %s (PG 17)", cfg.project_path)
    w.postgres.create_project(
        project=Project(spec=ProjectSpec(display_name=cfg.project, pg_version=17)),
        project_id=cfg.project,
    ).wait(LroOptions(timeout=timedelta(minutes=20)))


def ensure_catalog(w, cfg: Config) -> None:
    from databricks.sdk.common.lro import LroOptions
    from databricks.sdk.service.postgres import Catalog, CatalogCatalogSpec

    if _get(w.postgres.get_catalog, name=f"catalogs/{cfg.lakebase_catalog}"):
        log.info("catalog %s exists", cfg.lakebase_catalog)
        return
    log.info("registering %s as UC catalog %s", cfg.postgres_database, cfg.lakebase_catalog)
    w.postgres.create_catalog(
        catalog=Catalog(spec=CatalogCatalogSpec(postgres_database=cfg.postgres_database,
                                                branch=cfg.branch_path)),
        catalog_id=cfg.lakebase_catalog,
    ).wait(LroOptions(timeout=timedelta(minutes=10)))


def ensure_synced_tables(w, cfg: Config) -> list[str]:
    """Create missing synced tables; return the distinct sync pipeline ids."""
    from databricks.sdk.common.lro import LroOptions
    from databricks.sdk.service.postgres import SyncedTable

    pipeline_ids: list[str] = []
    by_policy: dict[str, str] = {}
    # existing tables first, so a re-run joins new tables to the existing pipeline of their policy
    existing = {s.pg_table: _get(w.postgres.get_synced_table, name=cfg.synced_table_name(s.pg_table))
                for s in SYNCED_TABLES}
    for spec in SYNCED_TABLES:
        st = existing[spec.pg_table]
        if st and st.status and st.status.pipeline_id:
            by_policy.setdefault(spec.policy, st.status.pipeline_id)
    for spec in SYNCED_TABLES:
        st = existing[spec.pg_table]
        if st is None:
            shared = by_policy.get(spec.policy)
            log.info("creating synced table %s <- %s (pipeline %s)", cfg.synced_table_id(spec.pg_table),
                     cfg.source_full_name(spec), shared or "new")
            w.postgres.create_synced_table(
                synced_table=SyncedTable(spec=synced_table_spec(cfg, spec, shared)),
                synced_table_id=cfg.synced_table_id(spec.pg_table),
            ).wait(LroOptions(timeout=timedelta(minutes=30)))
            st = w.postgres.get_synced_table(name=cfg.synced_table_name(spec.pg_table))
        else:
            _check_spec(cfg, spec, st)
        pid = st.status.pipeline_id if st.status else None
        if pid:
            by_policy.setdefault(spec.policy, pid)
        if pid and pid not in pipeline_ids:
            pipeline_ids.append(pid)
    if not pipeline_ids:
        raise RuntimeError("no sync pipeline id reported for the synced tables")
    return pipeline_ids


def _check_spec(cfg: Config, spec: SyncedSpec, st) -> None:
    """An existing synced table must still point at the intended source/key/policy (fail loudly,
    don't drift). GET does not always return the spec; then there is nothing to compare."""
    if st.spec is None:
        return
    have = (st.spec.source_table_full_name, list(st.spec.primary_key_columns or []),
            st.spec.scheduling_policy.value if st.spec.scheduling_policy else None)
    want = (cfg.source_full_name(spec), spec.primary_key, spec.policy)
    if have != want:
        raise RuntimeError(f"synced table {spec.pg_table} exists with {have}, expected {want}; "
                           f"delete it (delete-synced-table) and re-run setup")


def ensure_cdf_config(w, cfg: Config) -> str:
    """Lakehouse Sync (Beta): Postgres schema `app` -> UC {catalog}.{schema}.lb_<table>_history.

    The Postgres schema must already exist (the API rejects a missing one with "CdfConfig not
    found: Postgres schema ..."), so this runs in Task 10 after the app SP has created and owns
    schema `app`. Tables added to the schema later are picked up automatically. Returns a status
    string for the log/evidence.
    """
    from databricks.sdk.common.lro import LroOptions
    from databricks.sdk.errors import NotFound
    from databricks.sdk.service.postgres import CdfConfig

    parent = database_path(w, cfg)
    try:
        existing = [c for c in w.postgres.list_cdf_configs(parent=parent)
                    if c.postgres_schema == cfg.app_pg_schema]
    except NotFound:  # the list API returns 404 when there are no configs
        existing = []
    if existing:
        return f"exists: {existing[0].name}"
    log.info("creating CDF config %s: postgres %s -> %s.%s", cfg.cdf_config_id, cfg.app_pg_schema,
             cfg.catalog, cfg.schema)
    w.postgres.create_cdf_config(
        parent=parent,
        cdf_config=CdfConfig(catalog=cfg.catalog, schema=cfg.schema, postgres_schema=cfg.app_pg_schema),
        cdf_config_id=cfg.cdf_config_id,
    ).wait(LroOptions(timeout=timedelta(minutes=20)))
    cfg_name = f"{parent}/cdf-configs/{cfg.cdf_config_id}"
    for st in w.postgres.list_cdf_statuses(parent=cfg_name):  # statuses live under the config
        log.info("lakehouse sync %s -> %s: %s", st.postgres_table, st.uc_table, st.state)
    return "created"


def setup(w, cfg: Config, with_cdf: bool = False, register_catalog: bool = False) -> None:
    ensure_project(w, cfg)
    if register_catalog:
        ensure_catalog(w, cfg)
    # a table that joins an existing pipeline stays OFFLINE until that pipeline's next update
    sync(w, cfg)
    if with_cdf:
        log.info("lakehouse sync: %s", ensure_cdf_config(w, cfg))


# --------------------------------------------------------------------------- sync (job task)
_TERMINAL = {"COMPLETED", "FAILED", "CANCELED"}


def _latest_update_state(w, pipeline_id: str) -> tuple[str | None, str | None]:
    p = w.pipelines.get(pipeline_id=pipeline_id)
    if not p.latest_updates:
        return None, None
    u = p.latest_updates[0]
    return u.update_id, u.state.value if u.state else None


def _wait_update(w, pipeline_id: str, update_id: str) -> str:
    deadline = time.monotonic() + PIPELINE_WAIT_S
    while time.monotonic() < deadline:
        u = w.pipelines.get_update(pipeline_id=pipeline_id, update_id=update_id).update
        state = u.state.value if u and u.state else None
        if state in _TERMINAL:
            return state
        time.sleep(POLL_S)
    raise TimeoutError(f"pipeline {pipeline_id} update {update_id} not done after {PIPELINE_WAIT_S}s")


def refresh_pipeline(w, pipeline_id: str) -> None:
    """Start one update of a sync pipeline and wait (waits out an update already running first)."""
    upd, state = _latest_update_state(w, pipeline_id)
    if upd and state not in _TERMINAL:
        log.info("pipeline %s: waiting for running update %s (%s)", pipeline_id, upd, state)
        _wait_update(w, pipeline_id, upd)
    update_id = w.pipelines.start_update(pipeline_id=pipeline_id).update_id
    log.info("pipeline %s: started update %s", pipeline_id, update_id)
    state = _wait_update(w, pipeline_id, update_id)
    if state != "COMPLETED":
        raise RuntimeError(f"sync pipeline {pipeline_id} update {update_id} ended {state}")
    log.info("pipeline %s: update %s COMPLETED", pipeline_id, update_id)


def wait_online(w, cfg: Config) -> None:
    from databricks.sdk.service.postgres import SyncedTableState as S

    online = {S.SYNCED_TABLE_ONLINE, S.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE,
              S.SYNCED_TABLE_ONLINE_TRIGGERED_UPDATE, S.SYNCED_TABLE_ONLINE_CONTINUOUS_UPDATE}
    failed = {S.SYNCED_TABLE_OFFLINE_FAILED, S.SYNCED_TABLE_ONLINE_PIPELINE_FAILED}
    deadline = time.monotonic() + ONLINE_WAIT_S
    pending = [s.pg_table for s in SYNCED_TABLES]
    while pending:
        still = []
        for t in pending:
            st = w.postgres.get_synced_table(name=cfg.synced_table_name(t)).status
            state = st.detailed_state if st else None
            if state in failed:
                raise RuntimeError(f"synced table {t} is {state.value}: {st.message}")
            if state not in online:
                still.append(t)
        pending = still
        if pending:
            if time.monotonic() > deadline:
                raise TimeoutError(f"synced tables not ONLINE after {ONLINE_WAIT_S}s: {pending}")
            time.sleep(POLL_S)
    log.info("all %d synced tables ONLINE", len(SYNCED_TABLES))


def sync(w, cfg: Config) -> None:
    for pid in ensure_synced_tables(w, cfg):
        refresh_pipeline(w, pid)
    wait_online(w, cfg)


# --------------------------------------------------------------------------- entrypoint
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--project", default=Config.project)
    ap.add_argument("--serving-schema", default=Config.pg_schema)
    ap.add_argument("--lakebase-catalog", default=Config.lakebase_catalog)
    ap.add_argument("--register-catalog", action="store_true",
                    help="also register the database as UC catalog --lakebase-catalog (needs CREATE CATALOG)")
    ap.add_argument("--action", choices=["setup", "sync"], default="setup")
    ap.add_argument("--with-cdf", action="store_true",
                    help="also create the Lakehouse Sync config for schema app (Task 10, once it exists)")
    ap.add_argument("--profile", default=None, help="CLI profile for local runs (jobs use default auth)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
    cfg = Config(catalog=a.catalog, schema=a.schema, project=a.project, pg_schema=a.serving_schema,
                 lakebase_catalog=a.lakebase_catalog)
    if a.action == "setup":
        setup(w, cfg, with_cdf=a.with_cdf, register_catalog=a.register_catalog)
    else:
        sync(w, cfg)


if __name__ == "__main__":
    main()
