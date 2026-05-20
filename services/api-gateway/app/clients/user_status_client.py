import httpx
import time

from app.config import settings
from app.clients.http_client import get_shared_client
from app.logger import get_logger

log = get_logger("api-gateway.user-status")


async def get_user_status(user_id: str) -> dict:
    path = settings.user_status_path_template.format(user_id=user_id)
    url = f"{settings.user_service_url.rstrip('/')}{path}"
    started = time.perf_counter()

    try:
        client = get_shared_client()
        response = await client.get(url, timeout=settings.user_status_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "user_status_timing user_id=%s status_code=%d elapsed_ms=%.2f timeout_s=%.2f",
            user_id,
            response.status_code,
            elapsed_ms,
            settings.user_status_timeout_seconds,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        if settings.app_env.lower() == "development":
            log.warning(
                "user_status_unavailable user_id=%s elapsed_ms=%.2f timeout_s=%.2f — fail-open in development: %s",
                user_id,
                elapsed_ms,
                settings.user_status_timeout_seconds,
                exc,
            )
            return {"active": True, "deleted": False, "deleted_at": None}
        raise

    return {
        "active": bool(payload.get("active", True)),
        "deleted": bool(payload.get("deleted", False)),
        "deleted_at": payload.get("deleted_at"),
    }
