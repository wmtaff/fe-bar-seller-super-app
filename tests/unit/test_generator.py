"""Unit tests for the synthetic Fleetwise data generator (Task 2)."""

import csv
import hashlib
import json
import re
from pathlib import Path

import pytest

from fleetwise_gen import generate
from fleetwise_gen.config import AS_OF, CURRENT_FQ_END, CURRENT_FQ_START

SEED = 42
SF_OBJECTS = ["User", "UserRole", "Account", "Contact", "Opportunity",
              "OpportunityHistory", "Lead", "Task", "Event"]


# ---------- helpers ----------
def read_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def sf(out: Path, obj: str, batch: int = 0) -> list[dict]:
    p = out / "salesforce" / obj / f"batch={batch:04d}" / "part-0.json"
    return read_jsonl(p) if p.exists() else []


def transcripts(out: Path, batch: int = 0) -> list[dict]:
    d = out / "meet_transcripts" / f"batch={batch:04d}"
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def truth(out: Path, batch: int = 0) -> list[dict]:
    return read_jsonl(out / "_eval" / "truth" / f"batch={batch:04d}" / "part-0.json")


def tree_hashes(root: Path, include_manifest: bool = False) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith("_manifest/") and not include_manifest:
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def jordan(out: Path) -> dict:
    return next(u for u in sf(out, "User") if u["Name"] == "Jordan Rivera")


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def init_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("init")
    generate("init", out, SEED, 0)
    return out


@pytest.fixture(scope="session")
def inc_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("inc")
    generate("increment", out, SEED, 1)
    return out


# ---------- tests ----------
def test_init_counts_and_layout(init_dir):
    counts = json.loads((init_dir / "_manifest" / "batch=0000.json").read_text())["counts"]
    for obj in SF_OBJECTS:
        assert (init_dir / "salesforce" / obj / "batch=0000" / "part-0.json").exists(), obj
    assert (init_dir / "product_usage" / "batch=0000" / "part-0.csv").exists()
    assert (init_dir / "support_tickets" / "batch=0000" / "part-0.json").exists()
    assert 640 <= counts["User"] <= 700
    assert counts["Account"] == 5000
    assert counts["Contact"] == 20000
    assert counts["Opportunity"] == 15000
    assert counts["Lead"] == 4000
    assert 55000 <= counts["Task"] + counts["Event"] <= 65000
    assert counts["meet_transcripts"] == 600
    assert counts["support_tickets"] == 8000
    opps = sf(init_dir, "Opportunity")
    assert 2900 <= sum(not o["IsClosed"] for o in opps) <= 3100


def test_init_is_deterministic(init_dir, tmp_path):
    generate("init", tmp_path, SEED, 0)
    a, b = tree_hashes(init_dir), tree_hashes(tmp_path)
    assert a and a == b


def test_manifest_written(init_dir):
    m = json.loads((init_dir / "_manifest" / "batch=0000.json").read_text())
    assert m["batch"] == 0 and m["mode"] == "init"
    assert m["landed_at"].endswith("Z")
    assert m["counts"]["Opportunity"] == 15000


def test_ids_are_18_char_and_unique(init_dir):
    seen = set()
    for obj in SF_OBJECTS:
        ids = [r["Id"] for r in sf(init_dir, obj)]
        assert ids, obj
        assert all(isinstance(i, str) and len(i) == 18 and i.isalnum() for i in ids), obj
        assert len(set(ids)) == len(ids), obj
        assert not (seen & set(ids)), obj
        seen |= set(ids)
    meetings = [t["meeting_id"] for t in transcripts(init_dir)]
    assert len(set(meetings)) == len(meetings) == 600


def test_referential_integrity(init_dir):
    users = {u["Id"] for u in sf(init_dir, "User")}
    roles = {r["Id"] for r in sf(init_dir, "UserRole")}
    accounts = {a["Id"] for a in sf(init_dir, "Account")}
    contacts = {c["Id"]: c for c in sf(init_dir, "Contact")}
    opps = {o["Id"]: o for o in sf(init_dir, "Opportunity")}
    for u in sf(init_dir, "User"):
        assert u["UserRoleId"] in roles
        assert u["ManagerId"] is None or u["ManagerId"] in users
    for o in opps.values():
        assert o["AccountId"] in accounts and o["OwnerId"] in users
    for c in contacts.values():
        assert c["AccountId"] in accounts
    for h in sf(init_dir, "OpportunityHistory"):
        assert h["OpportunityId"] in opps
    for obj in ("Task", "Event"):
        for a in sf(init_dir, obj):
            assert a["OwnerId"] in users
            assert a["WhatId"] is None or a["WhatId"] in opps
            assert a["WhoId"] is None or a["WhoId"] in contacts
    emails = {c["Email"] for c in contacts.values()}
    for t in transcripts(init_dir):
        assert t["opportunity_id"] in opps
        assert opps[t["opportunity_id"]]["AccountId"] == t["account_id"]
        cust = [a for a in t["attendees"] if a["company"] != "Fleetwise"]
        assert cust and all(a["email"] in emails for a in cust)
        speakers = {a["name"] for a in t["attendees"]}
        assert all(turn["speaker"] in speakers for turn in t["turns"])
    with (init_dir / "product_usage" / "batch=0000" / "part-0.csv").open() as f:
        assert all(r["account_id"] in accounts for r in csv.DictReader(f))
    for tk in read_jsonl(init_dir / "support_tickets" / "batch=0000" / "part-0.json"):
        assert tk["account_id"] in accounts
    records = set(opps) | {l["Id"] for l in sf(init_dir, "Lead")} | {
        t["meeting_id"] for t in transcripts(init_dir)}
    assert all(t["record_id"] in records for t in truth(init_dir))


@pytest.mark.parametrize("which", ["init", "inc"])
def test_truth_not_in_raw(which, init_dir, inc_dir):
    root = init_dir if which == "init" else inc_dir
    banned = ("true_intent", "will_win", "planted_", "outcome_fields_to_mask")
    n = 0
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(("_eval/", "_manifest/")):
            text = p.read_text()
            assert not any(b in text for b in banned), rel
            n += 1
    assert n > 10


def test_truth_shape(init_dir):
    rows = truth(init_dir)
    kinds = {r["record_type"] for r in rows}
    assert {"Opportunity", "Lead", "Transcript"} <= kinds
    for r in rows:
        assert {"record_type", "record_id", "true_intent", "planted_competitors",
                "planted_next_steps", "will_win", "snapshot_date"} <= set(r)
        assert 0.0 <= r["true_intent"] <= 1.0
        assert isinstance(r["will_win"], bool)
        assert set(r["planted_competitors"]) <= {"RoadLynx", "FleetCore", "Trackwell"}
    assert any(r["planted_next_steps"] for r in rows if r["record_type"] == "Transcript")


def test_closed_opp_snapshot_mid_lifecycle(init_dir):
    opps = {o["Id"]: o for o in sf(init_dir, "Opportunity")}
    tr = {t["record_id"]: t for t in truth(init_dir) if t["record_type"] == "Opportunity"}
    closed = [o for o in opps.values() if o["IsClosed"]]
    assert len(closed) == 12000
    for o in closed:
        snap = tr[o["Id"]]["snapshot_date"]
        assert o["CreatedDate"][:10] < snap < o["CloseDate"], o["Id"]
    # transcripts on closed opps fall both before and after the snapshot
    before = after = 0
    for t in transcripts(init_dir):
        o = opps[t["opportunity_id"]]
        if o["IsClosed"]:
            if t["started_at"][:10] <= tr[o["Id"]]["snapshot_date"]:
                before += 1
            else:
                after += 1
    assert before > 20 and after > 20


def test_jordan_persona(init_dir):
    j = jordan(init_dir)
    assert j["Segment__c"] == "Mid-Market" and j["Region__c"] == "West"
    open_opps = [o for o in sf(init_dir, "Opportunity")
                 if o["OwnerId"] == j["Id"] and not o["IsClosed"]]
    assert len(open_opps) >= 25
    ids = {o["Id"] for o in open_opps}
    in_q = [o for o in open_opps if CURRENT_FQ_START <= o["CloseDate"] <= CURRENT_FQ_END]
    assert len(in_q) >= 0.7 * len(open_opps)
    with_tx = {t["opportunity_id"] for t in transcripts(init_dir) if t["opportunity_id"] in ids}
    assert len(with_tx) >= 8
    quotes = set()
    for t in truth(init_dir):
        if t["record_type"] == "Transcript":
            for q in t.get("competitor_quotes", []):
                if AS_OF < q["expires_on"] <= CURRENT_FQ_END:
                    quotes.add(t["record_id"])
    tx_opp = {t["meeting_id"]: t["opportunity_id"] for t in transcripts(init_dir)}
    assert len({tx_opp[m] for m in quotes if tx_opp[m] in ids}) >= 2


def test_morgan_manages_jordan_plus_seven(init_dir):
    users = sf(init_dir, "User")
    morgan = next(u for u in users if u["Name"] == "Morgan Lee")
    reports = [u for u in users if u["ManagerId"] == morgan["Id"]]
    assert len(reports) == 8
    assert jordan(init_dir)["Id"] in {u["Id"] for u in reports}
    assert sum(u["Name"] == "Morgan Lee" for u in users) == 1
    assert sum(u["Name"] == "Jordan Rivera" for u in users) == 1


def test_empty_persona_has_no_open_opps(init_dir):
    users = sf(init_dir, "User")
    taylor = next(u for u in users if u["Name"] == "Taylor Empty")
    assert taylor["Demo_Persona__c"] == "empty-demo"
    assert not [o for o in sf(init_dir, "Opportunity")
                if o["OwnerId"] == taylor["Id"] and not o["IsClosed"]]


def test_increment_stable_ids(init_dir, inc_dir):
    init_opps = {o["Id"] for o in sf(init_dir, "Opportunity")}
    inc_opps = sf(inc_dir, "Opportunity", 1)
    assert 140 <= len(inc_opps) <= 160
    assert {o["Id"] for o in inc_opps} <= init_opps
    assert all(o["LastModifiedDate"] == "2026-11-16T13:00:00.000Z" for o in inc_opps)
    # accounts / contacts / users never get new IDs in an increment
    for obj in ("Account", "Contact", "User"):
        assert {r["Id"] for r in sf(inc_dir, obj, 1)} <= {r["Id"] for r in sf(init_dir, obj)}
    new_leads = {l["Id"] for l in sf(inc_dir, "Lead", 1)}
    assert len(new_leads) == 50 and not (new_leads & {l["Id"] for l in sf(init_dir, "Lead")})
    acts = sf(inc_dir, "Task", 1) + sf(inc_dir, "Event", 1)
    assert 950 <= len(acts) <= 1050
    assert all(a["WhatId"] is None or a["WhatId"] in init_opps for a in acts)
    init_act = {a["Id"] for a in sf(init_dir, "Task") + sf(init_dir, "Event")}
    assert not ({a["Id"] for a in acts} & init_act)
    assert len(transcripts(inc_dir, 1)) == 40
    assert all(t["opportunity_id"] in init_opps for t in transcripts(inc_dir, 1))
    hist_ids = {h["Id"] for h in sf(init_dir, "OpportunityHistory")}
    assert not ({h["Id"] for h in sf(inc_dir, "OpportunityHistory", 1)} & hist_ids)
    with (inc_dir / "product_usage" / "batch=0001" / "part-0.csv").open() as f:
        days = {r["usage_date"] for r in csv.DictReader(f)}
    assert days == {"2026-11-17"}
    tickets = read_jsonl(inc_dir / "support_tickets" / "batch=0001" / "part-0.json")
    assert len(tickets) == 100


def test_increment_ids_independent_of_disk(inc_dir, tmp_path):
    generate("increment", tmp_path, SEED, 1)
    assert tree_hashes(inc_dir) == tree_hashes(tmp_path)


def test_increment_is_idempotent(inc_dir):
    before = tree_hashes(inc_dir, include_manifest=True)
    counts = generate("increment", inc_dir, SEED, 1)
    assert tree_hashes(inc_dir, include_manifest=True) == before
    assert counts["Lead"] == 50


def test_increment_batches_differ(tmp_path):
    generate("increment", tmp_path, SEED, 2)
    b2 = {o["Id"] for o in sf(tmp_path, "Lead", 2)}
    generate("increment", tmp_path, SEED, 1)
    b1 = {o["Id"] for o in sf(tmp_path, "Lead", 1)}
    assert len(b1) == len(b2) == 50 and not (b1 & b2)
    o2 = sf(tmp_path, "Opportunity", 2)
    assert all(o["LastModifiedDate"] == "2026-11-16T14:00:00.000Z" for o in o2)


def test_win_rate_tracks_intent(init_dir):
    tr = {t["record_id"]: t["true_intent"] for t in truth(init_dir)
          if t["record_type"] == "Opportunity"}
    closed = sorted((tr[o["Id"]], o["IsWon"]) for o in sf(init_dir, "Opportunity") if o["IsClosed"])
    q = len(closed) // 5
    bottom = sum(w for _, w in closed[:q]) / q
    top = sum(w for _, w in closed[-q:]) / q
    assert top > bottom + 0.3


def test_open_close_dates_in_current_and_next_quarter(init_dir):
    open_opps = [o for o in sf(init_dir, "Opportunity") if not o["IsClosed"]]
    near = [o for o in open_opps if "2026-11-01" <= o["CloseDate"] <= "2027-04-30"]
    assert len(near) >= 0.8 * len(open_opps)


def test_competitors_fictional_only(init_dir):
    opps = sf(init_dir, "Opportunity")
    comps = {o["Competitor__c"] for o in opps if o["Competitor__c"]}
    assert comps and comps <= {"RoadLynx", "FleetCore", "Trackwell"}
    products = {"Vehicle Telematics", "AI Dash Cams", "Driver Safety", "Fuel & Maintenance",
                "Compliance/ELD", "Equipment Monitoring"}
    for o in opps:
        assert set(o["Products__c"].split(";")) <= products


def test_transcript_roles_and_text(init_dir):
    roles = {"VP Operations", "Fleet Manager", "Safety Director", "CFO", "IT"}
    txs = transcripts(init_dir)
    seen = set()
    for t in txs:
        assert set(t) == {"meeting_id", "opportunity_id", "account_id", "started_at",
                          "duration_min", "attendees", "turns"}
        assert len(t["turns"]) >= 12
        for a in t["attendees"]:
            if a["company"] != "Fleetwise":
                assert a["role"] in roles
                seen.add(a["role"])
    assert seen == roles


MEET_CODE = re.compile(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$")


def test_meeting_ids_look_like_meet_codes(init_dir, inc_dir, tmp_path):
    generate("increment", tmp_path, SEED, 2)
    ids = ([t["meeting_id"] for t in transcripts(init_dir)]
           + [t["meeting_id"] for t in transcripts(inc_dir, 1)]
           + [t["meeting_id"] for t in transcripts(tmp_path, 2)])
    assert len(ids) == 680 and len(set(ids)) == 680
    assert all(MEET_CODE.match(i) for i in ids), [i for i in ids if not MEET_CODE.match(i)][:3]


def test_increment_preserves_next_step(init_dir, inc_dir):
    init_ns = {o["Id"]: o["NextStep"] for o in sf(init_dir, "Opportunity")}
    inc = sf(inc_dir, "Opportunity", 1)
    assert sum(1 for o in inc if init_ns[o["Id"]]) > 30
    for o in inc:
        assert o["NextStep"] == init_ns[o["Id"]], o["Id"]


def test_lead_truth_declares_masked_fields(init_dir, inc_dir):
    leads = {l["Id"]: l for l in sf(init_dir, "Lead") + sf(inc_dir, "Lead", 1)}
    rows = [t for t in truth(init_dir) + truth(inc_dir, 1) if t["record_type"] == "Lead"]
    assert len(rows) == 4050
    for t in rows:
        assert t["outcome_fields_to_mask"] == ["Status", "IsConverted", "ConvertedDate"]
        assert t["snapshot_date"] == leads[t["record_id"]]["CreatedDate"][:10]
    for t in truth(init_dir):
        if t["record_type"] != "Lead":
            assert t["outcome_fields_to_mask"] == []


def test_old_lead_status_not_binary(init_dir):
    old = [l for l in sf(init_dir, "Lead") if l["CreatedDate"][:10] < "2026-09-01"]
    statuses = {l["Status"] for l in old if not l["IsConverted"]}
    assert {"Nurturing", "Unqualified", "Working - Contacted"} <= statuses


def test_increment_closed_opps_get_truth(inc_dir):
    closed = [o for o in sf(inc_dir, "Opportunity", 1) if o["IsClosed"]]
    assert closed
    tr = {t["record_id"]: t for t in truth(inc_dir, 1) if t["record_type"] == "Opportunity"}
    assert set(tr) == {o["Id"] for o in closed}
    for o in closed:
        t = tr[o["Id"]]
        assert o["CreatedDate"][:10] < t["snapshot_date"] < o["CloseDate"]
        assert t["will_win"] == o["IsWon"]


def test_transcript_phrasing_varies(init_dir):
    txs = transcripts(init_dir)
    tr = {t["record_id"]: t for t in truth(init_dir) if t["record_type"] == "Transcript"}
    acks, openers, scattered = set(), set(), 0
    for t in txs:
        texts = [x["text"] for x in t["turns"]]
        acks.add(texts[next(i for i, x in enumerate(texts) if x.startswith(("What I was hoping",
                 "Today I wanted", "Today the goal", "Your renewal"))) + 1])
        recap = [x for x in texts if "you'll" in x or x.startswith(("So, to recap", "Okay, just so",
                 "Let me play back", "Before we drop", "Great. So action", "Let me summarize"))]
        openers |= {x.split(":")[0] for x in recap if ":" in x}
        if any("I've got my action items" in x for x in texts) or any(
                x.startswith(("Let me make a note", "Okay, that's on me", "Good point.")) for x in texts):
            scattered += 1
        for x in texts:
            assert "(CFO" not in x and "Fleet Manager)" not in x
        if tr[t["meeting_id"]]["call_type"] == "renewal":
            assert not any(x.startswith("We've been on") for x in texts)
    assert len(acks) >= 5 and len(openers) >= 5
    assert scattered >= 60


def _fy27q4_kpis(init_dir: Path, inc_dir: Path) -> dict[str, dict]:
    """Seller KPIs for FY27Q4 from raw files (init + increment 1), as gold_seller_kpis computes them."""
    opps = {o["Id"]: o for o in sf(init_dir, "Opportunity")}
    for o in sf(inc_dir, "Opportunity", 1):
        if o["LastModifiedDate"] >= opps[o["Id"]]["LastModifiedDate"]:
            opps[o["Id"]] = o
    out = {}
    for u in sf(init_dir, "User"):
        if not u["Title"].endswith("Account Executive"):
            continue
        quota = u["Quota__c"] / 4
        won = sum(o["Amount"] for o in opps.values() if o["OwnerId"] == u["Id"] and o["IsWon"]
                  and CURRENT_FQ_START <= o["CloseDate"] <= CURRENT_FQ_END)
        open_ = sum(o["Amount"] for o in opps.values() if o["OwnerId"] == u["Id"] and not o["IsClosed"]
                    and CURRENT_FQ_START <= o["CloseDate"] <= CURRENT_FQ_END)
        out[u["Name"]] = {"quota": quota, "won": won, "open": open_, "attainment": won / quota,
                          "coverage": open_ / (quota - won) if quota > won else None}
    return out


def test_jordan_kpis_plausible(init_dir, inc_dir):
    """Ruling R12: Jordan's FY27Q4 coverage is 3-4x with 25-40% attainment; org coverage is plausible."""
    k = _fy27q4_kpis(init_dir, inc_dir)
    j = k["Jordan Rivera"]
    assert j["quota"] * 4 == 2_000_000
    assert 3.0 <= j["coverage"] <= 4.0, j
    assert 0.25 <= j["attainment"] <= 0.40, j
    with_pipe = [v for v in k.values() if v["open"] > 0]
    in_band = [v for v in with_pipe if v["coverage"] is not None and 1.5 <= v["coverage"] <= 5.0]
    assert len(in_band) >= 0.8 * len(with_pipe), (len(in_band), len(with_pipe))
    jid = jordan(init_dir)["Id"]
    nxt = [o for o in sf(init_dir, "Opportunity") if o["OwnerId"] == jid and not o["IsClosed"]
           and "2027-02-01" <= o["CloseDate"] <= "2027-04-30"]
    assert 6 <= len(nxt) <= 8
