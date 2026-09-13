import pytest
from app.sources.adapters.internshala import InternshalaAdapter
from app.sources.base import JobSearchQuery, RawJob


def test_internshala_determine_search_paths_freshness_1h():
    adapter = InternshalaAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer", "Frontend Developer", "DevOps"],
        skills=["python", "react", "docker"],
        freshness_hours=1,
    )
    paths = adapter._determine_search_paths(query)
    # 1h freshness should restrict paths to top 2 core paths
    assert len(paths) <= 2
    assert "/jobs/computer-science-jobs/" in paths
    assert "/internships/software-development-internship/" in paths


def test_internshala_determine_search_paths_freshness_4h():
    adapter = InternshalaAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer"],
        skills=["python", "django", "javascript"],
        freshness_hours=4,
    )
    paths = adapter._determine_search_paths(query)
    # <= 4h freshness should cap paths to at most 4
    assert len(paths) <= 4


def test_internshala_determine_search_paths_freshness_24h():
    adapter = InternshalaAdapter()
    query = JobSearchQuery(
        roles=["Backend Developer"],
        skills=["python"],
        freshness_hours=24,
    )
    paths = adapter._determine_search_paths(query)
    # Standard 24h recall can include more paths
    assert len(paths) >= 2


@pytest.mark.asyncio
async def test_internshala_search_respects_1h_max_pages(monkeypatch):
    adapter = InternshalaAdapter()
    fetch_calls = []

    async def fake_fetch_page(url, allow_browser_fallback=True):
        fetch_calls.append((url, allow_browser_fallback))
        return """
        <div class="individual_internship">
            <div class="profile"><h3><a class="job-title-href" href="/job/detail/123">Software Engineer</a></h3></div>
            <div class="company-name"><a class="link_display_like_text">Acme Corp</a></div>
            <div class="status-info">Posted 10 mins ago</div>
            <div class="locations">Remote</div>
        </div>
        """

    monkeypatch.setattr(adapter, "_fetch_page", fake_fetch_page)

    query = JobSearchQuery(freshness_hours=1, limit=10)
    results = await adapter.search(query, max_pages_per_category=3)

    assert len(results) > 0
    # For 1h freshness, effective max_pages per category is 1. With 2 paths, at most 2 fetches.
    assert len(fetch_calls) <= 2
    assert all("/page-2/" not in url for url, _ in fetch_calls)
    assert adapter._metrics.queries_count > 0
    assert adapter._metrics.pages_count > 0
