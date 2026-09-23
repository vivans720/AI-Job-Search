import pytest
from app.services.pdf_generator_service import PDFGeneratorService


@pytest.mark.asyncio
async def test_pdf_generator_service_resume_render():
    candidate_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 555 0199",
        "location": "San Francisco, CA",
        "summary": "Experienced Full Stack Engineer with expertise in distributed systems and React.",
        "skills": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Docker"],
        "work_experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Corp",
                "duration": "2022 - Present",
                "bullets": [
                    "Engineered microservices processing 1M requests daily with 99.99% uptime.",
                    "Led frontend migration to Next.js reducing page load by 40%."
                ]
            }
        ],
        "projects": [
            {
                "name": "AI Job Assistant",
                "technologies": "Python, FastAPI, Playwright",
                "description": "Autonomous job search engine matching candidate profiles with open positions."
            }
        ],
        "education": [
            {
                "degree": "B.S. in Computer Science",
                "institution": "University of California, Berkeley",
                "year": "2018 - 2022"
            }
        ]
    }
    job_data = {
        "title": "Lead Backend Engineer",
        "company_name": "Acme Innovations"
    }

    html = PDFGeneratorService.render_resume_html(
        candidate_data=candidate_data,
        job_data=job_data,
        mode="EXISTING",
    )
    assert "Jane Doe" in html
    assert "Tech Corp" in html
    assert "AI Job Assistant" in html

    pdf_bytes = await PDFGeneratorService.generate_pdf_from_html(html)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_pdf_generator_service_cover_letter_render():
    candidate_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 555 0199",
        "location": "San Francisco, CA",
    }
    job_data = {
        "title": "Lead Backend Engineer",
        "company_name": "Acme Innovations"
    }
    cover_letter_text = (
        "Dear Hiring Team at Acme Innovations,\n\n"
        "I am writing to express my strong enthusiasm for the Lead Backend Engineer position. "
        "With my background building resilient distributed services in Python and FastAPI, "
        "I am confident in driving impactful results for your platform.\n\n"
        "Thank you for your consideration.\n\n"
        "Sincerely,\nJane Doe"
    )

    html = PDFGeneratorService.render_cover_letter_html(
        candidate_data=candidate_data,
        job_data=job_data,
        cover_letter_data=cover_letter_text,
    )
    assert "Acme Innovations" in html
    assert "Jane Doe" in html
    assert "Date:" in html
    # Check that literal "Date: Current" is not present
    assert "Date:</strong> Current" not in html

    pdf_bytes = await PDFGeneratorService.generate_pdf_from_html(html)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_pdf_generator_service_categorized_resume_render():
    candidate_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 555 0199",
        "location": "San Francisco, CA",
        "summary": "Experienced Full Stack Engineer.",
        "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker"],
        "work_experience": [
            {
                "title": "Senior Engineer",
                "company": "Tech Corp",
                "duration": "2022 - Present",
                "bullets": ["Engineered microservices processing 1M requests daily."]
            }
        ],
        "projects": [
            {
                "name": "Search Engine",
                "technologies": ["Python", "Elasticsearch"],
                "description": ["Distributed indexing engine."]
            }
        ],
        "education": [
            {
                "degree": "B.S. in CS",
                "institution": "UC Berkeley",
                "year": "2022"
            }
        ]
    }
    job_data = {
        "title": "Backend Engineer",
        "company_name": "Acme Innovations"
    }
    tailored_data = {
        "tailored_summary": "Tailored expert engineer.",
        "categorized_skills": {
            "Languages": ["Python"],
            "Databases": ["PostgreSQL"]
        },
        "highlighted_skills": ["Python"],
        "experience": [
            {
                "source_experience_index": 0,
                "selected_bullets": [{"content": "Engineered microservices processing 1M requests daily."}]
            }
        ]
    }

    html = PDFGeneratorService.render_resume_html(
        candidate_data=candidate_data,
        job_data=job_data,
        tailored_data=tailored_data,
        mode="TAILORED",
    )
    assert "Technical Competencies" in html
    assert "Languages:" in html
    assert "Databases:" in html
    assert "Engineered microservices" in html

    pdf_bytes = await PDFGeneratorService.generate_pdf_from_html(html)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:5] == b"%PDF-"

