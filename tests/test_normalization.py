from app.utils.normalization import (
    normalize_location,
    normalize_skill,
    normalize_skills,
    parse_salary_text,
)


def test_skill_normalization():
    assert normalize_skill("python3") == "Python"
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("postgres") == "PostgreSQL"
    assert normalize_skill("fastapi") == "FastAPI"
    assert normalize_skill("k8s") == "Kubernetes"
    assert normalize_skill("UnknownTech") == "UnknownTech"

    skills = ["py", "Python", "fast api", "FastAPI", "reactjs", "docker"]
    normalized = normalize_skills(skills)
    assert normalized == ["Python", "FastAPI", "React", "Docker"]


def test_location_normalization():
    assert normalize_location("bangalore") == "Bengaluru"
    assert normalize_location("Bengaluru, Karnataka") == "Bengaluru"
    assert normalize_location("Gurgaon") == "Gurugram"
    assert normalize_location("Noida") == "Delhi NCR"
    assert normalize_location("work from home") == "Remote"
    assert normalize_location("Remote - India") == "Remote (India)"


def test_salary_parsing():
    s1 = parse_salary_text("12 LPA")
    assert s1["salary_min"] == 1200000.0
    assert s1["salary_max"] == 1200000.0
    assert s1["salary_currency"] == "INR"

    s2 = parse_salary_text("8 - 14 LPA")
    assert s2["salary_min"] == 800000.0
    assert s2["salary_max"] == 1400000.0

    s3 = parse_salary_text("50,000/month")
    assert s3["salary_min"] == 600000.0
    assert s3["salary_max"] == 600000.0

    s4 = parse_salary_text("Not Disclosed")
    assert s4["salary_min"] is None
    assert s4["salary_max"] is None


def test_matches_target_role():
    from app.utils.normalization import matches_target_role

    # Positive matches for target clusters
    positives = [
        "AI / Backend Developer (6 Month Internship)",
        "Full Stack Developer (Next.js / FastAPI)",
        "Founding Engineer (Backend & AI)",
        "Machine Learning Intern",
        "Python Developer Intern",
        "Software Engineer - Backend",
        "Generative AI Engineer",
        "Junior Data Scientist",
    ]
    target_roles = ["Backend Developer", "Full Stack Developer", "AI Engineer", "Machine Learning"]
    for title in positives:
        assert matches_target_role(title, target_roles) is True, f"Failed positive match: {title}"

    # Strict negative controls
    negatives = [
        "Cyber Security Analyst",
        "HR Associate",
        "Fundraising Intern",
        "iOS Developer",
        "Flutter Developer",
        "Android Developer",
        "Hardware Test Engineer",
    ]
    for title in negatives:
        assert matches_target_role(title, target_roles) is False, f"Failed negative match: {title}"


def test_is_unpaid_salary_text():
    from app.utils.normalization import is_unpaid_salary_text

    assert is_unpaid_salary_text("Unpaid") is True
    assert is_unpaid_salary_text("Expenses only") is True
    assert is_unpaid_salary_text("Performance Based") is True
    assert is_unpaid_salary_text("Incentives Only") is True

    assert is_unpaid_salary_text("15,000 / month") is False
    assert is_unpaid_salary_text("10 LPA") is False
    assert is_unpaid_salary_text(None) is False


def test_experience_parsing_and_inference():
    from app.utils.normalization import parse_experience_requirement, infer_experience_from_title

    # 1. Non-experience sentences should never be returned as exp_text
    exp_min, exp_max, exp_text, conf = parse_experience_requirement("Agile Developer opportunity at TaskUs in India.")
    assert exp_min is None
    assert exp_max is None
    assert exp_text is None
    assert conf == "LOW"

    # 2. Legitimate experience patterns
    assert parse_experience_requirement("3-5 years")[0:3] == (3, 5, "3-5 years")
    assert parse_experience_requirement("Fresher")[0:3] == (0, 0, "Fresher")
    assert parse_experience_requirement("2+ yrs")[0:3] == (2, None, "2+ yrs")

    # 3. Title-based seniority inference
    senior_res = infer_experience_from_title("IN_Senior Associate_Java Full Stack Developer with React _Data & Analytics_Advisory_Bangalore")
    assert senior_res[0] == 5
    assert "Senior" in senior_res[2]

    intern_res = infer_experience_from_title("Frontend Engineer Intern")
    assert intern_res[0] == 0
    assert intern_res[1] == 1
    assert "Intern" in intern_res[2]

    assoc_res = infer_experience_from_title("Associate QA Engineer")
    assert assoc_res[0] == 1
    assert assoc_res[1] == 3
    assert "Associate" in assoc_res[2]

    lead_res = infer_experience_from_title("Tech Lead - Python")
    assert lead_res[0] == 7
    assert "Lead" in lead_res[2]
