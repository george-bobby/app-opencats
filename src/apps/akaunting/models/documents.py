from typing import Literal

from pydantic import BaseModel

from apps.akaunting.models.common import Links, Meta


type DocumentType = Literal["invoice", "bill"]


class DocumentItem(BaseModel):
    item_id: int
    name: str
    quantity: float
    price: float
    total: float
    discount: float = 0
    description: str | None = None
    tax_ids: list[int] | None = None


class Document(BaseModel):
    id: int  # noqa: A003, RUF100
    type: str  # noqa: A003, RUF100
    document_number: str
    status: str
    issued_at: str
    due_at: str
    amount: float
    amount_formatted: str
    category_id: int
    currency_code: str
    currency_rate: float
    contact_id: int
    contact_name: str
    contact_email: str
    contact_tax_number: str | None = None
    contact_phone: str | None = None
    contact_address: str | None = None
    notes: str | None = None
    created_from: str
    created_by: int
    created_at: str
    updated_at: str


class ListDocumentsResponse(BaseModel):
    data: list[Document]
    meta: Meta | None = None
    links: Links | None = None


class SingleDocumentResponse(BaseModel):
    data: Document
