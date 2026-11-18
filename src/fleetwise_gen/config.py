"""Constants for the Fleetwise synthetic data generator.

All dates are fixed (ruling R7): the data "as-of" date is 2026-11-16 and the
fiscal year starts Feb 1, so the current fiscal quarter FY27Q4 is
2026-11-01..2027-01-31.
"""

from datetime import date, datetime, timedelta, timezone

AS_OF_DATE = date(2026, 11, 16)
AS_OF = AS_OF_DATE.isoformat()
# Batch N lands at BATCH_BASE_TS + N hours (init = batch 0 = BATCH_BASE_TS).
BATCH_BASE_TS = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)

CURRENT_FQ_START = "2026-11-01"
CURRENT_FQ_END = "2027-01-31"
NEXT_FQ_START = "2027-02-01"
NEXT_FQ_END = "2027-04-30"
FISCAL_YEAR_START_MONTH = 2  # February

# ---- sizes for --init ----
N_RVPS = 8
N_MANAGERS = 60
N_SELLERS = 600
N_ACCOUNTS = 5000
CONTACTS_PER_ACCOUNT = 4
N_OPEN_OPPS = 3000
N_CLOSED_OPPS = 12000
N_LEADS = 4000
TARGET_ACTIVITIES = 60000
N_TRANSCRIPTS = 600
USAGE_DAYS = 90
N_TICKETS = 8000

# ---- sizes for each --increment ----
INC_STAGE_CHANGES = 150
INC_ACTIVITIES = 1000
INC_TRANSCRIPTS = 40
INC_TICKETS = 100
INC_LEADS = 50

# ---- reserved index ranges so increment IDs never collide with init IDs ----
# Increment entity i of batch N gets index BASE + (N-1)*STRIDE + i.
INC_INDEX_BASE = 1_000_000
INC_INDEX_STRIDE = 10_000

# ---- domain ----
PRODUCTS = [
    "Vehicle Telematics",
    "AI Dash Cams",
    "Driver Safety",
    "Fuel & Maintenance",
    "Compliance/ELD",
    "Equipment Monitoring",
]
# $ per vehicle per month (list).
PRODUCT_PRICE = {
    "Vehicle Telematics": 33,
    "AI Dash Cams": 39,
    "Driver Safety": 18,
    "Fuel & Maintenance": 12,
    "Compliance/ELD": 15,
    "Equipment Monitoring": 21,
}
PRODUCT_COL = {
    "Vehicle Telematics": "adoption_vehicle_telematics",
    "AI Dash Cams": "adoption_ai_dash_cams",
    "Driver Safety": "adoption_driver_safety",
    "Fuel & Maintenance": "adoption_fuel_maintenance",
    "Compliance/ELD": "adoption_compliance_eld",
    "Equipment Monitoring": "adoption_equipment_monitoring",
}
COMPETITORS = ["RoadLynx", "FleetCore", "Trackwell"]  # all fictional
INDUSTRIES = [
    "Construction",
    "Logistics & Transportation",
    "Field Services",
    "Public Sector",
    "Food & Beverage",
]
CUSTOMER_ROLES = ["VP Operations", "Fleet Manager", "Safety Director", "CFO", "IT"]
SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
# The 8 RVP territories (segment, region).
TERRITORIES = [
    ("Enterprise", "West"),
    ("Enterprise", "East"),
    ("Mid-Market", "West"),
    ("Mid-Market", "Central"),
    ("Mid-Market", "East"),
    ("SMB", "West"),
    ("SMB", "Central"),
    ("SMB", "East"),
]
REGION_STATES = {
    "West": ["CA", "WA", "OR", "AZ", "NV", "CO", "UT", "ID"],
    "Central": ["TX", "IL", "OH", "MN", "MO", "OK", "KS", "WI"],
    "East": ["NY", "NJ", "PA", "GA", "FL", "NC", "VA", "MA"],
}
# Fleet sizes and deal volume per segment are tuned (ruling R13) so that a seller's closed-won
# ACV over a year is roughly their segment quota / 1.2.
SEGMENT_FLEET = {"SMB": (150, 300), "Mid-Market": (380, 760), "Enterprise": (700, 1400)}
# Relative deal volume per seller of this segment (smooth weighted round-robin over sellers).
SEGMENT_DEAL_WEIGHT = {"SMB": 3.0, "Mid-Market": 2.75, "Enterprise": 3.0}
# Share of the account's fleet in scope for a New Business / Expansion opp (Renewal = 1.0).
OPP_FLEET_COVERAGE = (0.8, 1.0)
# Extra products beyond the first on a New Business / Expansion opp (drawn uniformly).
OPP_EXTRA_PRODUCTS = [0, 0, 0, 0, 1]
SEGMENT_CYCLE_DAYS = {"SMB": (20, 60), "Mid-Market": (45, 120), "Enterprise": (90, 220)}
SEGMENT_QUOTA = {"SMB": 600_000, "Mid-Market": 1_100_000, "Enterprise": 2_000_000}

OPEN_STAGES = ["Qualification", "Discovery", "Demo", "Proposal", "Negotiation"]
STAGE_PROB = {
    "Qualification": 10, "Discovery": 20, "Demo": 40, "Proposal": 60,
    "Negotiation": 80, "Closed Won": 100, "Closed Lost": 0,
}
STAGE_FORECAST = {
    "Qualification": "Pipeline", "Discovery": "Pipeline", "Demo": "Best Case",
    "Proposal": "Best Case", "Negotiation": "Commit", "Closed Won": "Closed",
    "Closed Lost": "Omitted",
}

FLEETWISE_COMPANY = "Fleetwise"
FLEETWISE_DOMAIN = "fleetwise.example"

# Demo personas (load-bearing for the app, Genie and tests).
JORDAN = ("Jordan", "Rivera")
MORGAN = ("Morgan", "Lee")
TAYLOR = ("Taylor", "Empty")
JORDAN_OPEN_OPPS = 25
JORDAN_TRANSCRIBED_OPPS = 10
JORDAN_QUOTE_OPPS = 3
JORDAN_QUOTA = 2_000_000  # annual (ruling R12)
# Jordan persona economics (ruling R13): his open deals are phased rollouts (25-40% of the
# fleet in scope), and one ~$165k deal closed won this quarter (attainment ~30%).
JORDAN_OPP_COVERAGE = (0.25, 0.4)
JORDAN_QTD_WON_ACV = 165_000
JORDAN_QTD_WON_DATE = "2026-11-06"
# Indices of Jordan's 25 open opps that close in FY28Q1; the other 18 close in FY27Q4, giving
# FY27Q4 coverage ~3.5x (rulings R12, R13). Transcribed opps are j < 10 and quote opps j < 3,
# so all 10 transcribed and all 3 quote opps stay in FY27Q4.
JORDAN_NEXT_Q_OPPS = (12, 13, 14, 16, 17, 18, 23)
# Quota (ruling R13): clamp(trailing-4-fiscal-quarter closed-won ACV x 1.2, 0.6x, 1.8x SEGMENT_QUOTA).
QUOTA_GROWTH = 1.2
QUOTA_MIN_X = 0.6
QUOTA_MAX_X = 1.8
TRAILING_4Q_START = "2025-11-01"  # FY26Q4 .. FY27Q3
TRAILING_4Q_END = "2026-10-31"


def batch_ts(batch: int) -> datetime:
    return BATCH_BASE_TS + timedelta(hours=batch)


def fmt_ts(dt: datetime) -> str:
    """Salesforce-style UTC timestamp with millis, e.g. 2026-11-16T12:00:00.000Z."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fiscal_quarter(d: date) -> str:
    """FY label for a date, FY starting Feb 1 (2026-11-16 -> FY27Q4)."""
    fy = d.year + 1 if d.month >= FISCAL_YEAR_START_MONTH else d.year
    q = ((d.month - FISCAL_YEAR_START_MONTH) % 12) // 3 + 1
    return f"FY{fy % 100:02d}Q{q}"
