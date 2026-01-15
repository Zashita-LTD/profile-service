"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_health_check():
    """Test health endpoint."""
    from profile_service.main import app
    
    with patch("profile_service.database.Neo4jDatabase.connect"):
        with patch("profile_service.database.Neo4jDatabase.disconnect"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    from profile_service.main import app
    
    with patch("profile_service.database.Neo4jDatabase.connect"):
        with patch("profile_service.database.Neo4jDatabase.disconnect"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/")
                assert response.status_code == 200
                data = response.json()
                assert "Profile Service" in data["service"]
