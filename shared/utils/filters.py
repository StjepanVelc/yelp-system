def apply_business_filters(query: str, params: dict, city=None, min_stars=None) -> tuple[str, dict]:
    if city:
        query += " AND city = :city"
        params["city"] = city
    if min_stars is not None:
        query += " AND stars >= :min_stars"
        params["min_stars"] = min_stars
    return query, params
