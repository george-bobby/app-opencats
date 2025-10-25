import asyncio
import random
from typing import Any

import aiohttp

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def get_all_orders_paginated(api_utils: MedusaAPIUtils) -> list[dict[str, Any]]:
    """Fetch ALL orders from Medusa API with pagination."""
    logger.info("Fetching all orders from Medusa API...")

    all_orders: list[dict[str, Any]] = []
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


async def get_order_details(order_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, Any] | None:
    try:
        url = f"{base_url}/admin/orders/{order_id}?fields=id,display_id,status,payment_status,*payment_collections,*payment_collections.payments"
        headers = auth.get_auth_headers()

        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("order", {})
            return None
    except Exception as e:
        logger.error(f"Error fetching order details for {order_id}: {e}")
        return None


async def create_payment_collection(order_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, Any] | None:
    """Create a payment collection for an order."""
    try:
        url = f"{base_url}/admin/payment-collections"
        headers = auth.get_auth_headers()
        payload = {"order_id": order_id, "amount": 0}

        async with session.post(url, headers=headers, json=payload) as response:
            if response.status in (200, 201):
                result = await response.json()
                return result.get("payment_collection", {})
            return None
    except Exception as e:
        logger.error(f"Error creating payment collection for {order_id}: {e}")
        return None


async def mark_order_as_paid(order_id: str, payment_collection_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Mark an order as paid via the payment collection endpoint."""
    try:
        url = f"{base_url}/admin/payment-collections/{payment_collection_id}/mark-as-paid"
        headers = auth.get_auth_headers()
        payload = {"order_id": order_id}

        async with session.post(url, headers=headers, json=payload) as response:
            return response.status in (200, 201)
    except Exception as e:
        logger.error(f"Error marking order as paid '{order_id}': {e}")
        return False


async def process_all_orders(api_utils: MedusaAPIUtils, percentage_to_mark: int) -> dict[str, int]:
    """Process orders and mark a percentage of them as paid."""
    orders = await get_all_orders_paginated(api_utils)
    if not orders:
        logger.warning("No orders found. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0}

    unpaid_orders = [o for o in orders if o.get("payment_status") not in ["paid", "captured"]]
    paid_count = len(orders) - len(unpaid_orders)

    logger.info(f"Order payment status analysis - Total orders: {len(orders)}, Already paid: {paid_count}, Unpaid: {len(unpaid_orders)}")

    if not unpaid_orders:
        logger.warning("All orders are already paid. Nothing to do.")
        return {"total": 0, "successful": 0, "failed": 0}

    num_to_mark = max(1, int(len(unpaid_orders) * (percentage_to_mark / 100)))
    orders_to_mark = random.sample(unpaid_orders, min(num_to_mark, len(unpaid_orders)))

    logger.info(f"Payment marking plan - To mark as paid: {len(orders_to_mark)} ({percentage_to_mark}%), To skip: {len(unpaid_orders) - len(orders_to_mark)}")
    logger.info(f"Starting payment marking process for {len(orders_to_mark)} orders...")

    successful = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        auth = api_utils.auth
        base_url = api_utils.base_url

        for idx, order in enumerate(orders_to_mark, 1):
            order_id = order.get("id")
            order_email = order.get("email", "N/A")

            if not order_id:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_mark)}] ✗ Missing order ID for email: {order_email}")
                continue

            logger.info(f"[{idx}/{len(orders_to_mark)}] Processing order: {order_id} (Email: {order_email})")

            order_details = await get_order_details(order_id, session, auth, base_url)
            if not order_details:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_mark)}] ✗ Failed to fetch order details for: {order_id}")
                continue

            payment_collections = order_details.get("payment_collections", [])
            payment_collection_id = None

            if not payment_collections:
                logger.info(f"[{idx}/{len(orders_to_mark)}]   Creating payment collection for: {order_id}")
                created_collection = await create_payment_collection(order_id, session, auth, base_url)
                if created_collection:
                    payment_collection_id = created_collection.get("id")
                    logger.info(f"[{idx}/{len(orders_to_mark)}]   ✓ Payment collection created: {payment_collection_id}")
                else:
                    logger.error(f"[{idx}/{len(orders_to_mark)}]   ✗ Failed to create payment collection")

                if not payment_collection_id:
                    failed += 1
                    logger.error(f"[{idx}/{len(orders_to_mark)}] ✗ No payment collection ID available for: {order_id}")
                    continue
            else:
                payment_collection = payment_collections[0]
                payment_collection_id = payment_collection.get("id")
                logger.info(f"[{idx}/{len(orders_to_mark)}]   Using existing payment collection: {payment_collection_id}")

                if not payment_collection_id or not isinstance(payment_collection_id, str):
                    failed += 1
                    logger.error(f"[{idx}/{len(orders_to_mark)}] ✗ Invalid payment collection ID for: {order_id}")
                    continue

            result = await mark_order_as_paid(order_id, payment_collection_id, session, auth, base_url)

            if result:
                successful += 1
                logger.info(f"[{idx}/{len(orders_to_mark)}] ✓ Successfully marked order as paid: {order_id}")
            else:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_mark)}] ✗ Failed to mark order as paid: {order_id}")

    logger.info(
        f"Payment marking completed - Total processed: {len(orders_to_mark)}, Successful: {successful}, Failed: {failed}, Success Rate: {(successful / len(orders_to_mark) * 100):.1f}%"
    )

    return {"total": len(orders_to_mark), "successful": successful, "failed": failed}


async def mark_orders_as_paid(percentage_to_mark: int = 70) -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Mark Orders as Paid Script")
    logger.info("=" * 60)

    logger.info(f"Payment marking percentage set to: {percentage_to_mark}%")

    async with MedusaAPIUtils() as api_utils:
        result = await process_all_orders(api_utils, percentage_to_mark)

    logger.info("=" * 60)
    logger.info("Mark Orders as Paid Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(mark_orders_as_paid(percentage_to_mark=70))
