from datetime import datetime

from pydantic import BaseModel

from apps.akaunting.models.accounts import Account
from apps.akaunting.models.common import CreatedFrom, Links, Meta


class Reconciliation(BaseModel):
    id: int  # noqa: A003, RUF100
    company_id: int
    account_id: int
    started_at: datetime
    ended_at: datetime
    closing_balance: float
    closing_balance_formatted: str
    reconciled: bool
    created_from: CreatedFrom
    created_by: int
    created_at: datetime
    updated_at: datetime
    account: Account


class ReconciliationsResponse(BaseModel):
    data: list[Reconciliation]
    links: Links
    meta: Meta


class SingleReconciliationResponse(BaseModel):
    data: Reconciliation
