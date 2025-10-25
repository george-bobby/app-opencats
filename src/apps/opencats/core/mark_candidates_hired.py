"""Mark candidates as hired in OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def mark_candidates_hired(candidate_ids: list[int] | None = None, job_order_id: int | None = None) -> dict[str, Any]:
    """Mark candidates as hired in OpenCATS.

    Args:
        candidate_ids: List of specific candidate IDs to mark as hired.
                      If None, marks random candidates as hired.
        job_order_id: Specific job order ID to associate with the hire.
    """
    logger.info("👨‍💼 Starting candidate status update to 'Hired'...")

    api_utils = OpenCATSAPIUtils()

    try:
        if candidate_ids:
            # Mark specific candidates
            candidates = []
            for candidate_id in candidate_ids:
                candidate = await api_utils.get_item(OpenCATSEndpoint.CANDIDATES, candidate_id)
                if candidate:
                    candidates.append(candidate)
        else:
            # Get all candidates
            candidates = await api_utils.get_all_items(OpenCATSEndpoint.CANDIDATES)
            # Take a sample for marking as hired (e.g., 10% of candidates)
            import random

            sample_size = max(1, len(candidates) // 10)
            candidates = random.sample(candidates, min(sample_size, len(candidates)))

        if not candidates:
            logger.info("✅ No candidates found to mark as hired")
            return {"success": True, "updated_count": 0}

        updated_count = 0
        for candidate in candidates:
            candidate_id = candidate.get("candidateID")
            if candidate_id:
                # Update candidate status to hired
                update_data = {"status": "Hired", "dateModified": "NOW()"}

                if job_order_id:
                    update_data["currentJobOrderID"] = job_order_id

                success = await api_utils.update_item(OpenCATSEndpoint.CANDIDATES, candidate_id, update_data)
                if success:
                    updated_count += 1
                    logger.info(f"👨‍💼 Marked candidate as hired: {candidate.get('firstName', '')} {candidate.get('lastName', '')} (ID: {candidate_id})")
                else:
                    logger.warning(f"⚠️ Failed to update candidate ID: {candidate_id}")

        logger.info(f"✅ Candidate status update completed. Updated {updated_count} candidates to 'Hired'")
        return {"success": True, "updated_count": updated_count}

    except Exception as e:
        logger.error(f"❌ Error during candidate status update: {e!s}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    asyncio.run(mark_candidates_hired())
