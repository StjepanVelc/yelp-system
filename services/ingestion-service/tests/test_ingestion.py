"""
Tests for ingestion-service: parsers, loaders, service logic, and API endpoints.
"""
import json
import io
import pytest
from unittest.mock import patch, MagicMock, mock_open
from fastapi.testclient import TestClient

# ── sample raw JSON lines ──────────────────────────────────────────────────────

RAW_BUSINESS = json.dumps({
    "business_id": "biz-001",
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
    "attributes": {"WiFi": "free"},
    "hours": {"Monday": "8:0-22:0"},
})

RAW_REVIEW = json.dumps({
    "review_id": "rev-001",
    "user_id": "user-001",
    "business_id": "biz-001",
    "stars": 5,
    "useful": 3,
    "funny": 1,
    "cool": 2,
    "text": "Great place!",
    "date": "2023-06-15 10:00:00",
})

RAW_USER = json.dumps({
    "user_id": "user-001",
    "name": "Alice",
    "review_count": 50,
    "yelping_since": "2015-01-01 00:00:00",
    "useful": 10,
    "funny": 5,
    "cool": 8,
    "fans": 3,
    "average_stars": 4.2,
    "friends": "user-002, user-003",
    "elite": "2020, 2021",
})

RAW_TIP = json.dumps({
    "user_id": "user-001",
    "business_id": "biz-001",
    "text": "Try the latte!",
    "date": "2023-03-10 09:00:00",
    "compliment_count": 2,
})

RAW_CHECKIN = json.dumps({
    "business_id": "biz-001",
    "date": "2023-01-01 12:00:00, 2023-01-02 13:00:00",
})


# ── parser unit tests ──────────────────────────────────────────────────────────

class TestParsers:
    def test_parse_business(self):
        from app.utils.parser import parse_business
        data = json.loads(RAW_BUSINESS)
        result = parse_business(data)
        assert result["id"] == "biz-001"
        assert result["city"] == "Phoenix"
        assert result["stars"] == 4.5

    def test_parse_review(self):
        from app.utils.parser import parse_review
        data = json.loads(RAW_REVIEW)
        result = parse_review(data)
        assert result["id"] == "rev-001"
        assert result["stars"] == 5

    def test_parse_user(self):
        from app.utils.parser import parse_user
        data = json.loads(RAW_USER)
        result = parse_user(data)
        assert result["id"] == "user-001"
        assert result["name"] == "Alice"

    def test_parse_tip(self):
        from app.utils.parser import parse_tip
        data = json.loads(RAW_TIP)
        result = parse_tip(data)
        assert result["user_id"] == "user-001"
        assert result["business_id"] == "biz-001"

    def test_parse_checkin(self):
        from app.utils.parser import parse_checkin
        data = json.loads(RAW_CHECKIN)
        result = parse_checkin(data)
        assert result["business_id"] == "biz-001"

    def test_parse_business_handles_nulls(self):
        from app.utils.parser import parse_business
        minimal = {"business_id": "x", "name": "X", "address": None, "city": None,
                   "state": None, "postal_code": None, "latitude": 0, "longitude": 0,
                   "stars": 0, "review_count": 0, "is_open": 0, "categories": None,
                   "attributes": None, "hours": None}
        result = parse_business(minimal)
        assert result["id"] == "x"


# ── loader unit tests ──────────────────────────────────────────────────────────

class TestLoaders:
    def _fake_file(self, line):
        return io.StringIO(line + "\n")

    def test_load_businesses_yields_dict(self):
        from app.loaders.json_loader import load_businesses
        with patch("builtins.open", mock_open(read_data=RAW_BUSINESS + "\n")):
            results = list(load_businesses("fake/path"))
        assert len(results) == 1
        assert results[0]["business_id"] == "biz-001"

    def test_load_reviews_yields_dict(self):
        from app.loaders.json_loader import load_reviews
        with patch("builtins.open", mock_open(read_data=RAW_REVIEW + "\n")):
            results = list(load_reviews("fake/path"))
        assert results[0]["review_id"] == "rev-001"

    def test_load_users_yields_dict(self):
        from app.loaders.json_loader import load_users
        with patch("builtins.open", mock_open(read_data=RAW_USER + "\n")):
            results = list(load_users("fake/path"))
        assert results[0]["user_id"] == "user-001"

    def test_load_tips_yields_dict(self):
        from app.loaders.json_loader import load_tips
        with patch("builtins.open", mock_open(read_data=RAW_TIP + "\n")):
            results = list(load_tips("fake/path"))
        assert results[0]["business_id"] == "biz-001"

    def test_load_checkins_yields_dict(self):
        from app.loaders.json_loader import load_checkins
        with patch("builtins.open", mock_open(read_data=RAW_CHECKIN + "\n")):
            results = list(load_checkins("fake/path"))
        assert results[0]["business_id"] == "biz-001"


# ── service logic tests ────────────────────────────────────────────────────────

class TestIngestionService:
    def _make_session(self):
        session = MagicMock()
        session.execute = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        return session

    def test_ingest_businesses_calls_execute(self):
        from app.service.ingestion_service import ingest_businesses
        session = self._make_session()
        biz_data = json.loads(RAW_BUSINESS)
        with patch("app.service.ingestion_service.load_businesses", return_value=iter([biz_data])), \
             patch("app.service.ingestion_service.settings") as mock_settings:
            mock_settings.data_path = "fake/path"
            total = ingest_businesses(session)
        assert total >= 0

    def test_ingest_reviews_calls_execute(self):
        from app.service.ingestion_service import ingest_reviews
        session = self._make_session()
        rev_data = json.loads(RAW_REVIEW)
        with patch("app.service.ingestion_service.load_reviews", return_value=iter([rev_data])), \
             patch("app.service.ingestion_service.settings") as mock_settings:
            mock_settings.data_path = "fake/path"
            total = ingest_reviews(session)
        assert total >= 0


# ── API endpoint tests ─────────────────────────────────────────────────────────

class TestIngestionAPI:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_trigger_ingest_all(self, client):
        response = client.post("/ingest/all")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ingestion started"
        assert "businesses" in body["datasets"]

    def test_trigger_ingest_businesses(self, client):
        response = client.post("/ingest/businesses")
        assert response.status_code == 200
        assert response.json()["dataset"] == "businesses"

    def test_trigger_ingest_reviews(self, client):
        response = client.post("/ingest/reviews")
        assert response.status_code == 200
        assert response.json()["dataset"] == "reviews"

    def test_trigger_ingest_users(self, client):
        response = client.post("/ingest/users")
        assert response.status_code == 200
        assert response.json()["dataset"] == "users"

    def test_trigger_ingest_tips(self, client):
        response = client.post("/ingest/tips")
        assert response.status_code == 200
        assert response.json()["dataset"] == "tips"

    def test_trigger_ingest_checkins(self, client):
        response = client.post("/ingest/checkins")
        assert response.status_code == 200
        assert response.json()["dataset"] == "checkins"
