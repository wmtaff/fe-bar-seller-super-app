"""Deterministic Google Meet transcript generator (templates + phrase banks).

No LLM: every call is assembled from phrase banks driven by the opportunity's
hidden `true_intent`, so output is reproducible and the planted signals
(competitors, quotes, next steps, sentiment) are known exactly and written to
`_eval/truth`. The raw transcript never contains the truth labels.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

from .config import FLEETWISE_COMPANY, PRODUCT_PRICE

# --------------------------------------------------------------------------- banks
VEHICLE_MIX = {
    "Construction": "pickups and crew trucks, plus a yard full of excavators, loaders and generators",
    "Logistics & Transportation": "Class 8 tractors and dry vans, with some reefers",
    "Field Services": "service vans and a few box trucks",
    "Public Sector": "plows, refuse trucks, and a lot of light-duty pickups",
    "Food & Beverage": "box trucks and reefers on daily delivery routes",
}
PAINS = {
    "Construction": [
        "we had two compact excavators walk off job sites this year and the insurance claim was a nightmare",
        "idle time on the heavy equipment is eating our fuel budget alive",
        "my supers can't tell me which crew truck is at which site without calling around",
    ],
    "Logistics & Transportation": [
        "we got dinged on hours-of-service in our last roadside inspection and it hurt our CSA score",
        "fuel is our second biggest cost after drivers, and we have no real visibility into idling",
        "customers keep calling dispatch for ETAs and we're guessing half the time",
    ],
    "Field Services": [
        "our techs are driving past each other across town because dispatch can't see who's closest",
        "when a customer disputes an invoice we can't prove what time the tech actually arrived",
        "overtime is up because the routing is basically done on a whiteboard",
    ],
    "Public Sector": [
        "the council wants real accountability on how the trucks are being used",
        "our plow routes are still tracked on paper, so when residents call we can't tell them anything",
        "the budget cycle locks in July, so anything we do has to be justified well before that",
    ],
    "Food & Beverage": [
        "we lost a full load of dairy last summer because a reefer unit failed and nobody knew for three hours",
        "the delivery windows at the grocery distribution centers are brutal and we pay fines when we miss them",
        "drivers are speeding to make their windows, and that's a safety problem waiting to happen",
    ],
}
SMALL_TALK = [
    ("Hey {cfirst}, thanks for making the time. How's the week going?",
     "Busy, but good. We're coming off a long stretch of {season}, so it's nice to sit down for a minute."),
    ("Hi everyone, appreciate you jumping on. Can you all hear me okay?",
     "Yep, loud and clear. Sorry, I'm in the yard office, so if you hear a backup alarm that's why."),
    ("Good to see you again, {cfirst}. Did you make it through the weather last week alright?",
     "We did. A couple of trucks got stuck on the north route, but nothing serious."),
    ("Thanks for having me, {cfirst}. I know this time of year is hectic for you all.",
     "It is, but this is one of the things on my list to get done, so the timing works."),
]
AGENDA = {
    "discovery": "What I was hoping to do today is learn how you run the fleet today, where the pain is, and then see if it even makes sense to go further. Sound good?",
    "demo_followup": "Today I wanted to go through the questions that came out of the demo, and talk about what a rollout could look like.",
    "pricing": "Today the goal is to walk through the proposal and pricing, and make sure it lines up with what you need.",
    "renewal": "Your renewal is coming up, so I wanted to review how the last year has gone, look at adoption, and talk about the terms going forward.",
}
DISCOVERY_Q = [
    "Can you walk me through how you keep track of the fleet today?",
    "Where does it hurt the most right now?",
    "Who else would be involved in a decision like this?",
    "What does your timeline look like on your end?",
    "What would success look like twelve months from now?",
]
BUYING_SIGNALS = [
    "Honestly, we'd like to have this rolled out before {deadline}.",
    "The budget is already approved for this. Finance signed off last week.",
    "If the numbers work, I don't see a reason we wouldn't move forward this quarter.",
    "Can you send over an order form so our legal team can start reviewing the paper?",
    "The drivers we piloted with actually liked the coaching alerts, which surprised me.",
    "What does implementation look like if we signed by the end of the month?",
    "I showed the dash cam footage to our insurance broker, and they want to talk about a premium discount.",
    "We'd want to start with all {fleet} vehicles, not just a pilot.",
    "My ops team keeps asking me when they get their logins.",
    "Who do I need to loop in on your side to get the security review going?",
    "The ROI model you sent is what I'm taking into the leadership meeting on Thursday.",
    "We've seen enough. I'm ready to take this to the CEO.",
]
OBJECTIONS = [
    ("To be honest, the timing is tough. We're in the middle of a reorg.",
     "That's fair. A lot of teams start with a small pilot so it doesn't compete with everything else going on."),
    ("The price is quite a bit above what we budgeted for.",
     "Understood. Let me look at what we can do on a three-year term, and we can also phase the products."),
    ("We just went through a painful rollout with our last vendor, so there's real change fatigue here.",
     "I hear that a lot. Our install team does it in waves, so no more than ten percent of the fleet is down on any given day."),
    ("I'm not sure the drivers will accept cameras in the cab. The union has concerns.",
     "Makes sense. The cameras can be set to event-only recording, and we have a driver privacy one-pager I can share with the union reps."),
    ("I need to understand how this integrates with our ERP before I can take it upstairs.",
     "We have an open API and prebuilt connectors. I can get our solutions engineer on with your IT team."),
    ("We'll probably wait until next fiscal year to revisit this.",
     "Okay. Would it help if I sent a business case you could use in the budget process?"),
    ("Leadership isn't convinced this is a priority right now.",
     "That's helpful to know. What would they need to see to make it a priority?"),
    ("I'm worried about the install downtime across {fleet} vehicles.",
     "We can do installs at your yard after hours. Most vans take about forty-five minutes."),
    ("Our current contract doesn't end until spring, so there's no rush on our side.",
     "Got it. We can line up the start date with the end of your current contract so you're not paying twice."),
]
NEUTRAL_LINES = [
    "Let me think about that and get back to you.",
    "That's interesting. I'd want to see it with our own data before I'd believe it.",
    "We're looking at a few options right now, so nothing's decided.",
    "I'll need to run that by the rest of the team.",
]
COMPETITOR_MENTIONS = [
    "Just so you know, we're also talking to {competitor}.",
    "{competitor} came in last week and did a demo for our safety team.",
    "We've been on {competitor} for a few years, and honestly the hardware keeps failing.",
    "To be transparent, {competitor} is cheaper on paper.",
]
COMPETITOR_RESPONSES = [
    "Appreciate you telling me. Most teams that switch from {competitor} tell us the difference is the AI event detection. It catches the stuff that actually causes claims.",
    "Thanks for being upfront. I'd love the chance to do a side-by-side with {competitor} on total cost, not just the per-vehicle price.",
    "Totally fair to look around. Ask {competitor} about their camera false-positive rate, because that's what drives managers crazy.",
]
QUOTE_LINE = ("{competitor} quoted us {price} a vehicle per month, and that quote is only good "
              "through {expires}.")
QUOTE_RESPONSE = ("Thanks for being straight with me. Let me put together a side-by-side before "
                  "{expires}. Once you factor in the coaching and the insurance savings, I think the numbers look different.")
PRODUCT_QA = {
    "Vehicle Telematics": (
        "How often does the GPS actually update?",
        "Every second while the vehicle is moving. You get live location in the dashboard and the mobile app, plus a full trip history."),
    "AI Dash Cams": (
        "Do the cameras record all the time?",
        "They buffer continuously, but by default we only upload clips when the AI detects an event, like harsh braking, a rolling stop, or phone use."),
    "Driver Safety": (
        "How does the coaching workflow work day to day?",
        "Managers get a queue of events each week, and drivers see a scorecard in their app, so it's coaching, not just discipline."),
    "Fuel & Maintenance": (
        "Can it flag fault codes before a truck breaks down on us?",
        "Yes. We read engine fault codes in real time and schedule preventive maintenance by mileage or engine hours."),
    "Compliance/ELD": (
        "Is the ELD certified, and how does it handle roadside inspections?",
        "It's on the FMCSA registered list. Drivers can show logs on the tablet or transfer them right at the roadside."),
    "Equipment Monitoring": (
        "Can we put trackers on the unpowered stuff, like trailers and generators?",
        "Yes. The battery-powered asset gateways last about three years and check in several times a day."),
}
ROLE_LINES = {  # (customer question, Fleetwise answer)
    "CFO": [
        ("What I care about is payback. How fast do customers like us typically see a return?",
         "Most customers your size see payback in about seven to nine months, mostly from fuel and insurance."),
        ("Can we do quarterly billing instead of annual up front?",
         "Yes, quarterly billing is fine on a multi-year agreement. I'll put that in the paper."),
    ],
    "IT": [
        ("Do you support SSO with our identity provider?",
         "Yes, we support SAML single sign-on and SCIM provisioning, so accounts follow your directory."),
        ("Where is the data stored, and do you have a SOC 2 report we can review?",
         "It's hosted in US data centers, and I'll send over our SOC 2 Type II report after this call."),
    ],
    "Safety Director": [
        ("We had a rollover in the spring, so anything that helps us coach before an incident is a big deal for me.",
         "That's exactly where the AI coaching helps. Drivers get nudged in the cab before it turns into an incident."),
        ("Our insurance renewal is coming up, and the carrier keeps asking what we're doing about distracted driving.",
         "We can give you a safety report to share with your carrier. A lot of customers use it to negotiate their premium."),
    ],
    "Fleet Manager": [
        ("Day to day, I just need to know where everything is and which units are due for service.",
         "That's the home screen: live map, plus a maintenance list sorted by what's due next."),
        ("I'm the one who has to get the drivers on board, so the app needs to be simple.",
         "The driver app is three taps to start a shift, and we run a training session with your drivers at install."),
    ],
    "VP Operations": [
        ("For me this is about utilization. I think we have too many vehicles for the work we do.",
         "The utilization report shows idle and unused vehicles by site, so you can right-size the fleet."),
        ("I need something I can show the leadership team every month.",
         "We have an executive summary report that goes out monthly. I can share a sample with your data after a pilot."),
    ],
}
EXTRA_EXCHANGES = [  # (seller, customer if intent high, customer if intent low)
    ("How are the drivers feeling about all this?",
     "Most of them are on board. The younger guys actually asked for the app.",
     "Mixed, honestly. Some of the veterans think it's Big Brother."),
    ("What happens today when a vehicle breaks down on a route?",
     "It's chaos. Dispatch calls around until someone answers, and we lose half a day. That's a big reason we're here.",
     "We deal with it. It's not great, but it hasn't been a big enough problem to change anything."),
    ("Have you looked at what you're spending on fuel per vehicle?",
     "Yes, and it's gone up every quarter this year. Finance wants a plan.",
     "Not really. Fuel is fuel, it's hard to control."),
    ("Would a reference call with a similar customer be helpful?",
     "Yes, that would help a lot with getting leadership comfortable.",
     "Maybe later. We're not at that point yet."),
    ("How do you want to handle the rollout, all at once or by site?",
     "Probably start with the two biggest yards, then everyone else the month after.",
     "If we did anything, it would have to be very slow."),
    ("What would make this a no-brainer for you?",
     "Honestly, if the insurance savings are real, it already is.",
     "It would need to pay for itself in the first year, and I'm not sure it does."),
    ("Is there anything from your last vendor experience you want to avoid?",
     "Long installs. Last time it took four months to get every truck online.",
     "Surprise fees. We got burned on hardware replacement charges."),
]
SE_LINES = [
    "On implementation, we'd plan installs over two or three weekends, and I'd run the admin training myself.",
    "From a technical side, the hardware is plug-and-play on the diagnostic port for most of your vehicles.",
    "I'll also set up the integration with your maintenance system during onboarding.",
]
ACKS = ["Great, that's really helpful.", "Perfect. I'll make sure we're ready on our side.",
        "Love hearing that.", "That's great to hear.", "Okay, good. That helps me plan."]
NEXT_STEP_SELLER = [
    "send over the revised proposal",
    "set up a twenty-vehicle pilot",
    "get our solutions engineer on a call with your IT team",
    "send the security questionnaire responses",
    "send the ROI model with your fuel numbers plugged in",
    "schedule the install planning call",
    "send the order form",
    "send a customer reference in {industry_lower}",
]
NEXT_STEP_SELLER_COMP = "put together a side-by-side comparison against {competitor}"
NEXT_STEP_CUSTOMER = [
    "share the current fuel spend by site",
    "loop in finance for a pricing review",
    "check the union agreement on in-cab cameras",
    "send the vehicle list with VINs",
    "get IT to review the SSO setup",
    "set up time with the leadership team",
]
CLOSING = {
    "positive": [("This was really helpful. Talk soon.", "Thanks, {cfirst}. Have a great rest of your week.")],
    "neutral": [("Okay, thanks. We'll be in touch.", "Sounds good. Thanks for the time, everyone.")],
    "negative": [("Alright. Send it over and we'll take a look when we can.",
                  "Will do. Thanks for being candid with me, {cfirst}.")],
}
SEASONS = {11: "storm season", 12: "the holiday rush", 1: "year-end close", 2: "winter routes",
           3: "spring kickoff", 4: "spring projects", 5: "paving season", 6: "summer peak",
           7: "summer peak", 8: "back-to-school routes", 9: "fall projects", 10: "harvest season"}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def spoken_date(d: date, with_weekday: bool = True) -> str:
    s = f"{d.strftime('%B')} {_ordinal(d.day)}"
    return f"{d.strftime('%A')}, {s}" if with_weekday else s


def _money(x: float) -> str:
    return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}".replace(".00", "")


def sentiment_for(intent: float, rng: random.Random) -> str:
    x = intent + rng.uniform(-0.08, 0.08)
    return "positive" if x >= 0.62 else "negative" if x < 0.38 else "neutral"


def render_call(rng: random.Random, *, meeting_id: str, call_type: str, started_at: datetime,
                opp: dict, account: dict, seller: dict, se_name: str | None,
                contacts: list[dict], mention_competitors: list[str],
                quote: dict | None) -> tuple[dict, dict]:
    """Return (transcript_json, planted) for one call."""
    intent = opp["intent"]
    sentiment = sentiment_for(intent, rng)
    call_date = started_at.date()
    fleet = opp["fleet_in_scope"]
    industry = account["Industry"]

    attendees = [{"name": seller["Name"], "email": seller["Email"], "role": "Account Executive",
                  "company": FLEETWISE_COMPANY}]
    if se_name:
        attendees.append({"name": se_name,
                          "email": se_name.lower().replace(" ", ".") + "@fleetwise.example",
                          "role": "Sales Engineer", "company": FLEETWISE_COMPANY})
    for c in contacts:
        attendees.append({"name": c["Name"], "email": c["Email"], "role": c["Role__c"],
                          "company": account["Name"]})
    by_role = {c["Role__c"]: c for c in contacts}
    lead_c = contacts[0]
    cfirst = lead_c["FirstName"]
    S = seller["Name"]
    turns: list[tuple[str, str]] = []

    def cust(role_pref: str | None = None) -> str:
        if role_pref and role_pref in by_role:
            return by_role[role_pref]["Name"]
        return rng.choice(contacts)["Name"]

    def fill(t: str, **kw) -> str:
        base = dict(cfirst=cfirst, fleet=fleet, industry_lower=industry.lower(),
                    season=SEASONS[call_date.month])
        base.update(kw)
        return t.format(**base)

    # 1. small talk + agenda
    s_line, c_line = rng.choice(SMALL_TALK)
    turns += [(S, fill(s_line)), (lead_c["Name"], fill(c_line))]
    if se_name:
        turns.append((S, f"I also brought {se_name.split()[0]}, one of our solutions engineers, for the technical questions."))
    turns.append((S, AGENDA[call_type]))
    turns.append((lead_c["Name"], "Works for me."))

    # 2. body by call type
    products = opp["products"]
    if call_type == "discovery":
        turns.append((S, DISCOVERY_Q[0]))
        turns.append((cust("Fleet Manager"),
                      f"Sure. We run about {account['Fleet_Size__c']} vehicles, mostly {VEHICLE_MIX[industry]}. "
                      f"Today it's a mix of spreadsheets and an old GPS system that half the trucks don't even report to."))
        turns.append((S, DISCOVERY_Q[1]))
        turns.append((cust("VP Operations"), f"Honestly, {rng.choice(PAINS[industry])}."))
        turns.append((S, "That's really common. How are you handling that today?"))
        turns.append((cust(), "Mostly phone calls and gut feel, if I'm being honest."))
        turns.append((S, DISCOVERY_Q[2]))
        roles_here = ", ".join(sorted({c['Role__c'] for c in contacts}))
        turns.append((lead_c["Name"], f"It'd be the group on this call ({roles_here}), and our CFO signs anything over budget."))
    elif call_type == "demo_followup":
        turns.append((cust(), "The team liked the demo. A few questions came up afterward."))
        for p in products[:3]:
            q, a = PRODUCT_QA[p]
            turns.append((cust(), q))
            turns.append((se_name or S, a))
    elif call_type == "pricing":
        monthly = fleet * sum(PRODUCT_PRICE[p] for p in products)
        disc = rng.choice([8, 10, 12, 15])
        turns.append((S, f"So for {fleet} vehicles on {', '.join(products)}, list comes to about "
                         f"{_money(monthly)} a month. On a three-year term we can take {disc} percent off that."))
        if intent >= 0.55:
            turns.append((cust("CFO"), "That's within the range we were expecting."))
        else:
            turns.append((cust("CFO"), "That's more than we were expecting, to be honest."))
        turns.append((S, "The bigger number to look at is the savings side. Fuel, insurance, and fewer accidents usually cover it."))
    else:  # renewal
        adoption = int(55 + 40 * intent)
        turns.append((S, f"Over the last quarter, about {adoption} percent of your vehicles reported every day, "
                         f"and harsh driving events are down {int(10 + 25 * intent)} percent since go-live."))
        if intent >= 0.55:
            turns.append((cust("VP Operations"), "We've been happy. The team uses it every day, and we'd like to talk about adding more."))
        else:
            turns.append((cust("Fleet Manager"), "Honestly, adoption has been spotty out in the field, and a couple of sites stopped using it."))

    # role-specific questions
    for role in [c["Role__c"] for c in contacts][:2]:
        if rng.random() < 0.7:
            q, a = rng.choice(ROLE_LINES[role])
            turns.append((by_role[role]["Name"], q))
            turns.append((se_name if (role == "IT" and se_name) else S, a))
    if se_name:
        turns.append((se_name, rng.choice(SE_LINES)))
        turns.append((lead_c["Name"], "Good to know, thanks."))
    for sq, hi_a, lo_a in rng.sample(EXTRA_EXCHANGES, rng.randint(2, 4)):
        turns.append((S, sq))
        turns.append((cust(), hi_a if intent + rng.uniform(-0.15, 0.15) >= 0.5 else lo_a))

    # 3. buying signals & objections scale with intent
    n_signals = max(0, round(intent * 4 + rng.uniform(-0.7, 0.7)))
    n_objections = max(0, round((1 - intent) * 3 + rng.uniform(-0.7, 0.7)))
    deadline = spoken_date(call_date + timedelta(days=rng.randint(30, 75)), with_weekday=False)
    acks = rng.sample(ACKS, len(ACKS))
    for line in rng.sample(BUYING_SIGNALS, min(n_signals, len(BUYING_SIGNALS))):
        turns.append((cust(), fill(line, deadline=deadline)))
        if acks and rng.random() < 0.6:
            turns.append((S, acks.pop()))
    for obj, resp in rng.sample(OBJECTIONS, min(n_objections, len(OBJECTIONS))):
        turns.append((cust(), fill(obj)))
        turns.append((S, fill(resp)))
    if 0.35 <= intent < 0.6:
        turns.append((cust(), rng.choice(NEUTRAL_LINES)))

    # 4. competitors
    for comp in mention_competitors:
        if quote and quote["competitor"] == comp:
            exp = spoken_date(date.fromisoformat(quote["expires_on"]), with_weekday=False)
            turns.append((cust("CFO"), QUOTE_LINE.format(competitor=comp,
                                                          price=_money(quote["price_per_vehicle"]),
                                                          expires=exp)))
            turns.append((S, QUOTE_RESPONSE.format(expires=exp)))
        else:
            turns.append((cust(), rng.choice(COMPETITOR_MENTIONS).format(competitor=comp)))
            turns.append((S, rng.choice(COMPETITOR_RESPONSES).format(competitor=comp)))

    # 5. next steps said aloud
    n_steps = 3 if intent >= 0.65 else 2 if intent >= 0.35 else 1
    seller_pool = [fill(x) for x in NEXT_STEP_SELLER]
    if mention_competitors:
        seller_pool.insert(0, NEXT_STEP_SELLER_COMP.format(competitor=mention_competitors[0]))
    steps = []
    s_actions = ([seller_pool[0]] if mention_competitors else []) + rng.sample(seller_pool[1 if mention_competitors else 0:], 2)
    c_actions = rng.sample(NEXT_STEP_CUSTOMER, 2)
    owners = ["seller", "customer", "seller"][:n_steps]
    si = ci = 0
    for k, who in enumerate(owners):
        due = call_date + timedelta(days=rng.randint(2, 9) + 3 * k)
        if due.weekday() >= 5:
            due += timedelta(days=7 - due.weekday())  # move weekend dues to Monday
        if who == "seller":
            steps.append({"action": s_actions[si], "owner": S, "due": due.isoformat()})
            si += 1
        else:
            c = rng.choice(contacts)
            steps.append({"action": c_actions[ci], "owner": c["Name"], "due": due.isoformat()})
            ci += 1
    steps.sort(key=lambda st: st["due"])
    parts = []
    for st in steps:
        when = spoken_date(date.fromisoformat(st["due"]))
        if st["owner"] == S:
            parts.append(f"I'll {st['action']} by {when}")
        else:
            parts.append(f"{st['owner'].split()[0]}, you'll {st['action']} by {when}")
    recap = "So, to recap next steps: " + "; and ".join(parts) + "."
    turns.append((S, recap))
    turns.append((lead_c["Name"], "Yep, that works." if sentiment != "negative" else "Sure. No promises on timing, though."))

    # 6. closing
    c_close, s_close = rng.choice(CLOSING[sentiment])
    turns.append((lead_c["Name"], fill(c_close)))
    turns.append((S, fill(s_close)))

    # timestamps spread over the meeting duration proportional to words spoken
    duration = {"discovery": 30, "demo_followup": 45, "pricing": 30, "renewal": 30}[call_type]
    duration = max(15, duration + rng.randint(-8, 12))
    words = [len(t.split()) + 6 for _, t in turns]
    total = sum(words)
    span = duration * 60 * 0.93
    out_turns, acc = [], 0.0
    for (speaker, text), w in zip(turns, words):
        sec = int(math.floor(acc / total * span)) + 4
        out_turns.append({"speaker": speaker,
                          "ts": f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}",
                          "text": text})
        acc += w
    transcript = {
        "meeting_id": meeting_id,
        "opportunity_id": opp["Id"],
        "account_id": account["Id"],
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_min": duration,
        "attendees": attendees,
        "turns": out_turns,
    }
    planted = {
        "competitors": list(mention_competitors),
        "next_steps": steps,
        "quotes": [quote] if quote and quote["competitor"] in mention_competitors else [],
        "sentiment": sentiment,
        "call_type": call_type,
    }
    return transcript, planted
