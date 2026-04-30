from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import Optional
from app.auth import require_roles
from app.clients import business_client
from app.config import settings
from app.logger import get_logger
import re

router = APIRouter(
    dependencies=[Depends(require_roles(settings.business_required_roles.split(",")))]
)
log = get_logger("api-gateway.business")

_CITY_RE = re.compile(r"^[A-Za-z\s\-'\.]{1,100}$")


@router.get("")
async def list_businesses(
    city: Optional[str] = Query(None, max_length=100),
    min_stars: Optional[float] = Query(None, ge=0.0, le=5.0),
    query: Optional[str] = Query(None, max_length=200),
    search_path: str = Query("auto", pattern="^(auto|fts|trigram|legacy)$"),
    page: int = Query(1, ge=1, le=1000),
    limit: int = Query(20, ge=1, le=100),
    response: Response = ...,
):
    if city:
        city = city.strip()
        if not _CITY_RE.match(city):
            raise HTTPException(status_code=422, detail="Invalid city name")

    query = query.strip() if query else None
    search_path = search_path.lower()
    log.info(
        "GET /businesses city=%s min_stars=%s search_path=%s has_query=%s page=%d",
        city,
        min_stars,
        search_path,
        bool(query),
        page,
    )
    try:
        payload, upstream_headers = await business_client.get_businesses(
            city=city,
            min_stars=min_stars,
            query=query,
            search_path=search_path,
            page=page,
            limit=limit,
        )
        response.headers["X-Search-Path"] = upstream_headers.get("X-Search-Path", "legacy")
        response.headers["X-Search-Version"] = upstream_headers.get("X-Search-Version", "legacy")
        response.headers["X-Search-Latency-Ms"] = upstream_headers.get("X-Search-Latency-Ms", "0")
        return payload
    except Exception as e:
        log.error("Error proxying GET /businesses: %s", e)
        raise HTTPException(status_code=502, detail="Upstream service error")


@router.get("/cities")
async def list_cities():
    log.info("GET /businesses/cities")
    try:
        return await business_client.get_cities()
    except Exception as e:
        log.error("Error proxying GET /businesses/cities: %s", e)
        raise HTTPException(status_code=502, detail="Upstream service error")


@router.get("/{business_id}")
async def get_business(business_id: str):
    # Yelp IDs are alphanumeric with hyphens/underscores, max 64 chars
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", business_id):
        raise HTTPException(status_code=422, detail="Invalid business ID")
    log.info("GET /businesses/%s", business_id)
    try:
        return await business_client.get_business(business_id)
    except Exception as e:
        log.error("Error proxying GET /businesses/%s: %s", business_id, e)
        raise HTTPException(status_code=502, detail="Upstream service error")


@router.get("/{business_id}/reviews")
async def get_business_reviews(
    business_id: str,
    page: int = Query(1, ge=1, le=1000),
    limit: int = Query(20, ge=1, le=50),
):
    if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", business_id):
        raise HTTPException(status_code=422, detail="Invalid business ID")
    log.info("GET /businesses/%s/reviews page=%d", business_id, page)
    try:
        return await business_client.get_reviews(business_id, page=page, limit=limit)
    except Exception as e:
        log.error("Error proxying GET /businesses/%s/reviews: %s", business_id, e)
        raise HTTPException(status_code=502, detail="Upstream service error")
