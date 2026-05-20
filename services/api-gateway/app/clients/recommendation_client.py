from app.config import settings
from app.clients.http_client import get_shared_client


async def get_recommendations(business_id: str, limit: int = 10):
    client = get_shared_client()
    response = await client.get(
        f"{settings.recommendation_service_url}/recommendations/{business_id}",
        params={"limit": limit},
    )
    response.raise_for_status()
    return response.json()
