"""
Tests for api-gateway: HTTP proxy routes, client wrappers, and error handling.
Downstream services are mocked via httpx.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# ── sample responses ───────────────────────────────────────────────────────────

BUSINESS_LIST = [
    {"id": "biz-001", "name": "Test Cafe", "city": "Phoenix", "stars": 4.5},
    {"id": "biz-002", "name": "Other Tea", "city": "Phoenix", "stars": 4.0},
]

BUSINESS_DETAIL = {"id": "biz-001", "name": "Test Cafe", "city": "Phoenix", "stars": 4.5}

RECOMMENDATIONS = [
    {"id": "biz-002", "name": "Other Tea", "city": "Phoenix", "stars": 4.0},
]


def make_mock_response(data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ── business proxy route tests ─────────────────────────────────────────────────

class TestBusinessGatewayRoutes:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_list_businesses_ok(self, client):
        with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)):
            response = client.get("/api/businesses")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_businesses_with_city_filter(self, client):
        with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)) as mock_fn:
            response = client.get("/api/businesses?city=Phoenix&min_stars=4.0")
        assert response.status_code == 200

    def test_get_business_by_id_ok(self, client):
        with patch("app.clients.business_client.get_business", new=AsyncMock(return_value=BUSINESS_DETAIL)):
            response = client.get("/api/businesses/biz-001")
        assert response.status_code == 200
        assert response.json()["id"] == "biz-001"

    def test_get_business_upstream_error_returns_502(self, client):
        with patch("app.clients.business_client.get_business", new=AsyncMock(side_effect=Exception("timeout"))):
            response = client.get("/api/businesses/biz-broken")
        assert response.status_code == 502


# ── recommendation proxy route tests ──────────────────────────────────────────

class TestRecommendationGatewayRoutes:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_get_recommendations_ok(self, client):
        with patch("app.clients.recommendation_client.get_recommendations", new=AsyncMock(return_value=RECOMMENDATIONS)):
            response = client.get("/api/recommendations/biz-001")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_recommendations_upstream_error_returns_502(self, client):
        with patch("app.clients.recommendation_client.get_recommendations", new=AsyncMock(side_effect=Exception("connection refused"))):
            response = client.get("/api/recommendations/biz-001")
        assert response.status_code == 502


# ── business client unit tests ─────────────────────────────────────────────────

class TestBusinessClient:
    @pytest.mark.anyio
    async def test_get_businesses_passes_params(self):
        from app.clients import business_client

        mock_resp = make_mock_response(BUSINESS_LIST)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await business_client.get_businesses(city="Phoenix", min_stars=4.0)
        assert result == BUSINESS_LIST

    @pytest.mark.anyio
    async def test_get_business_by_id(self):
        from app.clients import business_client

        mock_resp = make_mock_response(BUSINESS_DETAIL)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await business_client.get_business("biz-001")
        assert result["id"] == "biz-001"


# ── recommendation client unit tests ──────────────────────────────────────────

class TestRecommendationClient:
    @pytest.mark.anyio
    async def test_get_recommendations(self):
        from app.clients import recommendation_client

        mock_resp = make_mock_response(RECOMMENDATIONS)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await recommendation_client.get_recommendations("biz-001")
        assert isinstance(result, list)
