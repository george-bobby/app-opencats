import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import TAX_REGIONS_DATA
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_tax_region(region_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single tax region in Medusa."""
    country_code = region_data.get("country_code")
    if not country_code:
        return False

    try:
        url = f"{base_url}/admin/tax-regions"
        headers = auth.get_auth_headers()

        async with session.post(url, json=region_data, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_tax_region_internal(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed tax regions."""
    logger.info(f"Seeding {len(TAX_REGIONS_DATA)} tax regions")

    successful = 0
    failed = 0

    for region_data in TAX_REGIONS_DATA:
        try:
            result = await create_tax_region(region_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Tax regions seeded: {successful} successful, {failed} failed")

    return {"total": len(TAX_REGIONS_DATA), "successful": successful, "failed": failed}


async def seed_tax_region() -> dict[str, int]:
    """Seed all tax regions from predefined data."""
    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return {"total": 0, "successful": 0, "failed": 0}

        async with aiohttp.ClientSession() as session:
            return await seed_tax_region_internal(session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_tax_region())
