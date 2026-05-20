from app.config import settings
from app.clients.http_client import get_shared_client


async def get_businesses(city=None, min_stars=None, query=None, search_path="auto", page=1, limit=20):
    params = {"page": page, "limit": limit}
    if city:
        params["city"] = city
    if min_stars is not None:
        params["min_stars"] = min_stars
    if query:
        params["query"] = query
    if search_path:
        params["search_path"] = search_path

    client = get_shared_client()
    response = await client.get(f"{settings.business_service_url}/businesses", params=params)
    response.raise_for_status()
    headers = {
        "X-Search-Path": response.headers.get("X-Search-Path", "legacy"),
        "X-Search-Version": response.headers.get("X-Search-Version", "legacy"),
        "X-Search-Latency-Ms": response.headers.get("X-Search-Latency-Ms", "0"),
    }
    return response.json(), headers


async def get_cities():
    client = get_shared_client()
    response = await client.get(f"{settings.business_service_url}/businesses/cities")
    response.raise_for_status()
    return response.json()


async def get_business(business_id: str):
    client = get_shared_client()
    response = await client.get(f"{settings.business_service_url}/businesses/{business_id}")
    response.raise_for_status()
    return response.json()


async def get_reviews(business_id: str, page: int = 1, limit: int = 20):
    client = get_shared_client()
    response = await client.get(
        f"{settings.business_service_url}/businesses/{business_id}/reviews",
        params={"page": page, "limit": limit},
    )
    response.raise_for_status()
    return response.json()
