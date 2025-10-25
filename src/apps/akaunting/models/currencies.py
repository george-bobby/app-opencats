from pydantic import BaseModel

from apps.akaunting.models.common import CreatedFrom


class Currency(BaseModel):
    id: int  # noqa: A003, RUF100
    name: str
    code: str
    rate: float
    precision: int
    symbol: str
    symbol_first: int
    decimal_mark: str
    thousands_separator: str
    enabled: int
    created_from: CreatedFrom | None


class CurrenciesResponse(BaseModel):
    data: list[Currency]
