from sqlalchemy import text
from app.core.logger import get_logger

log = get_logger("business-service.repository")

FTS_FALLBACK_MIN_RESULTS = 5
SEARCH_PATH_AUTO = "auto"
SEARCH_PATH_FTS = "fts"
SEARCH_PATH_TRIGRAM = "trigram"
SEARCH_PATH_LEGACY = "legacy"


def _build_filter_clause(city=None, state=None, min_stars=None):
    clause = "WHERE 1=1"
    params = {}

    if city:
        clause += " AND city = :city"
        params["city"] = city

    if state:
        clause += " AND state = :state"
        params["state"] = state

    if min_stars is not None:
        clause += " AND stars >= :min_stars"
        params["min_stars"] = min_stars

    return clause, params


def _ranked_fts_candidates(session, parser_sql: str, user_query: str, filter_clause: str, params: dict, fetch_size: int):
    ranked_query = f"""
    WITH q AS (
        SELECT {parser_sql} AS tsq
    ),
    fts AS (
        SELECT
            b.*,
            ts_rank_cd(b.search_vector, q.tsq) AS text_rank,
            COALESCE(b.stars, 0) / 5.0 AS rating_score,
            LN(1 + COALESCE(b.review_count, 0)) AS review_ln
        FROM businesses b, q
        {filter_clause}
          AND b.search_vector @@ q.tsq
    ),
    stats AS (
        SELECT
            COALESCE(MAX(text_rank), 0) AS max_text_rank,
            COALESCE(MAX(review_ln), 0) AS max_review_ln
        FROM fts
    )
    SELECT
        fts.*,
        (
            0.60 * CASE WHEN stats.max_text_rank > 0 THEN fts.text_rank / stats.max_text_rank ELSE 0 END +
            0.20 * fts.rating_score +
            0.15 * CASE WHEN stats.max_review_ln > 0 THEN fts.review_ln / stats.max_review_ln ELSE 0 END
        ) AS final_score
    FROM fts
    CROSS JOIN stats
    ORDER BY final_score DESC, fts.text_rank DESC, fts.stars DESC, fts.review_count DESC
    LIMIT :fetch_size
    """

    query_params = dict(params)
    query_params.update({"query": user_query, "fetch_size": fetch_size})
    result = session.execute(text(ranked_query), query_params)
    return [dict(row._mapping) for row in result]


def _trigram_fallback_candidates(
    session,
    user_query: str,
    filter_clause: str,
    params: dict,
    existing_ids: set[str],
    fetch_size: int,
):
    if fetch_size <= 0:
        return []

    id_filter = ""
    query_params = dict(params)
    query_params.update({"query": user_query, "fetch_size": fetch_size})

    if existing_ids:
        id_filter = " AND b.id <> ALL(:existing_ids)"
        query_params["existing_ids"] = list(existing_ids)

    trigram_query = f"""
    WITH tri AS (
        SELECT
            b.*,
            similarity(COALESCE(b.name, ''), :query) AS trigram_score,
            COALESCE(b.stars, 0) / 5.0 AS rating_score,
            LN(1 + COALESCE(b.review_count, 0)) AS review_ln
        FROM businesses b
        {filter_clause}
          AND COALESCE(b.name, '') % :query
          {id_filter}
    ),
    stats AS (
        SELECT
            COALESCE(MAX(trigram_score), 0) AS max_trigram_score,
            COALESCE(MAX(review_ln), 0) AS max_review_ln
        FROM tri
    )
    SELECT
        tri.*,
        (
            0.65 * CASE WHEN stats.max_trigram_score > 0 THEN tri.trigram_score / stats.max_trigram_score ELSE 0 END +
            0.20 * tri.rating_score +
            0.15 * CASE WHEN stats.max_review_ln > 0 THEN tri.review_ln / stats.max_review_ln ELSE 0 END
        ) AS final_score
    FROM tri
    CROSS JOIN stats
    ORDER BY final_score DESC, tri.trigram_score DESC, tri.stars DESC, tri.review_count DESC
    LIMIT :fetch_size
    """

    result = session.execute(text(trigram_query), query_params)
    return [dict(row._mapping) for row in result]


def _is_timeout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "timeout" in message or "statement timeout" in message or "canceling statement" in message


def get_businesses(
    session,
    city=None,
    state=None,
    min_stars=None,
    query=None,
    search_path=SEARCH_PATH_AUTO,
    limit=20,
    offset=0,
    include_meta=False,
):
    filter_clause, params = _build_filter_clause(city=city, state=state, min_stars=min_stars)
    user_query = (query or "").strip()

    meta = {
        "search_path": SEARCH_PATH_LEGACY,
        "search_version": "legacy",
        "fallback_reason": None,
    }

    def _return(rows):
        return (rows, meta) if include_meta else rows

    if not user_query or search_path == SEARCH_PATH_LEGACY:
        sql = f"SELECT * FROM businesses {filter_clause} LIMIT :limit OFFSET :offset"
        query_params = dict(params)
        query_params.update({"limit": limit, "offset": offset})
        log.debug(
            "Query businesses city=%s state=%s min_stars=%s limit=%d offset=%d",
            city,
            state,
            min_stars,
            limit,
            offset,
        )
        result = session.execute(text(sql), query_params)
        rows = [dict(row._mapping) for row in result]

        if search_path == SEARCH_PATH_LEGACY:
            meta["fallback_reason"] = "forced_legacy"
        elif not user_query:
            meta["fallback_reason"] = "no_query"

        log.debug("Found %d businesses (legacy mode)", len(rows))
        return _return(rows)

    fetch_size = max(limit + offset, limit, FTS_FALLBACK_MIN_RESULTS)

    if search_path == SEARCH_PATH_TRIGRAM:
        rows = _trigram_fallback_candidates(
            session=session,
            user_query=user_query,
            filter_clause=filter_clause,
            params=params,
            existing_ids=set(),
            fetch_size=fetch_size,
        )
        paged_rows = rows[offset: offset + limit]
        meta["search_path"] = SEARCH_PATH_TRIGRAM
        meta["search_version"] = "v2"
        meta["fallback_reason"] = "forced_trigram"
        return _return(paged_rows)

    force_fts = search_path == SEARCH_PATH_FTS

    try:
        rows = _ranked_fts_candidates(
            session=session,
            parser_sql="websearch_to_tsquery('simple', :query)",
            user_query=user_query,
            filter_clause=filter_clause,
            params=params,
            fetch_size=fetch_size,
        )
    except Exception:
        log.warning("websearch_to_tsquery failed, falling back to plainto_tsquery", exc_info=True)
        rows = _ranked_fts_candidates(
            session=session,
            parser_sql="plainto_tsquery('simple', :query)",
            user_query=user_query,
            filter_clause=filter_clause,
            params=params,
            fetch_size=fetch_size,
        )
    except Exception as exc:
        fallback_reason = "fts_timeout" if _is_timeout_error(exc) else "fts_error"
        log.warning("FTS query failed, falling back to legacy search", exc_info=True)
        sql = f"SELECT * FROM businesses {filter_clause} LIMIT :limit OFFSET :offset"
        query_params = dict(params)
        query_params.update({"limit": limit, "offset": offset})
        result = session.execute(text(sql), query_params)
        rows = [dict(row._mapping) for row in result]
        meta["search_path"] = SEARCH_PATH_LEGACY
        meta["search_version"] = "legacy"
        meta["fallback_reason"] = fallback_reason
        return _return(rows)

    used_trigram_fallback = False

    fts_rows_count = len(rows)

    if not force_fts and fts_rows_count < max(FTS_FALLBACK_MIN_RESULTS, limit):
        fallback_rows = _trigram_fallback_candidates(
            session=session,
            user_query=user_query,
            filter_clause=filter_clause,
            params=params,
            existing_ids={str(row.get("id")) for row in rows if row.get("id")},
            fetch_size=fetch_size - len(rows),
        )
        used_trigram_fallback = len(fallback_rows) > 0
        rows.extend(fallback_rows)

    paged_rows = rows[offset: offset + limit]
    if used_trigram_fallback:
        meta["search_path"] = SEARCH_PATH_TRIGRAM
        meta["search_version"] = "v2"
        meta["fallback_reason"] = "fts_zero_results" if fts_rows_count == 0 else "fts_low_results"
    else:
        meta["search_path"] = SEARCH_PATH_FTS
        meta["search_version"] = "v2"

    log.debug(
        "FTS query businesses q=%s city=%s state=%s min_stars=%s limit=%d offset=%d returned=%d",
        user_query,
        city,
        state,
        min_stars,
        limit,
        offset,
        len(paged_rows),
    )
    return _return(paged_rows)


def get_cities(session):
    log.debug("Fetching distinct cities")
    result = session.execute(
        text(
            "SELECT DISTINCT TRIM(city) AS city "
            "FROM businesses "
            "WHERE city IS NOT NULL AND TRIM(city) <> '' "
            "ORDER BY city ASC"
        )
    )
    cities = [str(row._mapping["city"]) for row in result]
    log.debug("Found %d cities", len(cities))
    return cities


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


def get_user_status(session, user_id: str):
    log.debug("Fetching user status for user_id=%s", user_id)
    result = session.execute(
        text("SELECT user_id FROM users WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    row = result.fetchone()

    if row:
        return {
            "user_id": row._mapping["user_id"],
            "active": True,
            "deleted": False,
            "deleted_at": None,
        }

    return {
        "user_id": user_id,
        "active": False,
        "deleted": True,
        "deleted_at": "not-found",
    }

