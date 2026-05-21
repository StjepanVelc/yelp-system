import requests
import time
import json

BASE_URL = 'http://localhost:8001'

def wait_for_health(url, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(2)
    return False

def get_stats():
    return requests.get(f'{BASE_URL}/cache/stats').json()

def test_endpoint(path):
    print(f'Testing {path}...')
    for i in range(2):
        start = time.time()
        r = requests.get(f'{BASE_URL}{path}')
        elapsed = (time.time() - start) * 1000
        print(f'  Call {i+1}: {r.status_code}, {elapsed:.2f}ms')

if wait_for_health(f'{BASE_URL}/health') and wait_for_health('http://localhost:8000/health'):
    print('Services are up.')
    stats_before = get_stats()
    print('Stats before:', json.dumps(stats_before))
    
    test_endpoint('/businesses/Pns2l4eNsfO8kk83dixA6A')
    test_endpoint('/businesses/cities')
    
    stats_after = get_stats()
    print('Stats after:', json.dumps(stats_after))
    
    hits_delta = stats_after.get('hits', 0) - stats_before.get('hits', 0)
    misses_delta = stats_after.get('misses', 0) - stats_before.get('misses', 0)
    print(f'Delta - Hits: {hits_delta}, Misses: {misses_delta}')
else:
    print('Services failed to become healthy.')
