import pytest
from app.sources.adapters.naukri import NaukriAdapter
from app.sources.base import JobSearchQuery, RawJob


def test_naukri_determine_search_queries_freshness_1h():
    adapter = NaukriAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer", "Frontend Developer", "DevOps Engineer"],
        skills=["python", "django", "react", "typescript"],
        freshness_hours=1,
    )
    queries = adapter._determine_search_queries(query)
    # 1h freshness should cap queries to at most 2 without alias explosion
    assert len(queries) <= 2
    assert queries[0] == "Backend Developer"
    assert queries[1] == "Frontend Developer"


def test_naukri_determine_search_queries_freshness_4h():
    adapter = NaukriAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer"],
        skills=["python", "django", "react"],
        freshness_hours=4,
    )
    queries = adapter._determine_search_queries(query)
    # <= 4h freshness should cap queries to at most 4
    assert len(queries) <= 4


def test_naukri_determine_search_queries_freshness_24h():
    adapter = NaukriAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer"],
        skills=["python", "javascript"],
        freshness_hours=24,
    )
    queries = adapter._determine_search_queries(query)
    # Standard 24h recall includes aliases
    assert len(queries) >= 3


@pytest.mark.asyncio
async def test_naukri_search_respects_1h_max_pages(monkeypatch):
    import time
    adapter = NaukriAdapter()
    fetch_calls = []

    now_ms = int(time.time() * 1000)

    async def fake_fetch_url(url, headers=None):
        fetch_calls.append(url)
        return 200, f"""{{
            "jobDetails": [
                {{
                    "jobId": "12345678",
                    "title": "Software Engineer",
                    "companyName": "Acme Tech",
                    "createdDate": {now_ms},
                    "footerPlaceholderLabel": "Just now",
                    "placeholders": [{{"type": "location", "label": "Bengaluru"}}]
                }}
            ]
        }}"""

    monkeypatch.setattr(adapter, "_fetch_url", fake_fetch_url)

    query = JobSearchQuery(freshness_hours=1, limit=10)
    results = await adapter.search(query)

    assert len(results) > 0
    # For 1h freshness, effective max_pages per query is 1. With 2 queries, at most 2 API fetches.
    assert len(fetch_calls) <= 2
    assert all("pageNo=2" not in url for url in fetch_calls)
    assert adapter._metrics.queries_count > 0
    assert adapter._metrics.pages_count > 0
