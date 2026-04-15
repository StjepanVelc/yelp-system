import httpx
from app.config import settings


async def get_recommendations(business_id: str, limit: int = 10):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.recommendation_service_url}/recommendations/{business_id}",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()
