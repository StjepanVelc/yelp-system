"""
Tests for api-gateway: HTTP proxy routes, client wrappers, and error handling.
Downstream services are mocked via httpx.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.config import settings

# ── sample responses ───────────────────────────────────────────────────────────

BUSINESS_LIST = [
    {"id": "biz-001", "name": "Test Cafe", "city": "Phoenix", "stars": 4.5},
    {"id": "biz-002", "name": "Other Tea", "city": "Phoenix", "stars": 4.0},
]

BUSINESS_DETAIL = {"id": "biz-001", "name": "Test Cafe", "city": "Phoenix", "stars": 4.5}

RECOMMENDATIONS = [
    {"id": "biz-002", "name": "Other Tea", "city": "Phoenix", "stars": 4.0},
]


def make_token(
    *,
    subject: str = "user-123",
    roles=None,
    expired: bool = False,
    include_roles_claim: bool = True,
):
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=30)

    payload = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if include_roles_claim:
        payload[settings.jwt_roles_claim] = roles if roles is not None else ["business:read", "recommendation:read"]

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


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

    @pytest.fixture
    def auth_headers(self):
        token = make_token(roles=["business:read", "recommendation:read"])
        return {"Authorization": f"Bearer {token}"}

    def test_list_businesses_ok(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)):
                response = client.get("/api/businesses", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_businesses_with_city_filter(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)):
                response = client.get("/api/businesses?city=Phoenix&min_stars=4.0", headers=auth_headers)
        assert response.status_code == 200

    def test_list_businesses_with_search_query(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)) as mock_get:
                response = client.get("/api/businesses?query=pizza+tucson&page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        mock_get.assert_awaited_once_with(city=None, min_stars=None, query="pizza tucson", page=1, limit=5)

    def test_list_cities_ok(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_cities", new=AsyncMock(return_value=["Philadelphia", "Tucson"])):
                response = client.get("/api/businesses/cities", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == ["Philadelphia", "Tucson"]

    def test_get_business_by_id_ok(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_business", new=AsyncMock(return_value=BUSINESS_DETAIL)):
                response = client.get("/api/businesses/biz-001", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == "biz-001"

    def test_get_business_upstream_error_returns_502(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_business", new=AsyncMock(side_effect=Exception("timeout"))):
                response = client.get("/api/businesses/biz-broken", headers=auth_headers)
        assert response.status_code == 502

    def test_jwt_no_token_returns_401(self, client):
        response = client.get("/api/businesses")
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "no_token"

    def test_jwt_malformed_authorization_header_returns_401(self, client):
        response = client.get("/api/businesses", headers={"Authorization": "Token abc"})
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "malformed_authorization_header"

    def test_jwt_invalid_token_returns_401(self, client):
        response = client.get("/api/businesses", headers={"Authorization": "Bearer invalid.token.value"})
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_token"

    def test_jwt_expired_token_returns_401(self, client):
        token = make_token(roles=["business:read"], expired=True)
        response = client.get("/api/businesses", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "expired_token"

    def test_jwt_valid_token_missing_role_returns_403(self, client):
        token = make_token(include_roles_claim=False)
        response = client.get("/api/businesses", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "missing_role"

    def test_jwt_valid_token_insufficient_role_returns_403(self, client):
        token = make_token(roles=["business:write"])
        response = client.get("/api/businesses", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "insufficient_role"

    def test_jwt_valid_token_with_required_role_returns_200(self, client):
        token = make_token(roles=["business:read"])
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.business_client.get_businesses", new=AsyncMock(return_value=BUSINESS_LIST)):
                response = client.get("/api/businesses", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_jwt_valid_token_inactive_user_returns_403(self, client):
        token = make_token(roles=["business:read"])
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": False, "deleted": False})):
            response = client.get("/api/businesses", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "inactive_or_deleted_user"

    def test_exempt_health_route_without_token_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_exempt_docs_route_without_token_returns_200(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_exempt_openapi_route_without_token_returns_200(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200


# ── recommendation proxy route tests ──────────────────────────────────────────

class TestRecommendationGatewayRoutes:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    @pytest.fixture
    def auth_headers(self):
        token = make_token(roles=["business:read", "recommendation:read"])
        return {"Authorization": f"Bearer {token}"}

    def test_get_recommendations_ok(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.recommendation_client.get_recommendations", new=AsyncMock(return_value=RECOMMENDATIONS)):
                response = client.get("/api/recommendations/biz-001", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_recommendations_upstream_error_returns_502(self, client, auth_headers):
        with patch("app.clients.user_status_client.get_user_status", new=AsyncMock(return_value={"active": True, "deleted": False})):
            with patch("app.clients.recommendation_client.get_recommendations", new=AsyncMock(side_effect=Exception("connection refused"))):
                response = client.get("/api/recommendations/biz-001", headers=auth_headers)
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
            result = await business_client.get_businesses(city="Phoenix", min_stars=4.0, query="pizza")
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

    @pytest.mark.anyio
    async def test_get_cities(self):
        from app.clients import business_client

        mock_resp = make_mock_response(["Philadelphia", "Tucson"])
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await business_client.get_cities()
        assert result == ["Philadelphia", "Tucson"]


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
