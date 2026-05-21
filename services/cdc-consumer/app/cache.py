import logging

from redis import Redis
from redis.exceptions import RedisError


log = logging.getLogger("cdc-consumer.cache")


class RedisInvalidator:
    def __init__(self, redis_url: str, timeout_seconds: float) -> None:
        self._client = Redis.from_url(
            redis_url,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
            decode_responses=True,
        )

    def ping(self) -> None:
        self._client.ping()

    def delete_exact(self, key: str) -> int:
        try:
            deleted = int(self._client.delete(key))
            log.info("cache_invalidation_exact key=%s deleted=%d", key, deleted)
            return deleted
        except RedisError:
            log.warning("cache_invalidation_exact_failed key=%s", key, exc_info=True)
            return 0

    def delete_pattern(self, pattern: str) -> int:
        deleted = 0
        try:
            for key in self._client.scan_iter(match=pattern, count=1000):
                self._client.delete(key)
                deleted += 1
            log.info("cache_invalidation_pattern pattern=%s deleted=%d", pattern, deleted)
            return deleted
        except RedisError:
            log.warning("cache_invalidation_pattern_failed pattern=%s", pattern, exc_info=True)
            return deleted
