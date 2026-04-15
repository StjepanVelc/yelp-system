from fastapi import APIRouter, HTTPException
from app.clients import recommendation_client
from app.logger import get_logger

router = APIRouter()
log = get_logger("api-gateway.recommendation")


@router.get("/{business_id}")
async def get_recommendations(business_id: str, limit: int = 10):
    log.info("GET /recommendations/%s?limit=%d", business_id, limit)
    try:
        return await recommendation_client.get_recommendations(business_id, limit)
    except Exception as e:
        log.error("Error proxying GET /recommendations/%s: %s", business_id, e)
        raise HTTPException(status_code=502, detail=str(e))
