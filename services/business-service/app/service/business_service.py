from app.repository.business_repository import (
    get_businesses,
    get_business_by_id,
    get_cities,
    get_reviews,
    get_user_status,
)
from app.core.cache import cache_client, make_cache_key
from app.core.config import settings

DETAILS_TTL_SECONDS = 60 * 60
CITIES_TTL_SECONDS = 12 * 60 * 60


def fetch_businesses(session, city, state, min_stars, query, page, limit):
    offset = (page - 1) * limit
    return get_businesses(
        session,
        city=city,
        state=state,
        min_stars=min_stars,
        query=query,
        limit=limit,
        offset=offset,
    )


def fetch_businesses_with_meta(session, city, state, min_stars, query, search_path, page, limit):
    offset = (page - 1) * limit
    return get_businesses(
        session,
        city=city,
        state=state,
        min_stars=min_stars,
        query=query,
        search_path=search_path,
        limit=limit,
        offset=offset,
        include_meta=True,
    )


def fetch_business_by_id(session, business_id: str):
    key = make_cache_key("yelp", settings.app_env, "business", "details", business_id, "v1")
    cached = cache_client.get_json(key, namespace="business.details")
    if isinstance(cached, dict):
        return cached

    business = get_business_by_id(session, business_id)
    if business is not None:
        cache_client.set_json(key, business, ttl_seconds=DETAILS_TTL_SECONDS, namespace="business.details")
    return business


def fetch_cities(session):
    key = make_cache_key("yelp", settings.app_env, "business", "cities", "all", "v1")
    cached = cache_client.get_json(key, namespace="business.cities")
    if isinstance(cached, list):
        return cached

    cities = get_cities(session)
    cache_client.set_json(key, cities, ttl_seconds=CITIES_TTL_SECONDS, namespace="business.cities")
    return cities


def fetch_reviews(session, business_id: str, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    return get_reviews(session, business_id, limit=limit, offset=offset)


def fetch_user_status(session, user_id: str):
    return get_user_status(session, user_id)
