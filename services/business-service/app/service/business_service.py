import hashlib
import time

from app.repository.business_repository import (
    get_businesses,
    get_business_by_id,
    get_cities,
    get_reviews,
    get_user_status,
)
from app.core.cache import cache_client, make_cache_key
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("business-service.service")

DETAILS_TTL_SECONDS = 60 * 60
CITIES_TTL_SECONDS = 12 * 60 * 60


def _should_use_cache(entity_id: str) -> bool:
    pct = settings.cache_rollout_percent
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    bucket = int(hashlib.md5(entity_id.encode(), usedforsecurity=False).hexdigest(), 16) % 100
    return bucket < pct


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

    if not _should_use_cache(business_id):
        return get_business_by_id(session, business_id)

    if settings.cache_shadow_mode:
        result = get_business_by_id(session, business_id)
        cached = cache_client.get_json(key, namespace="business.details")
        if cached is not None:
            log.info("cache_shadow namespace=business.details cache_match=%s", cached == result)
        return result

    cached = cache_client.get_json(key, namespace="business.details")
    if isinstance(cached, dict):
        return cached

    lock_key = f"lock:{key}"
    lock_acquired = cache_client.acquire_lock(lock_key)
    if not lock_acquired and cache_client.enabled:
        cache_client.stats.stampede_wait("business.details")
        time.sleep(0.05)
        cached = cache_client.get_json(key, namespace="business.details")
        if isinstance(cached, dict):
            return cached

    try:
        business = get_business_by_id(session, business_id)
        if business is not None:
            cache_client.set_json(key, business, ttl_seconds=DETAILS_TTL_SECONDS, namespace="business.details")
        return business
    finally:
        if lock_acquired:
            cache_client.release_lock(lock_key)


def fetch_cities(session):
    if settings.cache_rollout_percent <= 0:
        return get_cities(session)

    key = make_cache_key("yelp", settings.app_env, "business", "cities", "all", "v1")

    if settings.cache_shadow_mode:
        result = get_cities(session)
        cached = cache_client.get_json(key, namespace="business.cities")
        if cached is not None:
            log.info("cache_shadow namespace=business.cities cache_match=%s", cached == result)
        return result

    cached = cache_client.get_json(key, namespace="business.cities")
    if isinstance(cached, list):
        return cached

    lock_key = f"lock:{key}"
    lock_acquired = cache_client.acquire_lock(lock_key)
    if not lock_acquired and cache_client.enabled:
        cache_client.stats.stampede_wait("business.cities")
        time.sleep(0.05)
        cached = cache_client.get_json(key, namespace="business.cities")
        if isinstance(cached, list):
            return cached

    try:
        cities = get_cities(session)
        cache_client.set_json(key, cities, ttl_seconds=CITIES_TTL_SECONDS, namespace="business.cities")
        return cities
    finally:
        if lock_acquired:
            cache_client.release_lock(lock_key)


def fetch_reviews(session, business_id: str, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    return get_reviews(session, business_id, limit=limit, offset=offset)


def fetch_user_status(session, user_id: str):
    return get_user_status(session, user_id)
