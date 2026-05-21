import asyncio
import aiohttp
import jwt
import time
import os

async def fetch(session, url, token):
    async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as response:
        return response.status

async def main():
    secret = "dev-secret-change-me"
    payload = {
        "iss": "yelp-auth",
        "aud": "yelp-api",
        "sub": "qVc8ODYU5SZjKXVBgXdI7w",
        "roles": ["business:read", "recommendation:read"],
        "exp": int(time.time()) + 1800
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    url = "http://localhost:8000/api/businesses/cities"
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url, token) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        print(f"Status codes: {results}")

if __name__ == "__main__":
    asyncio.run(main())
