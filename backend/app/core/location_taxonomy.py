"""
Indian Location Taxonomy & Hierarchy Module.
Covers 28 States, 8 Union Territories, major tech clusters, metro corridors,
localities, airport codes, and query expansion helpers.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any


class LocationEntityType(str, Enum):
    CITY = "CITY"
    METRO = "METRO"
    STATE = "STATE"
    COUNTRY = "COUNTRY"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class LocationEntity:
    name: str
    type: LocationEntityType
    state_or_ut: str | None = None
    metro: str | None = None
    country: str = "India"
    is_remote: bool = False
    raw_input: str = ""


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

# Airport IATA codes mapping directly to (Canonical City, State, Metro)
AIRPORT_CODES: dict[str, tuple[str, str, str | None]] = {
    "BLR": ("Bengaluru", "Karnataka", None),
    "DEL": ("Delhi", "Delhi", "Delhi NCR"),
    "BOM": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "HYD": ("Hyderabad", "Telangana", None),
    "PNQ": ("Pune", "Maharashtra", None),
    "MAA": ("Chennai", "Tamil Nadu", None),
    "CCU": ("Kolkata", "West Bengal", None),
    "IXC": ("Chandigarh", "Chandigarh", "Tricity (Chandigarh)"),
    "AMD": ("Ahmedabad", "Gujarat", "Gujarat Tech Corridor"),
    "COK": ("Kochi", "Kerala", "Kerala Tech Corridor"),
    "TRV": ("Thiruvananthapuram", "Kerala", "Kerala Tech Corridor"),
}

METRO_CLUSTERS: dict[str, dict[str, Any]] = {
    "Delhi NCR": {
        "canonical": "Delhi NCR",
        "state_or_ut": "Delhi",
        "cities": [
            "Delhi", "New Delhi", "Gurugram", "Noida", "Greater Noida",
            "Ghaziabad", "Faridabad", "Manesar", "Sonipat"
        ],
        "aliases": [
            "delhi ncr", "delhi-ncr", "ncr", "national capital region"
        ],
    },
    "Mumbai Metropolitan Region": {
        "canonical": "Mumbai Metropolitan Region",
        "state_or_ut": "Maharashtra",
        "cities": ["Mumbai", "Navi Mumbai", "Thane", "Kalyan"],
        "aliases": [
            "mmr", "mumbai metropolitan region", "greater mumbai"
        ],
    },
    "Tricity (Chandigarh)": {
        "canonical": "Tricity (Chandigarh)",
        "state_or_ut": "Chandigarh",
        "cities": ["Chandigarh", "Mohali", "Panchkula"],
        "aliases": [
            "tricity", "chandigarh tricity"
        ],
    },
    "Gujarat Tech Corridor": {
        "canonical": "Gujarat Tech Corridor",
        "state_or_ut": "Gujarat",
        "cities": ["Ahmedabad", "Gandhinagar", "Vadodara", "Surat", "Rajkot"],
        "aliases": [
            "gujarat tech corridor"
        ],
    },
    "Kerala Tech Corridor": {
        "canonical": "Kerala Tech Corridor",
        "state_or_ut": "Kerala",
        "cities": ["Kochi", "Thiruvananthapuram", "Kozhikode"],
        "aliases": [
            "kerala tech corridor"
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

CANONICAL_CITY_LOOKUP: dict[str, tuple[str, str, str | None]] = {}

for state_name, cities in STATE_CITIES_MAP.items():
    for city in cities:
        metro_name: str | None = None
        for m_name, m_info in METRO_CLUSTERS.items():
            if city in m_info["cities"]:
                metro_name = m_name
                break
        CANONICAL_CITY_LOOKUP[city.lower()] = (city, state_name, metro_name)

# Specific Suburbs, Historical Names, Tech Hubs & Aliases -> (Canonical City, State, Metro)
SPECIAL_ALIASES: dict[str, tuple[str, str, str | None]] = {
    # Karnataka / Bengaluru
    "bangalore": ("Bengaluru", "Karnataka", None),
    "bengaluru": ("Bengaluru", "Karnataka", None),
    "bangaluru": ("Bengaluru", "Karnataka", None),
    "bangalore urban": ("Bengaluru", "Karnataka", None),
    "bangalore rural": ("Bengaluru", "Karnataka", None),
    "greater bengaluru area": ("Bengaluru", "Karnataka", None),
    "greater bangalore": ("Bengaluru", "Karnataka", None),
    "whitefield": ("Bengaluru", "Karnataka", None),
    "electronic city": ("Bengaluru", "Karnataka", None),
    "koramangala": ("Bengaluru", "Karnataka", None),
    "indiranagar": ("Bengaluru", "Karnataka", None),
    "bellandur": ("Bengaluru", "Karnataka", None),
    "marathahalli": ("Bengaluru", "Karnataka", None),
    "manyata": ("Bengaluru", "Karnataka", None),
    "hebbal": ("Bengaluru", "Karnataka", None),
    "hsr layout": ("Bengaluru", "Karnataka", None),
    "mysore": ("Mysuru", "Karnataka", None),
    "mangalore": ("Mangaluru", "Karnataka", None),
    "hubli": ("Hubballi", "Karnataka", None),
    "belgaum": ("Belagavi", "Karnataka", None),

    # NCR / North
    "delhi": ("Delhi", "Delhi", "Delhi NCR"),
    "new delhi": ("New Delhi", "Delhi", "Delhi NCR"),
    "gurgaon": ("Gurugram", "Haryana", "Delhi NCR"),
    "gurugram": ("Gurugram", "Haryana", "Delhi NCR"),
    "manesar": ("Manesar", "Haryana", "Delhi NCR"),
    "noida": ("Noida", "Uttar Pradesh", "Delhi NCR"),
    "greater noida": ("Greater Noida", "Uttar Pradesh", "Delhi NCR"),
    "ghaziabad": ("Ghaziabad", "Uttar Pradesh", "Delhi NCR"),
    "faridabad": ("Faridabad", "Haryana", "Delhi NCR"),
    "sonipat": ("Sonipat", "Haryana", "Delhi NCR"),

    # Maharashtra / Mumbai / Pune
    "mumbai": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "bombay": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "navi mumbai": ("Navi Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "thane": ("Thane", "Maharashtra", "Mumbai Metropolitan Region"),
    "kalyan": ("Kalyan", "Maharashtra", "Mumbai Metropolitan Region"),
    "bkc": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "andheri": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "powai": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "goregaon": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "lower parel": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "malad": ("Mumbai", "Maharashtra", "Mumbai Metropolitan Region"),
    "pune": ("Pune", "Maharashtra", None),
    "poona": ("Pune", "Maharashtra", None),
    "pcmc": ("Pimpri-Chinchwad", "Maharashtra", None),
    "pimpri chinchwad": ("Pimpri-Chinchwad", "Maharashtra", None),
    "hinjewadi": ("Pune", "Maharashtra", None),
    "hinjawadi": ("Pune", "Maharashtra", None),
    "magarpatta": ("Pune", "Maharashtra", None),
    "kharadi": ("Pune", "Maharashtra", None),
    "baner": ("Pune", "Maharashtra", None),
    "wakad": ("Pune", "Maharashtra", None),
    "viman nagar": ("Pune", "Maharashtra", None),
    "nagpur": ("Nagpur", "Maharashtra", None),
    "nashik": ("Nashik", "Maharashtra", None),

    # Telangana & AP / Hyderabad
    "hyderabad": ("Hyderabad", "Telangana", None),
    "secunderabad": ("Secunderabad", "Telangana", None),
    "cyberabad": ("Hyderabad", "Telangana", None),
    "hitec city": ("Hyderabad", "Telangana", None),
    "hitech city": ("Hyderabad", "Telangana", None),
    "gachibowli": ("Hyderabad", "Telangana", None),
    "madhapur": ("Hyderabad", "Telangana", None),
    "kondapur": ("Hyderabad", "Telangana", None),
    "kukatpally": ("Hyderabad", "Telangana", None),
    "vizag": ("Visakhapatnam", "Andhra Pradesh", None),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh", None),

    # Tamil Nadu / Chennai
    "chennai": ("Chennai", "Tamil Nadu", None),
    "madras": ("Chennai", "Tamil Nadu", None),
    "greater chennai": ("Chennai", "Tamil Nadu", None),
    "omr": ("Chennai", "Tamil Nadu", None),
    "guindy": ("Chennai", "Tamil Nadu", None),
    "tidel park": ("Chennai", "Tamil Nadu", None),
    "sholinganallur": ("Chennai", "Tamil Nadu", None),
    "velachery": ("Chennai", "Tamil Nadu", None),
    "coimbatore": ("Coimbatore", "Tamil Nadu", None),

    # West Bengal / Kolkata
    "kolkata": ("Kolkata", "West Bengal", None),
    "calcutta": ("Kolkata", "West Bengal", None),
    "salt lake": ("Kolkata", "West Bengal", None),
    "salt lake city": ("Kolkata", "West Bengal", None),
    "sector v": ("Kolkata", "West Bengal", None),
    "new town": ("Kolkata", "West Bengal", None),
    "rajarhat": ("Kolkata", "West Bengal", None),
    "bidhannagar": ("Kolkata", "West Bengal", None),

    # Kerala
    "kochi": ("Kochi", "Kerala", "Kerala Tech Corridor"),
    "cochin": ("Kochi", "Kerala", "Kerala Tech Corridor"),
    "ernakulam": ("Kochi", "Kerala", "Kerala Tech Corridor"),
    "infopark": ("Kochi", "Kerala", "Kerala Tech Corridor"),
    "thiruvananthapuram": ("Thiruvananthapuram", "Kerala", "Kerala Tech Corridor"),
    "trivandrum": ("Thiruvananthapuram", "Kerala", "Kerala Tech Corridor"),
    "technopark": ("Thiruvananthapuram", "Kerala", "Kerala Tech Corridor"),
    "technocity": ("Thiruvananthapuram", "Kerala", "Kerala Tech Corridor"),
    "calicut": ("Kozhikode", "Kerala", "Kerala Tech Corridor"),
    "kozhikode": ("Kozhikode", "Kerala", "Kerala Tech Corridor"),
    "cyberpark": ("Kozhikode", "Kerala", "Kerala Tech Corridor"),

    # Gujarat
    "ahmedabad": ("Ahmedabad", "Gujarat", "Gujarat Tech Corridor"),
    "amdavad": ("Ahmedabad", "Gujarat", "Gujarat Tech Corridor"),
    "gandhinagar": ("Gandhinagar", "Gujarat", "Gujarat Tech Corridor"),
    "gift city": ("Gandhinagar", "Gujarat", "Gujarat Tech Corridor"),
    "baroda": ("Vadodara", "Gujarat", "Gujarat Tech Corridor"),
    "vadodara": ("Vadodara", "Gujarat", "Gujarat Tech Corridor"),
    "surat": ("Surat", "Gujarat", "Gujarat Tech Corridor"),
    "rajkot": ("Rajkot", "Gujarat", "Gujarat Tech Corridor"),

    # Tricity
    "chandigarh": ("Chandigarh", "Chandigarh", "Tricity (Chandigarh)"),
    "mohali": ("Mohali", "Punjab", "Tricity (Chandigarh)"),
    "sas nagar": ("Mohali", "Punjab", "Tricity (Chandigarh)"),
    "panchkula": ("Panchkula", "Haryana", "Tricity (Chandigarh)"),
}

CANONICAL_CITY_LOOKUP.update(SPECIAL_ALIASES)


def resolve_single_location(token: str) -> LocationEntity:
    """
    Standardize a single location token into a structured canonical LocationEntity.
    """
    if not token or not token.strip():
        return LocationEntity(name="Unknown", type=LocationEntityType.UNKNOWN, raw_input="")

    raw_clean = token.strip()
    lower = raw_clean.lower()

    # 1. Remote checks
    if any(k in lower for k in ["remote", "work from home", "wfh", "telecommute", "anywhere in india"]):
        if "india" in lower or "anywhere" in lower:
            return LocationEntity(
                name="Remote (India)",
                type=LocationEntityType.REMOTE,
                is_remote=True,
                raw_input=raw_clean,
            )
        return LocationEntity(
            name="Remote",
            type=LocationEntityType.REMOTE,
            is_remote=True,
            raw_input=raw_clean,
        )

    # 2. State codes check (e.g. KA -> Karnataka)
    upper = raw_clean.upper()
    if upper in STATE_CODES:
        state_full = STATE_CODES[upper]
        return LocationEntity(
            name=state_full,
            type=LocationEntityType.STATE,
            state_or_ut=state_full,
            raw_input=raw_clean,
        )

    # 3. Airport IATA code check (e.g. BLR -> Bengaluru)
    if upper in AIRPORT_CODES:
        city, state, metro = AIRPORT_CODES[upper]
        return LocationEntity(
            name=city,
            type=LocationEntityType.CITY,
            state_or_ut=state,
            metro=metro,
            raw_input=raw_clean,
        )

    # 4. Explicit Metro Cluster alias match (e.g. "delhi ncr", "ncr")
    for cluster_key, cluster_info in METRO_CLUSTERS.items():
        if lower == cluster_key.lower() or any(lower == a.lower() for a in cluster_info["aliases"]):
            return LocationEntity(
                name=cluster_info["canonical"],
                type=LocationEntityType.METRO,
                state_or_ut=cluster_info["state_or_ut"],
                metro=cluster_info["canonical"],
                raw_input=raw_clean,
            )

    # 5. Full State or UT match
    for state in INDIAN_STATES + INDIAN_UNION_TERRITORIES:
        if lower == state.lower():
            return LocationEntity(
                name=state,
                type=LocationEntityType.STATE,
                state_or_ut=state,
                raw_input=raw_clean,
            )

    # 6. City / Suburb alias exact match or bounded token match
    for alias in sorted(CANONICAL_CITY_LOOKUP.keys(), key=len, reverse=True):
        if alias == lower or f", {alias}" in lower or f"{alias}," in lower or f" {alias} " in f" {lower} ":
            city, state, metro = CANONICAL_CITY_LOOKUP[alias]
            return LocationEntity(
                name=city,
                type=LocationEntityType.CITY,
                state_or_ut=state,
                metro=metro,
                raw_input=raw_clean,
            )

    # 7. Substring check for State/UT (e.g., "Mysuru, Karnataka" or "Karnataka, India")
    for state in sorted(INDIAN_STATES + INDIAN_UNION_TERRITORIES, key=len, reverse=True):
        if state.lower() in lower:
            parts = [p.strip() for p in raw_clean.split(",") if p.strip()]
            city_candidate = parts[0]
            if city_candidate.lower() == state.lower():
                return LocationEntity(
                    name=state,
                    type=LocationEntityType.STATE,
                    state_or_ut=state,
                    raw_input=raw_clean,
                )
            # Try resolving candidate city
            if city_candidate.lower() in CANONICAL_CITY_LOOKUP:
                city, s_name, metro = CANONICAL_CITY_LOOKUP[city_candidate.lower()]
                return LocationEntity(
                    name=city,
                    type=LocationEntityType.CITY,
                    state_or_ut=s_name,
                    metro=metro,
                    raw_input=raw_clean,
                )
            return LocationEntity(
                name=city_candidate.title(),
                type=LocationEntityType.CITY,
                state_or_ut=state,
                raw_input=raw_clean,
            )

    # 8. Country match
    if lower in ["india", "pan india", "across india", "pan-india"]:
        return LocationEntity(
            name="India",
            type=LocationEntityType.COUNTRY,
            country="India",
            raw_input=raw_clean,
        )

    first_token = raw_clean.split(",")[0].strip()
    return LocationEntity(
        name=first_token.title() if first_token else "Unknown",
        type=LocationEntityType.UNKNOWN,
        raw_input=raw_clean,
    )


def parse_location_entities(raw_location: str | None) -> list[LocationEntity]:
    """
    Parses a location string into one or more canonical LocationEntity objects.
    Deterministically handles multi-location patterns like:
    - "Bengaluru / Hyderabad"
    - "Pune | Mumbai"
    - "Delhi NCR / Remote"
    - "Gurugram or Noida"
    - "Bengaluru, Hyderabad, Chennai"
    """
    if not raw_location or not raw_location.strip():
        return [LocationEntity(name="Unknown", type=LocationEntityType.UNKNOWN, raw_input="")]

    raw = raw_location.strip()

    # Split on primary delimiters: '/', '|', ';', or ' or '
    tokens = re.split(r"\s*(?:\/|\||;|\bor\b)\s*", raw, flags=re.IGNORECASE)

    final_tokens: list[str] = []
    for t in tokens:
        t_clean = t.strip()
        if not t_clean:
            continue
        if "," in t_clean:
            comma_parts = [p.strip() for p in t_clean.split(",") if p.strip()]
            is_single_qualified = False
            if len(comma_parts) == 2:
                p2_low = comma_parts[1].lower()
                all_states_low = {s.lower() for s in INDIAN_STATES + INDIAN_UNION_TERRITORIES}
                all_codes_low = {c.lower() for c in STATE_CODES.keys()}
                if p2_low in all_states_low or p2_low in all_codes_low or p2_low in {"india", "in"}:
                    is_single_qualified = True

            if is_single_qualified:
                final_tokens.append(t_clean)
            else:
                final_tokens.extend(comma_parts)
        else:
            final_tokens.append(t_clean)

    entities: list[LocationEntity] = []
    seen_names = set()

    for tok in final_tokens:
        entity = resolve_single_location(tok)
        if entity.name not in seen_names and entity.name != "Unknown":
            seen_names.add(entity.name)
            entities.append(entity)

    return entities if entities else [LocationEntity(name="Unknown", type=LocationEntityType.UNKNOWN, raw_input=raw)]


def normalize_location_string(raw_location: str | None) -> str:
    """
    Canonical string representation of location(s), deterministic and consistent.
    Multi-location jobs are formatted as 'City1 / City2'.
    """
    entities = parse_location_entities(raw_location)
    names = [e.name for e in entities if e.name != "Unknown"]
    return " / ".join(names) if names else "Unknown"


# Backward-compatible alias for existing imports
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
    Legacy wrapper returning ResolvedLocation.
    Uses first parsed LocationEntity.
    """
    entities = parse_location_entities(raw_location)
    primary = entities[0]
    return ResolvedLocation(
        canonical_name=primary.name,
        state_or_ut=primary.state_or_ut,
        is_remote=primary.is_remote,
        is_metro=(primary.type == LocationEntityType.METRO),
        is_state_level=(primary.type == LocationEntityType.STATE),
        raw_input=primary.raw_input or (raw_location or ""),
    )


def expand_location_query(locations: list[str] | None) -> set[str]:
    """
    Expands a list of query location strings to canonical names and child tokens:
    - State/UT expands to all its child cities
    - Metro expands to all its member cities
    - City expands to itself and known aliases
    - Remote expands to remote equivalents
    """
    if not locations:
        return set()

    expanded: set[str] = set()

    for loc in locations:
        if not loc or not loc.strip():
            continue
        entities = parse_location_entities(loc)
        for ent in entities:
            name_low = ent.name.lower()
            expanded.add(name_low)

            if ent.type == LocationEntityType.STATE or ent.name in STATE_CITIES_MAP:
                expanded.add(name_low)
                for city in STATE_CITIES_MAP.get(ent.name, []):
                    expanded.add(city.lower())

            if ent.type == LocationEntityType.METRO or ent.name in METRO_CLUSTERS:
                cluster_info = METRO_CLUSTERS.get(ent.name)
                if cluster_info:
                    for a in cluster_info["aliases"]:
                        expanded.add(a.lower())
                    for c in cluster_info["cities"]:
                        expanded.add(c.lower())

            if ent.is_remote:
                for r in ["remote", "work from home", "wfh", "telecommute", "anywhere in india", "remote (india)"]:
                    expanded.add(r)

            if ent.type == LocationEntityType.CITY:
                for alias, (c_city, _, _) in CANONICAL_CITY_LOOKUP.items():
                    if c_city.lower() == name_low:
                        expanded.add(alias.lower())

    return expanded


def match_location_criteria(
    job_normalized_location: str | None,
    job_raw_location: str | None,
    filter_locations: list[str] | None,
    job_remote_type: str | None = None,
) -> bool:
    """
    Authoritative canonical matcher: returns True if job matches any filter criteria.
    Operates on canonical entities, supporting:
    - Canonical city equality
    - Metro expansion (filtering by 'Delhi NCR' matches 'Noida' or 'Gurugram')
    - State expansion (filtering by 'Karnataka' matches 'Bengaluru' or 'Mysuru')
    - Remote matching
    - Multi-location jobs (matches if ANY constituent city matches)
    """
    if not filter_locations:
        return True

    target_cities: set[str] = set()
    target_metros: set[str] = set()
    target_states: set[str] = set()
    target_remote: bool = False
    target_country: bool = False

    for f_loc in filter_locations:
        if not f_loc or not f_loc.strip():
            continue
        for ent in parse_location_entities(f_loc):
            if ent.is_remote:
                target_remote = True
            elif ent.type == LocationEntityType.METRO:
                target_metros.add(ent.name)
                if ent.name in METRO_CLUSTERS:
                    for c in METRO_CLUSTERS[ent.name]["cities"]:
                        target_cities.add(c.lower())
            elif ent.type == LocationEntityType.STATE:
                target_states.add(ent.name)
                if ent.name in STATE_CITIES_MAP:
                    for c in STATE_CITIES_MAP[ent.name]:
                        target_cities.add(c.lower())
            elif ent.type == LocationEntityType.CITY:
                target_cities.add(ent.name.lower())
            elif ent.type == LocationEntityType.COUNTRY:
                target_country = True
            else:
                target_cities.add(ent.name.lower())

    is_remote_job = (
        (job_remote_type or "").upper() == "REMOTE"
        or (job_normalized_location and "remote" in job_normalized_location.lower())
        or (job_raw_location and any(r in job_raw_location.lower() for r in ["remote", "wfh", "work from home"]))
    )
    if target_remote and is_remote_job:
        return True

    loc_source = job_normalized_location or job_raw_location or ""
    job_entities = parse_location_entities(loc_source)

    for j_ent in job_entities:
        j_name_low = j_ent.name.lower()

        if j_ent.is_remote and target_remote:
            return True

        if target_country and j_ent.country == "India":
            return True

        if j_name_low in target_cities:
            return True

        if j_ent.type == LocationEntityType.METRO and j_ent.name in target_metros:
            return True

        if j_ent.metro and j_ent.metro in target_metros:
            return True

        if j_ent.state_or_ut and j_ent.state_or_ut in target_states:
            return True

        if j_ent.type == LocationEntityType.STATE and j_ent.name in target_states:
            return True

    return False


def get_taxonomy_tree() -> dict[str, Any]:
    """
    Returns canonical tree for UI navigation and filter dropdowns.
    """
    top_hubs = [
        {"name": "Bengaluru", "state": "Karnataka", "popular": True, "type": "CITY"},
        {"name": "Delhi NCR", "state": "Delhi", "popular": True, "type": "METRO"},
        {"name": "Mumbai", "state": "Maharashtra", "popular": True, "type": "CITY"},
        {"name": "Hyderabad", "state": "Telangana", "popular": True, "type": "CITY"},
        {"name": "Pune", "state": "Maharashtra", "popular": True, "type": "CITY"},
        {"name": "Chennai", "state": "Tamil Nadu", "popular": True, "type": "CITY"},
        {"name": "Kolkata", "state": "West Bengal", "popular": True, "type": "CITY"},
        {"name": "Gurugram", "state": "Haryana", "popular": True, "type": "CITY"},
        {"name": "Noida", "state": "Uttar Pradesh", "popular": True, "type": "CITY"},
        {"name": "Chandigarh", "state": "Chandigarh", "popular": False, "type": "CITY"},
        {"name": "Ahmedabad", "state": "Gujarat", "popular": False, "type": "CITY"},
        {"name": "Kochi", "state": "Kerala", "popular": False, "type": "CITY"},
        {"name": "Jaipur", "state": "Rajasthan", "popular": False, "type": "CITY"},
        {"name": "Indore", "state": "Madhya Pradesh", "popular": False, "type": "CITY"},
    ]

    states_tree = []
    for state in sorted(INDIAN_STATES + INDIAN_UNION_TERRITORIES):
        cities = STATE_CITIES_MAP.get(state, [])
        states_tree.append({
            "name": state,
            "is_ut": state in INDIAN_UNION_TERRITORIES,
            "cities": sorted(cities),
        })

    metro_list = []
    for m_name, m_data in METRO_CLUSTERS.items():
        metro_list.append({
            "name": m_name,
            "state_or_ut": m_data["state_or_ut"],
            "cities": sorted(m_data["cities"]),
        })

    return {
        "top_hubs": top_hubs,
        "metros": metro_list,
        "states": states_tree,
        "remote_options": ["Remote", "Remote (India)"],
    }
