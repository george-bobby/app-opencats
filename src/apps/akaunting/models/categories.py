from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from apps.akaunting.models.common import CreatedFrom, Links, Meta


type CategoryType = Literal["income", "expense", "item", "other"]


class Category(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    name: str
    type: CategoryType | str  # noqa: A003, RUF100
    color: str
    enabled: bool
    parent_id: int | None = None
    created_from: CreatedFrom
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class CategoriesResponse(BaseModel):
    data: list[Category]
    links: Links
    meta: Meta


class SingleCategoryResponse(BaseModel):
    data: Category
