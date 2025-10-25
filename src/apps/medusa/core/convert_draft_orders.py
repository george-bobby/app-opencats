import asyncio
import random
from typing import Any

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def convert_draft_order(draft_order_id: str, api_utils: MedusaAPIUtils) -> bool:
    """Convert a single draft order to an order."""
    try:
        status, _response = await api_utils._make_post_request(f"/admin/draft-orders/{draft_order_id}/convert-to-order")

        return status in (200, 201)

    except Exception as e:
        logger.error(f"Error converting draft order '{draft_order_id}': {e}")
        return False


async def process_draft_orders_conversion(draft_orders: list[dict[str, Any]], conversion_percentage: float, api_utils: MedusaAPIUtils) -> dict[str, int]:
    """Convert draft orders to orders based on conversion percentage."""
    if not draft_orders:
        logger.warning("No draft orders found. Exiting.")
        return {"total": 0, "to_convert": 0, "successful": 0, "failed": 0, "skipped": 0}

    total_orders = len(draft_orders)
    num_to_convert = int(total_orders * conversion_percentage)
    orders_to_convert = random.sample(draft_orders, num_to_convert)
    skipped = total_orders - num_to_convert

    logger.info(
        f"Draft orders analysis - Total: {total_orders}, To convert: {num_to_convert} ({conversion_percentage * 100:.0f}%), To skip: {skipped} ({(skipped / total_orders * 100):.0f}%)"
    )
    logger.info(f"Starting conversion process for {num_to_convert} draft orders...")

    successful = 0
    failed = 0

    for idx, draft_order in enumerate(orders_to_convert, 1):
        draft_order_id = draft_order.get("id")
        draft_order_email = draft_order.get("email", "N/A")

        if not draft_order_id:
            failed += 1
            logger.error(f"[{idx}/{num_to_convert}] ✗ Missing draft order ID for email: {draft_order_email}")
            continue

        logger.info(f"[{idx}/{num_to_convert}] Converting draft order: {draft_order_id} (Email: {draft_order_email})")

        result = await convert_draft_order(draft_order_id, api_utils)

        if result:
            successful += 1
            logger.info(f"[{idx}/{num_to_convert}] ✓ Successfully converted draft order: {draft_order_id}")
        else:
            failed += 1
            logger.error(f"[{idx}/{num_to_convert}] ✗ Failed to convert draft order: {draft_order_id}")

    logger.info(
        f"Draft orders conversion completed - "
        f"Total processed: {num_to_convert}, "
        f"Successful: {successful}, "
        f"Failed: {failed}, "
        f"Skipped: {skipped}, "
        f"Success Rate: {(successful / num_to_convert * 100):.1f}%"
    )

    return {"total": total_orders, "to_convert": num_to_convert, "successful": successful, "failed": failed, "skipped": skipped}


async def convert_draft_orders(conversion_percentage: float = 0.8):
    logger.info("=" * 60)
    logger.info("Starting Draft Orders Conversion Script")
    logger.info("=" * 60)

    logger.info(f"Conversion percentage set to: {conversion_percentage * 100:.0f}%")
    logger.info("Fetching draft orders from Medusa API...")

    async with MedusaAPIUtils() as api_utils:
        draft_orders = await api_utils.fetch_all_draft_orders()

        if draft_orders:
            logger.info(f"Successfully fetched {len(draft_orders)} draft orders")

        result = await process_draft_orders_conversion(draft_orders, conversion_percentage, api_utils)

    logger.info("=" * 60)
    logger.info("Draft Orders Conversion Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(convert_draft_orders(conversion_percentage=0.8))
