def score_business(target: dict, candidate: dict) -> float:
    """Score how similar candidate is to target business."""
    score = 0.0

    if candidate["id"] == target["id"]:
        return -1.0  # exclude self

    # Same city — strong signal
    if target.get("city") and target.get("city") == candidate.get("city"):
        score += 3.0

    # Same state — weak signal
    if target.get("state") and target.get("state") == candidate.get("state"):
        score += 1.0

    # Category overlap
    target_cats = set(c.strip() for c in (target.get("categories") or "").split(",") if c.strip())
    candidate_cats = set(c.strip() for c in (candidate.get("categories") or "").split(",") if c.strip())
    overlap = len(target_cats & candidate_cats)
    score += overlap * 2.0

    # Star rating similarity
    t_stars = target.get("stars") or 0
    c_stars = candidate.get("stars") or 0
    diff = abs(t_stars - c_stars)
    if diff <= 0.5:
        score += 2.0
    elif diff <= 1.0:
        score += 1.0

    # Only open businesses get a small boost
    if candidate.get("is_open"):
        score += 0.5

    return score


def rank_candidates(target: dict, candidates: list[dict]) -> list[dict]:
    scored = [(score_business(target, c), c) for c in candidates]
    scored = [(s, c) for s, c in scored if s >= 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]
