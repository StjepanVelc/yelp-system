from fastapi import APIRouter, HTTPException
from typing import Optional
from app.clients import business_client
from app.logger import get_logger

router = APIRouter()
log = get_logger("api-gateway.business")


@router.get("")
async def list_businesses(
    city: Optional[str] = None,
    min_stars: Optional[float] = None,
    page: int = 1,
    limit: int = 20,
):
    log.info("GET /businesses city=%s min_stars=%s page=%d", city, min_stars, page)
    try:
        return await business_client.get_businesses(city, min_stars, page, limit)
    except Exception as e:
        log.error("Error proxying GET /businesses: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{business_id}")
async def get_business(business_id: str):
    log.info("GET /businesses/%s", business_id)
    try:
        return await business_client.get_business(business_id)
    except Exception as e:
        log.error("Error proxying GET /businesses/%s: %s", business_id, e)
        raise HTTPException(status_code=502, detail=str(e))
