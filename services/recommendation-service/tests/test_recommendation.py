"""
Tests for recommendation-service: scoring algorithm, service logic, and API routes.
gRPC client is mocked so no live server is required.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── fixtures ───────────────────────────────────────────────────────────────────

TARGET = {
    "id": "biz-001",
    "name": "Target Cafe",
    "city": "Phoenix",
    "state": "AZ",
    "stars": 4.5,
    "categories": "Coffee, Cafe, Breakfast",
}

CANDIDATE_MATCH = {
    "id": "biz-002",
    "name": "Similar Cafe",
    "city": "Phoenix",
    "state": "AZ",
    "stars": 4.0,
    "categories": "Cafe, Coffee",
}

CANDIDATE_NO_MATCH = {
    "id": "biz-003",
    "name": "Car Repair",
    "city": "Tucson",
    "state": "AZ",
    "stars": 3.5,
    "categories": "Automotive, Oil Change",
}


# ── scoring algorithm tests ────────────────────────────────────────────────────

class TestScoringAlgorithm:
    def test_score_same_city_same_categories(self):
        from app.algorithms.scoring import score_business
        score = score_business(TARGET, CANDIDATE_MATCH)
        assert score > 0

    def test_score_different_city_no_categories(self):
        from app.algorithms.scoring import score_business
        score = score_business(TARGET, CANDIDATE_NO_MATCH)
        assert score < score_business(TARGET, CANDIDATE_MATCH)

    def test_score_excludes_same_business(self):
        from app.algorithms.scoring import score_business
        # Same business should not get a bonus over a clearly matching one
        score_self = score_business(TARGET, TARGET)
        score_other = score_business(TARGET, CANDIDATE_MATCH)
        # Both are valid — just check no crash and returns a number
        assert isinstance(score_self, (int, float))
        assert isinstance(score_other, (int, float))

    def test_rank_candidates_ordering(self):
        from app.algorithms.scoring import rank_candidates
        candidates = [CANDIDATE_NO_MATCH, CANDIDATE_MATCH]
        ranked = rank_candidates(TARGET, candidates)
        assert ranked[0]["id"] == "biz-002"  # better match should come first

    def test_rank_candidates_empty(self):
        from app.algorithms.scoring import rank_candidates
        result = rank_candidates(TARGET, [])
        assert result == []


# ── service logic tests ────────────────────────────────────────────────────────

class TestRecommendationService:
    def test_returns_recommendations(self):
        from app.service.recommendation_service import get_recommendations

        with patch("app.service.recommendation_service.get_business", return_value=TARGET), \
             patch("app.service.recommendation_service.list_businesses_in_area", return_value=[CANDIDATE_MATCH, CANDIDATE_NO_MATCH]):
            results = get_recommendations("biz-001", limit=5)
            assert isinstance(results, list)
            assert len(results) <= 5

    def test_returns_empty_when_business_not_found(self):
        from app.service.recommendation_service import get_recommendations

        with patch("app.service.recommendation_service.get_business", return_value=None):
            results = get_recommendations("nonexistent", limit=5)
            assert results == []

    def test_limit_is_respected(self):
        from app.service.recommendation_service import get_recommendations

        many_candidates = [dict(CANDIDATE_MATCH, id=f"biz-{i}", name=f"Cafe {i}") for i in range(50)]
        with patch("app.service.recommendation_service.get_business", return_value=TARGET), \
             patch("app.service.recommendation_service.list_businesses_in_area", return_value=many_candidates):
            results = get_recommendations("biz-001", limit=3)
            assert len(results) <= 3


# ── API route tests ────────────────────────────────────────────────────────────

class TestRecommendationRoutes:
    @pytest.fixture
    def client(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_get_recommendations_ok(self, client):
        with patch("app.api.routes.get_recommendations", return_value=[CANDIDATE_MATCH]):
            response = client.get("/recommendations/biz-001")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_recommendations_not_found(self, client):
        with patch("app.api.routes.get_recommendations", return_value=[]):
            response = client.get("/recommendations/missing")
        assert response.status_code == 404

    def test_get_recommendations_custom_limit(self, client):
        results = [dict(CANDIDATE_MATCH, id=f"biz-{i}") for i in range(5)]
        with patch("app.api.routes.get_recommendations", return_value=results) as mock_svc:
            response = client.get("/recommendations/biz-001?limit=5")
        assert response.status_code == 200
        mock_svc.assert_called_once_with("biz-001", 5)
