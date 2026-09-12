from app.utils.normalization import (
    normalize_skill,
    normalize_skills,
    scan_skills_in_text,
    extract_skills_from_text,
    normalize_location,
    parse_salary_text,
    parse_experience_requirement,
    matches_target_role,
)


def test_canonical_skill_normalization():
    assert normalize_skill("python3") == "Python"
    assert normalize_skill("reactjs") == "React"
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("k8s") == "Kubernetes"


def test_scan_skills_word_boundary():
    # 'rag' should not match inside 'courage' or 'storage'
    text = "We have courage to build high storage systems with Python and RAG."
    skills = scan_skills_in_text(text)
    assert "Python" in skills
    assert "RAG" in skills
    assert len(skills) == 2


def test_extract_skills_required_vs_preferred():
    desc = """
    Requirements:
    - Python
    - FastAPI
    - PostgreSQL

    Nice to have:
    - Docker
    - AWS
    """
    req, pref = extract_skills_from_text(desc)
    assert "Python" in req
    assert "FastAPI" in req
    assert "PostgreSQL" in req
    assert "Docker" in pref
    assert "AWS" in pref


def test_normalize_location_indian_cities():
    assert normalize_location("bangalore") == "Bengaluru"
    assert normalize_location("gurgaon") == "Gurugram"
    assert normalize_location("bombay") == "Mumbai"
    assert normalize_location("noida") == "Delhi NCR"


def test_salary_parsing():
    s1 = parse_salary_text("12 - 18 LPA")
    assert s1["salary_min"] == 1200000.0
    assert s1["salary_max"] == 1800000.0

    s2 = parse_salary_text("Unpaid Internship")
    assert s2["is_unpaid"] is True


def test_experience_parsing():
    # Must reject '5 days a week' from being parsed as 5 years experience
    min_y, max_y, snippet, conf = parse_experience_requirement("Working 5 days a week in office")
    assert min_y is None
    assert max_y is None

    # Normal experience
    min_y2, max_y2, _, conf2 = parse_experience_requirement("1-3 years of experience required")
    assert min_y2 == 1
    assert max_y2 == 3
    assert conf2 == "HIGH"
