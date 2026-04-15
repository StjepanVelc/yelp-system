from fastapi import APIRouter, Depends, HTTPException
from app.db.session import SessionLocal
from app.service.business_service import fetch_businesses, fetch_business_by_id
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
    min_stars: Optional[float] = None,
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db),
):
    log.info("GET /businesses city=%s min_stars=%s page=%d limit=%d", city, min_stars, page, limit)
    results = fetch_businesses(db, city, min_stars, page, limit)
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
