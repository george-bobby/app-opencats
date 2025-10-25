from typing import Literal

from pydantic import BaseModel, Field


type CreatedFrom = Literal["core::api", "core::ui", "core::seed", "core::import"]


class LinkItem(BaseModel):
    url: str | None = None
    label: str
    active: bool


class Links(BaseModel):
    first: str
    last: str
    prev: str | None = None
    next: str | None = None  # noqa: A003, RUF100


class Meta(BaseModel):
    current_page: int
    from_: int | None = Field(alias="from")
    last_page: int
    links: list[LinkItem]
    path: str
    per_page: int
    to: int | None
    total: int
