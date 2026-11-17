"""Top-level orchestration: generate(mode, out_dir, seed, batch) -> row counts."""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as C
from .activities import (_business_dt, activities_init, activity, event_row, hist_row,
                         history_rows, leads_increment, leads_init, truth_row)
from .entities import World, build_core, opp_row, rng_for
from .ids import MeetingIds
from .transcripts import render_call
from .usage import USAGE_COLUMNS, tickets_increment, tickets_init, usage_increment, usage_init
from .writer import write_csv, write_documents, write_jsonl, write_manifest

SF_OBJECTS = ["User", "UserRole", "Account", "Contact", "Opportunity", "OpportunityHistory",
              "Lead", "Task", "Event"]
CALL_LABEL = {"discovery": "Discovery call", "demo_followup": "Demo follow-up",
              "pricing": "Pricing review", "renewal": "Renewal review"}


# --------------------------------------------------------------------------- calls
def _call_type_for_stage(o: dict) -> str:
    if o["Type"] == "Renewal":
        return "renewal"
    s = o["StageName"]
    if s in ("Qualification", "Discovery"):
        return "discovery"
    if s == "Demo":
        return "demo_followup"
    return "pricing"


def _call_types(o: dict, n: int) -> list[str]:
    if o["Type"] == "Renewal":
        return ["renewal"] * n
    if o["IsClosed"]:
        return ["discovery", "pricing"][:n] if n <= 2 else ["discovery"] + ["demo_followup"] * (n - 2) + ["pricing"]
    last = _call_type_for_stage(o)
    if n == 1:
        return [last]
    first = "discovery" if last in ("discovery", "demo_followup") else "demo_followup"
    return [first] * (n - 1) + [last]


def _attendees(w: World, rng: random.Random, acc: dict, call_type: str) -> list[dict]:
    contacts = w.contacts_by_account[acc["Id"]]
    want = {"pricing": "CFO", "demo_followup": "IT", "renewal": "VP Operations",
            "discovery": "Fleet Manager"}[call_type]
    k = rng.choice([1, 2, 2, 3])
    chosen = rng.sample(contacts, k)
    pref = [c for c in contacts if c["Role__c"] == want]
    if pref and pref[0] not in chosen:
        chosen = [pref[0]] + chosen[: k - 1] if k > 1 else [pref[0]]
    return chosen


class CallFactory:
    """Renders calls + their Event rows + truth rows, with stable indices."""

    def __init__(self, w: World, kind_idx: dict[str, int], mids: MeetingIds):
        self.w = w
        self.kind_idx = kind_idx
        self.mids = mids

    def make(self, rng: random.Random, m_index: int, o: dict, call_type: str, started: datetime,
             mention_quote: bool, created_lm: datetime | None = None):
        w = self.w
        acc = w.account_by_id[o["AccountId"]]
        seller = w.user_by_id[o["OwnerId"]]
        se = rng.choice(w.sales_engineers) if (call_type == "demo_followup" or
                                               (call_type == "pricing" and rng.random() < 0.3)) else None
        contacts = _attendees(w, rng, acc, call_type)
        quote = o["quote"] if mention_quote else None
        mention = [c for c in o["competitors"]
                   if (quote and quote["competitor"] == c) or rng.random() < 0.7]
        mid = self.mids.get(m_index)
        tx, planted = render_call(rng, meeting_id=mid, call_type=call_type, started_at=started,
                                  opp=o, account=acc, seller=seller, se_name=se, contacts=contacts,
                                  mention_competitors=mention, quote=quote)
        ev_idx = self.kind_idx["Event"]
        self.kind_idx["Event"] += 1
        ev = event_row(w, ev_idx, f"{CALL_LABEL[call_type]} - {acc['Name']}", started,
                       tx["duration_min"], "Google Meet", contacts[0]["Id"], o["Id"], acc["Id"],
                       o["OwnerId"], f"Google Meet {mid}",
                       created_lm or started - timedelta(days=rng.randint(1, 7)),
                       created_lm or started)
        snap = o["snapshot"].isoformat() if o["IsClosed"] else C.AS_OF
        tr = truth_row("Transcript", mid, o["intent"], planted["competitors"], planted["next_steps"],
                       o["will_win"], snap, quotes=planted["quotes"], call_type=call_type,
                       sentiment=planted["sentiment"], opportunity_id=o["Id"])
        return tx, ev, tr, planted


def _spread_dates(rng: random.Random, lo: date, hi: date, n: int) -> list[date]:
    span = max(1, (hi - lo).days)
    return sorted(lo + timedelta(days=rng.randint(0, span)) for _ in range(n))


def plan_init_calls(w: World) -> list[tuple[dict, list[tuple[date, bool]]]]:
    """[(opp, [(call_date, mention_quote), ...])] totalling exactly N_TRANSCRIPTS calls."""
    rng = rng_for(w.seed, "callplan")
    as_of = C.AS_OF_DATE
    plan = []
    jordan_open = [o for o in w.opps if o["OwnerId"] == w.jordan_id and not o["IsClosed"]]
    for j, o in enumerate(jordan_open[: C.JORDAN_TRANSCRIBED_OPPS]):
        n = 2 if j in (0, 3, 5, 7) else 1
        dates = _spread_dates(rng, o["created"] + timedelta(days=3), as_of - timedelta(days=1), n)
        plan.append((o, [(d, k == n - 1 and o["quote"] is not None) for k, d in enumerate(dates)]))
    used = sum(len(c) for _, c in plan)
    # recent closed opps: one call before and one after the 60% snapshot
    recent_closed = [o for o in w.opps if o["IsClosed"] and o["close"] >= as_of - timedelta(days=150)
                     and (o["close"] - o["created"]).days >= 20]
    for o in rng.sample(recent_closed, 100):
        before = o["created"] + timedelta(days=rng.randint(2, max(2, (o["snapshot"] - o["created"]).days - 1)))
        after = o["snapshot"] + timedelta(days=rng.randint(1, max(1, (o["close"] - o["snapshot"]).days - 1)))
        q = o["quote"] is not None and after.isoformat() <= o["quote"]["expires_on"]
        plan.append((o, [(before, False), (after, q)]))
    used += 200
    remaining = C.N_TRANSCRIPTS - used
    pool = [o for o in w.opps if not o["IsClosed"] and o["OwnerId"] != w.jordan_id
            and o["StageName"] != "Qualification"]
    n_opps = 300
    doubles = remaining - n_opps
    for k, o in enumerate(rng.sample(pool, n_opps)):
        n = 2 if k < doubles else 1
        dates = _spread_dates(rng, o["created"] + timedelta(days=2), as_of - timedelta(days=1), n)
        plan.append((o, [(d, k2 == n - 1 and o["quote"] is not None and rng.random() < 0.7)
                         for k2, d in enumerate(dates)]))
    return plan


# --------------------------------------------------------------------------- init
def init_calls(w: World, factory: CallFactory):
    """Render the init calls and derive Opportunity.NextStep (deterministic).

    Both --init and --increment run this, so NextStep (taken from the seller's
    spoken next step) survives into increment rows.
    """
    rng = rng_for(w.seed, "calls")
    txs, events, tx_truth = [], [], []
    steps_by_opp: dict[str, list[dict]] = {}
    m = 0
    for o, calls in plan_init_calls(w):
        types = _call_types(o, len(calls))
        for (d, q), ct in zip(calls, types):
            started = _business_dt(d, rng)
            tx, ev, tr, planted = factory.make(rng, m, o, ct, started, q)
            m += 1
            txs.append(tx)
            events.append(ev)
            tx_truth.append(tr)
            steps_by_opp.setdefault(o["Id"], []).extend(planted["next_steps"])
            seller_steps = [s for s in planted["next_steps"] if s["owner"] == w.user_by_id[o["OwnerId"]]["Name"]]
            if seller_steps:
                o["next_step_field"] = seller_steps[0]["action"].capitalize()
    assert m == C.N_TRANSCRIPTS, m

    rng_ns = rng_for(w.seed, "nextstep")
    generic = ["Follow up on proposal", "Schedule demo", "Send pricing", "Confirm decision makers",
               "Check in after budget review"]
    for o in w.opps:
        if "next_step_field" not in o and not o["IsClosed"] and rng_ns.random() < 0.4:
            o["next_step_field"] = rng_ns.choice(generic)
    return txs, events, tx_truth, steps_by_opp


def opp_truth_row(o: dict, steps_by_opp: dict[str, list[dict]]) -> dict:
    return truth_row("Opportunity", o["Id"], o["intent"], o["competitors"],
                     steps_by_opp.get(o["Id"], []), o["will_win"],
                     (o["snapshot"] if o["IsClosed"] else C.AS_OF_DATE).isoformat(),
                     quotes=[o["quote"]] if o["quote"] else [])


def build_init(seed: int) -> dict:
    w = build_core(seed)
    kind_idx = {"Task": 0, "Event": 0}
    factory = CallFactory(w, kind_idx, MeetingIds(seed))
    # transcripts first (their Events take the first Event indices)
    txs, events, tx_truth, steps_by_opp = init_calls(w, factory)

    acts = activities_init(w, C.TARGET_ACTIVITIES - len(events), kind_idx)
    acts["Event"] = events + acts["Event"]

    hist, h = [], 0
    for o in w.opps:
        rows = history_rows(w, o, h)
        h += len(rows)
        hist += rows

    used_names = {a["Name"] for a in w.accounts}
    leads, lead_truth = leads_init(w, used_names)

    opp_truth = [opp_truth_row(o, steps_by_opp) for o in w.opps]
    return {
        "User": w.users, "UserRole": w.roles, "Account": w.accounts, "Contact": w.contacts,
        "Opportunity": [opp_row(w, o) for o in w.opps], "OpportunityHistory": hist,
        "Lead": leads, "Task": acts["Task"], "Event": acts["Event"],
        "meet_transcripts": txs, "product_usage": usage_init(w),
        "support_tickets": tickets_init(w), "truth": opp_truth + lead_truth + tx_truth,
    }


# --------------------------------------------------------------------------- increments
def apply_stage_changes(w: World, batch: int) -> tuple[list[dict], list[dict], list[dict]]:
    """Mutate opp state for `batch`; return (changed opp rows, history rows, opps closed now).

    An opp closed in an increment gets snapshot_date = created + 60% of its
    lifecycle (strictly before the close date), like init's closed opps.
    """
    rng = rng_for(w.seed, "inc", batch, "stage")
    ts = C.batch_ts(batch)
    ts_s = C.fmt_ts(ts)
    cands = [o for o in w.opps if not o["IsClosed"]
             and not (o["OwnerId"] == w.jordan_id and o["StageName"] == "Negotiation")]
    chosen = sorted(rng.sample(cands, min(C.INC_STAGE_CHANGES, len(cands))), key=lambda o: o["idx"])
    base = C.INC_INDEX_BASE + (batch - 1) * C.INC_INDEX_STRIDE
    opp_rows, hist, closed_now = [], [], []
    for i, o in enumerate(chosen):
        jordan = o["OwnerId"] == w.jordan_id
        st = o["StageName"]
        late = st in ("Proposal", "Negotiation")
        if not jordan and o["will_win"] and st == "Negotiation" and rng.random() < 0.6:
            o.update(StageName="Closed Won", IsClosed=True, IsWon=True, close=ts.date())
        elif not jordan and not o["will_win"] and ((late and rng.random() < 0.4) or rng.random() < 0.1):
            o.update(StageName="Closed Lost", IsClosed=True, IsWon=False, close=ts.date(),
                     loss_reason="Lost to Competitor" if o["competitors"] else
                     rng.choice(["No Decision", "Timing", "Budget"]))
            if o["competitors"]:
                o["crm_competitor"] = o["crm_competitor"] or o["competitors"][0]
        elif st != "Negotiation":
            o["StageName"] = C.OPEN_STAGES[C.OPEN_STAGES.index(st) + 1]
            if rng.random() < 0.3:
                o["Amount"] = int(round(o["Amount"] * rng.uniform(0.9, 1.1), -2))
        else:
            o["close"] = max(o["close"], ts.date()) + timedelta(days=rng.randint(7, 21))
        if o["IsClosed"]:
            cycle = (o["close"] - o["created"]).days
            o["snapshot"] = o["created"] + timedelta(days=max(1, min(cycle - 1, round(0.6 * cycle))))
            closed_now.append(o)
        o["last_modified"] = ts_s
        opp_rows.append(opp_row(w, o, ts_s))
        hist.append(hist_row(w, base + i, o, o["StageName"], ts_s))
    return opp_rows, hist, closed_now


def build_increment(seed: int, batch: int) -> dict:
    w = build_core(seed)
    mids = MeetingIds(seed)
    # replay init calls: derives NextStep + spoken next steps, and reserves init meeting ids
    _, _, _, steps_by_opp = init_calls(w, CallFactory(w, {"Task": 0, "Event": 0}, mids))
    for k in range(1, batch):
        apply_stage_changes(w, k)  # replay earlier batches (state only)
        kb = C.INC_INDEX_BASE + (k - 1) * C.INC_INDEX_STRIDE
        for i in range(C.INC_TRANSCRIPTS):
            mids.get(kb + i)  # reserve earlier batches' meeting ids in canonical order
    opp_rows, hist, closed_now = apply_stage_changes(w, batch)

    ts = C.batch_ts(batch)
    base = C.INC_INDEX_BASE + (batch - 1) * C.INC_INDEX_STRIDE
    kind_idx = {"Task": base, "Event": base}
    factory = CallFactory(w, kind_idx, mids)
    rng = rng_for(seed, "inc", batch, "calls")
    open_opps = [o for o in w.opps if not o["IsClosed"]]
    jordan_open = [o for o in open_opps if o["OwnerId"] == w.jordan_id]
    others = [o for o in open_opps if o["OwnerId"] != w.jordan_id]
    picked = rng.sample(jordan_open, min(3, len(jordan_open)))
    picked += rng.sample(others, C.INC_TRANSCRIPTS - len(picked))
    txs, events, tx_truth = [], [], []
    for k, o in enumerate(picked):
        started = ts - timedelta(minutes=rng.randint(35, 120))
        q = o["quote"] is not None and o["quote"]["expires_on"] >= started.date().isoformat() \
            and (o["OwnerId"] == w.jordan_id or rng.random() < 0.7)
        tx, ev, tr, _ = factory.make(rng, base + k, o, _call_type_for_stage(o), started, q,
                                     created_lm=ts)
        txs.append(tx)
        events.append(ev)
        tx_truth.append(tr)

    rng_a = rng_for(seed, "inc", batch, "activities")
    weights = [0.3 + o["intent"] for o in open_opps]
    acts = {"Task": [], "Event": list(events)}
    for o in rng_a.choices(open_opps, weights=weights, k=C.INC_ACTIVITIES - len(events)):
        acc = w.account_by_id[o["AccountId"]]
        when = ts - timedelta(minutes=rng_a.randint(1, 59))
        obj, row = activity(w, rng_a, kind_idx, acc, o, when, created=when, last_modified=ts)
        acts[obj].append(row)

    used_names = {a["Name"] for a in w.accounts}
    leads, lead_truth = leads_increment(w, batch, used_names)
    return {
        "Opportunity": opp_rows, "OpportunityHistory": hist, "Lead": leads,
        "Task": acts["Task"], "Event": acts["Event"], "meet_transcripts": txs,
        "product_usage": usage_increment(w, batch), "support_tickets": tickets_increment(w, batch),
        "truth": [opp_truth_row(o, steps_by_opp) for o in closed_now] + lead_truth + tx_truth,
    }


# --------------------------------------------------------------------------- entry point
def manifest_path(out_dir: Path, batch: int) -> Path:
    return Path(out_dir) / "_manifest" / f"batch={batch:04d}.json"


def generate(mode: str, out_dir, seed: int = 42, batch: int = 0) -> dict[str, int]:
    """Write one batch of raw files under out_dir and return row counts per dataset.

    init -> batch 0 (full history); increment -> batch >= 1. A batch whose
    manifest already exists is skipped (idempotent re-runs); the manifest is
    written last, so a partially written batch is regenerated on re-run.
    """
    out = Path(out_dir)
    if mode == "init":
        if batch not in (0, None):
            raise ValueError("init always writes batch 0")
        batch = 0
    elif mode == "increment":
        if batch is None or batch < 1:
            raise ValueError("increment needs --batch >= 1")
    else:
        raise ValueError(f"unknown mode {mode!r}")

    mpath = manifest_path(out, batch)
    if mpath.exists():
        return json.loads(mpath.read_text())["counts"]

    data = build_init(seed) if mode == "init" else build_increment(seed, batch)
    counts: dict[str, int] = {}
    for obj in SF_OBJECTS:
        rows = data.get(obj)
        if rows:
            write_jsonl(out, f"salesforce/{obj}", batch, rows)
        counts[obj] = len(rows or [])
    write_documents(out, "meet_transcripts", batch, data["meet_transcripts"], "meeting_id")
    counts["meet_transcripts"] = len(data["meet_transcripts"])
    write_csv(out, "product_usage", batch, USAGE_COLUMNS, data["product_usage"])
    counts["product_usage"] = len(data["product_usage"])
    write_jsonl(out, "support_tickets", batch, data["support_tickets"])
    counts["support_tickets"] = len(data["support_tickets"])
    write_jsonl(out, "_eval/truth", batch, data["truth"])
    counts["truth"] = len(data["truth"])
    write_manifest(out, batch, {
        "batch": batch, "mode": mode, "seed": seed,
        "landed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_timestamp": C.fmt_ts(C.batch_ts(batch)), "counts": counts,
    })
    return counts
