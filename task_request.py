import time
import jwt
import requests
from datetime import datetime, timedelta

secret = "dev-secret-change-me"
payload = {
    "iss": "yelp-auth",
    "aud": "yelp-api",
    "sub": "qVc8ODYU5SZjKXVBgXdI7w",
    "roles": ["business:read", "recommendation:read"],
    "exp": datetime.utcnow() + timedelta(minutes=30)
}
token = jwt.encode(payload, secret, algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}

urls = [
    "http://127.0.0.1:8001/businesses/cities",
    "http://127.0.0.1:8001/businesses/Pns2l4eNsfO8kk83dixA6A",
    "http://127.0.0.1:8000/api/businesses/cities",
    "http://127.0.0.1:8000/api/businesses/Pns2l4eNsfO8kk83dixA6A"
]

for url in urls:
    try:
        start = time.time()
        r = requests.get(url, headers=headers, timeout=5)
        elapsed = (time.time() - start) * 1000
        print(f"{url}: {r.status_code} {elapsed:.2f}ms")
    except Exception as e:
        print(f"{url}: Error {e}")
