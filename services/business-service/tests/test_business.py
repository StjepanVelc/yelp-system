"""
Tests for business-service API routes and repository.
Uses FastAPI TestClient and mocked DB session.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# ── helpers ────────────────────────────────────────────────────────────────────

SAMPLE_BUSINESS = {
    "id": "biz-001",
    "name": "Test Cafe",
    "address": "123 Main St",
    "city": "Phoenix",
    "state": "AZ",
    "postal_code": "85001",
    "latitude": 33.45,
    "longitude": -112.07,
    "stars": 4.5,
    "review_count": 120,
    "is_open": 1,
    "categories": "Coffee, Cafe",
    "attributes": None,
    "hours": None,
}


def make_app():
    """Build the FastAPI app with a mocked DB session."""
    from app.main import app
    return app


# ── repository unit tests ──────────────────────────────────────────────────────

class TestBusinessRepository:
    def _mock_session(self, rows):
        session = MagicMock()
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter(rows))
        session.execute.return_value = result
        return session

    def test_get_businesses_returns_list(self):
        from app.repository.business_repository import get_businesses

        mock_row = MagicMock()
        mock_row._mapping = SAMPLE_BUSINESS
        session = MagicMock()
        session.execute.return_value = [mock_row]

        results = get_businesses(session, city="Phoenix", limit=10, offset=0)
        assert isinstance(results, list)
        assert results[0]["city"] == "Phoenix"

    def test_get_businesses_no_filters(self):
        from app.repository.business_repository import get_businesses

        mock_row = MagicMock()
        mock_row._mapping = SAMPLE_BUSINESS
        session = MagicMock()
        session.execute.return_value = [mock_row]

        results = get_businesses(session)
        assert len(results) == 1

    def test_get_business_by_id_found(self):
        from app.repository.business_repository import get_business_by_id

        mock_row = MagicMock()
        mock_row._mapping = SAMPLE_BUSINESS
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = mock_row

        result = get_business_by_id(session, "biz-001")
        assert result is not None
        assert result["id"] == "biz-001"

    def test_get_business_by_id_not_found(self):
        from app.repository.business_repository import get_business_by_id

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        result = get_business_by_id(session, "nonexistent")
        assert result is None

    def test_get_cities_returns_list(self):
        from app.repository.business_repository import get_cities

        mock_row_1 = MagicMock()
        mock_row_1._mapping = {"city": "Philadelphia"}
        mock_row_2 = MagicMock()
        mock_row_2._mapping = {"city": "Tucson"}
        session = MagicMock()
        session.execute.return_value = [mock_row_1, mock_row_2]

        result = get_cities(session)
        assert result == ["Philadelphia", "Tucson"]

    def test_get_user_status_found(self):
        from app.repository.business_repository import get_user_status

        mock_row = MagicMock()
        mock_row._mapping = {"user_id": "user-123"}
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = mock_row

        result = get_user_status(session, "user-123")
        assert result["user_id"] == "user-123"
        assert result["active"] is True
        assert result["deleted"] is False

    def test_get_user_status_not_found(self):
        from app.repository.business_repository import get_user_status

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        result = get_user_status(session, "missing-user")
        assert result["user_id"] == "missing-user"
        assert result["active"] is False
        assert result["deleted"] is True


# ── service unit tests ─────────────────────────────────────────────────────────

class TestBusinessService:
    def test_fetch_businesses_calls_repository(self):
        from app.service.business_service import fetch_businesses

        with patch("app.service.business_service.get_businesses", return_value=[SAMPLE_BUSINESS]) as mock_repo:
            session = MagicMock()
            results = fetch_businesses(session, city="Phoenix", min_stars=4.0, page=1, limit=10)
            mock_repo.assert_called_once_with(session, city="Phoenix", min_stars=4.0, limit=10, offset=0)
            assert results == [SAMPLE_BUSINESS]

    def test_fetch_business_by_id_found(self):
        from app.service.business_service import fetch_business_by_id

        with patch("app.service.business_service.get_business_by_id", return_value=SAMPLE_BUSINESS):
            session = MagicMock()
            result = fetch_business_by_id(session, "biz-001")
            assert result["name"] == "Test Cafe"

    def test_fetch_business_by_id_not_found(self):
        from app.service.business_service import fetch_business_by_id

        with patch("app.service.business_service.get_business_by_id", return_value=None):
            session = MagicMock()
            result = fetch_business_by_id(session, "missing")
            assert result is None

    def test_fetch_cities_calls_repository(self):
        from app.service.business_service import fetch_cities

        with patch("app.service.business_service.get_cities", return_value=["Philadelphia", "Tucson"]) as mock_repo:
            session = MagicMock()
            result = fetch_cities(session)
            mock_repo.assert_called_once_with(session)
            assert result == ["Philadelphia", "Tucson"]

    def test_fetch_user_status_calls_repository(self):
        from app.service.business_service import fetch_user_status

        with patch(
            "app.service.business_service.get_user_status",
            return_value={"user_id": "user-123", "active": True, "deleted": False, "deleted_at": None},
        ) as mock_repo:
            session = MagicMock()
            result = fetch_user_status(session, "user-123")
            mock_repo.assert_called_once_with(session, "user-123")
            assert result["active"] is True


# ── API route integration tests ────────────────────────────────────────────────

class TestBusinessRoutes:
    @pytest.fixture
    def client(self):
        app = make_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_get_businesses_ok(self, client):
        with patch("app.service.business_service.fetch_businesses", return_value=[SAMPLE_BUSINESS]):
            response = client.get("/businesses?city=Phoenix")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_businesses_with_filters(self, client):
        with patch("app.service.business_service.fetch_businesses", return_value=[SAMPLE_BUSINESS]):
            response = client.get("/businesses?city=Phoenix&min_stars=4.0&page=1&limit=5")
        assert response.status_code == 200

    def test_get_cities_ok(self, client):
        with patch("app.service.business_service.fetch_cities", return_value=["Philadelphia", "Tucson"]):
            response = client.get("/businesses/cities")
        assert response.status_code == 200
        assert response.json() == ["Philadelphia", "Tucson"]

    def test_get_business_by_id_ok(self, client):
        with patch("app.service.business_service.fetch_business_by_id", return_value=SAMPLE_BUSINESS):
            response = client.get("/businesses/biz-001")
        assert response.status_code == 200
        assert response.json()["id"] == "biz-001"

    def test_get_business_by_id_not_found(self, client):
        with patch("app.service.business_service.fetch_business_by_id", return_value=None):
            response = client.get("/businesses/does-not-exist")
        assert response.status_code == 404

    def test_pagination_offset(self, client):
        with patch("app.service.business_service.fetch_businesses", return_value=[]) as mock_svc:
            client.get("/businesses?page=3&limit=20")
            # page=3, limit=20 → offset=40
            call_kwargs = mock_svc.call_args
            assert call_kwargs is not None

    def test_get_user_status_active(self, client):
        expected = {"user_id": "user-123", "active": True, "deleted": False, "deleted_at": None}
        with patch("app.service.business_service.fetch_user_status", return_value=expected):
            response = client.get("/users/user-123/status")
        assert response.status_code == 200
        assert response.json()["active"] is True

    def test_get_user_status_deleted(self, client):
        expected = {"user_id": "missing-user", "active": False, "deleted": True, "deleted_at": "not-found"}
        with patch("app.service.business_service.fetch_user_status", return_value=expected):
            response = client.get("/users/missing-user/status")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
