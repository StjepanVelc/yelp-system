import hashlib
import time

from app.clients.business_client import get_business, list_businesses_in_area
from app.algorithms.scoring import rank_candidates
from app.core.cache import cache_client, make_cache_key
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("recommendation-service.service")
RECOMMENDATION_TTL_SECONDS = 15 * 60


def _should_use_cache(entity_id: str) -> bool:
    pct = settings.cache_rollout_percent
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    bucket = int(hashlib.md5(entity_id.encode(), usedforsecurity=False).hexdigest(), 16) % 100
    return bucket < pct


def _fetch_from_source(business_id: str, limit: int) -> list[dict]:
    target = get_business(business_id)
    if not target:
        log.warning("Business not found via gRPC: %s", business_id)
        return []

    log.debug("Target: %s (%s, %s)", target.get("name"), target.get("city"), target.get("state"))

    candidates = list_businesses_in_area(
        city=target.get("city", ""),
        state=target.get("state", ""),
        limit=1000,
    )
    log.debug("Fetched %d candidates via gRPC", len(candidates))

    ranked = rank_candidates(target, candidates)

    if len(ranked) < limit:
        state_candidates = list_businesses_in_area(
            city="",
            state=target.get("state", ""),
            limit=1000,
        )
        log.debug("Expanded to state: %d additional candidates", len(state_candidates))
        ranked = rank_candidates(target, state_candidates)

    return ranked[:limit]


def get_recommendations(business_id: str, limit: int = 10) -> list[dict]:
    log.info("Getting recommendations for business_id=%s limit=%d", business_id, limit)
    cache_key = make_cache_key("yelp", settings.app_env, "recommendation", "by_business", business_id, str(limit), "v1")

    if not _should_use_cache(business_id):
        return _fetch_from_source(business_id, limit)

    if settings.cache_shadow_mode:
        results = _fetch_from_source(business_id, limit)
        cached = cache_client.get_json(cache_key, namespace="recommendation.by_business")
        if cached is not None:
            log.info("cache_shadow namespace=recommendation.by_business cache_match=%s", cached == results)
        return results

    cached = cache_client.get_json(cache_key, namespace="recommendation.by_business")
    if isinstance(cached, list):
        log.info("Returning %d recommendations for %s (cache hit)", len(cached), business_id)
        return cached

    lock_key = f"lock:{cache_key}"
    lock_acquired = cache_client.acquire_lock(lock_key)
    if not lock_acquired and cache_client.enabled:
        cache_client.stats.stampede_wait("recommendation.by_business")
        time.sleep(0.05)
        cached = cache_client.get_json(cache_key, namespace="recommendation.by_business")
        if isinstance(cached, list):
            log.info("Returning %d recommendations for %s (cache hit after wait)", len(cached), business_id)
            return cached

    try:
        results = _fetch_from_source(business_id, limit)
        if results:
            cache_client.set_json(
                cache_key,
                results,
                ttl_seconds=RECOMMENDATION_TTL_SECONDS,
                namespace="recommendation.by_business",
            )
        log.info("Returning %d recommendations for %s", len(results), business_id)
        return results
    finally:
        if lock_acquired:
            cache_client.release_lock(lock_key)


