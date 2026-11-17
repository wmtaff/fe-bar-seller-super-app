"""Shared fixtures for integration tests (live workspace via the CLI profile).

Names come from environment variables (see .env.example) with defaults that
match the bundle variables in databricks.yml.
"""

import os
import time

import pytest
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import (
    Disposition,
    Format,
    StatementParameterListItem,
    StatementState,
)

# Hard-pinned: the build must never use another profile.
PROFILE = "fevm-serverless-stable-s1omq8"
CATALOG = os.environ.get("FLEETWISE_CATALOG", "serverless_stable_s1omq8_catalog")
SCHEMA = os.environ.get("FLEETWISE_SCHEMA", "seller_superapp")
VOLUME = os.environ.get("FLEETWISE_VOLUME", "raw")
WAREHOUSE_ID = os.environ.get("FLEETWISE_WAREHOUSE_ID", "9a6db1d12e2ee6d3")
POLL_SECONDS = 2
DEADLINE_SECONDS = 600


@pytest.fixture(scope="session")
def names() -> dict:
    return {"catalog": CATALOG, "schema": SCHEMA, "volume": VOLUME, "warehouse_id": WAREHOUSE_ID}


@pytest.fixture(scope="session")
def ws() -> WorkspaceClient:
    return WorkspaceClient(profile=PROFILE)


@pytest.fixture(scope="session")
def sql(ws):
    """Return a callable: sql(query, parameters=None) -> list[dict].

    `parameters` maps named markers to values, e.g.
    sql("SELECT * FROM t WHERE id = :id", {"id": "006..."}); values are sent as
    strings (STRING type) unless given as (value, type) tuples.
    """

    def _params(parameters: dict | None) -> list[StatementParameterListItem] | None:
        if not parameters:
            return None
        items = []
        for name, val in parameters.items():
            val, typ = val if isinstance(val, tuple) else (val, None)
            items.append(
                StatementParameterListItem(
                    name=name, value=None if val is None else str(val), type=typ
                )
            )
        return items

    def _run(query: str, parameters: dict | None = None) -> list[dict]:
        resp = ws.statement_execution.execute_statement(
            statement=query,
            warehouse_id=WAREHOUSE_ID,
            wait_timeout="50s",
            disposition=Disposition.INLINE,
            format=Format.JSON_ARRAY,
            parameters=_params(parameters),
        )
        deadline = time.monotonic() + DEADLINE_SECONDS
        while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            if time.monotonic() > deadline:
                ws.statement_execution.cancel_execution(resp.statement_id)
                raise TimeoutError(
                    f"Statement {resp.statement_id} exceeded {DEADLINE_SECONDS}s; cancelled.\n{query}"
                )
            time.sleep(POLL_SECONDS)
            resp = ws.statement_execution.get_statement(resp.statement_id)
        if resp.status.state != StatementState.SUCCEEDED:
            err = resp.status.error
            raise RuntimeError(
                f"SQL {resp.status.state} (statement {resp.statement_id}): "
                f"{err.message if err else ''}\n{query}"
            )
        cols = [c.name for c in resp.manifest.schema.columns]
        rows = []
        result = resp.result
        while result is not None:
            rows.extend(dict(zip(cols, r)) for r in (result.data_array or []))
            if not result.next_chunk_index:
                break
            result = ws.statement_execution.get_statement_result_chunk_n(
                resp.statement_id, result.next_chunk_index
            )
        return rows

    return _run
