"""
Indian Location Taxonomy & Hierarchy Module.
Covers 28 States, 8 Union Territories, major tech clusters, metro corridors,
localities, airport codes, and query expansion helpers.
"""

from dataclasses import dataclass
from typing import Any

INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

INDIAN_UNION_TERRITORIES = [
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

STATE_CODES: dict[str, str] = {
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TG": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "UA": "Uttarakhand",
    "WB": "West Bengal",
    "AN": "Andaman and Nicobar Islands",
    "CH": "Chandigarh",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "DD": "Dadra and Nagar Haveli and Daman and Diu",
    "DL": "Delhi",
    "JK": "Jammu and Kashmir",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "PY": "Puducherry",
}

# Airport IATA codes mapping directly to (Canonical City, State)
# Kept separate from query expansion to prevent token substring collisions
AIRPORT_CODES: dict[str, tuple[str, str]] = {
    "BLR": ("Bengaluru", "Karnataka"),
    "DEL": ("Delhi NCR", "Delhi"),
    "BOM": ("Mumbai", "Maharashtra"),
    "HYD": ("Hyderabad", "Telangana"),
    "PNQ": ("Pune", "Maharashtra"),
    "MAA": ("Chennai", "Tamil Nadu"),
    "CCU": ("Kolkata", "West Bengal"),
    "IXC": ("Chandigarh", "Chandigarh"),
    "AMD": ("Ahmedabad", "Gujarat"),
    "COK": ("Kochi", "Kerala"),
    "TRV": ("Thiruvananthapuram", "Kerala"),
}

METRO_CLUSTERS: dict[str, dict[str, Any]] = {
    "Delhi NCR": {
        "canonical": "Delhi NCR",
        "state_or_ut": "Delhi",
        "cities": [
            "Delhi", "New Delhi", "Gurugram", "Gurgaon", "Noida", "Greater Noida",
            "Ghaziabad", "Faridabad", "Manesar", "Sonipat"
        ],
        "aliases": [
            "delhi ncr", "delhi-ncr", "ncr", "national capital region", "delhi", "new delhi",
            "gurgaon", "gurugram", "noida", "greater noida", "ghaziabad", "faridabad",
            "manesar"
        ],
    },
    "Bengaluru": {
        "canonical": "Bengaluru",
        "state_or_ut": "Karnataka",
        "cities": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi"],
        "aliases": [
            "bangalore", "bengaluru", "bangaluru", "bangalore urban",
            "bangalore rural", "greater bengaluru area", "whitefield", "electronic city",
            "koramangala", "indiranagar", "bellandur", "marathahalli", "manyata"
        ],
    },
    "Mumbai": {
        "canonical": "Mumbai",
        "state_or_ut": "Maharashtra",
        "cities": ["Mumbai", "Navi Mumbai", "Thane", "Kalyan"],
        "aliases": [
            "mumbai", "bombay", "navi mumbai", "thane", "bkc", "andheri", "powai",
            "goregaon", "lower parel", "malad", "mumbai metropolitan region", "mmr"
        ],
    },
    "Hyderabad": {
        "canonical": "Hyderabad",
        "state_or_ut": "Telangana",
        "cities": ["Hyderabad", "Secunderabad", "Warangal"],
        "aliases": [
            "hyderabad", "secunderabad", "cyberabad", "hitec city", "gachibowli",
            "madhapur", "kondapur", "kukatpally"
        ],
    },
    "Pune": {
        "canonical": "Pune",
        "state_or_ut": "Maharashtra",
        "cities": ["Pune", "Pimpri-Chinchwad", "Nagpur", "Nashik"],
        "aliases": [
            "pune", "poona", "pcmc", "pimpri chinchwad", "hinjewadi", "hinjawadi",
            "magarpatta", "kharadi", "viman nagar", "baner", "wakad"
        ],
    },
    "Chennai": {
        "canonical": "Chennai",
        "state_or_ut": "Tamil Nadu",
        "cities": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
        "aliases": [
            "chennai", "madras", "greater chennai area", "omr", "guindy",
            "sholinganallur", "tidel park", "velachery"
        ],
    },
    "Kolkata": {
        "canonical": "Kolkata",
        "state_or_ut": "West Bengal",
        "cities": ["Kolkata", "Howrah", "Durgapur", "Siliguri"],
        "aliases": [
            "kolkata", "calcutta", "salt lake", "salt lake city", "sector v",
            "new town", "rajarhat", "bidhannagar"
        ],
    },
    "Tricity (Chandigarh)": {
        "canonical": "Chandigarh",
        "state_or_ut": "Chandigarh",
        "cities": ["Chandigarh", "Mohali", "Panchkula"],
        "aliases": [
            "chandigarh", "mohali", "panchkula", "sas nagar", "tricity"
        ],
    },
    "Gujarat Tech Corridor": {
        "canonical": "Ahmedabad",
        "state_or_ut": "Gujarat",
        "cities": ["Ahmedabad", "Gandhinagar", "Vadodara", "Surat", "Rajkot"],
        "aliases": [
            "ahmedabad", "amdavad", "gandhinagar", "gift city", "vadodara", "baroda",
            "surat", "rajkot"
        ],
    },
    "Kerala Tech Corridor": {
        "canonical": "Kochi",
        "state_or_ut": "Kerala",
        "cities": ["Kochi", "Thiruvananthapuram", "Kozhikode"],
        "aliases": [
            "kochi", "cochin", "infopark", "ernakulam", "thiruvananthapuram", "trivandrum",
            "technopark", "technocity", "calicut", "kozhikode", "cyberpark"
        ],
    },
}

STATE_CITIES_MAP: dict[str, list[str]] = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Nellore", "Kakinada"],
    "Arunachal Pradesh": ["Itanagar"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama"],
    "Gujarat": ["Ahmedabad", "Gandhinagar", "Vadodara", "Surat", "Rajkot", "Bhavnagar"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal", "Panchkula", "Rohtak", "Sonipat", "Manesar"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Dharwad", "Belagavi", "Kalaburagi"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Navi Mumbai", "Thane", "Aurangabad", "Chhatrapati Sambhajinagar", "Kolhapur", "Solapur"],
    "Manipur": ["Imphal"],
    "Meghalaya": ["Shillong"],
    "Mizoram": ["Aizawl"],
    "Nagaland": ["Kohima", "Dimapur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Mohali", "Bathinda"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Bikaner", "Ajmer"],
    "Sikkim": ["Gangtok"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli"],
    "Telangana": ["Hyderabad", "Secunderabad", "Warangal", "Nizamabad", "Karimnagar"],
    "Tripura": ["Agartala"],
    "Uttar Pradesh": ["Noida", "Greater Noida", "Ghaziabad", "Lucknow", "Kanpur", "Agra", "Varanasi", "Prayagraj", "Meerut", "Bareilly"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rishikesh"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri"],
    "Delhi": ["Delhi", "New Delhi"],
    "Chandigarh": ["Chandigarh"],
    "Jammu and Kashmir": ["Srinagar", "Jammu"],
    "Ladakh": ["Leh"],
    "Puducherry": ["Puducherry"],
    "Andaman and Nicobar Islands": ["Port Blair"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa"],
    "Lakshadweep": ["Kavaratti"],
}

CANONICAL_CITY_LOOKUP: dict[str, tuple[str, str]] = {}

for state_name, cities in STATE_CITIES_MAP.items():
    for city in cities:
        CANONICAL_CITY_LOOKUP[city.lower()] = (city, state_name)

SPECIAL_ALIASES: dict[str, tuple[str, str]] = {
    # Karnataka
    "bangalore": ("Bengaluru", "Karnataka"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "bangaluru": ("Bengaluru", "Karnataka"),
    "whitefield": ("Bengaluru", "Karnataka"),
    "electronic city": ("Bengaluru", "Karnataka"),
    "koramangala": ("Bengaluru", "Karnataka"),
    "indiranagar": ("Bengaluru", "Karnataka"),
    "bellandur": ("Bengaluru", "Karnataka"),
    "marathahalli": ("Bengaluru", "Karnataka"),
    "manyata": ("Bengaluru", "Karnataka"),
    "hebbal": ("Bengaluru", "Karnataka"),
    "mysore": ("Mysuru", "Karnataka"),
    "mangalore": ("Mangaluru", "Karnataka"),
    "hubli": ("Hubballi", "Karnataka"),
    "belgaum": ("Belagavi", "Karnataka"),
    
    # NCR & North
    "delhi": ("Delhi NCR", "Delhi"),
    "new delhi": ("Delhi NCR", "Delhi"),
    "delhi ncr": ("Delhi NCR", "Delhi"),
    "ncr": ("Delhi NCR", "Delhi"),
    "gurgaon": ("Gurugram", "Haryana"),
    "gurugram": ("Gurugram", "Haryana"),
    "noida": ("Delhi NCR", "Uttar Pradesh"),
    "greater noida": ("Delhi NCR", "Uttar Pradesh"),
    "ghaziabad": ("Delhi NCR", "Uttar Pradesh"),
    "faridabad": ("Delhi NCR", "Haryana"),
    "manesar": ("Gurugram", "Haryana"),

    # Maharashtra
    "mumbai": ("Mumbai", "Maharashtra"),
    "bombay": ("Mumbai", "Maharashtra"),
    "navi mumbai": ("Navi Mumbai", "Maharashtra"),
    "thane": ("Thane", "Maharashtra"),
    "bkc": ("Mumbai", "Maharashtra"),
    "andheri": ("Mumbai", "Maharashtra"),
    "powai": ("Mumbai", "Maharashtra"),
    "goregaon": ("Mumbai", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"),
    "poona": ("Pune", "Maharashtra"),
    "hinjewadi": ("Pune", "Maharashtra"),
    "hinjawadi": ("Pune", "Maharashtra"),
    "magarpatta": ("Pune", "Maharashtra"),
    "kharadi": ("Pune", "Maharashtra"),
    "baner": ("Pune", "Maharashtra"),
    "wakad": ("Pune", "Maharashtra"),
    "pcmc": ("Pune", "Maharashtra"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "nashik": ("Nashik", "Maharashtra"),

    # Telangana & AP
    "hyderabad": ("Hyderabad", "Telangana"),
    "secunderabad": ("Hyderabad", "Telangana"),
    "cyberabad": ("Hyderabad", "Telangana"),
    "hitec city": ("Hyderabad", "Telangana"),
    "hitech city": ("Hyderabad", "Telangana"),
    "gachibowli": ("Hyderabad", "Telangana"),
    "madhapur": ("Hyderabad", "Telangana"),
    "kondapur": ("Hyderabad", "Telangana"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),

    # Tamil Nadu
    "chennai": ("Chennai", "Tamil Nadu"),
    "madras": ("Chennai", "Tamil Nadu"),
    "omr": ("Chennai", "Tamil Nadu"),
    "guindy": ("Chennai", "Tamil Nadu"),
    "tidel park": ("Chennai", "Tamil Nadu"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),

    # West Bengal
    "kolkata": ("Kolkata", "West Bengal"),
    "calcutta": ("Kolkata", "West Bengal"),
    "salt lake": ("Kolkata", "West Bengal"),
    "salt lake city": ("Kolkata", "West Bengal"),
    "sector v": ("Kolkata", "West Bengal"),
    "new town": ("Kolkata", "West Bengal"),
    "rajarhat": ("Kolkata", "West Bengal"),

    # Kerala
    "kochi": ("Kochi", "Kerala"),
    "cochin": ("Kochi", "Kerala"),
    "ernakulam": ("Kochi", "Kerala"),
    "infopark": ("Kochi", "Kerala"),
    "thiruvananthapuram": ("Thiruvananthapuram", "Kerala"),
    "trivandrum": ("Thiruvananthapuram", "Kerala"),
    "technopark": ("Thiruvananthapuram", "Kerala"),
    "calicut": ("Kozhikode", "Kerala"),
    "kozhikode": ("Kozhikode", "Kerala"),

    # Gujarat
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "amdavad": ("Ahmedabad", "Gujarat"),
    "gandhinagar": ("Gandhinagar", "Gujarat"),
    "gift city": ("Gandhinagar", "Gujarat"),
    "baroda": ("Vadodara", "Gujarat"),
    "vadodara": ("Vadodara", "Gujarat"),

    # Tricity
    "chandigarh": ("Chandigarh", "Chandigarh"),
    "mohali": ("Mohali", "Punjab"),
    "panchkula": ("Panchkula", "Haryana"),
}

CANONICAL_CITY_LOOKUP.update(SPECIAL_ALIASES)


@dataclass
class ResolvedLocation:
    canonical_name: str
    state_or_ut: str | None = None
    is_remote: bool = False
    is_metro: bool = False
    is_state_level: bool = False
    raw_input: str = ""


def resolve_canonical_location(raw_location: str | None) -> ResolvedLocation:
    """
    Standardize raw location string into canonical Indian location entity.
    Returns ResolvedLocation with city/state metadata.
    """
    if not raw_location or not raw_location.strip():
        return ResolvedLocation(canonical_name="Unknown", raw_input="")

    raw_clean = raw_location.strip()
    lower = raw_clean.lower()

    if any(k in lower for k in ["remote", "work from home", "wfh", "telecommute", "anywhere in india"]):
        if "india" in lower or "anywhere" in lower:
            return ResolvedLocation(canonical_name="Remote (India)", is_remote=True, raw_input=raw_clean)
        return ResolvedLocation(canonical_name="Remote", is_remote=True, raw_input=raw_clean)

    if raw_clean.upper() in STATE_CODES:
        state_full = STATE_CODES[raw_clean.upper()]
        return ResolvedLocation(
            canonical_name=state_full,
            state_or_ut=state_full,
            is_state_level=True,
            raw_input=raw_clean,
        )

    if raw_clean.upper() in AIRPORT_CODES:
        city, state = AIRPORT_CODES[raw_clean.upper()]
        return ResolvedLocation(
            canonical_name=city,
            state_or_ut=state,
            is_metro=False,
            raw_input=raw_clean,
        )

    for state in INDIAN_STATES + INDIAN_UNION_TERRITORIES:
        if lower == state.lower():
            return ResolvedLocation(
                canonical_name=state,
                state_or_ut=state,
                is_state_level=True,
                raw_input=raw_clean,
            )

    # 1. Exact / Suburb City match takes precedence (e.g. "gurgaon" -> Gurugram, "noida" -> Noida, "bengaluru" -> Bengaluru)
    for alias in sorted(CANONICAL_CITY_LOOKUP.keys(), key=len, reverse=True):
        if alias == lower or f", {alias}" in lower or f"{alias}," in lower or f" {alias} " in f" {lower} ":
            city, state = CANONICAL_CITY_LOOKUP[alias]
            return ResolvedLocation(
                canonical_name=city,
                state_or_ut=state,
                is_metro=False,
                raw_input=raw_clean,
            )

    # 2. Broad Metro Cluster alias match
    for cluster_key, cluster_info in METRO_CLUSTERS.items():
        for alias in sorted(cluster_info["aliases"], key=len, reverse=True):
            if alias == lower or f", {alias}" in lower or f"{alias}," in lower or f" {alias} " in f" {lower} ":
                return ResolvedLocation(
                    canonical_name=cluster_info["canonical"],
                    state_or_ut=cluster_info["state_or_ut"],
                    is_metro=True,
                    raw_input=raw_clean,
                )

    for state in sorted(INDIAN_STATES + INDIAN_UNION_TERRITORIES, key=len, reverse=True):
        if state.lower() in lower:
            parts = [p.strip() for p in raw_clean.split(",") if p.strip()]
            city_candidate = parts[0] if parts else state
            return ResolvedLocation(
                canonical_name=city_candidate.title(),
                state_or_ut=state,
                is_state_level=False,
                raw_input=raw_clean,
            )

    if lower in ["india", "pan india"]:
        return ResolvedLocation(canonical_name="India", raw_input=raw_clean)

    first_token = raw_clean.split(",")[0].strip()
    return ResolvedLocation(canonical_name=first_token.title(), raw_input=raw_clean)


def expand_location_query(locations: list[str] | None) -> set[str]:
    """
    Expands a list of query location strings to include:
    - All child cities if a State or UT was requested.
    - All cluster aliases/cities if a Metro Cluster was requested.
    - Synonyms and aliases for individual cities.
    """
    if not locations:
        return set()

    expanded: set[str] = set()

    for loc in locations:
        loc_str = loc.strip()
        if not loc_str:
            continue
        loc_lower = loc_str.lower()
        expanded.add(loc_lower)

        # State / UT Expansion
        for state_name, cities in STATE_CITIES_MAP.items():
            if loc_lower == state_name.lower():
                expanded.add(state_name.lower())
                for c in cities:
                    expanded.add(c.lower())

        # Metro Cluster Expansion (expand downward only when user asks for the cluster)
        for cluster_info in METRO_CLUSTERS.values():
            is_cluster_request = (
                loc_lower == cluster_info["canonical"].lower()
                or loc_lower in [a.lower() for a in cluster_info["aliases"]]
            )
            if is_cluster_request:
                for alias in cluster_info["aliases"]:
                    expanded.add(alias.lower())
                for city in cluster_info["cities"]:
                    expanded.add(city.lower())

        # Remote / WFH expansion
        if any(r in loc_lower for r in ["remote", "work from home", "wfh", "telecommute"]):
            for r_alias in ["remote", "work from home", "wfh", "telecommute", "anywhere in india", "remote (india)"]:
                expanded.add(r_alias)

        # Individual City alias expansion
        if loc_lower in CANONICAL_CITY_LOOKUP:
            canonical_city, parent_state = CANONICAL_CITY_LOOKUP[loc_lower]
            expanded.add(canonical_city.lower())
            for alias, (c_city, _) in CANONICAL_CITY_LOOKUP.items():
                if c_city.lower() == canonical_city.lower():
                    expanded.add(alias.lower())

    return expanded


def get_taxonomy_tree() -> dict[str, Any]:
    top_hubs = [
        {"name": "Bengaluru", "state": "Karnataka", "popular": True},
        {"name": "Delhi NCR", "state": "Delhi", "popular": True},
        {"name": "Mumbai", "state": "Maharashtra", "popular": True},
        {"name": "Hyderabad", "state": "Telangana", "popular": True},
        {"name": "Pune", "state": "Maharashtra", "popular": True},
        {"name": "Chennai", "state": "Tamil Nadu", "popular": True},
        {"name": "Kolkata", "state": "West Bengal", "popular": True},
        {"name": "Chandigarh", "state": "Chandigarh", "popular": False},
        {"name": "Ahmedabad", "state": "Gujarat", "popular": False},
        {"name": "Kochi", "state": "Kerala", "popular": False},
        {"name": "Jaipur", "state": "Rajasthan", "popular": False},
        {"name": "Indore", "state": "Madhya Pradesh", "popular": False},
    ]

    states_tree = []
    for state in sorted(INDIAN_STATES + INDIAN_UNION_TERRITORIES):
        cities = STATE_CITIES_MAP.get(state, [])
        states_tree.append({
            "name": state,
            "is_ut": state in INDIAN_UNION_TERRITORIES,
            "cities": sorted(cities),
        })

    return {
        "top_hubs": top_hubs,
        "states": states_tree,
        "remote_options": ["Remote", "Remote (India)"],
    }
