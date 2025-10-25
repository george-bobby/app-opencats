import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def fetch_current_store(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, Any] | None:
    """Fetch the current store."""
    try:
        url = f"{base_url}/admin/stores"
        headers = auth.get_auth_headers()

        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                stores = response_data.get("stores", [])
                return stores[0] if stores else None
            return None
    except Exception:
        return None


async def update_store_internal(
    store_id: str,
    region_id: str,
    location_id: str,
    channel_id: str,
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> dict[str, Any] | None:
    """Internal function to update store configuration."""
    payload = {
        "name": "Trendspire",
        "default_region_id": region_id,
        "default_location_id": location_id,
        "default_sales_channel_id": channel_id,
        "supported_currencies": [
            {"id": "stocur_01K6M53BVM3MTJXDMA6WX949B0", "currency_code": "eur", "is_default": False},
            {"id": "stocur_01K6M53BVM6W65WXYXQAREQ2VG", "currency_code": "usd", "is_default": True},
        ],
    }

    url = f"{base_url}/admin/stores/{store_id}"
    headers = auth.get_auth_headers()

    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                logger.info("Store updated: Trendspire")
                return await response.json()
            else:
                logger.warning(f"Failed to update store: {response.status}")
                return None
    except Exception:
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def update_store() -> dict[str, Any] | None:
    """Update store configuration with default settings."""
    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return None

        sales_channels = await api_utils.fetch_sales_channels()
        sales_channel = next((ch for ch in sales_channels if ch.get("name") == "Official Website"), None)

        if not sales_channel:
            logger.warning("Sales channel 'Official Website' not found")
            return None

        regions = await api_utils.fetch_regions()
        region = next((r for r in regions if r.get("name") == "United States"), None)

        if not region:
            logger.warning("Region 'United States' not found")
            return None

        stock_locations = await api_utils.fetch_stock_locations()
        stock_location = next((loc for loc in stock_locations if loc.get("name") == "Trendspire"), None)

        if not stock_location:
            logger.warning("Stock location 'Trendspire' not found")
            return None

        async with aiohttp.ClientSession() as session:
            current_store = await fetch_current_store(session, api_utils.auth, api_utils.base_url)
            if not current_store:
                logger.warning("No store found")
                return None

            return await update_store_internal(
                current_store.get("id"),
                region.get("id"),
                stock_location.get("id"),
                sales_channel.get("id"),
                session,
                api_utils.auth,
                api_utils.base_url,
            )


if __name__ == "__main__":
    asyncio.run(update_store())
