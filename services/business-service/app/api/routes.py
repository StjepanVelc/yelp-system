from time import perf_counter
from typing import Optional
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.db.session import SessionLocal
from app.service.business_service import (
    fetch_businesses_with_meta,
    fetch_business_by_id,
    fetch_cities,
    fetch_reviews,
    fetch_user_status,
)
from app.core.logger import get_logger

router = APIRouter()
user_router = APIRouter()
cache_router = APIRouter()
log = get_logger("business-service.routes")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def get_businesses(
    city: Optional[str] = None,
    state: Optional[str] = None,
    min_stars: Optional[float] = None,
    query: Optional[str] = Query(None, max_length=200),
    search_path: str = Query("auto", pattern="^(auto|fts|trigram|legacy)$"),
    page: int = 1,
    limit: int = 20,
    response: Response = ...,
    db=Depends(get_db),
):
    started = perf_counter()
    query_hash = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()[:12] if query and query.strip() else None
    log.info(
        "GET /businesses city=%s state=%s min_stars=%s search_path=%s query_hash=%s page=%d limit=%d",
        city,
        state,
        min_stars,
        search_path,
        query_hash,
        page,
        limit,
    )
    results, meta = fetch_businesses_with_meta(db, city, state, min_stars, query, search_path, page, limit)
    elapsed_ms = (perf_counter() - started) * 1000

    response.headers["X-Search-Path"] = str(meta.get("search_path", "legacy"))
    response.headers["X-Search-Version"] = str(meta.get("search_version", "legacy"))
    response.headers["X-Search-Latency-Ms"] = str(int(elapsed_ms))

    log.info(
        "search_metrics path=%s version=%s latency_ms=%.2f result_count=%d zero_results=%s has_query=%s query_hash=%s fallback_reason=%s",
        meta.get("search_path", "legacy"),
        meta.get("search_version", "legacy"),
        elapsed_ms,
        len(results),
        len(results) == 0,
        bool(query),
        query_hash,
        meta.get("fallback_reason"),
    )
    return results


@router.get("/cities")
def get_cities_list(db=Depends(get_db)):
    log.info("GET /businesses/cities")
    return fetch_cities(db)


@router.get("/{business_id}")
def get_business(business_id: str, db=Depends(get_db)):
    log.info("GET /businesses/%s", business_id)
    business = fetch_business_by_id(db, business_id)
    if not business:
        log.warning("Business not found: %s", business_id)
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.get("/{business_id}/reviews")
def get_business_reviews(
    business_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db=Depends(get_db),
):
    log.info("GET /businesses/%s/reviews page=%d limit=%d", business_id, page, limit)
    return fetch_reviews(db, business_id, page=page, limit=limit)


@user_router.get("/users/{user_id}/status")
def get_user_status(user_id: str, db=Depends(get_db)):
    log.info("GET /users/%s/status", user_id)
    return fetch_user_status(db, user_id)


@cache_router.get("/cache/stats")
def cache_stats():
    from app.core.cache import cache_client
    return cache_client.stats.snapshot()
