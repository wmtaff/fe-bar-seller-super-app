"""Product usage telemetry (daily per customer account) and support tickets."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone

from . import config as C
from .entities import World, rng_for
from .ids import ticket_id

USAGE_COLUMNS = (["account_id", "usage_date", "total_vehicles", "active_vehicles",
                  "driver_app_logins", "admin_logins", "safety_events"]
                 + [C.PRODUCT_COL[p] for p in C.PRODUCTS])


def trend_map(w: World) -> dict[str, float]:
    """90-day usage slope per customer: healthy accounts grow, at-risk ones drop.

    Accounts with an open opp blend in that opp's hidden intent, so usage is a
    real (noisy) signal for the scorer.
    """
    open_by_acc: dict[str, list[float]] = {}
    for o in w.opps:
        if not o["IsClosed"]:
            open_by_acc.setdefault(o["AccountId"], []).append(o["intent"])
    out = {}
    for a in w.accounts:
        if a["Type"] != "Customer":
            continue
        h = w.account_health[a["Id"]]
        x = 0.5 * h + 0.5 * (sum(open_by_acc[a["Id"]]) / len(open_by_acc[a["Id"]])
                             if a["Id"] in open_by_acc else h)
        # slope over 90 days; x < 0.3 => meaningful decline (-15% .. -45%)
        out[a["Id"]] = (x - 0.5) * 0.6 if x >= 0.3 else -0.15 - (0.3 - x) * 1.2
    return out


def usage_row(w: World, acc: dict, slope: float, t: int, d: date, rng: random.Random) -> list:
    """t = days since window start (0..89 at init; 89 = as-of date; 89+N for batch N)."""
    h = w.account_health[acc["Id"]]
    fleet = acc["Fleet_Size__c"]
    base_util = 0.55 + 0.4 * h
    level = max(0.05, base_util * (1 + slope * (t - 89) / 89))
    weekend = 0.55 if d.weekday() >= 5 else 1.0
    active = min(fleet, max(0, round(fleet * level * weekend * rng.uniform(0.93, 1.07))))
    owned = set((acc["Products_Owned__c"] or "").split(";"))
    row = [acc["Id"], d.isoformat(), fleet, active,
           round(active * rng.uniform(0.6, 0.9)), max(0, round(rng.gauss(2 + fleet / 120, 1))),
           max(0, round(active * rng.uniform(0.01, 0.05) * (1.6 - h)))]
    for p in C.PRODUCTS:
        if p in owned:
            row.append(round(min(1.0, max(0.0, (0.45 + 0.5 * h) * (1 + slope * (t - 89) / 89)
                                          + rng.uniform(-0.03, 0.03))), 3))
        else:
            row.append(0.0)
    return row


def usage_init(w: World) -> list[list]:
    trends = trend_map(w)
    rows = []
    start = C.AS_OF_DATE - timedelta(days=C.USAGE_DAYS - 1)
    for a in w.accounts:
        if a["Id"] not in trends:
            continue
        rng = rng_for(w.seed, "usage", a["Id"])
        for t in range(C.USAGE_DAYS):
            rows.append(usage_row(w, a, trends[a["Id"]], t, start + timedelta(days=t), rng))
    return rows


def usage_increment(w: World, batch: int) -> list[list]:
    """One new usage day: as-of date + batch days."""
    trends = trend_map(w)
    d = C.AS_OF_DATE + timedelta(days=batch)
    rows = []
    for a in w.accounts:
        if a["Id"] in trends:
            rng = rng_for(w.seed, "usage", a["Id"], "batch", batch)
            rows.append(usage_row(w, a, trends[a["Id"]], 89 + batch, d, rng))
    return rows


# --------------------------------------------------------------------------- tickets
SUBJECTS = {
    "Vehicle Telematics": ["Vehicles not showing live location", "GPS pings delayed by several minutes",
                           "Trip history missing for one unit", "Gateway offline after battery replacement"],
    "AI Dash Cams": ["Camera not uploading event clips", "False harsh-braking alerts on gravel roads",
                     "Dash cam lens fogging in cold mornings", "Need footage retrieval for an accident claim"],
    "Driver Safety": ["Driver scorecards not updating", "Coaching queue showing duplicate events",
                      "Question about speeding thresholds by road type"],
    "Fuel & Maintenance": ["Fault codes not syncing to maintenance schedule", "Fuel card import failing",
                           "Preventive maintenance reminders sent to wrong manager"],
    "Compliance/ELD": ["Driver unable to certify logs", "ELD malfunction indicator on tablet",
                       "Roadside inspection log transfer failed", "Unassigned driving time showing up"],
    "Equipment Monitoring": ["Asset tracker not checking in", "Trailer geofence alerts not firing",
                             "Engine hours missing for generator"],
}
CHANNELS = ["Email", "Phone", "Chat", "Web Form"]


def _ticket(w: World, i: int, acc: dict, created: datetime, rng: random.Random,
            as_of: datetime) -> dict:
    h = w.account_health[acc["Id"]]
    owned = (acc["Products_Owned__c"] or "Vehicle Telematics").split(";")
    product = rng.choice(owned)
    r = rng.random()
    p1 = 0.03 + 0.12 * (1 - h)
    sev = "P1" if r < p1 else "P2" if r < p1 + 0.2 else "P3" if r < p1 + 0.65 else "P4"
    age_h = (as_of - created).total_seconds() / 3600
    if age_h > 24 * 14:
        status = "Closed" if rng.random() < 0.8 else "Solved"
    elif age_h > 48:
        status = rng.choice(["Solved", "Solved", "Pending", "Open"])
    else:
        status = rng.choice(["Open", "Open", "Pending"])
    solved = status in ("Solved", "Closed")
    resolve_h = rng.uniform(1, 30) * {"P1": 1, "P2": 3, "P3": 8, "P4": 16}[sev]
    solved_at = created + timedelta(hours=min(resolve_h, max(1.0, age_h - 1))) if solved else None
    csat = None
    if solved and rng.random() < 0.45:
        csat = max(1, min(5, round(rng.gauss(2.2 + 2.6 * h, 0.8))))
    contacts = w.contacts_by_account[acc["Id"]]
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {
        "ticket_id": ticket_id(i), "account_id": acc["Id"],
        "requester_contact_id": rng.choice(contacts)["Id"], "product": product,
        "subject": rng.choice(SUBJECTS[product]), "severity": sev, "status": status,
        "channel": rng.choice(CHANNELS), "created_at": created.strftime(fmt),
        "updated_at": (solved_at or min(as_of, created + timedelta(hours=rng.uniform(0.2, 12)))).strftime(fmt),
        "solved_at": solved_at.strftime(fmt) if solved_at else None,
        "first_response_minutes": int(rng.uniform(4, 240) * (0.3 if sev == "P1" else 1)),
        "csat_score": csat,
    }


def _ticket_weights(w: World) -> tuple[list[dict], list[float]]:
    custs = [a for a in w.accounts if a["Type"] == "Customer"]
    weights = [a["Fleet_Size__c"] ** 0.5 * (1.6 - w.account_health[a["Id"]]) for a in custs]
    return custs, weights


def tickets_init(w: World) -> list[dict]:
    rng = rng_for(w.seed, "tickets")
    custs, weights = _ticket_weights(w)
    as_of = datetime.combine(C.AS_OF_DATE, time(12), tzinfo=timezone.utc)
    out = []
    for i, acc in enumerate(rng.choices(custs, weights=weights, k=C.N_TICKETS)):
        created = as_of - timedelta(hours=365 * 24 * rng.random() ** 1.3)
        out.append(_ticket(w, i, acc, created, rng, as_of))
    return out


def tickets_increment(w: World, batch: int) -> list[dict]:
    rng = rng_for(w.seed, "tickets", "batch", batch)
    custs, weights = _ticket_weights(w)
    ts = C.batch_ts(batch)
    base = C.INC_INDEX_BASE + (batch - 1) * C.INC_INDEX_STRIDE
    out = []
    for i, acc in enumerate(rng.choices(custs, weights=weights, k=C.INC_TICKETS)):
        created = ts - timedelta(minutes=rng.uniform(1, 59))
        t = _ticket(w, base + i, acc, created, rng, ts)
        t["updated_at"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append(t)
    return out
