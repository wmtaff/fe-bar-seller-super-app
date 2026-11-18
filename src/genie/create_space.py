"""Create or update the Genie space "Fleetwise Revenue Copilot" (Task 9). Idempotent by title.

    python src/genie/create_space.py            # names from databricks.yml variable defaults
    python src/genie/create_space.py --catalog c --schema s --warehouse-id w

src/genie/space.json is the space definition (serialized_space v2) with ${catalog} / ${schema}
placeholders. If a space with the same title exists it is updated in place (same id, so the
app embed and links keep working); otherwise it is created. The id is written to
src/genie/space_id.txt. The space is not shared with anyone (permissions stay owner-only).
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SPACE_ID_FILE, SPACE_TEMPLATE, TITLE, default, workspace_client  # noqa: E402

DESCRIPTION = (
    "Ask about your Fleetwise pipeline, accounts, sales calls, AI deal scores and next best "
    "actions. Every view is row-scoped to the caller's seller/manager persona."
)
_ID = re.compile(r"^[0-9a-f]{32}$")
# Genie space tables (ruling R22): row-scoped views, plus tables with no seller-owned rows.
ALLOWED_BASE_TABLES = {"gold_user_hierarchy", "gold_lead_scores", "gold_nba_feedback"}


def render_space(template: str, catalog: str, schema: str) -> dict:
    """Substitute the placeholders, parse, and validate the serialized space."""
    text = template.replace("${catalog}", catalog).replace("${schema}", schema)
    leftover = re.search(r"\$\{[^}]*\}", text)
    if leftover:
        raise ValueError(f"unresolved placeholder: {leftover.group(0)}")
    space = json.loads(text)
    validate_space(space, f"{catalog}.{schema}.")
    return space


def _sorted_ids(items, what):
    ids = [i["id"] for i in items]
    bad = [i for i in ids if not _ID.match(i)]
    if bad:
        raise ValueError(f"{what}: ids must be 32 lowercase hex chars: {bad}")
    if ids != sorted(ids):
        raise ValueError(f"{what} must be sorted by id")
    return ids


def validate_space(space: dict, prefix: str) -> None:
    """The API's documented constraints, checked locally so a bad edit fails fast."""
    if space.get("version") != 2:
        raise ValueError("serialized_space version must be 2")
    tables = space["data_sources"]["tables"]
    idents = [t["identifier"] for t in tables]
    for ident in idents:
        if not ident.startswith(prefix):
            raise ValueError(f"table outside {prefix}: {ident}")
        name = ident[len(prefix):]
        if not (name.startswith("v_") or name in ALLOWED_BASE_TABLES):
            raise ValueError(f"Genie may only use row-scoped views or owner-less tables (R22): {name}")
    if idents != sorted(idents):
        raise ValueError("data_sources.tables must be sorted by identifier")
    if len(idents) > 30:
        raise ValueError("at most 30 tables")
    ins = space.get("instructions", {})
    if len(ins.get("text_instructions", [])) > 1:
        raise ValueError("instructions.text_instructions must contain at most one item")
    q_ids = _sorted_ids(space.get("config", {}).get("sample_questions", []), "sample_questions")
    i_ids = []
    for key in ("text_instructions", "example_question_sqls", "join_specs"):
        i_ids += _sorted_ids(ins.get(key, []), key)
    for what, ids in (("question", q_ids), ("instruction", i_ids)):
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate {what} ids")


def find_space_id(spaces, title: str) -> str | None:
    """Id of the space with this exact title; None if none; error if ambiguous."""
    matches = [s.space_id for s in spaces if s.title == title]
    if len(matches) > 1:
        raise RuntimeError(f"{len(matches)} Genie spaces titled {title!r}: {matches}; delete the extras")
    return matches[0] if matches else None


def list_all_spaces(w):
    token = None
    while True:
        resp = w.genie.list_spaces(page_size=100, page_token=token)
        yield from resp.spaces or []
        token = resp.next_page_token
        if not token:
            return


def main(argv=None) -> str:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", default=default("catalog", "FLEETWISE_CATALOG"))
    ap.add_argument("--schema", default=default("schema", "FLEETWISE_SCHEMA"))
    ap.add_argument("--warehouse-id", default=default("warehouse_id", "FLEETWISE_WAREHOUSE_ID"))
    ap.add_argument("--profile", default=default("profile", "DATABRICKS_CONFIG_PROFILE"))
    ap.add_argument("--title", default=TITLE)
    ap.add_argument("--parent-path", help="workspace folder (default: /Workspace/Users/<me>/fleetwise)")
    args = ap.parse_args(argv)
    for name in ("catalog", "schema", "warehouse_id"):
        if not getattr(args, name):
            ap.error(f"--{name.replace('_', '-')} is required")

    space = render_space(SPACE_TEMPLATE.read_text(), args.catalog, args.schema)
    serialized = json.dumps(space)
    w = workspace_client(args.profile)

    space_id = find_space_id(list_all_spaces(w), args.title)
    if space_id:
        w.genie.update_space(space_id, serialized_space=serialized, title=args.title,
                             description=DESCRIPTION, warehouse_id=args.warehouse_id)
        action = "updated"
    else:
        parent = args.parent_path or f"/Workspace/Users/{w.current_user.me().user_name}/fleetwise"
        w.workspace.mkdirs(parent)
        space_id = w.genie.create_space(args.warehouse_id, serialized, title=args.title,
                                        description=DESCRIPTION, parent_path=parent).space_id
        action = "created"
    SPACE_ID_FILE.write_text(space_id + "\n")
    print(f"{action} Genie space {args.title!r}: {space_id}")
    print(f"{w.config.host.rstrip('/')}/genie/rooms/{space_id}")
    return space_id


if __name__ == "__main__":
    main()
