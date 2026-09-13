"""
Comprehensive unit tests for Indian Location Taxonomy, Hierarchical Query Expansion,
and Normalization across all 28 states and 8 union territories.
"""

import pytest
from app.core.location_taxonomy import (
    INDIAN_STATES,
    INDIAN_UNION_TERRITORIES,
    resolve_canonical_location,
    expand_location_query,
    get_taxonomy_tree,
)
from app.utils.normalization import normalize_location


def test_indian_states_and_uts_count():
    assert len(INDIAN_STATES) == 28
    assert len(INDIAN_UNION_TERRITORIES) == 8


def test_top_tech_metro_canonical_resolution():
    # Bengaluru variations
    assert resolve_canonical_location("bangalore").canonical_name == "Bengaluru"
    assert resolve_canonical_location("Bengaluru, India").canonical_name == "Bengaluru"
    assert resolve_canonical_location("BLR").canonical_name == "Bengaluru"
    assert resolve_canonical_location("Whitefield").canonical_name == "Bengaluru"
    assert resolve_canonical_location("Electronic City").canonical_name == "Bengaluru"

    # Delhi NCR variations
    assert resolve_canonical_location("gurgaon").canonical_name == "Gurugram"
    assert resolve_canonical_location("noida").canonical_name == "Noida"
    assert resolve_canonical_location("delhi ncr").canonical_name == "Delhi NCR"
    assert resolve_canonical_location("New Delhi").canonical_name == "New Delhi"

    # Mumbai MMR
    assert resolve_canonical_location("bombay").canonical_name == "Mumbai"
    assert resolve_canonical_location("navi mumbai").canonical_name == "Navi Mumbai"
    assert resolve_canonical_location("thane").canonical_name == "Thane"

    # Pune
    assert resolve_canonical_location("poona").canonical_name == "Pune"
    assert resolve_canonical_location("hinjewadi").canonical_name == "Pune"

    # Hyderabad
    assert resolve_canonical_location("cyberabad").canonical_name == "Hyderabad"
    assert resolve_canonical_location("hitec city").canonical_name == "Hyderabad"

    # Chennai & Kolkata
    assert resolve_canonical_location("madras").canonical_name == "Chennai"
    assert resolve_canonical_location("calcutta").canonical_name == "Kolkata"
    assert resolve_canonical_location("salt lake").canonical_name == "Kolkata"


def test_state_queries_and_codes():
    # State names
    assert resolve_canonical_location("Karnataka").canonical_name == "Karnataka"
    assert resolve_canonical_location("Maharashtra").canonical_name == "Maharashtra"
    assert resolve_canonical_location("Telangana").canonical_name == "Telangana"

    # State codes
    assert resolve_canonical_location("KA").canonical_name == "Karnataka"
    assert resolve_canonical_location("MH").canonical_name == "Maharashtra"
    assert resolve_canonical_location("DL").canonical_name == "Delhi"


def test_remote_and_pan_india():
    assert resolve_canonical_location("Remote").canonical_name == "Remote"
    assert resolve_canonical_location("Work from home").canonical_name == "Remote"
    assert resolve_canonical_location("Remote - India").canonical_name == "Remote (India)"
    assert resolve_canonical_location("Anywhere in India").canonical_name == "Remote (India)"


def test_multi_location_strings():
    res = normalize_location("Pune / Bangalore")
    assert res == "Pune / Bengaluru"

    res2 = normalize_location("Hyderabad / Gurugram")
    assert res2 == "Hyderabad / Gurugram"


def test_query_expansion():
    # Expanding a state should include its child cities
    expanded_ka = expand_location_query(["Karnataka"])
    assert "bengaluru" in expanded_ka
    assert "mysuru" in expanded_ka

    # Expanding a metro cluster includes cross-district cities
    expanded_ncr = expand_location_query(["Delhi NCR"])
    assert "noida" in expanded_ncr
    assert "gurugram" in expanded_ncr
    assert "delhi" in expanded_ncr

    # Expanding a city includes aliases
    expanded_blr = expand_location_query(["Bengaluru"])
    assert "bangalore" in expanded_blr
    assert "whitefield" in expanded_blr


def test_delhi_ncr_does_not_leak_other_cities():
    from app.services.job_service import _matches_location_token
    expanded_ncr = expand_location_query(["Delhi NCR"])
    assert "del" not in expanded_ncr
    assert "hyd" not in expanded_ncr
    
    # Check that none of expanded_ncr matches Hyderabad or Bangalore
    for token in expanded_ncr:
        assert not _matches_location_token(token, "hyderabad, india")
        assert not _matches_location_token(token, "hyderabad")
        assert not _matches_location_token(token, "bengaluru, karnataka")
        assert not _matches_location_token(token, "mumbai, maharashtra")


def test_taxonomy_tree_structure():
    tree = get_taxonomy_tree()
    assert "top_hubs" in tree
    assert "states" in tree
    assert "metros" in tree
    assert len(tree["states"]) == 36  # 28 + 8


def test_alias_normalization_and_entity_distinctions():
    from app.core.location_taxonomy import (
        parse_location_entities,
        LocationEntityType,
        normalize_location_string,
    )
    # Bangalore / Bengaluru aliases
    b1 = parse_location_entities("Bangalore")[0]
    b2 = parse_location_entities("Bengaluru")[0]
    b3 = parse_location_entities("Whitefield")[0]
    assert b1.name == "Bengaluru" and b1.type == LocationEntityType.CITY
    assert b2.name == "Bengaluru" and b2.type == LocationEntityType.CITY
    assert b3.name == "Bengaluru" and b3.type == LocationEntityType.CITY

    # Gurgaon / Gurugram
    g1 = parse_location_entities("gurgaon")[0]
    g2 = parse_location_entities("Gurugram")[0]
    assert g1.name == "Gurugram" and g1.type == LocationEntityType.CITY
    assert g1.state_or_ut == "Haryana" and g1.metro == "Delhi NCR"
    assert g2.name == "Gurugram" and g2.type == LocationEntityType.CITY

    # Noida / Greater Noida
    n1 = parse_location_entities("Noida")[0]
    n2 = parse_location_entities("Greater Noida")[0]
    assert n1.name == "Noida" and n1.type == LocationEntityType.CITY
    assert n1.state_or_ut == "Uttar Pradesh" and n1.metro == "Delhi NCR"
    assert n2.name == "Greater Noida" and n2.type == LocationEntityType.CITY
    assert n2.state_or_ut == "Uttar Pradesh" and n2.metro == "Delhi NCR"

    # Bombay / Mumbai
    m1 = parse_location_entities("Bombay")[0]
    assert m1.name == "Mumbai" and m1.type == LocationEntityType.CITY
    assert m1.state_or_ut == "Maharashtra" and m1.metro == "Mumbai Metropolitan Region"

    # Madras / Chennai
    c1 = parse_location_entities("Madras")[0]
    assert c1.name == "Chennai" and c1.type == LocationEntityType.CITY

    # Trivandrum / Thiruvananthapuram
    t1 = parse_location_entities("Trivandrum")[0]
    assert t1.name == "Thiruvananthapuram" and t1.type == LocationEntityType.CITY
    assert t1.state_or_ut == "Kerala"


def test_city_state_metro_clean_separation():
    from app.core.location_taxonomy import parse_location_entities, LocationEntityType

    city_ent = parse_location_entities("Bengaluru")[0]
    state_ent = parse_location_entities("Karnataka")[0]
    metro_ent = parse_location_entities("Delhi NCR")[0]
    country_ent = parse_location_entities("India")[0]
    remote_ent = parse_location_entities("Remote")[0]

    assert city_ent.type == LocationEntityType.CITY
    assert state_ent.type == LocationEntityType.STATE
    assert metro_ent.type == LocationEntityType.METRO
    assert country_ent.type == LocationEntityType.COUNTRY
    assert remote_ent.type == LocationEntityType.REMOTE

    # Distinct names
    assert city_ent.name != state_ent.name
    assert city_ent.name != metro_ent.name
    assert city_ent.name != country_ent.name


def test_multi_location_parsing_and_formatting():
    from app.core.location_taxonomy import (
        parse_location_entities,
        normalize_location_string,
    )
    # Delimited by slash
    multi1 = parse_location_entities("Bengaluru / Hyderabad")
    assert len(multi1) == 2
    assert multi1[0].name == "Bengaluru"
    assert multi1[1].name == "Hyderabad"
    assert normalize_location_string("Bengaluru / Hyderabad") == "Bengaluru / Hyderabad"

    # Delimited by pipe
    multi2 = parse_location_entities("Pune | Mumbai")
    assert len(multi2) == 2
    assert multi2[0].name == "Pune"
    assert multi2[1].name == "Mumbai"

    # Comma separated distinct cities
    multi3 = parse_location_entities("Noida, Gurugram")
    assert len(multi3) == 2
    assert multi3[0].name == "Noida"
    assert multi3[1].name == "Gurugram"

    # City with State qualifier should stay single entity
    single_qual = parse_location_entities("Bengaluru, Karnataka")
    assert len(single_qual) == 1
    assert single_qual[0].name == "Bengaluru"


def test_canonical_criteria_matching():
    from app.core.location_taxonomy import match_location_criteria

    # 1. Exact city match
    assert match_location_criteria("Bengaluru", "Bangalore", ["Bengaluru"])
    assert match_location_criteria("Bengaluru", "Bangalore", ["Bangalore"])

    # 2. Metro expansion: filtering by 'Delhi NCR' matches Noida, Gurugram, or Delhi
    assert match_location_criteria("Noida", "Noida", ["Delhi NCR"])
    assert match_location_criteria("Gurugram", "Gurgaon", ["Delhi NCR"])
    assert match_location_criteria("Delhi", "New Delhi", ["Delhi NCR"])
    # But filtering by 'Noida' does NOT match Gurugram
    assert not match_location_criteria("Gurugram", "Gurugram", ["Noida"])

    # 3. State expansion: filtering by 'Karnataka' matches Bengaluru or Mysuru
    assert match_location_criteria("Bengaluru", "Bengaluru", ["Karnataka"])
    assert match_location_criteria("Mysuru", "Mysore", ["Karnataka"])
    # Filtering by 'Karnataka' does NOT match Pune
    assert not match_location_criteria("Pune", "Pune", ["Karnataka"])

    # 4. Multi-location job matches if any city matches
    assert match_location_criteria("Pune / Bengaluru", "Pune / Bengaluru", ["Bengaluru"])
    assert match_location_criteria("Pune / Bengaluru", "Pune / Bengaluru", ["Pune"])
    assert not match_location_criteria("Pune / Bengaluru", "Pune / Bengaluru", ["Hyderabad"])

    # 5. Remote matching
    assert match_location_criteria("Remote", "Remote", ["Remote"])
    assert match_location_criteria("Bengaluru", "Bengaluru", ["Remote"], job_remote_type="REMOTE")
    assert not match_location_criteria("Bengaluru", "Bengaluru", ["Remote"], job_remote_type="ONSITE")


def test_matching_service_location_score_consistency():
    from app.services.matching_service import MatchingService
    svc = MatchingService()

    # Direct city match
    score = svc.compute_location_score(
        job_location="Bangalore",
        normalized_location="Bengaluru",
        remote_type="ONSITE",
        preferred_locations=["Bengaluru"],
        remote_preference=False,
    )
    assert score == 100.0

    # Metro expansion match (prefer Delhi NCR, job in Noida)
    score_ncr = svc.compute_location_score(
        job_location="Noida, UP",
        normalized_location="Noida",
        remote_type="ONSITE",
        preferred_locations=["Delhi NCR"],
        remote_preference=False,
    )
    assert score_ncr == 100.0

    # Same state affinity (prefer Bengaluru, job in Mysuru)
    score_state = svc.compute_location_score(
        job_location="Mysuru",
        normalized_location="Mysuru",
        remote_type="ONSITE",
        preferred_locations=["Bengaluru"],
        remote_preference=False,
    )
def test_facet_and_filter_consistency_on_multi_location_jobs():
    from app.core.location_taxonomy import (
        match_location_criteria,
        parse_location_entities,
    )

    mock_jobs = [
        {"id": 1, "norm": "Bengaluru", "raw": "Bengaluru, Karnataka", "remote_type": "ONSITE"},
        {"id": 2, "norm": "Pune / Bengaluru", "raw": "Pune / Bengaluru", "remote_type": "ONSITE"},
        {"id": 3, "norm": "Noida", "raw": "Noida", "remote_type": "ONSITE"},
        {"id": 4, "norm": "Gurugram", "raw": "Gurgaon", "remote_type": "ONSITE"},
        {"id": 5, "norm": "Remote", "raw": "Remote", "remote_type": "REMOTE"},
    ]

    # Test filtering for "Bengaluru"
    filtered_blr = [
        j for j in mock_jobs
        if match_location_criteria(j["norm"], j["raw"], ["Bengaluru"], j["remote_type"])
    ]
    assert len(filtered_blr) == 2  # job 1 and job 2

    # Test facet counting for "Bengaluru"
    location_facets: dict[str, int] = {}
    for j in mock_jobs:
        for ent in parse_location_entities(j["norm"]):
            if ent.name != "Unknown":
                location_facets[ent.name] = location_facets.get(ent.name, 0) + 1

    assert location_facets["Bengaluru"] == len(filtered_blr)

    # Test filtering for "Delhi NCR" (Metro expansion matches Noida and Gurugram)
    filtered_ncr = [
        j for j in mock_jobs
        if match_location_criteria(j["norm"], j["raw"], ["Delhi NCR"], j["remote_type"])
    ]
    assert len(filtered_ncr) == 2  # Noida and Gurugram



