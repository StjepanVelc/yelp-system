from sqlalchemy import text
from app.core.logger import get_logger

log = get_logger("business-service.repository")


def get_businesses(session, city=None, state=None, min_stars=None, limit=20, offset=0):
    query = "SELECT * FROM businesses WHERE 1=1"
    params = {}

    if city:
        query += " AND city = :city"
        params["city"] = city

    if state:
        query += " AND state = :state"
        params["state"] = state

    if min_stars is not None:
        query += " AND stars >= :min_stars"
        params["min_stars"] = min_stars

    query += " LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    log.debug("Query businesses city=%s state=%s min_stars=%s limit=%d offset=%d", city, state, min_stars, limit, offset)
    result = session.execute(text(query), params)
    rows = [dict(row._mapping) for row in result]
    log.debug("Found %d businesses", len(rows))
    return rows


def get_business_by_id(session, business_id: str):
    log.debug("Fetching business by id: %s", business_id)
    result = session.execute(
        text("SELECT * FROM businesses WHERE id = :id"),
        {"id": business_id},
    )
    row = result.fetchone()
    if row:
        log.debug("Business found: %s", business_id)
    else:
        log.debug("Business not found: %s", business_id)
    return dict(row._mapping) if row else None


def get_reviews(session, business_id: str, limit: int = 20, offset: int = 0):
    log.debug("Fetching reviews for business %s limit=%d offset=%d", business_id, limit, offset)
    result = session.execute(
        text(
            "SELECT review_id, user_id, stars, text, date, useful, funny, cool "
            "FROM reviews WHERE business_id = :bid "
            "ORDER BY date DESC LIMIT :limit OFFSET :offset"
        ),
        {"bid": business_id, "limit": limit, "offset": offset},
    )
    rows = [dict(row._mapping) for row in result]
    log.debug("Found %d reviews", len(rows))
    return rows

