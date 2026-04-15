from pydantic import BaseModel
from typing import Optional


class BusinessResponse(BaseModel):
    id: str
    name: Optional[str]
    city: Optional[str]
    state: Optional[str]
    stars: Optional[float]
    review_count: Optional[int]
    is_open: Optional[bool]
    categories: Optional[str]

    model_config = {"from_attributes": True}
