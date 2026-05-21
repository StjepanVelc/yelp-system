import requests
import time

base_url = "http://localhost:8001"

def test_endpoint(endpoint):
    start = time.time()
    try:
        response = requests.get(f"{base_url}{endpoint}")
        elapsed = (time.time() - start) * 1000
        status = response.status_code
        body = response.text[:120] if status == 200 else ""
        print(f"Endpoint: {endpoint} | Status: {status} | Time: {elapsed:.2f}ms")
        if body:
            print(f"  Body: {body}...")
    except Exception as e:
        print(f"Endpoint: {endpoint} | Error: {e}")

def get_stats():
    try:
        res = requests.get(f"{base_url}/cache/stats")
        print(f"Cache Stats: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Cache Stats Error: {e}")

print("Pre-test stats:")
get_stats()

endpoints = ["/businesses/Pns2l4eNsfO8kk83dixA6A", "/businesses/cities"]
for ep in endpoints:
    for _ in range(2):
        test_endpoint(ep)

print("\nPost-test stats:")
get_stats()
