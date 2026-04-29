import httpx

from app.config import settings


async def get_user_status(user_id: str) -> dict:
    path = settings.user_status_path_template.format(user_id=user_id)
    url = f"{settings.user_service_url.rstrip('/')}{path}"

    async with httpx.AsyncClient(timeout=settings.user_status_timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()

    return {
        "active": bool(payload.get("active", True)),
        "deleted": bool(payload.get("deleted", False)),
        "deleted_at": payload.get("deleted_at"),
    }
