"""Seed companies data into OpenCATS."""

import asyncio
from typing import Any

from apps.opencats.config.constants import COMPANIES_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


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
