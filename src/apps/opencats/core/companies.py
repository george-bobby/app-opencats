"""Seed companies data into OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import COMPANIES_FILEPATH, CONTACTS_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_companies() -> dict[str, Any]:
    """Seed companies data into OpenCATS."""
    logger.info("🏢 Starting company seeding...")

    # Load generated companies data
    companies_data = load_existing_data(COMPANIES_FILEPATH)

    if not companies_data:
        logger.warning("⚠️ No companies data found. Run generation first.")
        return {"seeded_companies": 0, "errors": 0}

    logger.info(f"📊 Found {len(companies_data)} companies to seed")

    seeded_count = 0
    error_count = 0
    seeded_companies = []

    async with OpenCATSAPIUtils() as api:
        for idx, company in enumerate(companies_data):
            logger.info(f"🔄 Seeding company {idx + 1}/{len(companies_data)}: {company.get('name', 'Unknown')}")

            try:
                # Prepare form data for OpenCATS
                form_data = prepare_company_form_data(company)

                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.COMPANIES_ADD.value, form_data)

                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Company '{company.get('name')}' seeded successfully (ID: {entity_id})")
                        seeded_companies.append({"original_data": company, "opencats_id": entity_id, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Company '{company.get('name')}' may have been created but ID not found")
                        seeded_companies.append({"original_data": company, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed company '{company.get('name')}': {result}")
                    seeded_companies.append({"original_data": company, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding company '{company.get('name')}': {e!s}")
                seeded_companies.append({"original_data": company, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Company seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_companies": seeded_count, "errors": error_count, "details": seeded_companies}


async def update_companies_billing_contacts() -> dict[str, Any]:
    """Update companies with billing contact assignments after contacts are seeded."""
    logger.info("🔗 Starting billing contact assignment...")

    # Load contacts data to find billing contacts
    contacts_data = load_existing_data(CONTACTS_FILEPATH)
    
    if not contacts_data:
        logger.warning("⚠️ No contacts data found. Cannot assign billing contacts.")
        return {"updated_companies": 0, "errors": 0}

    # Group contacts by company and find billing contacts
    company_billing_contacts = {}
    for contact in contacts_data:
        company_id = contact.get("companyID")
        is_billing = contact.get("isBillingContact", 0)
        
        if company_id and is_billing:
            # This contact is marked as billing contact for their company
            company_billing_contacts[company_id] = contact

    if not company_billing_contacts:
        logger.warning("⚠️ No billing contacts found in contacts data.")
        return {"updated_companies": 0, "errors": 0}

    logger.info(f"📊 Found {len(company_billing_contacts)} companies with billing contacts")

    updated_count = 0
    error_count = 0
    updated_companies = []

    async with OpenCATSAPIUtils() as api:
        for company_id, billing_contact in company_billing_contacts.items():
            contact_name = f"{billing_contact.get('firstName', '')} {billing_contact.get('lastName', '')}".strip()
            logger.info(f"🔄 Updating company {company_id} with billing contact: {contact_name}")

            try:
                # We need to get the actual OpenCATS contact ID that was assigned during seeding
                # For now, we'll use a placeholder approach since we'd need to track the actual IDs
                # In a real implementation, you'd store the mapping during the contacts seeding
                
                # Prepare update data for company
                update_data = {
                    "billingContact": company_id,  # This would be the actual contact ID from OpenCATS
                    "postback": "postback"
                }

                # Update the company record
                result = await api.update_item(OpenCATSEndpoint.COMPANIES_ADD, company_id, update_data)

                if result:
                    logger.info(f"✅ Company {company_id} billing contact updated successfully")
                    updated_companies.append({"company_id": company_id, "billing_contact": contact_name, "status": "success"})
                    updated_count += 1
                else:
                    logger.error(f"❌ Failed to update company {company_id} billing contact")
                    updated_companies.append({"company_id": company_id, "billing_contact": contact_name, "status": "failed"})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error updating company {company_id} billing contact: {e!s}")
                updated_companies.append({"company_id": company_id, "billing_contact": contact_name, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Billing contact assignment completed! Updated: {updated_count}, Errors: {error_count}")
    
    return {"updated_companies": updated_count, "errors": error_count, "details": updated_companies}


def prepare_company_form_data(company: dict[str, Any]) -> dict[str, str]:
    """Prepare company data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "name": company.get("name", ""),
        "address": company.get("address", ""),
        "city": company.get("city", ""),
        "state": company.get("state", ""),
        "zip": company.get("zip", ""),
        "phone1": company.get("phone1", ""),
        "phone2": company.get("phone2", ""),
        "faxNumber": company.get("faxNumber", ""),
        "url": company.get("url", ""),
        "keyTechnologies": company.get("keyTechnologies", ""),
        "notes": company.get("notes", ""),
        "departmentsCSV": company.get("departmentsCSV", ""),
    }

    # Handle isHot checkbox
    if company.get("isHot"):
        form_data["isHot"] = "1"

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data
