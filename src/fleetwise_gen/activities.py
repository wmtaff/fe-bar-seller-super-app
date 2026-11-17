"""OpportunityHistory, Leads, and Task/Event activities."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone

from . import config as C
from . import names as N
from .entities import World, _company_name, _slug, beta, dts, faker_for, phone, rng_for
from .ids import sfid


# --------------------------------------------------------------------------- history
def history_rows(w: World, o: dict, start_idx: int) -> list[dict]:
    if o["IsClosed"]:
        stages = C.OPEN_STAGES[: o["path_len"]] + [o["StageName"]]
        start, end = o["created"], o["close"]
    else:
        stages = C.OPEN_STAGES[: C.OPEN_STAGES.index(o["StageName"]) + 1]
        start, end = o["created"], date.fromisoformat(o["last_modified"][:10])
    n = len(stages)
    rows = []
    for k, st in enumerate(stages):
        d = start if k == 0 else start + timedelta(days=round((end - start).days * k / max(1, n - 1)))
        rows.append(hist_row(w, start_idx + k, o, st, dts(d, 16, 5 + k)))
    return rows


def hist_row(w: World, idx: int, o: dict, stage: str, created_ts: str) -> dict:
    return {
        "Id": sfid("OpportunityHistory", idx, w.seed), "OpportunityId": o["Id"],
        "StageName": stage, "Amount": o["Amount"], "CloseDate": o["close"].isoformat(),
        "Probability": C.STAGE_PROB[stage], "ForecastCategory": C.STAGE_FORECAST[stage],
        "CreatedById": o["OwnerId"], "CreatedDate": created_ts,
    }


# --------------------------------------------------------------------------- leads
LEAD_NOTES_HIGH = [
    "Requested pricing for {fleet} vehicles; wants to be live before {month}.",
    "Budget approved for telematics this year; evaluating two vendors.",
    "Asked for a demo of {product} for the safety team as soon as possible.",
    "Insurance carrier is requiring dash cams at their next renewal.",
    "Had a DOT audit finding last quarter; needs ELD fixed fast.",
    "Ops director reached out directly after a referral from a current customer.",
]
LEAD_NOTES_MID = [
    "Interested in fuel savings; timeline unclear.",
    "Attended the driver safety webinar; asked about driver privacy.",
    "Wants to understand total cost for {fleet} vehicles before involving finance.",
    "Exploring options for next year's budget.",
]
LEAD_NOTES_LOW = [
    "Downloaded the ELD compliance guide; no stated project.",
    "Just browsing pricing; very price sensitive.",
    "Said they're happy with their current setup for now.",
    "Small fleet, owner-operated; may not need a platform.",
    "Student researching fleet technology.",
]
LEAD_COMPETITOR_NOTE = "Currently on {comp}; contract ends in {month}."
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def _lead(w: World, idx: int, rng: random.Random, fk, created: datetime, used: set[str],
          sellers_by_region: dict[str, list[dict]], age_days: int) -> tuple[dict, dict]:
    intent = beta(rng, 1.4, 3.0)
    will_win = rng.random() < 0.03 + 0.85 * intent ** 2
    industry = rng.choice(C.INDUSTRIES)
    company = _company_name(rng, fk, industry, used)
    region = rng.choice(["West", "Central", "East"])
    state = rng.choice(C.REGION_STATES[region])
    fleet = int(10 * (900 / 10) ** (rng.random() ** 1.4))
    product = rng.choice(C.PRODUCTS)
    month = MONTHS[(created.month + rng.randint(1, 5)) % 12]
    bank = LEAD_NOTES_HIGH if intent >= 0.55 else LEAD_NOTES_MID if intent >= 0.3 else LEAD_NOTES_LOW
    notes = [n.format(fleet=fleet, month=month, product=product)
             for n in rng.sample(bank, rng.choice([1, 1, 2]))]
    comps = []
    if rng.random() < 0.3:
        comps = [rng.choice(C.COMPETITORS)]
        notes.append(LEAD_COMPETITOR_NOTE.format(comp=comps[0], month=MONTHS[rng.randint(0, 11)]))
    fn, ln = fk.first_name(), fk.last_name()
    if age_days < 7:
        status, converted = "Open - Not Contacted", False
    elif age_days < 45:
        status, converted = "Working - Contacted", False
    elif will_win:
        status, converted = "Qualified", age_days > 60
    else:
        status, converted = rng.choice(["Unqualified", "Unqualified", "Nurture"]), False
    owner = rng.choice(sellers_by_region[region])
    interest = sorted({product, rng.choice(C.PRODUCTS)}, key=C.PRODUCTS.index)
    lead = {
        "Id": sfid("Lead", idx, w.seed), "FirstName": fn, "LastName": ln, "Name": f"{fn} {ln}",
        "Company": company, "Title": rng.choice(N.LEAD_TITLES),
        "Email": f"{fn[0]}{ln}".lower().replace("'", "").replace(" ", "") + "@" + _slug(company) + ".com",
        "Phone": phone(rng), "LeadSource": rng.choice(N.LEAD_SOURCES), "Status": status,
        "Industry": industry, "State": state, "Country": "United States",
        "Fleet_Size__c": fleet, "Products_Of_Interest__c": ";".join(interest),
        "Description": " ".join(notes), "OwnerId": owner["Id"], "IsConverted": converted,
        "ConvertedDate": (created.date() + timedelta(days=rng.randint(40, 60))).isoformat() if converted else None,
        "CreatedDate": C.fmt_ts(created),
        "LastModifiedDate": C.fmt_ts(created + timedelta(days=min(age_days, rng.randint(0, 50)))),
    }
    truth = truth_row("Lead", lead["Id"], intent, comps, [], will_win, created.date().isoformat())
    return lead, truth


def _sellers_by_region(w: World) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"West": [], "Central": [], "East": []}
    for u in w.users:
        if u["Title"].endswith("Account Executive") and u["Segment__c"] != "Enterprise" \
                and u["Id"] != w.taylor_id:
            out[u["Region__c"]].append(u)
    return out


def leads_init(w: World, used_names: set[str]) -> tuple[list[dict], list[dict]]:
    rng = rng_for(w.seed, "leads")
    fk = faker_for(w.seed, 4)
    sbr = _sellers_by_region(w)
    as_of = datetime.combine(C.AS_OF_DATE, time(12), tzinfo=timezone.utc)
    leads, truth = [], []
    for i in range(C.N_LEADS):
        age = int(365 * rng.random() ** 1.2)
        created = as_of - timedelta(days=age, minutes=rng.randint(0, 600))
        lead, t = _lead(w, i, rng, fk, created, used_names, sbr, age)
        leads.append(lead)
        truth.append(t)
    return leads, truth


def leads_increment(w: World, batch: int, used_names: set[str]) -> tuple[list[dict], list[dict]]:
    rng = rng_for(w.seed, "leads", "batch", batch)
    fk = faker_for(w.seed, 100 + batch)
    sbr = _sellers_by_region(w)
    ts = C.batch_ts(batch)
    base = C.INC_INDEX_BASE + (batch - 1) * C.INC_INDEX_STRIDE
    leads, truth = [], []
    for i in range(C.INC_LEADS):
        created = ts - timedelta(minutes=rng.randint(1, 59))
        lead, t = _lead(w, base + i, rng, fk, created, used_names, sbr, 0)
        lead["LastModifiedDate"] = C.fmt_ts(ts)
        leads.append(lead)
        truth.append(t)
    return leads, truth


def truth_row(record_type: str, record_id: str, intent: float, competitors: list[str],
              next_steps: list[dict], will_win: bool, snapshot_date: str, *,
              quotes: list[dict] | None = None, call_type: str | None = None,
              sentiment: str | None = None, opportunity_id: str | None = None) -> dict:
    return {
        "record_type": record_type, "record_id": record_id, "true_intent": round(intent, 4),
        "planted_competitors": competitors, "planted_next_steps": next_steps,
        "will_win": bool(will_win), "snapshot_date": snapshot_date,
        "competitor_quotes": quotes or [], "call_type": call_type,
        "planted_sentiment": sentiment, "opportunity_id": opportunity_id,
    }


# --------------------------------------------------------------------------- activities
CALL_SUBJECTS = ["Call - discovery follow-up", "Call - left voicemail", "Call - pricing questions",
                 "Call - check-in", "Call - reference call prep", "Call - install scheduling"]
EMAIL_SUBJECTS = ["Email: Sent proposal", "Email: Follow-up on demo", "Email: Shared ROI model",
                  "Email: Security questionnaire", "Email: Intro to solutions engineer",
                  "Email: Checking in", "Email: Sent order form", "Email: Recap and next steps"]
MEETING_SUBJECTS = ["Onsite visit - yard walk", "Meeting - product demo", "Meeting - executive alignment",
                    "Meeting - install planning", "Meeting - QBR", "Lunch with operations team"]
DESCRIPTIONS = [None, None, "Left a voicemail, will try again Thursday.", "Customer asked for references.",
                "Sent pricing for the full fleet.", "Discussed install logistics.",
                "No response yet.", "Good conversation, they are comparing options.",
                "Asked about contract terms.", "Walked through the safety dashboard."]


def _business_dt(d: date, rng: random.Random) -> datetime:
    if d.weekday() == 5:
        d -= timedelta(days=1)
    elif d.weekday() == 6:
        d += timedelta(days=1)
    return datetime.combine(d, time(rng.randint(15, 22), rng.choice([0, 15, 30, 45])),
                            tzinfo=timezone.utc)


def activity(w: World, rng: random.Random, kind_idx: dict[str, int], acc: dict, o: dict | None,
             when: datetime, future: bool = False, created: datetime | None = None,
             last_modified: datetime | None = None) -> tuple[str, dict]:
    contacts = w.contacts_by_account[acc["Id"]]
    who = rng.choice(contacts)["Id"]
    owner = o["OwnerId"] if o else acc["OwnerId"]
    if created is None:
        created = when - timedelta(days=rng.randint(0, 3)) if future else when
    if last_modified is None:
        last_modified = created if future else when
    lm = last_modified
    if rng.random() < 0.7:
        obj = "Task"
        is_call = rng.random() < 0.45
        idx = kind_idx[obj]
        kind_idx[obj] += 1
        row = {
            "Id": sfid("Task", idx, w.seed),
            "Subject": rng.choice(CALL_SUBJECTS if is_call else EMAIL_SUBJECTS),
            "Type": "Call" if is_call else "Email", "TaskSubtype": "Call" if is_call else "Email",
            "Status": "Not Started" if future else "Completed",
            "Priority": "High" if rng.random() < 0.15 else "Normal",
            "ActivityDate": when.date().isoformat(), "WhoId": who,
            "WhatId": o["Id"] if o else None, "AccountId": acc["Id"], "OwnerId": owner,
            "CallDurationInSeconds": rng.randint(30, 1500) if is_call and not future else None,
            "Description": rng.choice(DESCRIPTIONS), "IsClosed": not future,
            "CreatedDate": C.fmt_ts(created), "LastModifiedDate": C.fmt_ts(lm),
        }
    else:
        obj = "Event"
        idx = kind_idx[obj]
        kind_idx[obj] += 1
        dur = rng.choice([30, 30, 45, 60, 90])
        row = event_row(w, idx, rng.choice(MEETING_SUBJECTS), when, dur,
                        rng.choice(["Google Meet", "Google Meet", "Onsite", "Customer office"]),
                        who, o["Id"] if o else None, acc["Id"], owner, rng.choice(DESCRIPTIONS),
                        created, lm)
    return obj, row


def event_row(w: World, idx: int, subject: str, start: datetime, dur: int, location: str,
              who: str, what: str | None, account_id: str, owner: str, desc: str | None,
              created: datetime, lm: datetime) -> dict:
    return {
        "Id": sfid("Event", idx, w.seed), "Subject": subject, "Type": "Meeting",
        "StartDateTime": C.fmt_ts(start), "EndDateTime": C.fmt_ts(start + timedelta(minutes=dur)),
        "DurationInMinutes": dur, "Location": location, "WhoId": who, "WhatId": what,
        "AccountId": account_id, "OwnerId": owner, "Description": desc,
        "CreatedDate": C.fmt_ts(created), "LastModifiedDate": C.fmt_ts(lm),
    }


def activities_init(w: World, budget: int, kind_idx: dict[str, int]) -> dict[str, list[dict]]:
    rng = rng_for(w.seed, "activities")
    out: dict[str, list[dict]] = {"Task": [], "Event": []}
    seg_f = {"SMB": 0.7, "Mid-Market": 1.0, "Enterprise": 1.5}
    acct_level = int(budget * 0.06)
    opp_budget = budget - acct_level
    weights = []
    for o in w.opps:
        acc = w.account_by_id[o["AccountId"]]
        x = (0.35 + o["intent"]) * seg_f[acc["Segment__c"]] * (1.8 if not o["IsClosed"] else 1.0)
        if o["OwnerId"] == w.jordan_id:
            x *= 4
        weights.append(x)
    scale = opp_budget / sum(weights)
    as_of = C.AS_OF_DATE
    for o, wt in zip(w.opps, weights):
        acc = w.account_by_id[o["AccountId"]]
        n = int(wt * scale + rng.random())
        for k in range(n):
            if not o["IsClosed"] and k == 0 and rng.random() < 0.25 + 0.5 * o["intent"]:
                when = _business_dt(as_of + timedelta(days=rng.randint(1, 10)), rng)
                obj, row = activity(w, rng, kind_idx, acc, o, when, future=True,
                                    created=_business_dt(as_of - timedelta(days=rng.randint(0, 3)), rng))
            else:
                start = o["created"]
                end = o["close"] if o["IsClosed"] else as_of
                span = max(0, (end - start).days)
                if o["IsClosed"]:
                    d = start + timedelta(days=rng.randint(0, span))
                else:
                    a = 1.5 - 1.1 * o["intent"]
                    d = start + timedelta(days=int(span * rng.random() ** a))
                when = min(_business_dt(d, rng), datetime.combine(as_of, time(11), tzinfo=timezone.utc))
                obj, row = activity(w, rng, kind_idx, acc, o, when)
            out[obj].append(row)
    accts = [a for a in w.accounts]
    for _ in range(acct_level):
        acc = rng.choice(accts)
        d = as_of - timedelta(days=int(365 * rng.random() ** 1.3))
        when = min(_business_dt(d, rng), datetime.combine(as_of, time(11), tzinfo=timezone.utc))
        obj, row = activity(w, rng, kind_idx, acc, None, when)
        out[obj].append(row)
    return out
