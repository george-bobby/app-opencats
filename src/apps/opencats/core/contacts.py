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
                # Note: reportsTo will be set in a separate pass after all contacts are seeded
                form_data = prepare_contact_form_data(contact, skip_reports_to=True)

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


async def update_contacts_reports_to() -> dict[str, Any]:
    """Update contacts with proper reporting hierarchy after all contacts are seeded.
    
    Rules:
    - Billing contacts should NOT have a reports_to value (they are at the top)
    - Other contacts at the same company should report to the billing contact
    """
    logger.info("🔗 Starting reports_to relationship setup...")

    # Load contacts data
    contacts_data = load_existing_data(CONTACTS_FILEPATH)
    
    if not contacts_data:
        logger.warning("⚠️ No contacts data found. Cannot set up reporting relationships.")
        return {"updated_contacts": 0, "errors": 0}

    # Group contacts by company and identify billing contacts
    contacts_by_company = {}
    billing_contacts_by_company = {}
    
    for contact in contacts_data:
        company_id = contact.get("companyID")
        is_billing = contact.get("isBillingContact", 0)
        contact_name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        
        if company_id:
            if company_id not in contacts_by_company:
                contacts_by_company[company_id] = []
            contacts_by_company[company_id].append(contact)
            
            if is_billing:
                billing_contacts_by_company[company_id] = contact_name

    logger.info(f"📊 Found {len(contacts_by_company)} companies with contacts")
    logger.info(f"📊 Found {len(billing_contacts_by_company)} companies with billing contacts")

    updated_count = 0
    error_count = 0
    updated_contacts = []

    async with OpenCATSAPIUtils() as api:
        # Get all seeded contacts from OpenCATS to get their actual IDs
        logger.info("📊 Fetching seeded contacts from OpenCATS...")
        seeded_contacts = await api.get_all_items("contacts")
        
        if not seeded_contacts:
            logger.error("❌ Could not retrieve contacts from OpenCATS")
            return {"updated_contacts": 0, "errors": 1}

        # Create a mapping of contact names and company IDs to actual OpenCATS contact IDs
        contact_lookup = {}
        for contact in seeded_contacts:
            contact_name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
            company_id = contact.get("companyID")
            key = (contact_name, company_id)
            contact_lookup[key] = contact.get("contactID")

        # Now process each company's contacts
        for company_id, contacts in contacts_by_company.items():
            billing_contact_name = billing_contacts_by_company.get(company_id)
            
            if not billing_contact_name:
                logger.info(f"ℹ️ Company ID {company_id} has no billing contact, skipping reports_to setup")
                continue
            
            # Get all seeded contacts for this company from OpenCATS
            # We need the actual OpenCATS company ID
            from apps.opencats.config.constants import COMPANIES_FILEPATH
            companies_list = load_existing_data(COMPANIES_FILEPATH)
            
            if company_id <= len(companies_list):
                company_name = companies_list[company_id - 1].get("name")
                
                # Get actual OpenCATS company ID
                seeded_companies = await api.get_all_items("companies")
                actual_company_id = None
                for company in seeded_companies:
                    if company.get("name", "").strip() == company_name:
                        actual_company_id = company.get("companyID")
                        break
                
                if not actual_company_id:
                    logger.warning(f"⚠️ Could not find OpenCATS company ID for: {company_name}")
                    continue
                
                # Find billing contact's actual ID
                billing_contact_key = (billing_contact_name, actual_company_id)
                billing_contact_id = contact_lookup.get(billing_contact_key)
                
                if not billing_contact_id:
                    logger.warning(f"⚠️ Could not find billing contact ID for: {billing_contact_name}")
                    continue
                
                logger.info(f"ℹ️ Processing company '{company_name}' (ID: {actual_company_id})")
                logger.info(f"ℹ️ Billing contact: {billing_contact_name} (ID: {billing_contact_id})")
                
                # Process each contact in this company
                for contact in contacts:
                    contact_name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
                    is_billing = contact.get("isBillingContact", 0)
                    
                    # Find this contact's actual OpenCATS ID
                    contact_key = (contact_name, actual_company_id)
                    actual_contact_id = contact_lookup.get(contact_key)
                    
                    if not actual_contact_id:
                        logger.warning(f"⚠️ Could not find contact ID for: {contact_name}")
                        continue
                    
                    try:
                        if is_billing:
                            # Billing contact should NOT have a reports_to value
                            logger.info(f"🔄 Clearing reports_to for billing contact: {contact_name} (ID: {actual_contact_id})")
                            update_data = {
                                "reportsTo": "",  # Clear reports_to
                                "postback": "postback"
                            }
                        else:
                            # Non-billing contact should report to the billing contact
                            logger.info(f"🔄 Setting {contact_name} (ID: {actual_contact_id}) to report to billing contact {billing_contact_name} (ID: {billing_contact_id})")
                            update_data = {
                                "reportsTo": str(billing_contact_id),
                                "postback": "postback"
                            }
                        
                        # Update the contact record
                        from apps.opencats.config.constants import OpenCATSEndpoint
                        result = await api.update_item(OpenCATSEndpoint.CONTACTS_ADD, actual_contact_id, update_data)
                        
                        if result:
                            logger.info(f"✅ Updated contact {actual_contact_id} reports_to relationship")
                            updated_contacts.append({
                                "contact_id": actual_contact_id,
                                "contact_name": contact_name,
                                "company_id": actual_company_id,
                                "reports_to": billing_contact_id if not is_billing else None,
                                "is_billing": is_billing,
                                "status": "success"
                            })
                            updated_count += 1
                        else:
                            logger.error(f"❌ Failed to update contact {actual_contact_id} reports_to")
                            error_count += 1
                    
                    except Exception as e:
                        logger.error(f"❌ Error updating contact {contact_name} reports_to: {e!s}")
                        error_count += 1
                    
                    # Small delay between requests
                    await asyncio.sleep(0.3)

    logger.succeed(f"✅ Reports_to relationship setup completed! Updated: {updated_count}, Errors: {error_count}")
    
    return {"updated_contacts": updated_count, "errors": error_count, "details": updated_contacts}


def prepare_contact_form_data(contact: dict[str, Any], skip_reports_to: bool = False) -> dict[str, str]:
    """Prepare contact data for OpenCATS form submission.
    
    Args:
        contact: Contact data dictionary
        skip_reports_to: If True, don't include reportsTo field (for initial seeding)
    """
    form_data = {
        "postback": "postback",
        "companyID": str(contact.get("companyID", "")),
        "firstName": contact.get("firstName", ""),
        "lastName": contact.get("lastName", ""),
        "title": contact.get("title", ""),
        "department": contact.get("department", ""),
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
    
    # Only include reportsTo if not skipping (for updates after all contacts are seeded)
    if not skip_reports_to:
        form_data["reportsTo"] = contact.get("reportsTo", "")

    # Handle isHot checkbox
    if contact.get("isHot"):
        form_data["isHot"] = "1"

    # Note: isBillingContact is handled separately in post-processing
    # since it requires updating the company record after the contact is created

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data
