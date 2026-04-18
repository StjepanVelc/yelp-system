from fastapi import APIRouter, HTTPException, Query
from app.clients import recommendation_client
from app.logger import get_logger
import re

router = APIRouter()
log = get_logger("api-gateway.recommendation")


@router.get("/{business_id}")
async def get_recommendations(
    business_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", business_id):
        raise HTTPException(status_code=422, detail="Invalid business ID")
    log.info("GET /recommendations/%s?limit=%d", business_id, limit)
    try:
        return await recommendation_client.get_recommendations(business_id, limit)
    except Exception as e:
        log.error("Error proxying GET /recommendations/%s: %s", business_id, e)
        raise HTTPException(status_code=502, detail="Upstream service error")
