from app.clients.business_client import get_business, list_businesses_in_area
from app.algorithms.scoring import rank_candidates
from app.core.cache import cache_client, make_cache_key
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("recommendation-service.service")
RECOMMENDATION_TTL_SECONDS = 15 * 60


def get_recommendations(business_id: str, limit: int = 10) -> list[dict]:
    log.info("Getting recommendations for business_id=%s limit=%d", business_id, limit)
    cache_key = make_cache_key("yelp", settings.app_env, "recommendation", "by_business", business_id, str(limit), "v1")
    cached = cache_client.get_json(cache_key, namespace="recommendation.by_business")
    if isinstance(cached, list):
        return cached

    target = get_business(business_id)
    if not target:
        log.warning("Business not found via gRPC: %s", business_id)
        return []

    log.debug("Target: %s (%s, %s)", target.get("name"), target.get("city"), target.get("state"))

    # Fetch candidates from the same city first; fall back to state if too few
    candidates = list_businesses_in_area(
        city=target.get("city", ""),
        state=target.get("state", ""),
        limit=1000,
    )
    log.debug("Fetched %d candidates via gRPC", len(candidates))

    ranked = rank_candidates(target, candidates)

    # If not enough results from same city, expand to full state
    if len(ranked) < limit:
        state_candidates = list_businesses_in_area(
            city="",
            state=target.get("state", ""),
            limit=1000,
        )
        log.debug("Expanded to state: %d additional candidates", len(state_candidates))
        ranked = rank_candidates(target, state_candidates)

    results = ranked[:limit]
    cache_client.set_json(
        cache_key,
        results,
        ttl_seconds=RECOMMENDATION_TTL_SECONDS,
        namespace="recommendation.by_business",
    )

    log.info("Returning %d recommendations for %s", len(results), business_id)
    return results


