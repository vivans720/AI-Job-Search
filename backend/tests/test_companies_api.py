import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.database import get_db


@pytest.mark.asyncio
async def test_suggest_companies_empty_query():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/companies/suggest?q=")
            assert res.status_code == 200
            assert res.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_suggest_companies_mocked():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("Google",), ("Goldman Sachs",)]
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/companies/suggest?q=Go&limit=5")
            assert res.status_code == 200
            data = res.json()
            assert data == ["Google", "Goldman Sachs"]
    finally:
        app.dependency_overrides.pop(get_db, None)
