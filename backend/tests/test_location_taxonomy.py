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
    assert resolve_canonical_location("noida").canonical_name == "Delhi NCR"
    assert resolve_canonical_location("delhi ncr").canonical_name == "Delhi NCR"
    assert resolve_canonical_location("New Delhi").canonical_name == "Delhi NCR"

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


def test_taxonomy_tree_structure():
    tree = get_taxonomy_tree()
    assert "top_hubs" in tree
    assert "states" in tree
    assert len(tree["states"]) == 36  # 28 + 8
