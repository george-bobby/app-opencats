from datetime import datetime

from pydantic import BaseModel

from apps.akaunting.models.common import Links, Meta


class Transfer(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    from_account: str
    from_account_id: int
    to_account: str
    to_account_id: int
    amount: float
    amount_formatted: str
    currency_code: str
    paid_at: datetime
    created_from: str
    created_by: int
    created_at: datetime
    updated_at: datetime


class TransfersResponse(BaseModel):
    data: list[Transfer]
    links: Links
    meta: Meta


class SingleTransferResponse(BaseModel):
    data: Transfer
