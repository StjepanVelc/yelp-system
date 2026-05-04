"""
Redis cache load test + chaos scenario.

Usage:
    python scripts/cache_load_test.py --help
    python scripts/cache_load_test.py load     # concurrent requests, report hit-rate
    python scripts/cache_load_test.py chaos    # manual chaos checklist

Requirements (host machine):
    pip install httpx
"""

import argparse
import concurrent.futures
import json
import sys
import time
from dataclasses import dataclass, field

try:
    import httpx
except ImportError:
    sys.exit("Install httpx first:  pip install httpx")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GATEWAY_BASE = "http://localhost:8000"
BUSINESS_STATS_URL = "http://localhost:8001/cache/stats"
RECOMMENDATION_STATS_URL = "http://localhost:8002/cache/stats"

# A representative set of business IDs present in the dev dataset.
# Override via --ids flag or extend this list.
SAMPLE_IDS = [
    "Pns2l4eNsfO8kk83dixA6A",
    "mpf3x-BjTdTEA3uyVmlQNQ",
    "QXAEGFB4oINsVuTFxEYKFQ",
    "nBbRCOgKFgfg5JhePnJanA",
    "RESDUcs7fIiihp38-d6_6g",
    "K7lWdNUhCbcnEvI0NhGewg",
    "IHKNfXzT7DnMSN-Rv6IEbg",
    "IufhCRKT9S3OxPvBZ4nKxA",
    "z2Hl4B9LME3wMZqS02LWXg",
    "zjAB4mrE4JkTPVwcfXCxPQ",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class Result:
    ok: int = 0
    err: int = 0
    total_ms: float = 0.0
    latencies: list = field(default_factory=list)


def fetch_one(client: httpx.Client, url: str) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        r = client.get(url, timeout=5.0)
        elapsed = (time.perf_counter() - start) * 1000
        return r.status_code == 200, elapsed
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return False, elapsed


def pull_stats(url: str) -> dict:
    try:
        r = httpx.get(url, timeout=3.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def print_stats(label: str, stats: dict) -> None:
    total = stats.get("total", {})
    if not total:
        print(f"  {label}: no stats returned (service not running?)")
        return
    hits = total.get("hits", 0)
    misses = total.get("misses", 0)
    errors = total.get("errors", 0)
    hit_rate = total.get("hit_rate", 0.0)
    print(f"  {label}:")
    print(f"    hits={hits}  misses={misses}  errors={errors}  hit_rate={hit_rate:.1%}")
    for ns, ns_data in stats.get("namespaces", {}).items():
        ns_hr = ns_data.get("hit_rate", 0.0)
        ns_hits = ns_data.get("hits", 0)
        ns_misses = ns_data.get("misses", 0)
        print(f"    [{ns}] hits={ns_hits} misses={ns_misses} hit_rate={ns_hr:.1%}")


# ---------------------------------------------------------------------------
# Load test
# ---------------------------------------------------------------------------

def run_load_test(concurrency: int, rounds: int, ids: list[str]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  LOAD TEST — concurrency={concurrency}  rounds={rounds}  ids={len(ids)}")
    print(f"{'=' * 60}")

    # Snapshot before
    print("\n[BEFORE] Cache stats:")
    before_biz = pull_stats(BUSINESS_STATS_URL)
    before_rec = pull_stats(RECOMMENDATION_STATS_URL)
    print_stats("business-service", before_biz)
    print_stats("recommendation-service", before_rec)

    # Build URL list
    urls = []
    for biz_id in ids:
        urls.append(f"{GATEWAY_BASE}/businesses/{biz_id}")
        urls.append(f"{GATEWAY_BASE}/recommendations/{biz_id}")
    # Repeat for `rounds`
    all_urls = urls * rounds

    result = Result()
    t0 = time.perf_counter()

    with httpx.Client() as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futs = [pool.submit(fetch_one, client, u) for u in all_urls]
            for f in concurrent.futures.as_completed(futs):
                ok, ms = f.result()
                result.latencies.append(ms)
                if ok:
                    result.ok += 1
                else:
                    result.err += 1

    elapsed = time.perf_counter() - t0
    total_req = result.ok + result.err
    sorted_lat = sorted(result.latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.50)] if sorted_lat else 0
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] if sorted_lat else 0
    rps = total_req / elapsed if elapsed > 0 else 0

    print(f"\n[RESULTS]")
    print(f"  requests : {total_req}  ok={result.ok}  err={result.err}")
    print(f"  duration : {elapsed:.1f}s   rps={rps:.0f}")
    print(f"  latency  : p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms")

    # Snapshot after
    print("\n[AFTER] Cache stats:")
    after_biz = pull_stats(BUSINESS_STATS_URL)
    after_rec = pull_stats(RECOMMENDATION_STATS_URL)
    print_stats("business-service", after_biz)
    print_stats("recommendation-service", after_rec)

    # Delta
    def delta_hits(before: dict, after: dict) -> tuple[int, int]:
        def total_hits(d: dict) -> int:
            return d.get("total", {}).get("hits", 0)
        def total_misses(d: dict) -> int:
            return d.get("total", {}).get("misses", 0)
        return (total_hits(after) - total_hits(before),
                total_misses(after) - total_misses(before))

    biz_dh, biz_dm = delta_hits(before_biz, after_biz)
    rec_dh, rec_dm = delta_hits(before_rec, after_rec)
    print(f"\n[DELTA during test]")
    print(f"  business-service     +hits={biz_dh}  +misses={biz_dm}")
    print(f"  recommendation-service +hits={rec_dh}  +misses={rec_dm}")

    if result.err > 0:
        print(f"\n  ⚠  {result.err} requests failed — check service logs")
    elif p95 < 100:
        print(f"\n  ✓  p95 < 100ms — cache warm, healthy")
    else:
        print(f"\n  ⚠  p95 >= 100ms — cache may not be warmed yet; run again")


# ---------------------------------------------------------------------------
# Chaos scenario
# ---------------------------------------------------------------------------

def run_chaos() -> None:
    print(f"\n{'=' * 60}")
    print("  CHAOS SCENARIO — Redis kill & recovery")
    print(f"{'=' * 60}")
    print("""
This is a manual checklist (automated kill requires Docker socket access).
Run these steps while the stack is serving traffic:

STEP 1 — Baseline traffic (background)
  Open another shell and run:
    python scripts/cache_load_test.py load --rounds 5 --concurrency 10

STEP 2 — Kill Redis mid-traffic
  docker compose stop redis

STEP 3 — Observe fail-open
  Expected: services continue returning 200; logs show:
    cache_get_failed   <- Redis read error, fail-open
    cache_set_failed   <- Redis write error, ignored

STEP 4 — Check error rate
  curl http://localhost:8001/cache/stats
  Expected: errors counter rising; hit_rate=0.0 (all misses)

STEP 5 — Restore Redis
  docker compose start redis

STEP 6 — Verify auto-recovery
  After ~10s (first requests after Redis restarts):
  - hit_rate resumes rising
  - No service restart required
  - Logs show cache_set as cache re-warms

STEP 7 — Memory pressure test
  docker compose exec redis redis-cli DEBUG SETOBJ <key> 0 100000000
  # observe allkeys-lru eviction via: redis-cli INFO stats | grep evicted
  # hit_rate should drop then stabilise as LRU keeps hot keys

SUCCESS CRITERIA:
  □ No 5xx during Redis downtime
  □ DB query rate absorbs cache traffic (temporary DB load spike acceptable)
  □ Cache auto-recovers without service restart
  □ allkeys-lru evicts cold keys, not hot keys
""")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redis cache load test and chaos scenario for yelp-system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cache_load_test.py load
  python scripts/cache_load_test.py load --rounds 10 --concurrency 20
  python scripts/cache_load_test.py chaos
  python scripts/cache_load_test.py stats
""",
    )
    sub = parser.add_subparsers(dest="cmd")

    load_cmd = sub.add_parser("load", help="Run concurrent load test and report cache hit-rate")
    load_cmd.add_argument("--concurrency", type=int, default=10, help="Parallel workers (default: 10)")
    load_cmd.add_argument("--rounds", type=int, default=3, help="How many times to iterate through SAMPLE_IDS (default: 3)")
    load_cmd.add_argument("--ids", nargs="*", help="Space-separated business IDs to use instead of built-in list")

    sub.add_parser("chaos", help="Print chaos test checklist (Redis kill & recovery)")
    sub.add_parser("stats", help="Print current cache stats from both services")

    args = parser.parse_args()

    if args.cmd == "load":
        ids = args.ids if args.ids else SAMPLE_IDS
        run_load_test(concurrency=args.concurrency, rounds=args.rounds, ids=ids)
    elif args.cmd == "chaos":
        run_chaos()
    elif args.cmd == "stats":
        print("\n[Current cache stats]")
        print_stats("business-service", pull_stats(BUSINESS_STATS_URL))
        print_stats("recommendation-service", pull_stats(RECOMMENDATION_STATS_URL))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
