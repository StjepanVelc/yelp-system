from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ReviewMessage(_message.Message):
    __slots__ = ("review_id", "user_id", "business_id", "stars", "useful", "funny", "cool", "text", "date")
    REVIEW_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    BUSINESS_ID_FIELD_NUMBER: _ClassVar[int]
    STARS_FIELD_NUMBER: _ClassVar[int]
    USEFUL_FIELD_NUMBER: _ClassVar[int]
    FUNNY_FIELD_NUMBER: _ClassVar[int]
    COOL_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    review_id: str
    user_id: str
    business_id: str
    stars: float
    useful: int
    funny: int
    cool: int
    text: str
    date: str
    def __init__(self, review_id: _Optional[str] = ..., user_id: _Optional[str] = ..., business_id: _Optional[str] = ..., stars: _Optional[float] = ..., useful: _Optional[int] = ..., funny: _Optional[int] = ..., cool: _Optional[int] = ..., text: _Optional[str] = ..., date: _Optional[str] = ...) -> None: ...

class UserMessage(_message.Message):
    __slots__ = ("user_id", "name", "review_count", "yelping_since", "fans", "average_stars")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    REVIEW_COUNT_FIELD_NUMBER: _ClassVar[int]
    YELPING_SINCE_FIELD_NUMBER: _ClassVar[int]
    FANS_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_STARS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    name: str
    review_count: int
    yelping_since: str
    fans: int
    average_stars: float
    def __init__(self, user_id: _Optional[str] = ..., name: _Optional[str] = ..., review_count: _Optional[int] = ..., yelping_since: _Optional[str] = ..., fans: _Optional[int] = ..., average_stars: _Optional[float] = ...) -> None: ...

class TipMessage(_message.Message):
    __slots__ = ("user_id", "business_id", "text", "date", "compliment_count")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    BUSINESS_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    COMPLIMENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    business_id: str
    text: str
    date: str
    compliment_count: int
    def __init__(self, user_id: _Optional[str] = ..., business_id: _Optional[str] = ..., text: _Optional[str] = ..., date: _Optional[str] = ..., compliment_count: _Optional[int] = ...) -> None: ...

class CheckinMessage(_message.Message):
    __slots__ = ("business_id", "date")
    BUSINESS_ID_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    business_id: str
    date: str
    def __init__(self, business_id: _Optional[str] = ..., date: _Optional[str] = ...) -> None: ...
