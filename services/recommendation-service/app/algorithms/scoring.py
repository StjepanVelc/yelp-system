import math


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_business(target: dict, candidate: dict) -> float:
    """Score how similar candidate is to target business (higher = more similar)."""
    if candidate["id"] == target["id"]:
        return -1.0  # exclude self

    score = 0.0

    # ── Geographic proximity ──────────────────────────────────────────────
    try:
        km = _haversine_km(
            target["latitude"], target["longitude"],
            candidate["latitude"], candidate["longitude"],
        )
        if km <= 1:
            score += 5.0
        elif km <= 3:
            score += 4.0
        elif km <= 5:
            score += 3.0
        elif km <= 10:
            score += 2.0
        elif km <= 25:
            score += 1.0
    except (TypeError, KeyError):
        # fall back to city/state signals if coordinates are missing
        if target.get("city") and target.get("city") == candidate.get("city"):
            score += 3.0
        if target.get("state") and target.get("state") == candidate.get("state"):
            score += 1.0

    # ── Category overlap ──────────────────────────────────────────────────
    target_cats = {c.strip() for c in (target.get("categories") or "").split(",") if c.strip()}
    candidate_cats = {c.strip() for c in (candidate.get("categories") or "").split(",") if c.strip()}
    overlap = len(target_cats & candidate_cats)
    score += overlap * 2.5  # weighted heavily — same niche matters most

    # ── Star rating similarity ────────────────────────────────────────────
    t_stars = target.get("stars") or 0
    c_stars = candidate.get("stars") or 0
    diff = abs(t_stars - c_stars)
    if diff <= 0.5:
        score += 2.0
    elif diff <= 1.0:
        score += 1.0

    # ── Open status ───────────────────────────────────────────────────────
    if candidate.get("is_open"):
        score += 0.5

    # ── Review count (popularity) ─────────────────────────────────────────
    rc = candidate.get("review_count") or 0
    if rc >= 500:
        score += 1.0
    elif rc >= 100:
        score += 0.5

    return score


def rank_candidates(target: dict, candidates: list[dict]) -> list[dict]:
    scored = [(score_business(target, c), c) for c in candidates]
    scored = [(s, c) for s, c in scored if s >= 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]

