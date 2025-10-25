import asyncio
import random
from typing import Any

import aiohttp

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def create_shipment(order_id: str, fulfillment_id: str, items: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    try:
        url = f"{base_url}/admin/orders/{order_id}/fulfillments/{fulfillment_id}/shipments"
        headers = auth.get_auth_headers()

        tracking_number = f"TRACK{random.randint(100000, 999999)}"

        payload = {"items": items, "labels": [{"tracking_number": tracking_number, "tracking_url": "#", "label_url": "#"}], "no_notification": False}

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception as e:
        logger.error(f"Error creating shipment for order {order_id}: {e}")
        return False


async def ship_order(order_id: str, session: aiohttp.ClientSession, auth, base_url: str, api_utils: MedusaAPIUtils) -> tuple[bool, str]:
    """Mark an order as shipped by creating shipments for all fulfillments"""
    try:
        order = await api_utils.fetch_order_by_id(order_id)

        if not order:
            return False, "failed"

        payment_status = order.get("payment_status", "")

        if payment_status != "captured":
            return False, "unpaid"

        fulfillment_status = order.get("fulfillment_status", "")

        if fulfillment_status != "fulfilled":
            return False, "not_fulfilled"

        if fulfillment_status in ["shipped", "delivered", "partially_shipped"]:
            return False, "already_shipped"

        fulfillments = order.get("fulfillments", [])

        if not fulfillments:
            return False, "failed"

        all_success = True
        for fulfillment in fulfillments:
            fulfillment_id = fulfillment.get("id")
            if not fulfillment_id:
                continue

            shipped_at = fulfillment.get("shipped_at")
            if shipped_at:
                continue

            fulfillment_items = []

            if fulfillment.get("items"):
                fulfillment_items = fulfillment.get("items", [])
            elif fulfillment.get("fulfill_items"):
                fulfillment_items = fulfillment.get("fulfill_items", [])
            else:
                order_items = order.get("items", [])
                for order_item in order_items:
                    item_id = order_item.get("id")
                    quantity = order_item.get("quantity", 0)
                    if quantity > 0:
                        fulfillment_items.append({"line_item_id": item_id, "id": item_id, "quantity": quantity})

            if not fulfillment_items:
                continue

            items: list[dict[str, Any]] = []
            for item in fulfillment_items:
                line_item_id = item.get("line_item_id") or item.get("id")
                if line_item_id:
                    items.append({"id": line_item_id, "quantity": item.get("quantity", 1)})

            if not items:
                continue

            success = await create_shipment(order_id, fulfillment_id, items, session, auth, base_url)
            if not success:
                all_success = False

        if all_success:
            return True, "success"
        else:
            return False, "failed"

    except Exception as e:
        logger.error(f"Error shipping order '{order_id}': {e}")
        return False, "failed"


async def get_all_orders_paginated(api_utils: MedusaAPIUtils) -> list[dict[str, Any]]:
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


async def process_all_orders(api_utils: MedusaAPIUtils, shipping_percentage: float) -> dict[str, int]:
    """Process fulfilled orders for shipping (only if paid)."""

    # Fetch ALL orders with pagination
    orders = await get_all_orders_paginated(api_utils)

    if not orders:
        logger.warning("No orders found. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "unpaid": 0}

    logger.info(f"Successfully fetched {len(orders)} orders")

    # Filter orders that are fulfilled and paid
    fulfilled_and_paid_orders = [order for order in orders if order.get("fulfillment_status") == "fulfilled" and order.get("payment_status") == "captured"]

    fulfilled_count = len([o for o in orders if o.get("fulfillment_status") == "fulfilled"])
    paid_count = len([o for o in orders if o.get("payment_status") == "captured"])

    logger.info(f"Order status analysis - Total orders: {len(orders)}, Fulfilled: {fulfilled_count}, Paid: {paid_count}, Fulfilled & Paid: {len(fulfilled_and_paid_orders)}")

    if not fulfilled_and_paid_orders:
        logger.warning("No fulfilled and paid orders found to ship. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "unpaid": 0}

    # Select percentage of fulfilled and paid orders to ship
    num_to_ship = max(1, int(len(fulfilled_and_paid_orders) * shipping_percentage))
    orders_to_ship = random.sample(fulfilled_and_paid_orders, min(num_to_ship, len(fulfilled_and_paid_orders)))

    logger.info(f"Shipping plan - To mark as shipped: {len(orders_to_ship)} ({shipping_percentage * 100:.0f}%), To skip: {len(fulfilled_and_paid_orders) - len(orders_to_ship)}")
    logger.info(f"Starting shipping process for {len(orders_to_ship)} orders...")

    successful = 0
    failed = 0
    skipped = 0
    unpaid = 0

    async with aiohttp.ClientSession() as session:
        auth = api_utils.auth
        base_url = api_utils.base_url

        for idx, order in enumerate(orders_to_ship, 1):
            order_id = order.get("id")
            order_email = order.get("email", "N/A")
            fulfillment_status = order.get("fulfillment_status", "N/A")
            payment_status = order.get("payment_status", "N/A")

            if not order_id:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_ship)}] ✗ Missing order ID for email: {order_email}")
                continue

            logger.info(f"[{idx}/{len(orders_to_ship)}] Processing order: {order_id} (Email: {order_email}, Payment: {payment_status}, Fulfillment: {fulfillment_status})")

            result, status = await ship_order(order_id, session, auth, base_url, api_utils)

            if result:
                successful += 1
                logger.info(f"[{idx}/{len(orders_to_ship)}] ✓ Successfully marked order as shipped: {order_id}")
            elif status == "unpaid":
                unpaid += 1
                logger.warning(f"[{idx}/{len(orders_to_ship)}] ⊘ Skipped (unpaid): {order_id}")
            elif status == "not_fulfilled":
                skipped += 1
                logger.warning(f"[{idx}/{len(orders_to_ship)}] ⊘ Skipped (not fulfilled): {order_id}")
            elif status == "already_shipped":
                skipped += 1
                logger.info(f"[{idx}/{len(orders_to_ship)}] ⊘ Skipped (already shipped): {order_id}")
            else:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_ship)}] ✗ Failed to mark order as shipped: {order_id}")

    logger.info(
        f"Shipping process completed - "
        f"Total processed: {len(orders_to_ship)}, "
        f"Successful: {successful}, "
        f"Failed: {failed}, "
        f"Skipped: {skipped}, "
        f"Unpaid: {unpaid}, "
        f"Success Rate: {(successful / len(orders_to_ship) * 100):.1f}%"
    )

    return {"total": len(orders_to_ship), "successful": successful, "failed": failed, "skipped": skipped, "unpaid": unpaid}


async def mark_orders_as_shipped(shipping_percentage: float = 1.0) -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Mark Orders as Shipped Script")
    logger.info("=" * 60)

    logger.info(f"Shipping percentage set to: {shipping_percentage * 100:.0f}%")

    async with MedusaAPIUtils() as api_utils:
        result = await process_all_orders(api_utils, shipping_percentage)

    logger.info("=" * 60)
    logger.info("Mark Orders as Shipped Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(mark_orders_as_shipped(shipping_percentage=1.0))
