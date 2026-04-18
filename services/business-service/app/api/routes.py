from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.session import SessionLocal
from app.service.business_service import fetch_businesses, fetch_business_by_id, fetch_reviews
from app.core.logger import get_logger
from typing import Optional

router = APIRouter()
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
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db),
):
    log.info("GET /businesses city=%s state=%s min_stars=%s page=%d limit=%d", city, state, min_stars, page, limit)
    results = fetch_businesses(db, city, state, min_stars, page, limit)
    log.debug("Returning %d businesses", len(results))
    return results


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
