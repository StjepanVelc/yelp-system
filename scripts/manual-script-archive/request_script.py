import requests
import time

urls = [
    'http://localhost:8001/businesses/cities',
    'http://localhost:8001/businesses/Pns2l4eNsfO8kk83dixA6A'
]

for i in range(2):
    print(f'Round {i+1}:')
    for url in urls:
        start = time.time()
        try:
            r = requests.get(url, timeout=10)
            elapsed = (time.time() - start) * 1000
            print(f'  GET {url} - Status: {r.status_code} - Elapsed: {elapsed:.2f}ms')
        except Exception as e:
            print(f'  GET {url} - Error: {e}')
