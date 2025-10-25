import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import SALES_CHANNELS_DATA
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_sales_channel(channel_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single sales channel in Medusa."""
    name = channel_data.get("name")
    if not name:
        return False

    try:
        url = f"{base_url}/admin/sales-channels"
        headers = auth.get_auth_headers()

        payload = {
            "name": name,
            "description": channel_data.get("description", ""),
            "is_disabled": channel_data.get("is_disabled", False),
        }

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_sales_channels_internal(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed sales channels."""
    logger.info(f"Seeding {len(SALES_CHANNELS_DATA)} sales channels")

    successful = 0
    failed = 0

    for channel_data in SALES_CHANNELS_DATA:
        try:
            result = await create_sales_channel(channel_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Sales channels seeded: {successful} successful, {failed} failed")

    return {"total": len(SALES_CHANNELS_DATA), "successful": successful, "failed": failed}


async def seed_sales_channels() -> dict[str, int]:
    async with MedusaAPIUtils() as api_utils, aiohttp.ClientSession() as session:
        return await seed_sales_channels_internal(session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_sales_channels())
