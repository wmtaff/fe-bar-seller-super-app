"""Word banks for plausible (fictional) company names, places and titles."""

TOWNS = [
    "Cedar Hollow", "Pine Ridge", "Silver Creek", "Granite Falls", "Maple Grove", "Red Mesa",
    "Copper Basin", "Blue Heron", "Willow Bend", "Iron Gate", "Stone Harbor", "Clearwater",
    "Eagle Pass", "Fox Run", "Hawthorne", "Juniper Flats", "Kingsbridge", "Lakemont",
    "Millbrook", "North Fork", "Oak Haven", "Prairie View", "Quarry Point", "Ridgeway",
    "Sandstone", "Timberline", "Valley Forge", "Westbrook", "Yellow Pine", "Summit Park",
    "Harbor View", "Desert Springs", "Riverside", "Elm Crossing", "Bayview", "Highland",
    "Brookfield", "Canyon Ridge", "Fairhaven", "Glenwood", "Ashford", "Bridgewater",
    "Crestview", "Dunmore", "Evergreen", "Foxborough", "Greystone", "Hillcrest",
]
ADJ = [
    "Summit", "Keystone", "Pioneer", "Frontier", "Liberty", "Atlas", "Beacon", "Cornerstone",
    "Evergreen", "Horizon", "Ironwood", "Landmark", "Meridian", "Northstar", "Patriot",
    "Redline", "Sterling", "Trailhead", "Vanguard", "Bluewater", "Coastal", "Heartland",
    "Lone Pine", "Mesa", "Quicksilver", "Rocky Mountain", "Sunbelt", "Tri-County", "Allied",
    "Precision", "Reliable", "Express", "Continental", "Great Plains", "Golden State",
]
INDUSTRY_TEMPLATES = {
    "Construction": [
        "{last} Construction", "{adj} Builders", "{town} Contracting", "{last} & Sons Excavating",
        "{adj} Paving", "{last} Concrete", "{adj} Civil Group", "{town} Earthworks",
        "{last} General Contractors", "{adj} Crane & Rigging",
    ],
    "Logistics & Transportation": [
        "{adj} Freight", "{last} Logistics", "{town} Trucking", "{adj} Line Transport",
        "{last} Express Lines", "{adj} Carriers", "{town} Distribution", "{last} Haulage",
        "{adj} Intermodal", "{last} Cartage",
    ],
    "Field Services": [
        "{last} Plumbing & HVAC", "{town} Pest Control", "{adj} Home Services",
        "{last} Electric", "{adj} Landscaping", "{town} Mechanical", "{last} Roofing",
        "{adj} Facility Services", "{town} Cable & Fiber", "{last} Fire Protection",
    ],
    "Public Sector": [
        "{town} Public Works", "{town} County Transit", "{town} Water Authority",
        "{town} Unified School District", "{town} Parks Department", "{town} Sanitation District",
        "{town} County Fleet Services", "{town} Housing Authority",
    ],
    "Food & Beverage": [
        "{adj} Beverage Distributors", "{last} Foods", "{town} Dairy", "{adj} Produce",
        "{last} Bakery Supply", "{town} Coffee Roasters", "{adj} Foodservice",
        "{last} Brewing Distribution", "{town} Meat Co.", "{adj} Fresh Markets",
    ],
}
NAME_SUFFIXES = ["Inc.", "LLC", "Co.", "Group", "Corp.", "Holdings", "Partners", "Services"]

CONTACT_TITLES = {
    "VP Operations": ["VP of Operations", "Vice President, Operations", "Director of Operations",
                      "COO"],
    "Fleet Manager": ["Fleet Manager", "Fleet Operations Manager", "Director of Fleet",
                      "Transportation Manager"],
    "Safety Director": ["Safety Director", "Director of Safety & Compliance", "EHS Manager",
                        "Risk & Safety Manager"],
    "CFO": ["CFO", "Chief Financial Officer", "VP Finance", "Controller"],
    "IT": ["IT Director", "Director of IT", "IT Manager", "Systems Administrator"],
}
LEAD_TITLES = [
    "Fleet Manager", "Operations Manager", "Safety Coordinator", "Owner", "General Manager",
    "Director of Operations", "Transportation Supervisor", "Controller", "IT Manager",
    "Dispatch Manager",
]
LEAD_SOURCES = ["Web", "Webinar", "Trade Show", "Partner Referral", "Outbound", "Content Download",
                "Customer Referral"]
OPP_LEAD_SOURCES = ["Inbound", "Outbound", "Partner", "Event", "Customer Expansion"]
DIRECTIONS = ["North", "South", "East", "West", "Greater", "Upper", "Lower", "Central"]
