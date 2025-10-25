from datetime import datetime

from pydantic import BaseModel

from apps.akaunting.models.common import CreatedFrom, Links, Meta


class Account(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    name: str
    number: str
    currency_code: str
    opening_balance: float
    opening_balance_formatted: str
    current_balance: float
    current_balance_formatted: str
    bank_name: str | None = None
    bank_phone: str | None = None
    bank_address: str | None = None
    enabled: bool
    type: str  # noqa: A003, RUF100
    created_from: CreatedFrom
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class AccountsResponse(BaseModel):
    data: list[Account]
    links: Links
    meta: Meta


class SingleAccountResponse(BaseModel):
    data: Account
