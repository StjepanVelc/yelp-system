from google.protobuf.message import Message
from typing import Iterable

class GetBusinessRequest(Message):
    business_id: str
    def __init__(self, *, business_id: str = ...) -> None: ...

class ListBusinessesRequest(Message):
    city: str
    min_stars: float
    page: int
    limit: int
    def __init__(self, *, city: str = ..., min_stars: float = ..., page: int = ..., limit: int = ...) -> None: ...

class BusinessResponse(Message):
    id: str
    name: str
    city: str
    state: str
    stars: float
    review_count: int
    is_open: bool
    categories: str
    latitude: float
    longitude: float
    address: str
    postal_code: str
    def __init__(
        self,
        *,
        id: str = ...,
        name: str = ...,
        city: str = ...,
        state: str = ...,
        stars: float = ...,
        review_count: int = ...,
        is_open: bool = ...,
        categories: str = ...,
        latitude: float = ...,
        longitude: float = ...,
        address: str = ...,
        postal_code: str = ...,
    ) -> None: ...

class ListBusinessesResponse(Message):
    businesses: list[BusinessResponse]
    def __init__(self, *, businesses: Iterable[BusinessResponse] = ...) -> None: ...
