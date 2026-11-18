"""Task 10: the deployed Fleetwise Seller Hub, called with the developer's user OAuth token.

Skips until the app is deployed and RUNNING. Covers the R16 second-principal check (the app SP
cannot read an unfiltered base gold table but can read the row-filtered view), the persona
switcher contract (seller|manager|empty only, never admin) and persona scoping of the API.
"""

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.after_app]

APP_NAME = "fleetwise-seller-hub"


@pytest.fixture(scope="module")
def app(ws):
    try:
        a = ws.apps.get(APP_NAME)
    except Exception as e:  # noqa: BLE001 - not deployed yet
        pytest.skip(f"{APP_NAME} not found: {e}")
    if not (a.app_status and a.app_status.state and a.app_status.state.value == "RUNNING"):
        pytest.skip(f"{APP_NAME} is not RUNNING ({a.app_status})")
    token = ws.config.oauth_token().access_token
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"

    def call(method: str, path: str, **kw) -> requests.Response:
        return s.request(method, a.url.rstrip("/") + path, timeout=120, **kw)

    yield call
    call("PUT", "/api/persona", json={"persona": "seller"})  # leave the demo on Jordan


def test_sp_second_principal_governance(app):
    """R16: as the app SP, the base gold table is denied and the row-filtered view works."""
    body = app("GET", "/api/health/governance").json()
    assert body["base_table"]["ok"] is False, body
    assert body["base_table"]["error"] in {"PERMISSION_DENIED", "INSUFFICIENT_PERMISSIONS", "TABLE_OR_VIEW_NOT_FOUND"}, body
    assert body["view"]["ok"] is True, body
    assert body["pass"] is True


def test_persona_rejects_admin_and_unknown(app):
    for bad in ({"persona": "admin"}, {"persona": "empty-demo"}, {"persona": "seller", "email": "x@y"}):
        assert app("PUT", "/api/persona", json=bad).status_code == 400, bad


def test_persona_scopes_home(app):
    assert app("PUT", "/api/persona", json={"persona": "seller"}).status_code == 200
    me = app("GET", "/api/me").json()
    seller = app("GET", "/api/home").json()
    assert me["persona_name"] == "Jordan Rivera" and me["visible_owner_count"] == 1, me
    assert seller["priority_deals"] and all(d["owner_name"] == "Jordan Rivera" for d in seller["priority_deals"])
    assert len(seller["priority_deals"]) <= 15 and len(seller["actions"]) <= 20

    assert app("PUT", "/api/persona", json={"persona": "manager"}).status_code == 200
    manager = app("GET", "/api/home").json()
    assert app("GET", "/api/me").json()["visible_owner_count"] > 1
    assert {d["owner_name"] for d in manager["priority_deals"]} - {"Morgan Lee"}, "manager sees the team"

    assert app("PUT", "/api/persona", json={"persona": "empty"}).status_code == 200
    empty = app("GET", "/api/home").json()
    assert empty["priority_deals"] == [], empty


def test_deal_outside_scope_is_404(app):
    assert app("PUT", "/api/persona", json={"persona": "manager"}).status_code == 200
    team_deal = app("GET", "/api/home").json()["priority_deals"][0]["opportunity_id"]
    assert app("PUT", "/api/persona", json={"persona": "empty"}).status_code == 200
    assert app("GET", f"/api/deals/{team_deal}").status_code == 404


def test_health_db(app):
    body = app("GET", "/api/health/db").json()
    assert body["ok"] is True and body["latency_ms"] >= 0
