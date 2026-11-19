"""Governed views must be (re)defined without dropping their grants (Task 11 finding).

CREATE OR REPLACE VIEW drops privileges granted on the view, so every job run removed the app
service principal's SELECT (applied from src/governance/grants.sql). The job's view DDL uses
CREATE VIEW IF NOT EXISTS + ALTER VIEW ... AS instead, which keeps the object and its grants.
"""

import re
from pathlib import Path

GOV = Path(__file__).resolve().parents[2] / "src" / "governance"
JOB_VIEW_FILES = ["row_filters.sql", "ai_views.sql"]


def _code(path: Path) -> str:
    return "\n".join(line.split("--", 1)[0] for line in path.read_text().splitlines())


def test_no_create_or_replace_view():
    for f in JOB_VIEW_FILES:
        assert not re.search(r"CREATE\s+OR\s+REPLACE\s+VIEW", _code(GOV / f), re.I), f


def test_every_view_is_created_and_altered_with_the_same_query():
    for f in JOB_VIEW_FILES:
        code = _code(GOV / f)
        created = dict(re.findall(r"CREATE VIEW IF NOT EXISTS (\w+)\nCOMMENT '(?:[^']|'')*'\nAS (.*?);", code, re.S))
        altered = dict(re.findall(r"ALTER VIEW (\w+) AS (.*?);", code, re.S))
        assert created, f
        assert created == altered, f
