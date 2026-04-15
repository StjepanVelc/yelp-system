from app.repository.business_repository import get_businesses, get_business_by_id


def fetch_businesses(session, city, min_stars, page, limit):
    offset = (page - 1) * limit
    return get_businesses(session, city, min_stars, limit, offset)


def fetch_business_by_id(session, business_id: str):
    return get_business_by_id(session, business_id)
