from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from apps.akaunting.models.accounts import Account
from apps.akaunting.models.categories import Category
from apps.akaunting.models.common import Links, Meta
from apps.akaunting.models.contacts import Contact
from apps.akaunting.models.currencies import Currency


class ContactPersons(BaseModel):
    data: list = []


class Taxes(BaseModel):
    data: list = []


class Transaction(BaseModel):
    id: int  # noqa: A003, RUF100
    number: str
    company_id: int
    type: Literal["income", "expense", "income-transfer", "expense-transfer"]  # noqa: A003, RUF100
    account_id: int
    paid_at: datetime
    amount: float
    amount_formatted: str
    currency_code: str
    currency_rate: float
    document_id: int | None = None
    contact_id: int
    description: str | None = None
    category_id: int
    payment_method: str
    reference: str | None = None
    parent_id: int
    split_id: int | None = None
    attachment: bool
    created_from: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    account: Account
    category: Category
    currency: Currency
    contact: Contact
    taxes: Taxes


class TransactionsResponse(BaseModel):
    data: list[Transaction]
    links: Links
    meta: Meta
