"""Delete existing companies from OpenCATS."""

import asyncio
from typing import Any

from apps.opencats.config.constants import OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from common.logger import logger


async def delete_existing_companies() -> dict[str, Any]:
    """Delete all existing companies from OpenCATS."""
    logger.info("🗑️ Starting company deletion...")

    api_utils = OpenCATSAPIUtils()

    try:
        # Get all existing companies
        companies = await api_utils.get_all_items(OpenCATSEndpoint.COMPANIES)

        if not companies:
            logger.info("✅ No companies found to delete")
            return {"success": True, "deleted_count": 0}

        deleted_count = 0
        for company in companies:
            company_id = company.get("companyID")
            if company_id:
                success = await api_utils.delete_item(OpenCATSEndpoint.COMPANIES, company_id)
                if success:
                    deleted_count += 1
                    logger.info(f"🗑️ Deleted company: {company.get('name', '')} (ID: {company_id})")
                else:
                    logger.warning(f"⚠️ Failed to delete company ID: {company_id}")

        logger.info(f"✅ Company deletion completed. Deleted {deleted_count} companies")
        return {"success": True, "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"❌ Error during company deletion: {e!s}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    asyncio.run(delete_existing_companies())
