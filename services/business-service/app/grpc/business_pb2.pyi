from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetBusinessRequest(_message.Message):
    __slots__ = ("business_id",)
    BUSINESS_ID_FIELD_NUMBER: _ClassVar[int]
    business_id: str
    def __init__(self, business_id: _Optional[str] = ...) -> None: ...

class ListBusinessesRequest(_message.Message):
    __slots__ = ("city", "min_stars", "page", "limit", "state", "search_query")
    CITY_FIELD_NUMBER: _ClassVar[int]
    MIN_STARS_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SEARCH_QUERY_FIELD_NUMBER: _ClassVar[int]
    city: str
    min_stars: float
    page: int
    limit: int
    state: str
    search_query: str
    def __init__(self, city: _Optional[str] = ..., min_stars: _Optional[float] = ..., page: _Optional[int] = ..., limit: _Optional[int] = ..., state: _Optional[str] = ..., search_query: _Optional[str] = ...) -> None: ...

class BusinessResponse(_message.Message):
    __slots__ = ("id", "name", "city", "state", "stars", "review_count", "is_open", "categories", "latitude", "longitude", "address", "postal_code")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STARS_FIELD_NUMBER: _ClassVar[int]
    REVIEW_COUNT_FIELD_NUMBER: _ClassVar[int]
    IS_OPEN_FIELD_NUMBER: _ClassVar[int]
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    POSTAL_CODE_FIELD_NUMBER: _ClassVar[int]
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
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., city: _Optional[str] = ..., state: _Optional[str] = ..., stars: _Optional[float] = ..., review_count: _Optional[int] = ..., is_open: bool = ..., categories: _Optional[str] = ..., latitude: _Optional[float] = ..., longitude: _Optional[float] = ..., address: _Optional[str] = ..., postal_code: _Optional[str] = ...) -> None: ...

class ListBusinessesResponse(_message.Message):
    __slots__ = ("businesses",)
    BUSINESSES_FIELD_NUMBER: _ClassVar[int]
    businesses: _containers.RepeatedCompositeFieldContainer[BusinessResponse]
    def __init__(self, businesses: _Optional[_Iterable[_Union[BusinessResponse, _Mapping]]] = ...) -> None: ...
