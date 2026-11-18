"""OpenJev (System One) question maps for deal and lead scoring (Task 6, spec 4.4).

System One question format: each question has a `type` (score | choice | noul), the
`instructions` the model answers, and `criteria`: an ordered list of levels for `score`,
a {key: description} map for `choice`; `noul` needs instructions only (answer 0..1).

Bump QUESTIONS_VERSION when any question changes: every open opp/lead is then re-scored.
"""

QUESTIONS_VERSION = "v1"
MODEL = "system.ai.openjev-qwen35-4b"

CLOSE_LEVELS = ["Very unlikely", "Unlikely", "Possible", "Likely", "Very likely"]
FIT_LEVELS = ["Very poor fit", "Poor fit", "Moderate fit", "Good fit", "Excellent fit"]

DEAL_QUESTIONS: dict = {
    "close_this_quarter": {
        "type": "score",
        "instructions": "How likely is this Fleetwise opportunity to close (won) by its close date "
        "in the current fiscal quarter? Weigh stage, time left, activity, competition, account "
        "health and what was said on recent calls.",
        "criteria": CLOSE_LEVELS,
    },
    "next_action": {
        "type": "choice",
        "instructions": "What is the single best next action for the Fleetwise seller on this deal?",
        "criteria": {
            "send_proposal": "The customer is ready for pricing: send or revise the proposal.",
            "multithread": "Only one contact is engaged: bring in more stakeholders (IT, finance, operations).",
            "schedule_demo": "The customer has not yet seen the product working: schedule a demo or pilot.",
            "exec_sponsor": "The deal is large or stuck at a decision: engage an executive sponsor on both sides.",
            "address_risk": "A blocker is open (competitor quote, support issues, objections): address it directly.",
            "nurture": "The customer is not ready to buy now: keep in touch and nurture.",
        },
    },
    "competitive_risk": {
        "type": "noul",
        "instructions": "Is a competitor actively in this deal with a real chance of winning it?",
    },
    "churn_risk": {
        "type": "noul",
        "instructions": "Is this account at risk of churning or shrinking (declining usage, open or "
        "severe support tickets, negative sentiment)?",
    },
}

LEAD_QUESTIONS: dict = {
    "conversion_fit": {
        "type": "score",
        "instructions": "How well does this inbound lead fit Fleetwise (fleet telematics, AI dash cams, "
        "driver safety, fuel and maintenance, ELD compliance, equipment monitoring) and how likely is "
        "it to convert to a qualified opportunity?",
        "criteria": FIT_LEVELS,
    },
    "route_to": {
        "type": "choice",
        "instructions": "Which Fleetwise sales segment should work this lead?",
        "criteria": {
            "SMB": "Small fleets (roughly under 50 vehicles), simple buying process.",
            "Mid-Market": "Mid-size fleets (roughly 50 to 500 vehicles), a few stakeholders.",
            "Enterprise": "Large fleets (roughly over 500 vehicles), complex multi-stakeholder buying.",
        },
    },
}
