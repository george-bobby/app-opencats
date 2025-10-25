"""Mark job orders as filled in OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def mark_joborders_filled(job_order_ids: list[int] | None = None) -> dict[str, Any]:
    """Mark job orders as filled in OpenCATS.

    Args:
        job_order_ids: List of specific job order IDs to mark as filled.
                      If None, marks all active job orders as filled.
    """
    logger.info("📋 Starting job order status update to 'Filled'...")

    api_utils = OpenCATSAPIUtils()

    try:
        if job_order_ids:
            # Mark specific job orders
            job_orders = []
            for job_id in job_order_ids:
                job_order = await api_utils.get_item(OpenCATSEndpoint.JOBORDERS, job_id)
                if job_order:
                    job_orders.append(job_order)
        else:
            # Get all active job orders
            job_orders = await api_utils.get_all_items(OpenCATSEndpoint.JOBORDERS)
            # Filter for active job orders only
            job_orders = [jo for jo in job_orders if jo.get("status") == "Active"]

        if not job_orders:
            logger.info("✅ No job orders found to mark as filled")
            return {"success": True, "updated_count": 0}

        updated_count = 0
        for job_order in job_orders:
            job_order_id = job_order.get("jobOrderID")
            if job_order_id:
                # Update job order status to filled
                update_data = {"status": "Filled", "dateModified": "NOW()"}

                success = await api_utils.update_item(OpenCATSEndpoint.JOBORDERS, job_order_id, update_data)
                if success:
                    updated_count += 1
                    logger.info(f"📋 Marked job order as filled: {job_order.get('title', '')} (ID: {job_order_id})")
                else:
                    logger.warning(f"⚠️ Failed to update job order ID: {job_order_id}")

        logger.info(f"✅ Job order status update completed. Updated {updated_count} job orders to 'Filled'")
        return {"success": True, "updated_count": updated_count}

    except Exception as e:
        logger.error(f"❌ Error during job order status update: {e!s}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    asyncio.run(mark_joborders_filled())
