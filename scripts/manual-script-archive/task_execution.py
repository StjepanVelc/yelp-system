import requests
import time
import json

def get_stats():
    r = requests.get("http://localhost:8001/cache/stats")
    data = r.json()
    return data

# 1) GET cache stats (pre)
pre_stats = get_stats()
bd_pre = pre_stats.get("business.details", {"hits": 0, "misses": 0})
bc_pre = pre_stats.get("business.cities", {"hits": 0, "misses": 0})
print(f"Initial - business.details: (hits={bd_pre['hits']}, misses={bd_pre['misses']})")
print(f"Initial - business.cities: (hits={bc_pre['hits']}, misses={bc_pre['misses']})")

# 2) Health checks
h1 = requests.get("http://localhost:8001/health")
h2 = requests.get("http://localhost:8000/health")
print(f"Health 8001: {h1.status_code} {h1.json().get('status')}")
print(f"Health 8000: {h2.status_code} {h2.json().get('status')}")

# 3) Sequential GET requests
def timed_get(url):
    start = time.time()
    r = requests.get(url)
    elapsed = (time.time() - start) * 1000
    return r.status_code, elapsed

s1, e1 = timed_get("http://localhost:8001/businesses/Pns2l4eNsfO8kk83dixA6A")
print(f"GET /businesses/Pns2l4eNsfO8kk83dixA6A: {s1} {e1:.2f}ms")

s2, e2 = timed_get("http://localhost:8001/businesses/cities")
print(f"GET /businesses/cities: {s2} {e2:.2f}ms")

# 4) GET cache stats (post)
post_stats = get_stats()
bd_post = post_stats.get("business.details", {"hits": 0, "misses": 0})
bc_post = post_stats.get("business.cities", {"hits": 0, "misses": 0})

bd_h_delta = bd_post['hits'] - bd_pre['hits']
bd_m_delta = bd_post['misses'] - bd_pre['misses']
bc_h_delta = bc_post['hits'] - bc_pre['hits']
bc_m_delta = bc_post['misses'] - bc_pre['misses']

print(f"Delta - business.details: hits={bd_h_delta}, misses={bd_m_delta}")
print(f"Delta - business.cities: hits={bc_h_delta}, misses={bc_m_delta}")
