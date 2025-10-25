import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.settings import settings
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_tags_data() -> list[dict[str, Any]]:
    """Load tags data from JSON file."""
    tags_filepath = settings.DATA_PATH / "tags.json"
    tags = load_json_file(tags_filepath, default=[])
    if not isinstance(tags, list) or not tags:
        logger.warning("No tags data found")
        return []
    return tags


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_tag(tag_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single product tag in Medusa."""
    if not tag_data.get("value"):
        return False

    try:
        payload = {"value": tag_data["value"]}
        url = f"{base_url}/admin/product-tags"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_tags_internal(tags_data: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed tags."""
    logger.info(f"Seeding {len(tags_data)} tags")

    successful = 0
    failed = 0

    for tag_data in tags_data:
        try:
            result = await create_tag(tag_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Tags seeded: {successful} successful, {failed} failed")

    return {"total": len(tags_data), "successful": successful, "failed": failed}


async def seed_tags() -> dict[str, int]:
    tags_data = load_tags_data()

    if not tags_data:
        return {"total": 0, "successful": 0, "failed": 0}

    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return {"total": 0, "successful": 0, "failed": 0}

        async with aiohttp.ClientSession() as session:
            return await seed_tags_internal(tags_data, session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_tags())
