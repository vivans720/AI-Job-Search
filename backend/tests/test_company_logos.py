import pytest
from app.sources.adapters.linkedin import LinkedInAdapter
from app.sources.adapters.internshala import InternshalaAdapter
from app.sources.adapters.naukri import NaukriAdapter
from app.sources.base import RawJob, NormalizedJob
from app.schemas.job import JobListItem, JobDetail

def test_raw_and_normalized_job_logo_fields():
    raw = RawJob(
        source="test",
        title="Software Engineer",
        company_name="Acme Corp",
        company_logo_url="https://example.com/logo.png",
        description="Write code",
        source_url="https://example.com/job/1",
    )
    assert raw.company_logo_url == "https://example.com/logo.png"

    norm = NormalizedJob(
        source="test",
        title="Software Engineer",
        normalized_title="Software Engineer",
        role_category="BACKEND",
        company_name="Acme Corp",
        normalized_company="acme corp",
        company_logo_url=raw.company_logo_url,
        description="Write code",
        normalized_location="Bangalore",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        source_url=raw.source_url,
        application_url=raw.source_url,
        job_hash="testhash123",
    )
    assert norm.company_logo_url == "https://example.com/logo.png"

def test_api_schema_company_logo_url():
    item = JobListItem(
        id="test-id",
        title="Software Engineer",
        company="Acme Corp",
        company_logo_url="https://example.com/logo.png",
        location="Bangalore",
        source="linkedin",
        application_url="https://example.com/apply",
    )
    assert item.company_logo_url == "https://example.com/logo.png"

def test_linkedin_adapter_logo_extraction():
    adapter = LinkedInAdapter()
    html_card = """
    <div class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:123456">
        <img class="artdeco-entity-image" src="https://media.licdn.com/dms/image/company-logo.jpg" alt="Acme Corp logo" />
        <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123456">
            <span class="sr-only">Software Engineer</span>
        </a>
        <h4 class="base-search-card__subtitle">Acme Corp</h4>
        <span class="job-search-card__location">Bengaluru, Karnataka, India</span>
    </div>
    """
    jobs = adapter.parse_html(html_card)
    assert len(jobs) == 1
    assert jobs[0].company_logo_url == "https://media.licdn.com/dms/image/company-logo.jpg"
    assert jobs[0].company_name == "Acme Corp"

def test_internshala_adapter_logo_extraction():
    adapter = InternshalaAdapter()
    html_card = """
    <div class="individual_internship" id="individual_internship_999">
        <div class="internship_logo">
            <img src="/static/images/companies/acme_logo.png" alt="Acme Tech" />
        </div>
        <div class="profile">
            <h3><a class="job-title-href" href="/job/detail/software-engineer-999">Software Engineer</a></h3>
        </div>
        <div class="company-name">Acme Tech</div>
        <div class="locations"><a>Bangalore</a></div>
    </div>
    """
    jobs = adapter.parse_html(html_card)
    assert len(jobs) == 1
    assert jobs[0].company_logo_url == "https://internshala.com/static/images/companies/acme_logo.png"
    assert jobs[0].company_name == "Acme Tech"

def test_naukri_adapter_next_data_logo_extraction():
    adapter = NaukriAdapter()
    dummy_html = """
    <html>
    <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "searchPageData": {
                        "jobDetails": [
                            {
                                "jobId": "987654",
                                "title": "Full Stack Developer",
                                "companyName": "Acme Systems",
                                "logoPath": "https://img.naukimg.com/logo_images/groups/v1/1234.gif",
                                "placeholders": [{"type": "location", "label": "Bangalore"}],
                                "jobDescription": "Build great apps"
                            }
                        ]
                    }
                }
            }
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    jobs = adapter.parse_html(dummy_html)
    assert len(jobs) == 1
    assert jobs[0].company_logo_url == "https://img.naukimg.com/logo_images/groups/v1/1234.gif"
    assert jobs[0].company_name == "Acme Systems"

def test_naukri_adapter_html_card_logo_extraction():
    adapter = NaukriAdapter()
    dummy_html = """
    <div class="srp-jobtuple-wrapper">
        <div class="cust-job-tuple">
            <a class="title" href="/job-listings-frontend-engineer-111222">Frontend Engineer</a>
            <a class="comp-name">Acme Design</a>
            <div class="comp-logo"><img src="https://img.naukimg.com/logo.png" alt="logo" /></div>
            <div class="locWdth">Mumbai</div>
        </div>
    </div>
    """
    jobs = adapter.parse_html(dummy_html)
    assert len(jobs) == 1
    assert jobs[0].company_logo_url == "https://img.naukimg.com/logo.png"
    assert jobs[0].company_name == "Acme Design"
