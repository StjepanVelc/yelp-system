import json
import random
import time
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("business-service.cache")


class RedisCacheClient:
    def __init__(self) -> None:
        self._enabled = settings.redis_enabled
        self._timeout = settings.redis_timeout_seconds
        self._client: Redis | None = None

        if not self._enabled:
            log.info("cache_initialized enabled=false")
            return

        try:
            self._client = Redis.from_url(
                settings.redis_url,
                socket_timeout=self._timeout,
                socket_connect_timeout=self._timeout,
                decode_responses=True,
            )
            self._client.ping()
            log.info("cache_initialized enabled=true source=redis")
        except RedisError:
            self._enabled = False
            self._client = None
            log.warning("cache_initialized enabled=false reason=redis_unreachable", exc_info=True)

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def jitter_ttl(self, ttl_seconds: int, jitter_ratio: float = 0.15) -> int:
        if ttl_seconds <= 0:
            return ttl_seconds
        delta = int(ttl_seconds * jitter_ratio)
        if delta <= 0:
            return ttl_seconds
        return max(1, ttl_seconds + random.randint(-delta, delta))

    def get_json(self, key: str, namespace: str) -> dict[str, Any] | list[Any] | None:
        started = time.perf_counter()
        if not self.enabled:
            log.debug("cache_miss cache_source=disabled cache_key=%s cache_key_namespace=%s", key, namespace)
            return None

        try:
            raw = self._client.get(key)
            latency_ms = (time.perf_counter() - started) * 1000
            if raw is None:
                log.debug(
                    "cache_miss cache_source=redis cache_key=%s cache_key_namespace=%s cache_latency_ms=%.2f",
                    key,
                    namespace,
                    latency_ms,
                )
                return None

            log.debug(
                "cache_hit cache_source=redis cache_key=%s cache_key_namespace=%s cache_latency_ms=%.2f",
                key,
                namespace,
                latency_ms,
            )
            return json.loads(raw)
        except (RedisError, json.JSONDecodeError):
            log.warning("cache_get_failed cache_key=%s cache_key_namespace=%s", key, namespace, exc_info=True)
            return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int, namespace: str) -> None:
        if not self.enabled:
            return

        try:
            effective_ttl = self.jitter_ttl(ttl_seconds)
            self._client.setex(key, effective_ttl, json.dumps(payload))
            log.debug(
                "cache_set cache_source=redis cache_key=%s cache_key_namespace=%s cache_ttl=%d",
                key,
                namespace,
                effective_ttl,
            )
        except (RedisError, TypeError, ValueError):
            log.warning("cache_set_failed cache_key=%s cache_key_namespace=%s", key, namespace, exc_info=True)

    def delete_pattern(self, pattern: str, namespace: str) -> int:
        if not self.enabled:
            return 0

        deleted = 0
        try:
            for key in self._client.scan_iter(match=pattern, count=500):
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


cache_client = RedisCacheClient()


def make_cache_key(*parts: str) -> str:
    sanitized = [str(part).strip().replace(" ", "_") for part in parts]
    return ":".join(sanitized)