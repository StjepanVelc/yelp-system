import requests
import time
import statistics
import os

endpoints = [
    "http://localhost:8000/businesses/Pns2l4eNsfO8kk83dixA6A",
    "http://localhost:8000/businesses/cities",
    "http://localhost:8000/recommendations/Pns2l4eNsfO8kk83dixA6A?limit=5"
]

health_ports = [8000, 8001, 8002, 8003]

token = os.getenv("BENCHMARK_BEARER_TOKEN", "").strip()
headers = {"Authorization": f"Bearer {token}"} if token else {}

print("--- Health Checks ---")
for port in health_ports:
    url = f"http://localhost:{port}/health"
    try:
        resp = requests.get(url, timeout=2)
        print(f"Port {port}: {resp.status_code}")
    except Exception as e:
        print(f"Port {port}: Reachable=False")

print("\n--- Latency Benchmark (ms) ---")
for url in endpoints:
    times = []
    status_counts = {}
    for _ in range(10):
        try:
            start = time.perf_counter()
            resp = requests.get(url, timeout=10, headers=headers)
            end = time.perf_counter()
            status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1
            if resp.status_code == 200:
                times.append((end - start) * 1000)
        except Exception:
            pass
    
    if times:
        avg = statistics.mean(times)
        p50 = statistics.median(times)
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times_sorted) * 0.95)] if len(times_sorted) >= 1 else 0
        print(f"URL: {url}")
        print(f"  Avg: {avg:.2f}, p50: {p50:.2f}, p95: {p95:.2f}")
    else:
        print(f"URL: {url} - Failed to collect data")
        if status_counts:
            print(f"  Status codes: {status_counts}")
            if status_counts.get(401) or status_counts.get(403):
                print("  Hint: endpoint is protected. Set BENCHMARK_BEARER_TOKEN and rerun.")

if not token:
    print("\nInfo: BENCHMARK_BEARER_TOKEN is not set.")
    print("For protected gateway routes, export a valid JWT token before running benchmark.")
