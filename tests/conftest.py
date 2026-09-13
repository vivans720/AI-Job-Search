import pytest
import pytest_asyncio
import httpx
from typing import AsyncGenerator
import sys
from pathlib import Path

# Ensure backend directory is in pythonpath
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Ensure database has pgvector initialized if available."""
    try:
        from app.database import engine, init_pgvector
        await init_pgvector()
    except Exception:
        engine = None
    yield
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for testing FastAPI routes."""
    from app.main import app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
