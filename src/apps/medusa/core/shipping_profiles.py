import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import SHIPPING_PROFILES_DATA
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_shipping_profile(profile_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single shipping profile in Medusa."""
    name = profile_data.get("name")
    if not name:
        return False

    try:
        url = f"{base_url}/admin/shipping-profiles"
        headers = auth.get_auth_headers()

        payload = {"name": name, "type": profile_data.get("type", "default")}

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_shipping_profiles_internal(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed shipping profiles."""
    logger.info(f"Seeding {len(SHIPPING_PROFILES_DATA)} shipping profiles")

    successful = 0
    failed = 0

    for profile_data in SHIPPING_PROFILES_DATA:
        try:
            result = await create_shipping_profile(profile_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Shipping profiles seeded: {successful} successful, {failed} failed")

    return {"total": len(SHIPPING_PROFILES_DATA), "successful": successful, "failed": failed}


async def seed_shipping_profiles() -> dict[str, int]:
    """Seed all shipping profiles from predefined data."""
    async with MedusaAPIUtils() as api_utils, aiohttp.ClientSession() as session:
        return await seed_shipping_profiles_internal(session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_shipping_profiles())
