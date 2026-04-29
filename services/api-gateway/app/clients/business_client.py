import httpx
from app.config import settings


async def get_businesses(city=None, min_stars=None, page=1, limit=20):
    params = {"page": page, "limit": limit}
    if city:
        params["city"] = city
    if min_stars is not None:
        params["min_stars"] = min_stars
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.business_service_url}/businesses", params=params)
        response.raise_for_status()
        return response.json()


async def get_cities():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.business_service_url}/businesses/cities")
        response.raise_for_status()
        return response.json()


async def get_business(business_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.business_service_url}/businesses/{business_id}")
        response.raise_for_status()
        return response.json()


async def get_reviews(business_id: str, page: int = 1, limit: int = 20):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.business_service_url}/businesses/{business_id}/reviews",
            params={"page": page, "limit": limit},
        )
        response.raise_for_status()
        return response.json()
