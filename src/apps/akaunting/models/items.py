from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from apps.akaunting.models.common import CreatedFrom, Links, Meta
from apps.akaunting.models.taxes import Tax


ItemType = Literal["product", "service"]


class ItemCategory(BaseModel):
    id: int | None  # noqa: A003, RUF100
    company_id: int | None
    name: str
    type: str | None  # noqa: A003, RUF100
    color: str | None
    enabled: bool | None
    parent_id: int | None
    created_from: str | None
    created_by: int | None
    created_at: str
    updated_at: str


class ItemTaxRelation(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    item_id: int
    tax_id: int
    created_from: CreatedFrom
    created_by: int
    created_at: datetime
    updated_at: datetime
    tax: Tax | None


class ItemTaxes(BaseModel):
    data: list[ItemTaxRelation] = []


class Item(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    type: ItemType  # noqa: A003, RUF100
    name: str
    description: str | None
    sale_price: float
    sale_price_formatted: str
    purchase_price: float | None
    purchase_price_formatted: str
    category_id: int | None
    picture: bool
    enabled: bool
    created_from: CreatedFrom
    created_by: int
    created_at: datetime
    updated_at: datetime
    taxes: ItemTaxes
    category: ItemCategory


class ItemResponse(BaseModel):
    data: Item


class ListItemsResponse(BaseModel):
    data: list[Item]
    links: Links
    meta: Meta
