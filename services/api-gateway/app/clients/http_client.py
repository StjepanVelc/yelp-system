import httpx

_shared_client: httpx.AsyncClient | None = None


def get_shared_client() -> httpx.AsyncClient:
    global _shared_client

    if _shared_client is None:
        _shared_client = httpx.AsyncClient()

    return _shared_client


async def close_shared_client() -> None:
    global _shared_client

    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None