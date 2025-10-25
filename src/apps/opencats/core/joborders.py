"""Seed job orders data into OpenCATS."""

import asyncio
from typing import Any

from apps.opencats.config.constants import JOBORDERS_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


async def seed_joborders() -> dict[str, Any]:
    """Seed job orders data into OpenCATS."""
    logger.info("💼 Starting job order seeding...")

    # Load generated job orders data
    joborders_data = load_existing_data(JOBORDERS_FILEPATH)

    if not joborders_data:
        logger.warning("⚠️ No job orders data found. Run generation first.")
        return {"seeded_joborders": 0, "errors": 0}

    logger.info(f"📊 Found {len(joborders_data)} job orders to seed")

    seeded_count = 0
    error_count = 0
    seeded_joborders = []

    async with OpenCATSAPIUtils() as api:
        for idx, joborder in enumerate(joborders_data):
            joborder_title = joborder.get("title", "Unknown")
            logger.info(f"🔄 Seeding job order {idx + 1}/{len(joborders_data)}: {joborder_title}")

            try:
                # Prepare form data for OpenCATS
                form_data = prepare_joborder_form_data(joborder)

                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.JOBORDERS_ADD.value, form_data)

                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Job order '{joborder_title}' seeded successfully (ID: {entity_id})")
                        seeded_joborders.append({"original_data": joborder, "opencats_id": entity_id, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Job order '{joborder_title}' may have been created but ID not found")
                        seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed job order '{joborder_title}': {result}")
                    seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding job order '{joborder_title}': {e!s}")
                seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Job order seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_joborders": seeded_count, "errors": error_count, "details": seeded_joborders}


def prepare_joborder_form_data(joborder: dict[str, Any]) -> dict[str, str]:
    """Prepare job order data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "companyID": str(joborder.get("companyID", "")),
        "recruiter": str(joborder.get("recruiter", "")),
        "owner": str(joborder.get("owner", "")),
        "openings": str(joborder.get("openings", "")),
        "title": joborder.get("title", ""),
        "companyJobID": joborder.get("companyJobID", ""),
        "type": joborder.get("type", ""),
        "city": joborder.get("city", ""),
        "state": joborder.get("state", ""),
        "duration": joborder.get("duration", ""),
        "department": joborder.get("department", ""),
        "maxRate": joborder.get("maxRate", ""),
        "salary": joborder.get("salary", ""),
        "description": joborder.get("description", ""),
        "notes": joborder.get("notes", ""),
        "startDate": joborder.get("startDate", ""),
        "questionnaire": joborder.get("questionnaire", "none"),
    }

    # Handle contactID (optional)
    if joborder.get("contactID"):
        form_data["contactID"] = str(joborder.get("contactID"))

    # Handle checkboxes
    if joborder.get("isHot"):
        form_data["isHot"] = "1"

    if joborder.get("public"):
        form_data["public"] = "1"

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data
