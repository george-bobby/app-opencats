"""Price Lists API operations for Medusa."""

import asyncio
import random
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import PRICE_LIST_CONFIGS
from apps.medusa.utils.api_auth import get_medusa_auth_headers, get_medusa_base_url
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


def generate_prices(config: dict[str, Any], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate prices for products based on configuration."""
    num_products = random.randint(20, 30)
    selected_products = random.sample(products, min(num_products, len(products)))

    prices = []
    for product in selected_products:
        for variant in product.get("variants", []):
            variant_prices = variant.get("prices", [])
            if not variant_prices:
                continue

            base_price = variant_prices[0]
            original_amount = base_price.get("amount", 0)
            discount = config.get("discount_percentage", 0)
            discounted_amount = int(original_amount * (1 - discount / 100)) if discount > 0 else original_amount

            prices.append(
                {
                    "amount": discounted_amount,
                    "currency_code": base_price.get("currency_code", "usd"),
                    "variant_id": variant["id"],
                }
            )

    return prices


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    reraise=True,
)
async def create_price_list(session: Any, price_list_data: dict[str, Any]) -> bool:
    """Create a price list in Medusa."""
    if not session:
        return False

    try:
        payload = {
            "title": price_list_data["title"],
            "type": price_list_data.get("type", "sale"),
            "status": price_list_data.get("status", "active"),
        }

        if price_list_data.get("description"):
            payload["description"] = price_list_data["description"]
        if price_list_data.get("starts_at"):
            payload["starts_at"] = price_list_data["starts_at"]
        if price_list_data.get("ends_at"):
            payload["ends_at"] = price_list_data["ends_at"]
        if price_list_data.get("prices"):
            payload["prices"] = price_list_data["prices"]
        if price_list_data.get("rules"):
            payload["rules"] = price_list_data["rules"]

        base_url = get_medusa_base_url()
        url = f"{base_url}/admin/price-lists"
        headers = get_medusa_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        return False


async def seed_price_lists_internal(session: Any) -> dict[str, int]:
    """Internal function to seed price lists."""
    async with MedusaAPIUtils() as api_utils:
        products = await api_utils.fetch_products()
        sales_channels = await api_utils.fetch_sales_channels()

    if not products or not sales_channels:
        return {"total": 0, "successful": 0, "failed": 0}

    channel_map = {sc["name"]: sc for sc in sales_channels}

    logger.info(f"Seeding price lists: {len(PRICE_LIST_CONFIGS)} total")

    successful = 0
    failed = 0

    for config in PRICE_LIST_CONFIGS:
        channel_name = config.get("channel_name")
        price_list_name = config.get("price_list_name")

        if not channel_name or not price_list_name:
            failed += 1
            continue

        sales_channel = channel_map.get(channel_name)
        if not sales_channel:
            failed += 1
            continue

        prices = generate_prices(config, products)

        price_list_data = {
            "title": price_list_name,
            "description": config.get("description", ""),
            "type": config.get("type", "sale"),
            "status": config.get("status", "active"),
            "prices": prices,
            "rules": {"sales_channel_id": [sales_channel["id"]]},
        }

        result = await create_price_list(session, price_list_data)

        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Seeded price lists: {successful} successful, {failed} failed")

    return {"total": len(PRICE_LIST_CONFIGS), "successful": successful, "failed": failed}


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    reraise=True,
)
async def seed_price_lists():
    """Seed price lists in Medusa."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        return await seed_price_lists_internal(session)


if __name__ == "__main__":
    asyncio.run(seed_price_lists())
