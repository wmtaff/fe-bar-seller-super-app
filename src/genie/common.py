"""Shared helpers for the Genie scripts (Task 9): bundle variables and the workspace client.

Catalog, schema and warehouse come from the bundle variable defaults in databricks.yml (one
source of truth, nothing hard-coded here); every value can be overridden on the command line.
"""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GENIE_DIR = Path(__file__).resolve().parent
SPACE_TEMPLATE = GENIE_DIR / "space.json"
SPACE_ID_FILE = GENIE_DIR / "space_id.txt"
TITLE = "Fleetwise Revenue Copilot"


def bundle_var(name: str, bundle_file: Path = ROOT / "databricks.yml") -> str | None:
    """Default value of a bundle variable in databricks.yml (None if absent)."""
    variables = yaml.safe_load(bundle_file.read_text()).get("variables") or {}
    return (variables.get(name) or {}).get("default")


def default(name: str, env: str) -> str | None:
    """Environment variable first, then the bundle variable default."""
    return os.environ.get(env) or bundle_var(name)


def workspace_client(profile: str | None):
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient(profile=profile)
