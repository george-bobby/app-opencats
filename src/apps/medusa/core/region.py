"""Regions API operations for Medusa."""

import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import REGIONS_DATA
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_region(region_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    name = region_data.get("name")
    if not name:
        return False

    try:
        url = f"{base_url}/admin/regions"
        headers = auth.get_auth_headers()

        async with session.post(url, json=region_data, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_region() -> dict[str, int]:
    async with MedusaAPIUtils() as api_utils:
        logger.info(f"Seeding {len(REGIONS_DATA)} regions")

        successful = 0
        failed = 0

        async with aiohttp.ClientSession() as session:
            auth = api_utils.auth
            base_url = api_utils.base_url

            for region_data in REGIONS_DATA:
                try:
                    result = await create_region(region_data, session, auth, base_url)

                    if result:
                        successful += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

        logger.info(f"Regions seeded: {successful} successful, {failed} failed")

        return {"total": len(REGIONS_DATA), "successful": successful, "failed": failed}


if __name__ == "__main__":
    asyncio.run(seed_region())
