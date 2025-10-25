import asyncio
import random

import aiohttp

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def mark_fulfillment_delivered(order_id: str, fulfillment_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    try:
        url = f"{base_url}/admin/orders/{order_id}/fulfillments/{fulfillment_id}/mark-as-delivered"
        headers = auth.get_auth_headers()

        async with session.post(url, headers=headers) as response:
            return response.status in (200, 201)

    except Exception as e:
        logger.error(f"Error marking fulfillment {fulfillment_id} as delivered for order {order_id}: {e}")
        return False


async def deliver_order(order_id: str, session: aiohttp.ClientSession, auth, base_url: str, api_utils: MedusaAPIUtils) -> bool:
    """Mark an order as delivered by marking all shipped fulfillments as delivered."""
    try:
        order = await api_utils.fetch_order_by_id(order_id)

        if not order:
            return False

        fulfillment_status = order.get("fulfillment_status", "")

        if fulfillment_status not in ["shipped", "partially_shipped"]:
            return False

        if fulfillment_status == "delivered":
            return False

        fulfillments = order.get("fulfillments", [])

        if not fulfillments:
            return False

        all_success = True
        for fulfillment in fulfillments:
            fulfillment_id = fulfillment.get("id")
            if not fulfillment_id:
                continue

            delivered_at = fulfillment.get("delivered_at")
            if delivered_at:
                continue

            shipped_at = fulfillment.get("shipped_at")
            if not shipped_at:
                continue

            success = await mark_fulfillment_delivered(order_id, fulfillment_id, session, auth, base_url)
            if not success:
                all_success = False

        return bool(all_success)

    except Exception as e:
        logger.error(f"Error delivering order '{order_id}': {e}")
        return False


async def get_all_orders_paginated(api_utils: MedusaAPIUtils) -> list[dict]:
    """Fetch ALL orders from Medusa API with pagination."""
    logger.info("Fetching all orders from Medusa API...")

    all_orders = []
    offset = 0
    limit = 50

    while True:
        orders = await api_utils.fetch_orders(limit=limit, offset=offset)

        if not orders:
            break

        all_orders.extend(orders)

        if len(all_orders) % 100 == 0:
            logger.info(f"Fetched {len(all_orders)} orders so far...")

        if len(orders) < limit:
            break

        offset += limit

    logger.info(f"Successfully fetched {len(all_orders)} total orders")
    return all_orders


async def process_all_orders(api_utils: MedusaAPIUtils, delivery_percentage: float) -> dict[str, int]:
    """Process shipped orders for delivery."""

    # Fetch ALL orders with pagination instead of just limit
    orders = await get_all_orders_paginated(api_utils)

    if not orders:
        logger.warning("No orders found. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

    logger.info(f"Successfully fetched {len(orders)} orders")

    shipped_orders = [order for order in orders if order.get("fulfillment_status") in ["shipped", "partially_shipped"]]
    non_shipped_count = len(orders) - len(shipped_orders)

    logger.info(f"Order fulfillment status analysis - Total orders: {len(orders)}, Shipped: {len(shipped_orders)}, Not shipped: {non_shipped_count}")

    if not shipped_orders:
        logger.warning("No shipped orders found to deliver. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

    num_to_deliver = max(1, int(len(shipped_orders) * delivery_percentage))
    orders_to_deliver = random.sample(shipped_orders, min(num_to_deliver, len(shipped_orders)))

    logger.info(f"Delivery plan - To mark as delivered: {len(orders_to_deliver)} ({delivery_percentage * 100:.0f}%), To skip: {len(shipped_orders) - len(orders_to_deliver)}")
    logger.info(f"Starting delivery marking process for {len(orders_to_deliver)} orders...")

    successful = 0
    failed = 0
    skipped = len(shipped_orders) - len(orders_to_deliver)

    async with aiohttp.ClientSession() as session:
        auth = api_utils.auth
        base_url = api_utils.base_url

        for idx, order in enumerate(orders_to_deliver, 1):
            order_id = order.get("id")
            order_email = order.get("email", "N/A")
            fulfillment_status = order.get("fulfillment_status", "N/A")

            if not order_id:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_deliver)}] ✗ Missing order ID for email: {order_email}")
                continue

            logger.info(f"[{idx}/{len(orders_to_deliver)}] Processing order: {order_id} (Email: {order_email}, Status: {fulfillment_status})")

            result = await deliver_order(order_id, session, auth, base_url, api_utils)

            if result:
                successful += 1
                logger.info(f"[{idx}/{len(orders_to_deliver)}] ✓ Successfully marked order as delivered: {order_id}")
            else:
                order_details = await api_utils.fetch_order_by_id(order_id)
                fulfillment_status = order_details.get("fulfillment_status", "") if order_details else ""

                if fulfillment_status == "delivered":
                    skipped += 1
                    logger.info(f"[{idx}/{len(orders_to_deliver)}] ⊘ Skipped (already delivered): {order_id}")
                elif fulfillment_status in ["not_fulfilled", "fulfilled"]:
                    skipped += 1
                    logger.warning(f"[{idx}/{len(orders_to_deliver)}] ⊘ Skipped (status: {fulfillment_status}): {order_id}")
                else:
                    failed += 1
                    logger.error(f"[{idx}/{len(orders_to_deliver)}] ✗ Failed to mark order as delivered: {order_id}")

    logger.info(
        f"Delivery marking completed - "
        f"Total processed: {len(orders_to_deliver)}, "
        f"Successful: {successful}, "
        f"Failed: {failed}, "
        f"Skipped: {skipped}, "
        f"Success Rate: {(successful / len(orders_to_deliver) * 100):.1f}%"
    )

    return {"total": len(orders_to_deliver), "successful": successful, "failed": failed, "skipped": skipped}


async def mark_orders_as_delivered(delivery_percentage: float = 0.9) -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Mark Orders as Delivered Script")
    logger.info("=" * 60)

    logger.info(f"Delivery percentage set to: {delivery_percentage * 100:.0f}%")

    async with MedusaAPIUtils() as api_utils:
        result = await process_all_orders(api_utils, delivery_percentage)

    logger.info("=" * 60)
    logger.info("Mark Orders as Delivered Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(mark_orders_as_delivered(delivery_percentage=0.9))
