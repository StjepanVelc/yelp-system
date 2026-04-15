def paginate(page: int, limit: int) -> tuple[int, int]:
    """Returns (limit, offset) for SQL queries."""
    offset = (page - 1) * limit
    return limit, offset
