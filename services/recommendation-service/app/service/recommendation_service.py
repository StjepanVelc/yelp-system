from app.clients.business_client import get_business, list_businesses_in_area
from app.algorithms.scoring import rank_candidates
from app.core.logger import get_logger

log = get_logger("recommendation-service.service")


def get_recommendations(business_id: str, limit: int = 10) -> list[dict]:
    log.info("Getting recommendations for business_id=%s limit=%d", business_id, limit)
    target = get_business(business_id)
    if not target:
        log.warning("Business not found via gRPC: %s", business_id)
        return []

    log.debug("Target business: %s (%s, %s)", target.get("name"), target.get("city"), target.get("state"))
    candidates = list_businesses_in_area(
        city=target.get("city", ""),
        state=target.get("state", ""),
        limit=500,
    )
    log.debug("Fetched %d candidates via gRPC", len(candidates))
    ranked = rank_candidates(target, candidates)
    log.info("Returning %d recommendations for %s", min(limit, len(ranked)), business_id)
    return ranked[:limit]

