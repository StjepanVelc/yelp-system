import httpx

from app.config import settings
from app.logger import get_logger

log = get_logger("api-gateway.user-status")


async def get_user_status(user_id: str) -> dict:
    path = settings.user_status_path_template.format(user_id=user_id)
    url = f"{settings.user_service_url.rstrip('/')}{path}"

    try:
        async with httpx.AsyncClient(timeout=settings.user_status_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        if settings.app_env.lower() == "development":
            log.warning("user_status_unavailable user_id=%s — fail-open in development: %s", user_id, exc)
            return {"active": True, "deleted": False, "deleted_at": None}
        raise

    return {
        "active": bool(payload.get("active", True)),
        "deleted": bool(payload.get("deleted", False)),
        "deleted_at": payload.get("deleted_at"),
    }
