from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from apps.akaunting.models.common import Links, Meta


type ContactType = Literal["customer", "vendor"]


class ContactPerson(BaseModel):
    data: list = Field(default_factory=list)


class Contact(BaseModel):
    id: int | None = None  # noqa: A003, RUF100
    company_id: int | None = None
    user_id: int | None = None
    type: str | None = None  # noqa: A003, RUF100
    name: str | None = None
    email: str | None = None
    tax_number: str | None = None
    phone: str | None = None
    address: str | None = None
    website: str | None = None
    currency_code: str | None = None
    enabled: bool | None = None
    reference: str | None = None
    created_from: str | None = None
    created_by: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    contact_persons: ContactPerson | None = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str) -> datetime | None:
        if v == "":
            return None
        return v


class ContactsResponse(BaseModel):
    data: list[Contact]
    links: Links
    meta: Meta


class SingleContactResponse(BaseModel):
    data: Contact
