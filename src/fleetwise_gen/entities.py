"""Core world: users, roles, accounts, contacts, opportunities (+ hidden truth).

`build_core(seed)` is pure and deterministic; both --init and --increment call
it, so increments can derive state (and stable IDs) without reading disk.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from faker import Faker

from . import config as C
from . import names as N
from .ids import sfid


def rng_for(seed: int, *parts) -> random.Random:
    """Independent, reproducible stream per purpose (str seeds hash via sha512)."""
    return random.Random(":".join([str(seed), *map(str, parts)]))


def faker_for(seed: int, offset: int) -> Faker:
    f = Faker("en_US")
    f.seed_instance(seed * 1000 + offset)
    return f


def dts(d: date, hour: int = 15, minute: int = 0) -> str:
    return C.fmt_ts(datetime.combine(d, time(hour, minute), tzinfo=timezone.utc))


def phone(rng: random.Random) -> str:
    # 555-01xx numbers are reserved for fiction.
    return f"({rng.randint(201, 989)}) 555-01{rng.randint(0, 99):02d}"


def beta(rng: random.Random, a: float, b: float) -> float:
    return rng.betavariate(a, b)


@dataclass
class World:
    seed: int
    users: list[dict] = field(default_factory=list)
    roles: list[dict] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)
    contacts: list[dict] = field(default_factory=list)
    contacts_by_account: dict[str, list[dict]] = field(default_factory=dict)
    opps: list[dict] = field(default_factory=list)  # internal state incl. hidden fields
    user_by_id: dict[str, dict] = field(default_factory=dict)
    account_by_id: dict[str, dict] = field(default_factory=dict)
    jordan_id: str = ""
    morgan_id: str = ""
    taylor_id: str = ""
    sales_engineers: list[str] = field(default_factory=list)
    account_health: dict[str, float] = field(default_factory=dict)


# --------------------------------------------------------------------------- users
def _build_users(w: World) -> None:
    seed = w.seed
    rng = rng_for(seed, "users")
    fk = faker_for(seed, 1)
    reserved = {" ".join(C.JORDAN), " ".join(C.MORGAN), " ".join(C.TAYLOR)}
    used_names: set[str] = set(reserved)
    used_emails: set[str] = set()

    def new_name() -> tuple[str, str]:
        while True:
            fn, ln = fk.first_name(), fk.last_name()
            if f"{fn} {ln}" not in used_names:
                used_names.add(f"{fn} {ln}")
                return fn, ln

    def email(fn: str, ln: str) -> str:
        base = f"{fn}.{ln}".lower().replace("'", "").replace(" ", "")
        e, k = f"{base}@{C.FLEETWISE_DOMAIN}", 2
        while e in used_emails:
            e, k = f"{base}{k}@{C.FLEETWISE_DOMAIN}", k + 1
        used_emails.add(e)
        return e

    # roles: RVP / Manager / AE per territory
    for t, (seg, reg) in enumerate(C.TERRITORIES):
        w.roles.append({"Id": sfid("UserRole", t, seed), "Name": f"RVP - {seg} {reg}",
                        "DeveloperName": f"RVP_{seg.replace('-', '')}_{reg}", "ParentRoleId": None})
    for t, (seg, reg) in enumerate(C.TERRITORIES):
        w.roles.append({"Id": sfid("UserRole", 8 + t, seed), "Name": f"Sales Manager - {seg} {reg}",
                        "DeveloperName": f"MGR_{seg.replace('-', '')}_{reg}",
                        "ParentRoleId": w.roles[t]["Id"]})
    for t, (seg, reg) in enumerate(C.TERRITORIES):
        w.roles.append({"Id": sfid("UserRole", 16 + t, seed), "Name": f"Account Executive - {seg} {reg}",
                        "DeveloperName": f"AE_{seg.replace('-', '')}_{reg}",
                        "ParentRoleId": w.roles[8 + t]["Id"]})
    for r in w.roles:
        r["LastModifiedDate"] = dts(date(2024, 1, 8))

    idx = 0

    def add_user(fn, ln, title, role_idx, manager_id, seg, reg, quota, persona=None, username=None):
        nonlocal idx
        uid = sfid("User", idx, seed)
        idx += 1
        e = email(fn, ln)
        created = date(2021, 1, 4) + timedelta(days=rng.randint(0, 1400))
        u = {
            "Id": uid, "Username": username or e, "Email": e, "FirstName": fn, "LastName": ln,
            "Name": f"{fn} {ln}", "Alias": (fn[0] + ln[:4]).lower(), "Title": title,
            "UserRoleId": w.roles[role_idx]["Id"], "ManagerId": manager_id, "IsActive": True,
            "Segment__c": seg, "Region__c": reg, "Quota__c": quota, "Demo_Persona__c": persona,
            "CreatedDate": dts(created, 16), "LastModifiedDate": dts(created + timedelta(days=30), 16),
        }
        w.users.append(u)
        return u

    rvps = []
    for t, (seg, reg) in enumerate(C.TERRITORIES):
        fn, ln = new_name()
        rvps.append(add_user(fn, ln, "Regional Vice President", t, None, seg, reg, None))
    mgr_counts = [7, 7, 8, 8, 8, 7, 7, 8]
    managers = []  # (user, territory)
    for t, n in enumerate(mgr_counts):
        seg, reg = C.TERRITORIES[t]
        for k in range(n):
            if t == 2 and k == 0:
                fn, ln, persona = C.MORGAN[0], C.MORGAN[1], "manager"
            else:
                (fn, ln), persona = new_name(), None
            m = add_user(fn, ln, "Sales Manager", 8 + t, rvps[t]["Id"], seg, reg, None, persona)
            managers.append((m, t))
    w.morgan_id = next(m["Id"] for m, _ in managers if m["Name"] == "Morgan Lee")
    # sellers: Morgan gets exactly 8 (Jordan + 7); others share the rest.
    others = [(m, t) for m, t in managers if m["Id"] != w.morgan_id]
    per = {m["Id"]: 0 for m, _ in managers}
    per[w.morgan_id] = 8
    remaining = C.N_SELLERS - 8
    for i in range(remaining):
        per[others[i % len(others)][0]["Id"]] += 1
    mm_west_second = next(m["Id"] for m, t in managers if t == 2 and m["Id"] != w.morgan_id)
    team_quota = {}
    for m, t in managers:
        seg, reg = C.TERRITORIES[t]
        for k in range(per[m["Id"]]):
            senior = rng.random() < 0.3
            quota = int(C.SEGMENT_QUOTA[seg] * (1.15 if senior else 1.0) * rng.uniform(0.9, 1.1) / 10000) * 10000
            title = "Senior Account Executive" if senior else "Account Executive"
            if m["Id"] == w.morgan_id and k == 0:
                u = add_user(*C.JORDAN, "Senior Account Executive", 16 + t, m["Id"], seg, reg,
                             C.JORDAN_QUOTA, "seller")
                w.jordan_id = u["Id"]
            elif m["Id"] == mm_west_second and k == 0:
                u = add_user(*C.TAYLOR, "Account Executive", 16 + t, m["Id"], seg, reg, 900_000,
                             "empty-demo", username=f"empty-demo@{C.FLEETWISE_DOMAIN}")
                w.taylor_id = u["Id"]
            else:
                fn, ln = new_name()
                u = add_user(fn, ln, title, 16 + t, m["Id"], seg, reg, quota)
            team_quota[m["Id"]] = team_quota.get(m["Id"], 0) + u["Quota__c"]
    for m, t in managers:
        m["Quota__c"] = team_quota[m["Id"]]
    for r in rvps:
        r["Quota__c"] = sum(m["Quota__c"] for m, _ in managers if m["ManagerId"] == r["Id"])
    w.user_by_id = {u["Id"]: u for u in w.users}
    w.sales_engineers = [f"{fk.first_name()} {fk.last_name()}" for _ in range(16)]


# --------------------------------------------------------------------------- accounts / contacts
def _company_name(rng: random.Random, fk: Faker, industry: str, used: set[str]) -> str:
    for attempt in range(20):
        tpl = rng.choice(N.INDUSTRY_TEMPLATES[industry])
        name = tpl.format(last=fk.last_name(), adj=rng.choice(N.ADJ), town=rng.choice(N.TOWNS))
        if attempt >= 3:
            if industry == "Public Sector":
                name = f"{rng.choice(N.DIRECTIONS)} {name}"
            else:
                name = f"{name} {rng.choice(N.NAME_SUFFIXES)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("could not find a unique company name")


def _slug(name: str) -> str:
    keep = "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ")
    words = [x for x in keep.split() if x not in {"inc", "llc", "co", "corp", "the", "and"}]
    return "".join(words[:3])


def _build_accounts(w: World) -> None:
    seed = w.seed
    rng = rng_for(seed, "accounts")
    fk = faker_for(seed, 2)
    sellers = [u for u in w.users if u["Title"].endswith("Account Executive")]
    pool = [u for u in sellers if u["Id"] not in (w.taylor_id, w.jordan_id)]
    rng.shuffle(pool)
    owners = [w.jordan_id] * 20 + [pool[i % len(pool)]["Id"] for i in range(C.N_ACCOUNTS - 20)]
    used: set[str] = set()
    for i in range(C.N_ACCOUNTS):
        owner = w.user_by_id[owners[i]]
        seg, reg = owner["Segment__c"], owner["Region__c"]
        industry = rng.choice(C.INDUSTRIES)
        name = _company_name(rng, fk, industry, used)
        lo, hi = C.SEGMENT_FLEET[seg]
        fleet = int(lo * (hi / lo) ** rng.random())
        employees = int(fleet * rng.uniform(1.8, 4.5))
        created = date(2019, 6, 1) + timedelta(days=rng.randint(0, 1800))
        acc = {
            "Id": sfid("Account", i, seed), "Name": name, "Industry": industry, "Type": "Prospect",
            "Segment__c": seg, "Region__c": reg, "BillingCity": rng.choice(N.TOWNS),
            "BillingState": rng.choice(C.REGION_STATES[reg]), "BillingCountry": "United States",
            "Phone": phone(rng), "Website": f"www.{_slug(name)}.com",
            "NumberOfEmployees": employees, "Fleet_Size__c": fleet,
            "AnnualRevenue": int(employees * rng.uniform(90_000, 260_000) / 1000) * 1000,
            "OwnerId": owner["Id"], "Products_Owned__c": None, "Current_ARR__c": 0,
            "Customer_Since__c": None, "CreatedDate": dts(created, 17),
            "LastModifiedDate": dts(created + timedelta(days=rng.randint(1, 60)), 17),
        }
        w.accounts.append(acc)
        w.account_health[acc["Id"]] = beta(rng, 2.6, 1.8)
    w.account_by_id = {a["Id"]: a for a in w.accounts}

    rngc = rng_for(seed, "contacts")
    fkc = faker_for(seed, 3)
    ci = 0
    for a in w.accounts:
        roles = rngc.sample(C.CUSTOMER_ROLES, C.CONTACTS_PER_ACCOUNT)
        lst = []
        domain = _slug(a["Name"]) + ".com"
        emails = set()
        for role in roles:
            fn, ln = fkc.first_name(), fkc.last_name()
            e = f"{fn[0]}{ln}".lower().replace("'", "").replace(" ", "") + "@" + domain
            if e in emails:
                e = f"{fn}.{ln}".lower().replace("'", "").replace(" ", "") + "@" + domain
            emails.add(e)
            created = date.fromisoformat(a["CreatedDate"][:10]) + timedelta(days=rngc.randint(0, 400))
            c = {
                "Id": sfid("Contact", ci, seed), "AccountId": a["Id"], "FirstName": fn, "LastName": ln,
                "Name": f"{fn} {ln}", "Title": rngc.choice(N.CONTACT_TITLES[role]), "Role__c": role,
                "Email": e, "Phone": phone(rngc), "MobilePhone": phone(rngc),
                "MailingState": a["BillingState"], "OwnerId": a["OwnerId"],
                "LeadSource": rngc.choice(N.LEAD_SOURCES),
                "CreatedDate": dts(min(created, C.AS_OF_DATE), 18),
                "LastModifiedDate": dts(min(created + timedelta(days=20), C.AS_OF_DATE), 18),
            }
            ci += 1
            lst.append(c)
            w.contacts.append(c)
        w.contacts_by_account[a["Id"]] = lst


# --------------------------------------------------------------------------- opportunities
def _p_win(intent: float, opp_type: str) -> float:
    if opp_type == "Renewal":
        return 0.45 + 0.5 * intent
    return 0.04 + 0.9 * intent ** 1.6


def _amount(fleet: int, products: list[str], coverage: float) -> int:
    monthly = fleet * coverage * sum(C.PRODUCT_PRICE[p] for p in products)
    return max(1200, int(round(monthly * 12, -2)))


def _pick_products(rng: random.Random, owned: set[str], opp_type: str) -> list[str]:
    if opp_type == "Renewal" and owned:
        return [p for p in C.PRODUCTS if p in owned]
    pool = [p for p in C.PRODUCTS if p not in owned] or list(C.PRODUCTS)
    if opp_type == "New Business" and "Vehicle Telematics" in pool and rng.random() < 0.75:
        first = ["Vehicle Telematics"]
    else:
        first = [rng.choice(pool)]
    extra = [p for p in pool if p not in first]
    k = min(len(extra), rng.choice([0, 0, 1, 1, 2]))
    chosen = set(first) | set(rng.sample(extra, k))
    return [p for p in C.PRODUCTS if p in chosen]


def _competitors(rng: random.Random, intent: float) -> list[str]:
    if rng.random() < 0.3 + 0.35 * (1 - intent):
        k = 2 if rng.random() < 0.2 else 1
        return sorted(rng.sample(C.COMPETITORS, k))
    return []


def _new_opp(w: World, idx: int, acc: dict, intent: float, opp_type: str, products: list[str],
             coverage: float, rng: random.Random) -> dict:
    fleet_scope = max(5, int(acc["Fleet_Size__c"] * coverage))
    comps = _competitors(rng, intent)
    return {
        "idx": idx, "Id": sfid("Opportunity", idx, w.seed), "AccountId": acc["Id"],
        "OwnerId": acc["OwnerId"], "Type": opp_type, "products": products,
        "Amount": _amount(acc["Fleet_Size__c"], products, coverage), "fleet_in_scope": fleet_scope,
        "intent": round(intent, 4), "will_win": rng.random() < _p_win(intent, opp_type),
        "competitors": comps,
        "crm_competitor": comps[0] if comps and rng.random() < 0.55 else None,
        "quote": None, "LeadSource": rng.choice(N.OPP_LEAD_SOURCES),
    }


def _quote(rng: random.Random, comp: str, products: list[str], lo: date, hi: date) -> dict:
    list_price = sum(C.PRODUCT_PRICE[p] for p in products)
    days = max(0, (hi - lo).days)
    return {"competitor": comp,
            "price_per_vehicle": round(list_price * rng.uniform(0.72, 0.92), 2),
            "expires_on": (lo + timedelta(days=rng.randint(0, days))).isoformat()}


def _build_opps(w: World) -> None:
    seed = w.seed
    rng = rng_for(seed, "opps")
    as_of = C.AS_OF_DATE
    owned: dict[str, set[str]] = {a["Id"]: set() for a in w.accounts}
    arr: dict[str, int] = {a["Id"]: 0 for a in w.accounts}
    since: dict[str, date] = {}
    jordan_accounts = [a for a in w.accounts if a["OwnerId"] == w.jordan_id]
    other_accounts = [a for a in w.accounts if a["OwnerId"] != w.jordan_id]

    # ---- closed opps, generated in close-date order per account so types make sense
    closed_specs = []
    for k in range(C.N_CLOSED_OPPS):
        acc = rng.choice(w.accounts)
        close = as_of - timedelta(days=1 + int(729 * rng.random() ** 1.15))
        closed_specs.append((close, k, acc))
    closed_specs.sort(key=lambda x: (x[0], x[1]))
    idx = 0
    for close, _, acc in closed_specs:
        seg = acc["Segment__c"]
        lo, hi = C.SEGMENT_CYCLE_DAYS[seg]
        cycle = rng.randint(lo, hi)
        intent = beta(rng, 2, 2)
        if owned[acc["Id"]]:
            opp_type = "Renewal" if rng.random() < 0.45 else "Expansion"
        else:
            opp_type = "New Business"
        products = _pick_products(rng, owned[acc["Id"]], opp_type)
        coverage = 1.0 if opp_type == "Renewal" else rng.uniform(0.35, 1.0)
        o = _new_opp(w, idx, acc, intent, opp_type, products, coverage, rng)
        idx += 1
        created = close - timedelta(days=cycle)
        o.update(created=created, close=close, snapshot=created + timedelta(days=round(0.6 * cycle)),
                 IsClosed=True, IsWon=o["will_win"],
                 StageName="Closed Won" if o["will_win"] else "Closed Lost")
        o["last_modified"] = dts(close, 22)
        if o["competitors"] and rng.random() < 0.35:
            o["quote"] = _quote(rng, o["competitors"][0], products,
                                created + timedelta(days=cycle // 2), close + timedelta(days=20))
        if o["IsWon"]:
            o["loss_reason"] = None
            owned[acc["Id"]] |= set(products)
            arr[acc["Id"]] = (o["Amount"] if opp_type == "Renewal" else arr[acc["Id"]] + o["Amount"])
            since.setdefault(acc["Id"], close)
            # the stage path of a won deal goes through every open stage
            o["path_len"] = len(C.OPEN_STAGES)
        else:
            if o["competitors"] and rng.random() < 0.6:
                o["loss_reason"] = "Lost to Competitor"
                o["crm_competitor"] = o["crm_competitor"] or o["competitors"][0]
            else:
                o["loss_reason"] = rng.choice(["No Decision", "Price", "Timing", "Budget", "Went Dark"])
            o["path_len"] = rng.randint(1, len(C.OPEN_STAGES))
        w.opps.append(o)

    # account firmographics derived from closed history
    for a in w.accounts:
        if owned[a["Id"]]:
            a["Type"] = "Customer"
            a["Products_Owned__c"] = ";".join(p for p in C.PRODUCTS if p in owned[a["Id"]])
            a["Current_ARR__c"] = arr[a["Id"]]
            a["Customer_Since__c"] = since[a["Id"]].isoformat()

    # ---- open opps: Jordan's 25 first, then the rest on other accounts
    jordan_stages = (["Negotiation"] * 4 + ["Proposal"] * 7 + ["Demo"] * 7 + ["Discovery"] * 5
                     + ["Qualification"] * 2)
    jordan_intents = [0.86, 0.52, 0.47, 0.78, 0.31, 0.69, 0.58, 0.81, 0.43, 0.64,
                      0.25, 0.72, 0.55, 0.38, 0.9, 0.6, 0.49, 0.67, 0.34, 0.75,
                      0.57, 0.44, 0.83, 0.29, 0.62]
    open_renewal: set[str] = set()
    open_products: dict[str, set[str]] = {}
    for j in range(C.N_OPEN_OPPS):
        if j < C.JORDAN_OPEN_OPPS:
            acc = jordan_accounts[j % len(jordan_accounts)]
            intent = jordan_intents[j]
        else:
            acc = rng.choice(other_accounts)
            intent = beta(rng, 2, 2)
        is_cust = acc["Type"] == "Customer"
        opp_type = ("Renewal" if rng.random() < 0.4 else "Expansion") if is_cust else "New Business"
        if opp_type == "Renewal" and acc["Id"] in open_renewal:
            opp_type = "Expansion"  # at most one open renewal per account
        if opp_type == "Renewal":
            open_renewal.add(acc["Id"])
        # avoid duplicating products already in an open opp on the same account
        taken = owned[acc["Id"]] | open_products.setdefault(acc["Id"], set())
        if opp_type != "Renewal" and len(taken) >= len(C.PRODUCTS):
            taken = owned[acc["Id"]]
        products = _pick_products(rng, taken if opp_type != "Renewal" else owned[acc["Id"]], opp_type)
        open_products[acc["Id"]] |= set(products)
        coverage = 1.0 if opp_type == "Renewal" else rng.uniform(0.35, 1.0)
        o = _new_opp(w, idx, acc, intent, opp_type, products, coverage, rng)
        idx += 1
        seg = acc["Segment__c"]
        lo, hi = C.SEGMENT_CYCLE_DAYS[seg]
        age = rng.randint(max(10, lo // 2), int(hi * 1.3))
        created = as_of - timedelta(days=age)
        # close date: mostly current + next fiscal quarter
        u = rng.random()
        if j < C.JORDAN_OPEN_OPPS:
            # Ruling R12: the 7 JORDAN_NEXT_Q_OPPS close in FY28Q1 (Feb-Apr 2027), the other 18
            # in FY27Q4 (Nov 20 - Jan 29). The rng draws are unchanged, so the rest of the world
            # is identical to before.
            off = rng.randint(0, 70) if j < 20 else rng.randint(0, 80)
            close = (date(2027, 2, 1) + timedelta(days=off) if j in C.JORDAN_NEXT_Q_OPPS
                     else date(2026, 11, 20) + timedelta(days=min(off, 70)))
            stage = jordan_stages[j]
        else:
            if u < 0.04:
                close = date(2026, 11, 1) + timedelta(days=rng.randint(0, 14))  # slipped
            elif u < 0.6:
                close = as_of + timedelta(days=rng.randint(1, 76))
            elif u < 0.9:
                close = date(2027, 2, 1) + timedelta(days=rng.randint(0, 88))
            else:
                close = date(2027, 5, 1) + timedelta(days=rng.randint(0, 91))
            progress = min(1.0, age / ((lo + hi) / 2))
            x = 0.3 * progress + 0.3 * intent + 0.4 * rng.random()
            stage = C.OPEN_STAGES[sum(x > t for t in (0.47, 0.57, 0.67, 0.79))]
        if j < C.JORDAN_QUOTE_OPPS:
            o["competitors"] = [C.COMPETITORS[j % 3]]
            o["crm_competitor"] = o["competitors"][0] if j == 0 else None
            o["quote"] = {"competitor": o["competitors"][0],
                          "price_per_vehicle": round(sum(C.PRODUCT_PRICE[p] for p in products) * 0.8, 2),
                          "expires_on": (date(2026, 12, 4) + timedelta(days=17 * j)).isoformat()}
        elif o["competitors"] and rng.random() < 0.35:
            o["quote"] = _quote(rng, o["competitors"][0], products, as_of + timedelta(days=4),
                                max(as_of + timedelta(days=10), close))
        lm_days = int(age * (1 - rng.random() ** (0.5 + 2 * intent)))
        o.update(created=created, close=close, snapshot=as_of, IsClosed=False, IsWon=False,
                 StageName=stage, loss_reason=None,
                 last_modified=dts(min(as_of, created + timedelta(days=lm_days)), 21))
        w.opps.append(o)


def opp_row(w: World, o: dict, last_modified: str | None = None) -> dict:
    """Salesforce-shaped Opportunity row from internal state (no truth fields)."""
    acc = w.account_by_id[o["AccountId"]]
    stage = o["StageName"]
    primary = o["products"][0]
    suffix = {"New Business": "New Business", "Expansion": "Expansion", "Renewal": "Renewal"}[o["Type"]]
    name = (f"{acc['Name']} - {primary} {suffix}" if len(o["products"]) == 1
            else f"{acc['Name']} - {primary} + {len(o['products']) - 1} {suffix}")
    return {
        "Id": o["Id"], "Name": name, "AccountId": o["AccountId"], "OwnerId": o["OwnerId"],
        "StageName": stage, "Amount": o["Amount"], "CloseDate": o["close"].isoformat(),
        "IsClosed": o["IsClosed"], "IsWon": o["IsWon"], "Probability": C.STAGE_PROB[stage],
        "ForecastCategoryName": C.STAGE_FORECAST[stage], "Type": o["Type"],
        "LeadSource": o["LeadSource"], "Products__c": ";".join(o["products"]),
        "Primary_Product__c": primary, "Fleet_Size__c": o["fleet_in_scope"],
        "Competitor__c": o["crm_competitor"], "Loss_Reason__c": o["loss_reason"],
        "NextStep": o.get("next_step_field"), "CreatedDate": dts(o["created"], 16),
        "LastModifiedDate": last_modified or o["last_modified"],
    }


def _calibrate_quotas(w: World) -> None:
    """Set seller quotas from each territory's current-quarter position (ruling R12).

    Deal sizes vary a lot by segment and each seller has only a few deals, so a flat
    segment quota gives implausible pipeline coverage (0.3x for SMB, 6x+ for Enterprise).
    Like a territory plan, each seller's quarterly quota = current-quarter closed-won ACV +
    open current-quarter pipeline / a target coverage drawn from 1.9x..3.6x. Sellers with no
    current-quarter pipeline keep the segment default; personas keep their fixed quotas.
    Managers and RVPs get the roll-up of their team.
    """
    rng = rng_for(w.seed, "quota")
    q_start, q_end = date.fromisoformat(C.CURRENT_FQ_START), date.fromisoformat(C.CURRENT_FQ_END)
    won: dict[str, int] = {}
    open_: dict[str, int] = {}
    for o in w.opps:
        if not (q_start <= o["close"] <= q_end):
            continue
        if o["IsClosed"] and o["IsWon"]:
            won[o["OwnerId"]] = won.get(o["OwnerId"], 0) + o["Amount"]
        elif not o["IsClosed"]:
            open_[o["OwnerId"]] = open_.get(o["OwnerId"], 0) + o["Amount"]
    for u in w.users:
        if not u["Title"].endswith("Account Executive"):
            continue
        target = rng.uniform(1.9, 3.6)
        if u["Id"] in (w.jordan_id, w.taylor_id) or not open_.get(u["Id"]):
            continue
        quarterly = won.get(u["Id"], 0) + open_[u["Id"]] / target
        u["Quota__c"] = max(C.MIN_ANNUAL_QUOTA, int(round(4 * quarterly, -4)))
    for m in w.users:
        if m["Title"] == "Sales Manager":
            m["Quota__c"] = sum(u["Quota__c"] for u in w.users if u["ManagerId"] == m["Id"])
    for r in w.users:
        if r["Title"] == "Regional Vice President":
            r["Quota__c"] = sum(m["Quota__c"] for m in w.users if m["ManagerId"] == r["Id"])


def build_core(seed: int) -> World:
    w = World(seed=seed)
    _build_users(w)
    _build_accounts(w)
    _build_opps(w)
    _calibrate_quotas(w)
    return w
