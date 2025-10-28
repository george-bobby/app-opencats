"""Seed contacts data into OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import CONTACTS_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_contacts() -> dict[str, Any]:
    """Seed contacts data into OpenCATS."""
    logger.info("👥 Starting contact seeding...")

    # Load generated contacts data
    contacts_data = load_existing_data(CONTACTS_FILEPATH)

    if not contacts_data:
        logger.warning("⚠️ No contacts data found. Run generation first.")
        return {"seeded_contacts": 0, "errors": 0}

    logger.info(f"📊 Found {len(contacts_data)} contacts to seed")

    seeded_count = 0
    error_count = 0
    seeded_contacts = []

    async with OpenCATSAPIUtils() as api:
        for idx, contact in enumerate(contacts_data):
            contact_name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
            logger.info(f"🔄 Seeding contact {idx + 1}/{len(contacts_data)}: {contact_name}")

            try:
                # Prepare form data for OpenCATS
                form_data = prepare_contact_form_data(contact)

                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.CONTACTS_ADD.value, form_data)

                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Contact '{contact_name}' seeded successfully (ID: {entity_id})")
                        seeded_contacts.append({"original_data": contact, "opencats_id": entity_id, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Contact '{contact_name}' may have been created but ID not found")
                        seeded_contacts.append({"original_data": contact, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed contact '{contact_name}': {result}")
                    seeded_contacts.append({"original_data": contact, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding contact '{contact_name}': {e!s}")
                seeded_contacts.append({"original_data": contact, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Contact seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_contacts": seeded_count, "errors": error_count, "details": seeded_contacts}


def prepare_contact_form_data(contact: dict[str, Any]) -> dict[str, str]:
    """Prepare contact data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "companyID": str(contact.get("companyID", "")),
        "firstName": contact.get("firstName", ""),
        "lastName": contact.get("lastName", ""),
        "title": contact.get("title", ""),
        "department": contact.get("department", ""),
        "reportsTo": contact.get("reportsTo", ""),
        "email1": contact.get("email1", ""),
        "email2": contact.get("email2", ""),
        "phoneWork": contact.get("phoneWork", ""),
        "phoneCell": contact.get("phoneCell", ""),
        "phoneOther": contact.get("phoneOther", ""),
        "address": contact.get("address", ""),
        "city": contact.get("city", ""),
        "state": contact.get("state", ""),
        "zip": contact.get("zip", ""),
        "notes": contact.get("notes", ""),
        "departmentsCSV": contact.get("departmentsCSV", ""),
    }

    # Handle isHot checkbox
    if contact.get("isHot"):
        form_data["isHot"] = "1"

    # Note: isBillingContact is handled separately in post-processing
    # since it requires updating the company record after the contact is created

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data
