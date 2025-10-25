import asyncio
import random
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import ORDERS_FILEPATH
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_orders_data() -> list[dict[str, Any]]:
    logger.info(f"Loading orders data from: {ORDERS_FILEPATH}")

    orders_data = load_json_file(ORDERS_FILEPATH, default=[])
    if not isinstance(orders_data, list) or not orders_data:
        logger.warning("No orders data found in orders.json or invalid format")
        return []

    logger.info(f"Successfully loaded {len(orders_data)} orders from file")
    return orders_data


async def build_channel_stock_location_map(sales_channels: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, list[str]]:
    """Build a mapping of sales channel IDs to their associated stock location IDs."""
    logger.info("Building sales channel to stock location mapping...")

    channel_stock_location_map: dict[str, list[str]] = {}

    for channel in sales_channels:
        channel_id = channel.get("id")
        if not channel_id:
            continue

        try:
            headers = auth.get_auth_headers()
            url = f"{base_url}/admin/stock-locations"
            params = {"sales_channel_id": channel_id}

            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    locations = result.get("stock_locations", [])
                    location_ids = [loc.get("id") for loc in locations if loc.get("id")]

                    if location_ids:
                        channel_stock_location_map[channel_id] = location_ids

        except Exception:
            pass

    logger.info(f"Channel-Location mapping built - {len(channel_stock_location_map)} channels mapped")
    return channel_stock_location_map


def prepare_channel_data(sales_channels: list[dict[str, Any]], channel_stock_location_map: dict[str, list[str]]) -> dict[str, Any]:
    """Prepare sales channel data for order creation."""
    official_website_channel = None
    available_channels = []

    for channel in sales_channels:
        channel_name = channel.get("name", "").lower()
        if channel_name == "default sales channel" or channel.get("is_disabled", False):
            continue

        channel_id = channel.get("id")
        if channel_id and channel_id in channel_stock_location_map:
            available_channels.append(channel)
            if channel_name == "official website":
                official_website_channel = channel

    logger.info(f"Available sales channels: {len(available_channels)}")
    return {
        "official_website_channel": official_website_channel,
        "available_channels": available_channels,
    }


def select_sales_channel(channel_data: dict[str, Any]) -> dict[str, Any] | None:
    """Select a sales channel for the order."""
    available_channels = channel_data["available_channels"]
    official_website_channel = channel_data["official_website_channel"]

    if not available_channels:
        return None

    if official_website_channel and random.random() < 0.75:
        return official_website_channel

    other_channels = [ch for ch in available_channels if ch.get("id") != official_website_channel.get("id")] if official_website_channel else available_channels
    return random.choice(other_channels) if other_channels else official_website_channel


def select_random_items(
    order_data: dict[str, Any],
    products_cache: list[dict[str, Any]],
    sales_channel_id: str | None,
    channel_stock_location_map: dict[str, list[str]],
    stock_locations_cache: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select random items for the order."""
    if not products_cache:
        return []

    channel_locations = []
    if sales_channel_id and sales_channel_id in channel_stock_location_map:
        channel_locations = channel_stock_location_map[sales_channel_id]

    if not channel_locations:
        channel_locations = [loc.get("id") for loc in stock_locations_cache if loc.get("id")]

    valid_variants = []
    for product in products_cache:
        for variant in product.get("variants", []):
            has_valid_price = any(p.get("amount") and p.get("amount") > 0 and p.get("currency_code", "").lower() == "usd" for p in variant.get("prices", []))

            if has_valid_price:
                valid_variants.append({"variant_id": variant.get("id"), "product_title": product.get("title", "Unknown"), "variant_title": variant.get("title", "")})

    if not valid_variants:
        return []

    desired_count = len(order_data.get("items", [])) or random.randint(1, 3)
    num_items = min(desired_count, len(valid_variants))
    selected = random.sample(valid_variants, num_items)

    items = []
    for item in selected:
        quantity = random.randint(1, 3)
        items.append({"variant_id": item["variant_id"], "quantity": quantity})

    return items


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_order(
    order_data: dict[str, Any],
    customers_cache: list[dict[str, Any]],
    products_cache: list[dict[str, Any]],
    regions_cache: list[dict[str, Any]],
    stock_locations_cache: list[dict[str, Any]],
    channel_data: dict[str, Any],
    channel_stock_location_map: dict[str, list[str]],
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> bool:
    """Create a single order via Medusa API with retry logic."""
    try:
        customer = None
        if order_data.get("customer_email"):
            customer = next((c for c in customers_cache if c.get("email") == order_data["customer_email"]), None)
        if not customer and order_data.get("customer_id"):
            customer = next((c for c in customers_cache if c.get("id") == order_data["customer_id"]), None)
        if not customer and customers_cache:
            customer = random.choice(customers_cache)

        region = None
        if order_data.get("region_id"):
            region = next((r for r in regions_cache if r.get("id") == order_data["region_id"]), None)
        if not region and regions_cache:
            region = random.choice(regions_cache)

        sales_channel = select_sales_channel(channel_data)
        sales_channel_id = sales_channel.get("id") if sales_channel else None

        payload: dict[str, Any] = {
            "region_id": region.get("id") if region else order_data.get("region_id"),
            "email": customer.get("email") if customer else order_data.get("customer_email", "customer@example.com"),
        }

        if customer:
            payload["customer_id"] = customer.get("id")
        if sales_channel_id:
            payload["sales_channel_id"] = sales_channel_id
        if order_data.get("shipping_address"):
            payload["shipping_address"] = order_data["shipping_address"]
        if order_data.get("billing_address"):
            payload["billing_address"] = order_data["billing_address"]

        headers = auth.get_auth_headers()
        url = f"{base_url}/admin/draft-orders"

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status not in (200, 201):
                logger.error("Failed to create draft order")
                return False

            result = await response.json()
            draft_order_id = result.get("draft_order", {}).get("id")

            if not draft_order_id:
                return False

            # Start edit session
            url = f"{base_url}/admin/draft-orders/{draft_order_id}/edit"
            async with session.post(url, headers=headers) as edit_response:
                if edit_response.status not in (200, 201):
                    return False

            # Add items
            items = select_random_items(order_data, products_cache, sales_channel_id, channel_stock_location_map, stock_locations_cache)
            if not items:
                return False

            url = f"{base_url}/admin/draft-orders/{draft_order_id}/edit/items"
            payload = {"items": items}

            async with session.post(url, json=payload, headers=headers) as items_response:
                if items_response.status not in (200, 201):
                    response_text = await items_response.text()
                    if "not associated with any stock location" in response_text and sales_channel_id:
                        items_no_channel = select_random_items(order_data, products_cache, None, channel_stock_location_map, stock_locations_cache)
                        if items_no_channel:
                            payload = {"items": items_no_channel}
                            async with session.post(url, json=payload, headers=headers) as retry_response:
                                if retry_response.status not in (200, 201):
                                    return False
                        else:
                            return False
                    else:
                        return False

            # Request confirmation
            url = f"{base_url}/admin/draft-orders/{draft_order_id}/edit/request"
            async with session.post(url, headers=headers) as request_response:
                if request_response.status not in (200, 201):
                    return False

            # Confirm edit
            url = f"{base_url}/admin/draft-orders/{draft_order_id}/edit/confirm"
            async with session.post(url, headers=headers) as confirm_response:
                if confirm_response.status not in (200, 201):
                    return False

            return True

    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise


async def seed_orders() -> dict[str, int]:
    logger.info("=" * 60)
    logger.info("Starting Order Seeding Script")
    logger.info("=" * 60)

    orders_data = load_orders_data()

    async with MedusaAPIUtils() as api_utils:
        # Fetch all catalog data
        logger.info("Fetching catalog data from Medusa API...")

        customers_cache = await api_utils._fetch_with_pagination("/admin/customers", "customers", initial_limit=1000)
        products_cache = await api_utils.fetch_products(limit=1000)
        regions = await api_utils.fetch_regions()
        sales_channels_cache = await api_utils.fetch_sales_channels()
        stock_locations_cache = await api_utils.fetch_stock_locations()

        usd_regions = [r for r in regions if r.get("currency_code", "").upper() == "USD"]
        regions_cache = usd_regions if usd_regions else []

        logger.info(
            f"Successfully fetched catalog data - "
            f"Customers: {len(customers_cache)}, "
            f"Products: {len(products_cache)}, "
            f"USD Regions: {len(regions_cache)}, "
            f"Sales Channels: {len(sales_channels_cache)}, "
            f"Stock Locations: {len(stock_locations_cache)}"
        )

        if not orders_data:
            logger.warning("No orders to create. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0}

        if not products_cache:
            logger.warning("No products available. Cannot create orders. Exiting.")
            return {"total": 0, "successful": 0, "failed": 0}

        # Create session for order creation operations
        async with aiohttp.ClientSession() as session:
            auth = api_utils.auth
            base_url = api_utils.base_url

            channel_stock_location_map = await build_channel_stock_location_map(sales_channels_cache, session, auth, base_url)
            channel_data = prepare_channel_data(sales_channels_cache, channel_stock_location_map)

            total = len(orders_data)
            logger.info(f"Starting order creation process - Total orders: {total}")

            successful = 0
            failed = 0

            for idx, order_data in enumerate(orders_data, 1):
                customer_email = order_data.get("customer_email", "N/A")
                logger.info(f"[{idx}/{total}] Creating order for customer: {customer_email}")

                try:
                    result = await create_order(
                        order_data,
                        customers_cache,
                        products_cache,
                        regions_cache,
                        stock_locations_cache,
                        channel_data,
                        channel_stock_location_map,
                        session,
                        auth,
                        base_url,
                    )

                    if result:
                        successful += 1
                        logger.info(f"[{idx}/{total}] ✓ Successfully created order for: {customer_email}")
                    else:
                        failed += 1
                        logger.error(f"[{idx}/{total}] ✗ Failed to create order for: {customer_email}")
                except Exception as e:
                    failed += 1
                    logger.error(f"[{idx}/{total}] ✗ Exception creating order for: {customer_email} - {e}")

            logger.info(f"Order creation completed - Total: {total}, Successful: {successful}, Failed: {failed}, Success Rate: {(successful / total * 100):.1f}%")

            logger.info("=" * 60)
            logger.info("Order Seeding Script Completed")
            logger.info("=" * 60)

            return {"total": total, "successful": successful, "failed": failed}


if __name__ == "__main__":
    asyncio.run(seed_orders())
