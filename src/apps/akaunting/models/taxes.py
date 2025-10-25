from pydantic import BaseModel

from apps.akaunting.models.common import CreatedFrom, Links, Meta


class Tax(BaseModel):
    id: int | None = None  # noqa: A003, RUF100
    company_id: int | None = None
    name: str
    rate: float
    enabled: bool | None = None
    created_from: CreatedFrom | None = None
    created_by: int | None = None
    created_at: str | None = ""
    updated_at: str | None = ""


class TaxesResponse(BaseModel):
    data: list[Tax]
    links: Links
    meta: Meta
