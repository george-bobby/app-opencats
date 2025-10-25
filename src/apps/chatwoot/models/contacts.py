from typing import Any

from pydantic import BaseModel, Field


class SocialProfiles(BaseModel):
    facebook: str | None = None
    github: str | None = None
    instagram: str | None = None
    linkedin: str | None = None
    twitter: str | None = None


class AdditionalAttributes(BaseModel):
    description: str | None = None
    company_name: str | None = None
    country_code: str | None = None
    country: str | None = None
    city: str | None = None
    social_profiles: SocialProfiles | None = None


class ContactInbox(BaseModel):
    inbox: Any | None = None
    source_id: str | None = None


class Contact(BaseModel):
    additional_attributes: AdditionalAttributes | None = None
    availability_status: str = "offline"
    email: str | None = None
    id: int  # noqa: A003, RUF100
    name: str
    phone_number: str | None = None
    blocked: bool = False
    identifier: str | None = None
    thumbnail: str = ""
    custom_attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: int
    contact_inboxes: list = Field(default_factory=list)


class ContactPayload(BaseModel):
    contact: Contact
    contact_inbox: ContactInbox
