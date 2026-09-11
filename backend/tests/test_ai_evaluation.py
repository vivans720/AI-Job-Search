import pytest
from unittest.mock import AsyncMock, MagicMock
from app.intelligence.service import AIService
from app.intelligence.evaluation.metrics import (
    set_precision_recall_f1,
    evaluate_candidate_profile_extraction,
    evaluate_job_enrichment_extraction,
)
from app.intelligence.evaluation.runner import EvaluationRunner


def test_metrics_precision_recall_f1():
    predicted = ["python", "fastapi", "docker", "unknown_tool"]
    ground_truth = ["Python", "FastAPI", "Docker", "Kubernetes"]

    res = set_precision_recall_f1(predicted, ground_truth)
    assert res["precision"] == 0.75  # 3 / 4
    assert res["recall"] == 0.75     # 3 / 4
    assert res["f1"] == 0.75


def test_evaluate_candidate_profile_extraction():
    pred = {
        "programming_languages": ["Python", "JavaScript"],
        "frameworks": ["FastAPI"],
        "databases": ["PostgreSQL"],
        "cloud": [],
        "tools": ["Git"],
        "skills": ["REST APIs"],
        "experience_level": "MID",
        "experience_years": 3,
    }
    truth = {
        "programming_languages": ["Python"],
        "frameworks": ["FastAPI"],
        "databases": ["PostgreSQL"],
        "cloud": ["Docker"],
        "tools": ["Git"],
        "skills": ["REST APIs"],
        "experience_level": "MID",
        "experience_years": 3,
    }
    eval_res = evaluate_candidate_profile_extraction(pred, truth)
    assert eval_res["experience_level_match"] == 1.0
    assert eval_res["experience_years_diff"] == 0
    assert eval_res["skill_precision"] == round(5 / 6, 4)
    assert eval_res["skill_recall"] == round(5 / 6, 4)


def test_evaluate_job_enrichment_extraction():
    pred = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "tech_stack": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "seniority": "MID",
    }
    truth = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker", "Kubernetes"],
        "tech_stack": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "seniority": "MID",
    }
    eval_res = evaluate_job_enrichment_extraction(pred, truth)
    assert eval_res["seniority_match"] == 1.0
    assert eval_res["required_skills_f1"] == 1.0
    assert eval_res["preferred_skills_f1"] == round(2 * 1.0 * 0.5 / (1.0 + 0.5), 4)


@pytest.mark.asyncio
async def test_evaluation_runner_mocked():
    mock_provider = MagicMock()
    # Mock resume extraction output
    mock_provider.complete_json = AsyncMock(side_effect=[
        # Resume 1: Alex Kumar
        {
            "candidate_name": "Alex Kumar",
            "experience_level": "MID",
            "experience_years": 3,
            "target_roles": ["Backend Engineer"],
            "programming_languages": ["Python"],
            "frameworks": ["FastAPI", "Django"],
            "databases": ["PostgreSQL", "Redis"],
            "cloud": ["AWS", "Docker", "Kubernetes"],
            "tools": ["Git", "GitHub Actions"],
            "skills": ["REST APIs", "Microservices", "CI/CD", "SQL Optimization"],
        },
        # Resume 2: Priya Sharma
        {
            "candidate_name": "Priya Sharma",
            "experience_level": "FRESHER",
            "experience_years": 0,
            "target_roles": ["Frontend Developer"],
            "programming_languages": ["JavaScript", "TypeScript", "HTML", "CSS"],
            "frameworks": ["React", "Next.js", "Tailwind CSS"],
            "databases": [],
            "cloud": [],
            "tools": ["Git", "GitHub", "Figma"],
            "skills": ["UI", "Responsive Design"],
        },
        # Job 1: Backend
        {
            "standardized_title": "Backend Software Engineer",
            "role_category": "Backend",
            "seniority": "MID",
            "min_experience_years": 2,
            "max_experience_years": 4,
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Linux"],
            "preferred_skills": ["Kubernetes", "Celery"],
            "core_responsibilities": ["Build REST APIs"],
            "requirements_summary": ["2+ years experience"],
            "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Linux", "Kubernetes", "Celery"],
        },
        # Job 2: Frontend
        {
            "standardized_title": "Frontend Software Engineering Intern",
            "role_category": "Frontend",
            "seniority": "FRESHER",
            "min_experience_years": 0,
            "max_experience_years": 1,
            "required_skills": ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Git", "GitHub"],
            "preferred_skills": ["Next.js", "Vite"],
            "core_responsibilities": ["Build responsive UI"],
            "requirements_summary": ["Fresher or final year student"],
            "tech_stack": ["React", "TypeScript", "JavaScript", "Tailwind CSS", "HTML", "CSS", "Git", "GitHub"],
        },
    ])

    service = AIService(provider=mock_provider)
    runner = EvaluationRunner(service=service)

    fixtures = runner.load_fixtures()
    assert len(fixtures) >= 4

    report = await runner.run_evaluation()
    assert report["total_fixtures"] >= 4
    assert report["schema_valid_rate"] == 1.0
    assert report["summary"]["avg_resume_skill_f1"] > 0.8
    assert report["summary"]["avg_job_required_skill_f1"] > 0.8
