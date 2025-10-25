import asyncio
import random
from typing import Any

import aiohttp

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def get_trendspire_stock_location(api_utils: MedusaAPIUtils) -> str | None:
    """Get the Trendspire stock location ID."""
    logger.info("Looking up Trendspire stock location...")

    stock_locations = await api_utils.fetch_stock_locations()

    for location in stock_locations:
        if location.get("name") == "Trendspire":
            location_id = location.get("id")
            logger.info(f"Found Trendspire stock location: {location_id}")
            return location_id

    logger.warning("Trendspire stock location not found")
    return None


async def fetch_shipping_options(stock_location_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> list[dict[str, Any]]:
    """Fetch available shipping options for a stock location."""
    logger.info(f"Fetching shipping options for stock location: {stock_location_id}")

    try:
        url = f"{base_url}/admin/shipping-options"
        params = {"stock_location_id": stock_location_id, "limit": 50}
        headers = auth.get_auth_headers()

        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                if isinstance(response_data, dict):
                    options = response_data.get("shipping_options", [])
                elif isinstance(response_data, list):
                    options = response_data
                else:
                    options = []

                logger.info(f"Found {len(options)} shipping options")
                return options

            logger.warning("Failed to fetch shipping options")
            return []

    except Exception as e:
        logger.error(f"Error fetching shipping options: {e}")
        return []


async def get_inventory_item_id_for_line_item(line_item: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> str | None:
    """Get inventory_item_id by fetching the product and finding the variant."""
    product_id = line_item.get("product_id")
    variant_id = line_item.get("variant_id")

    if not product_id or not variant_id:
        return None

    try:
        url = f"{base_url}/admin/products/{product_id}"
        params = {"fields": "*variants,*variants.inventory_items"}
        headers = auth.get_auth_headers()

        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                product = response_data.get("product", {})

                for variant in product.get("variants", []):
                    if variant.get("id") == variant_id:
                        inventory_items = variant.get("inventory_items", [])
                        if inventory_items and len(inventory_items) > 0:
                            inv_item = inventory_items[0]
                            inventory_item_id = inv_item.get("inventory_item_id") or inv_item.get("id")
                            if inventory_item_id:
                                return inventory_item_id
            return None
    except Exception:
        return None


async def create_inventory_reservation(line_item: dict[str, Any], location_id: str, quantity: int, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create an inventory reservation for a line item."""
    try:
        line_item_id = line_item.get("id")
        inventory_item_id = await get_inventory_item_id_for_line_item(line_item, session, auth, base_url)

        if not inventory_item_id:
            return False

        url = f"{base_url}/admin/reservations"
        headers = auth.get_auth_headers()

        payload = {"line_item_id": line_item_id, "inventory_item_id": inventory_item_id, "location_id": location_id, "quantity": quantity}

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                return True
            else:
                response_text = await response.text()
                return "already" in response_text.lower() or "exists" in response_text.lower()

    except Exception:
        return False


async def create_reservations_for_order(order: dict[str, Any], location_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create inventory reservations for all items in an order."""
    items = order.get("items", [])
    if not items:
        return False

    all_success = True
    for item in items:
        quantity = item.get("quantity", 0)
        fulfilled_quantity = item.get("fulfilled_quantity", 0)
        remaining = quantity - fulfilled_quantity

        if remaining > 0:
            success = await create_inventory_reservation(item, location_id, remaining, session, auth, base_url)
            if not success:
                all_success = False

    return all_success


async def fulfill_order(order_id: str, location_id: str, shipping_option_id: str, session: aiohttp.ClientSession, auth, base_url: str, api_utils: MedusaAPIUtils) -> bool:
    """Create fulfillment for an order."""
    try:
        order = await api_utils.fetch_order_by_id(order_id)
        if not order:
            return False

        fulfillment_status = order.get("fulfillment_status", "")

        if fulfillment_status in ["fulfilled", "delivered", "shipped", "partially_fulfilled"]:
            return False

        await create_reservations_for_order(order, location_id, session, auth, base_url)

        items = order.get("items", [])
        fulfillment_items: list[dict[str, Any]] = []

        for item in items:
            quantity = item.get("quantity", 0)
            fulfilled_quantity = item.get("fulfilled_quantity", 0)
            remaining = quantity - fulfilled_quantity

            if remaining > 0:
                fulfillment_items.append({"id": item.get("id"), "quantity": remaining})

        if not fulfillment_items:
            return False

        url = f"{base_url}/admin/orders/{order_id}/fulfillments"
        headers = auth.get_auth_headers()

        payload = {"location_id": location_id, "shipping_option_id": shipping_option_id, "no_notification": False, "items": fulfillment_items}

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception as e:
        logger.error(f"Error fulfilling order '{order_id}': {e}")
        return False


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


async def process_all_orders(api_utils: MedusaAPIUtils, percentage_to_fulfill: int) -> dict[str, int]:
    """Process orders and fulfill a percentage of them."""
    location_id = await get_trendspire_stock_location(api_utils)
    if not location_id:
        logger.warning("Cannot proceed without Trendspire stock location. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

    async with aiohttp.ClientSession() as session:
        auth = api_utils.auth
        base_url = api_utils.base_url

        shipping_options = await fetch_shipping_options(location_id, session, auth, base_url)
        if not shipping_options:
            logger.warning("Cannot proceed without shipping options. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        logger.info("Searching for Standard Shipping option...")
        standard_shipping = None
        for option in shipping_options:
            option_name = option.get("name", "").lower()
            if "standard" in option_name and "shipping" in option_name:
                standard_shipping = option
                break

        if not standard_shipping:
            logger.warning("Standard Shipping option not found. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        shipping_option_id = standard_shipping.get("id")
        shipping_option_name = standard_shipping.get("name", "Unknown")
        logger.info(f"Using shipping option: '{shipping_option_name}' (ID: {shipping_option_id})")

        if not shipping_option_id or not isinstance(shipping_option_id, str):
            logger.warning("Invalid shipping option ID. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        orders = await get_all_orders_paginated(api_utils)
        if not orders:
            logger.warning("No orders found. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        unfulfilled_orders = [o for o in orders if o.get("fulfillment_status") not in ["fulfilled", "delivered", "shipped"]]
        fulfilled_count = len(orders) - len(unfulfilled_orders)

        logger.info(f"Order status analysis - Total orders: {len(orders)}, Already fulfilled: {fulfilled_count}, Unfulfilled: {len(unfulfilled_orders)}")

        if not unfulfilled_orders:
            logger.warning("All orders are already fulfilled. Nothing to do.")
            return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        num_to_fulfill = max(1, int(len(unfulfilled_orders) * (percentage_to_fulfill / 100)))
        orders_to_fulfill = random.sample(unfulfilled_orders, min(num_to_fulfill, len(unfulfilled_orders)))

        logger.info(f"Fulfillment plan - To fulfill: {len(orders_to_fulfill)} ({percentage_to_fulfill}%), To skip: {len(unfulfilled_orders) - len(orders_to_fulfill)}")
        logger.info(f"Starting fulfillment process for {len(orders_to_fulfill)} orders...")

        successful = 0
        failed = 0
        skipped = 0

        for idx, order in enumerate(orders_to_fulfill, 1):
            order_id = order.get("id")
            order_email = order.get("email", "N/A")

            if not order_id:
                failed += 1
                logger.error(f"[{idx}/{len(orders_to_fulfill)}] ✗ Missing order ID for email: {order_email}")
                continue

            logger.info(f"[{idx}/{len(orders_to_fulfill)}] Fulfilling order: {order_id} (Email: {order_email})")

            result = await fulfill_order(order_id, location_id, shipping_option_id, session, auth, base_url, api_utils)

            if result:
                successful += 1
                logger.info(f"[{idx}/{len(orders_to_fulfill)}] ✓ Successfully fulfilled order: {order_id}")
            else:
                fulfillment_status = order.get("fulfillment_status", "")
                if fulfillment_status in ["fulfilled", "delivered", "shipped"]:
                    skipped += 1
                    logger.info(f"[{idx}/{len(orders_to_fulfill)}] ⊘ Skipped order (already fulfilled): {order_id}")
                else:
                    failed += 1
                    logger.error(f"[{idx}/{len(orders_to_fulfill)}] ✗ Failed to fulfill order: {order_id}")

        logger.info(
            f"Order fulfillment completed - "
            f"Total processed: {len(orders_to_fulfill)}, "
            f"Successful: {successful}, "
            f"Failed: {failed}, "
            f"Skipped: {skipped}, "
            f"Success Rate: {(successful / len(orders_to_fulfill) * 100):.1f}%"
        )

        return {"total": len(orders_to_fulfill), "successful": successful, "failed": failed, "skipped": skipped}


async def mark_orders_as_fulfilled(percentage_to_fulfill: int = 100) -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Order Fulfillment Script")
    logger.info("=" * 60)

    logger.info(f"Fulfillment percentage set to: {percentage_to_fulfill}%")

    async with MedusaAPIUtils() as api_utils:
        result = await process_all_orders(api_utils, percentage_to_fulfill)

    logger.info("=" * 60)
    logger.info("Order Fulfillment Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(mark_orders_as_fulfilled(percentage_to_fulfill=100))
