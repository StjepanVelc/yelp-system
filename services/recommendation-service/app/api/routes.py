from fastapi import APIRouter, HTTPException
from app.service.recommendation_service import get_recommendations
from app.core.logger import get_logger

router = APIRouter()
log = get_logger("recommendation-service.routes")


@router.get("/{business_id}")
def recommend(business_id: str, limit: int = 10):
    log.info("GET /recommendations/%s?limit=%d", business_id, limit)
    results = get_recommendations(business_id, limit)
    if not results:
        log.warning("No recommendations found for %s", business_id)
        raise HTTPException(status_code=404, detail="Business not found or no recommendations available")
    return results

