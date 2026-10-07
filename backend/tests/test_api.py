import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "database": "healthy"}

@pytest.mark.asyncio
async def test_api_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/data/status")
    assert response.status_code == 200
    assert "providers" in response.json()

@pytest.mark.asyncio
async def test_api_rainfall():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/rainfall/latest")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
