from app.repository.business_repository import get_businesses, get_business_by_id, get_reviews


def fetch_businesses(session, city, state, min_stars, page, limit):
    offset = (page - 1) * limit
    return get_businesses(session, city=city, state=state, min_stars=min_stars, limit=limit, offset=offset)


def fetch_business_by_id(session, business_id: str):
    return get_business_by_id(session, business_id)


def fetch_reviews(session, business_id: str, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    return get_reviews(session, business_id, limit=limit, offset=offset)
