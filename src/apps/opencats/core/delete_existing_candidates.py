"""Delete existing candidates from OpenCATS."""

import asyncio
from typing import Any

from apps.opencats.config.constants import OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from common.logger import logger


async def delete_existing_candidates() -> dict[str, Any]:
    """Delete all existing candidates from OpenCATS."""
    logger.info("🗑️ Starting candidate deletion...")

    api_utils = OpenCATSAPIUtils()

    try:
        # Get all existing candidates
        candidates = await api_utils.get_all_items(OpenCATSEndpoint.CANDIDATES)

        if not candidates:
            logger.info("✅ No candidates found to delete")
            return {"success": True, "deleted_count": 0}

        deleted_count = 0
        for candidate in candidates:
            candidate_id = candidate.get("candidateID")
            if candidate_id:
                success = await api_utils.delete_item(OpenCATSEndpoint.CANDIDATES, candidate_id)
                if success:
                    deleted_count += 1
                    logger.info(f"🗑️ Deleted candidate: {candidate.get('firstName', '')} {candidate.get('lastName', '')} (ID: {candidate_id})")
                else:
                    logger.warning(f"⚠️ Failed to delete candidate ID: {candidate_id}")

        logger.info(f"✅ Candidate deletion completed. Deleted {deleted_count} candidates")
        return {"success": True, "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"❌ Error during candidate deletion: {e!s}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    asyncio.run(delete_existing_candidates())
