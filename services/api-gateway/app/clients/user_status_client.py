import httpx
import time
from threading import Lock

from app.config import settings
from app.clients.http_client import get_shared_client
from app.logger import get_logger

log = get_logger("api-gateway.user-status")

_USER_STATUS_CACHE: dict[str, tuple[float, dict]] = {}
_USER_STATUS_CACHE_LOCK = Lock()


def clear_user_status_cache() -> None:
    with _USER_STATUS_CACHE_LOCK:
        _USER_STATUS_CACHE.clear()


def _get_cached_user_status(user_id: str) -> dict | None:
    ttl = float(settings.user_status_cache_ttl_seconds)
    if ttl <= 0:
        return None

    now = time.monotonic()
    with _USER_STATUS_CACHE_LOCK:
        cached = _USER_STATUS_CACHE.get(user_id)
        if cached is None:
            return None

        expires_at, payload = cached
        if expires_at <= now:
            _USER_STATUS_CACHE.pop(user_id, None)
            return None

        return payload


def _set_cached_user_status(user_id: str, payload: dict) -> None:
    ttl = float(settings.user_status_cache_ttl_seconds)
    if ttl <= 0:
        return

    expires_at = time.monotonic() + ttl
    with _USER_STATUS_CACHE_LOCK:
        _USER_STATUS_CACHE[user_id] = (expires_at, payload)


async def get_user_status(user_id: str) -> dict:
    cached_payload = _get_cached_user_status(user_id)
    if cached_payload is not None:
        log.info(
            "user_status_cache_hit user_id=%s ttl_s=%.2f",
            user_id,
            settings.user_status_cache_ttl_seconds,
        )
        return cached_payload

    log.info(
        "user_status_cache_miss user_id=%s ttl_s=%.2f",
        user_id,
        settings.user_status_cache_ttl_seconds,
    )

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

    _set_cached_user_status(
        user_id,
        {
            "active": bool(payload.get("active", True)),
            "deleted": bool(payload.get("deleted", False)),
            "deleted_at": payload.get("deleted_at"),
        },
    )

    return {
        "active": bool(payload.get("active", True)),
        "deleted": bool(payload.get("deleted", False)),
        "deleted_at": payload.get("deleted_at"),
    }
