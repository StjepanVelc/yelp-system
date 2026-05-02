from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("ingestion-service.cache")


class RedisInvalidationClient:
    def __init__(self) -> None:
        self._enabled = settings.redis_enabled
        self._client: Redis | None = None

        if not self._enabled:
            log.info("cache_invalidation_client enabled=false")
            return

        try:
            self._client = Redis.from_url(
                settings.redis_url,
                socket_timeout=settings.redis_timeout_seconds,
                socket_connect_timeout=settings.redis_timeout_seconds,
                decode_responses=True,
            )
            self._client.ping()
            log.info("cache_invalidation_client enabled=true")
        except RedisError:
            self._enabled = False
            self._client = None
            log.warning("cache_invalidation_client enabled=false reason=redis_unreachable", exc_info=True)

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def delete_pattern(self, pattern: str, namespace: str) -> int:
        if not self.enabled:
            return 0

        deleted = 0
        try:
            for key in self._client.scan_iter(match=pattern, count=1000):
                self._client.delete(key)
                deleted += 1
            log.info(
                "cache_invalidation cache_key_namespace=%s cache_pattern=%s deleted=%d",
                namespace,
                pattern,
                deleted,
            )
        except RedisError:
            log.warning(
                "cache_invalidation_failed cache_key_namespace=%s cache_pattern=%s",
                namespace,
                pattern,
                exc_info=True,
            )
        return deleted


cache_invalidator = RedisInvalidationClient()