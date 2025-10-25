"""Product Types seeding for Medusa."""

import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import TYPES_FILEPATH
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_types_data() -> list[dict[str, Any]]:
    """Load product types data from JSON file."""
    types = load_json_file(TYPES_FILEPATH, default=[])
    if not isinstance(types, list) or not types:
        logger.warning("No product types data found")
        return []
    return types


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_type(type_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single product type in Medusa."""
    value = type_data.get("value")
    if not value:
        return False

    try:
        url = f"{base_url}/admin/product-types"
        headers = auth.get_auth_headers()

        async with session.post(url, json={"value": value}, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_types_internal(types_data: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed product types."""
    logger.info(f"Seeding {len(types_data)} product types")

    successful = 0
    failed = 0

    for type_data in types_data:
        try:
            result = await create_type(type_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Product types seeded: {successful} successful, {failed} failed")

    return {"total": len(types_data), "successful": successful, "failed": failed}


async def seed_types() -> dict[str, int]:
    """Seed all product types from JSON file."""
    types_data = load_types_data()

    if not types_data:
        return {"total": 0, "successful": 0, "failed": 0}

    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return {"total": 0, "successful": 0, "failed": 0}

        async with aiohttp.ClientSession() as session:
            return await seed_types_internal(types_data, session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_types())
