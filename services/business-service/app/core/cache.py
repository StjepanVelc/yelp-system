import json
import random
import time
from collections import defaultdict
from threading import Lock as ThreadLock
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("business-service.cache")

_LOCK_LEASE_SECONDS = 5


class CacheStats:
    """Thread-safe in-memory hit/miss/error counters per namespace."""

    def __init__(self) -> None:
        self._lock = ThreadLock()
        self._hits: dict[str, int] = defaultdict(int)
        self._misses: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)
        self._locks_acquired: dict[str, int] = defaultdict(int)
        self._stampede_waits: dict[str, int] = defaultdict(int)
        self._latency_total_ms: dict[str, float] = defaultdict(float)
        self._latency_samples: dict[str, int] = defaultdict(int)
        self._invalidations: dict[str, int] = defaultdict(int)
        self._invalidated_keys: dict[str, int] = defaultdict(int)

    def hit(self, namespace: str) -> None:
        with self._lock:
            self._hits[namespace] += 1

    def miss(self, namespace: str) -> None:
        with self._lock:
            self._misses[namespace] += 1

    def error(self, namespace: str) -> None:
        with self._lock:
            self._errors[namespace] += 1

    def lock_acquired(self, namespace: str) -> None:
        with self._lock:
            self._locks_acquired[namespace] += 1

    def stampede_wait(self, namespace: str) -> None:
        with self._lock:
            self._stampede_waits[namespace] += 1

    def latency(self, namespace: str, latency_ms: float) -> None:
        with self._lock:
            self._latency_total_ms[namespace] += latency_ms
            self._latency_samples[namespace] += 1

    def invalidation(self, namespace: str, deleted: int) -> None:
        with self._lock:
            self._invalidations[namespace] += 1
            self._invalidated_keys[namespace] += deleted

    def snapshot(self) -> dict:
        with self._lock:
            namespaces = (
                set(self._hits)
                | set(self._misses)
                | set(self._errors)
                | set(self._stampede_waits)
                | set(self._locks_acquired)
                | set(self._latency_total_ms)
                | set(self._invalidations)
                | set(self._invalidated_keys)
            )
            result: dict[str, Any] = {}
            for ns in sorted(namespaces):
                h = self._hits[ns]
                m = self._misses[ns]
                t = h + m
                latency_samples = self._latency_samples[ns]
                latency_total_ms = round(self._latency_total_ms[ns], 2)
                result[ns] = {
                    "hits": h,
                    "misses": m,
                    "errors": self._errors[ns],
                    "hit_rate": round(h / t, 4) if t else 0.0,
                    "locks_acquired": self._locks_acquired[ns],
                    "stampede_waits": self._stampede_waits[ns],
                    "latency_samples": latency_samples,
                    "cache_latency_ms_total": latency_total_ms,
                    "cache_latency_ms_avg": round(latency_total_ms / latency_samples, 2) if latency_samples else 0.0,
                    "invalidations": self._invalidations[ns],
                    "invalidated_keys": self._invalidated_keys[ns],
                }
            total_hits = sum(self._hits.values())
            total_misses = sum(self._misses.values())
            total = total_hits + total_misses
            total_latency_samples = sum(self._latency_samples.values())
            total_latency_ms = round(sum(self._latency_total_ms.values()), 2)
            return {
                "namespaces": result,
                "total": {
                    "hits": total_hits,
                    "misses": total_misses,
                    "errors": sum(self._errors.values()),
                    "hit_rate": round(total_hits / total, 4) if total else 0.0,
                    "latency_samples": total_latency_samples,
                    "cache_latency_ms_total": total_latency_ms,
                    "cache_latency_ms_avg": round(total_latency_ms / total_latency_samples, 2) if total_latency_samples else 0.0,
                    "invalidations": sum(self._invalidations.values()),
                    "invalidated_keys": sum(self._invalidated_keys.values()),
                },
            }


class RedisCacheClient:
    def __init__(self) -> None:
        self._enabled = settings.redis_enabled
        self._timeout = settings.redis_timeout_seconds
        self._client: Redis | None = None
        self.stats = CacheStats()

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
            self.stats.miss(namespace)
            log.debug("cache_miss cache_source=disabled cache_key=%s cache_key_namespace=%s", key, namespace)
            return None

        try:
            raw = self._client.get(key)
            latency_ms = (time.perf_counter() - started) * 1000
            self.stats.latency(namespace, latency_ms)
            if raw is None:
                self.stats.miss(namespace)
                log.debug(
                    "cache_miss cache_source=redis cache_key=%s cache_key_namespace=%s cache_latency_ms=%.2f",
                    key,
                    namespace,
                    latency_ms,
                )
                return None

            self.stats.hit(namespace)
            log.debug(
                "cache_hit cache_source=redis cache_key=%s cache_key_namespace=%s cache_latency_ms=%.2f",
                key,
                namespace,
                latency_ms,
            )
            return json.loads(raw)
        except (RedisError, json.JSONDecodeError):
            self.stats.error(namespace)
            log.warning("cache_get_failed cache_key=%s cache_key_namespace=%s", key, namespace, exc_info=True)
            return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int, namespace: str) -> None:
        if not self.enabled:
            return

        try:
            effective_ttl = self.jitter_ttl(ttl_seconds)
            started = time.perf_counter()
            self._client.setex(key, effective_ttl, json.dumps(payload))
            self.stats.latency(namespace, (time.perf_counter() - started) * 1000)
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
            self.stats.invalidation(namespace, deleted)
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

    def acquire_lock(self, lock_key: str) -> bool:
        """Acquire a short-lease distributed lock to prevent cache stampedes.
        Returns True if the lock was successfully acquired.
        """
        if not self.enabled:
            return False
        try:
            result = self._client.set(lock_key, "1", nx=True, ex=_LOCK_LEASE_SECONDS)
            return result is True
        except RedisError:
            log.debug("cache_lock_acquire_failed lock_key=%s", lock_key)
            return False

    def release_lock(self, lock_key: str) -> None:
        """Release a previously acquired stampede lock."""
        if not self.enabled:
            return
        try:
            self._client.delete(lock_key)
        except RedisError:
            log.debug("cache_lock_release_failed lock_key=%s", lock_key)


cache_client = RedisCacheClient()


def make_cache_key(*parts: str) -> str:
    sanitized = [str(part).strip().replace(" ", "_") for part in parts]
    return ":".join(sanitized)