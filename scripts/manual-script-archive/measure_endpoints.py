import requests
import time

urls = [
    'http://localhost:8001/businesses/cities',
    'http://127.0.0.1:8001/businesses/cities',
    'http://localhost:8000/api/businesses/cities',
    'http://127.0.0.1:8000/api/businesses/cities'
]

print(f"{'URL':<50} | {'Status':<6} | {'Elapsed (ms)':<12}")
print("-" * 75)

for url in urls:
    try:
        start_time = time.perf_counter()
        response = requests.get(url, timeout=10)
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        print(f"{url:<50} | {response.status_code:<6} | {elapsed_ms:>12.2f}")
    except Exception as e:
        print(f"{url:<50} | ERROR  | {str(e)}")
